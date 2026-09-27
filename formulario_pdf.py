"""Extracción local de formularios EXALTA con texto, sin servicios de IA."""
from hashlib import sha256
from io import BytesIO
import re
import unicodedata

import pandas as pd
from pypdf import PdfReader
from perfil_postulante import CAMPOS, trl_numero

MAPEO = {
    '2.1': 'nombre', '2.5': 'industria_principal_declarada',
    '4.1': 'estado_comercial', '4.3': 'evidencia_comercial_declarada',
    '4.5': 'ingresos_solucion_12m', '4.6': 'concentracion_cliente_categoria',
    '4.7': 'clientes_activos_cantidad', '4.8': 'pilotos_convertidos_cantidad',
    '4.9': 'pilotos_cantidad_categoria', '4.11': 'pipeline_declarado',
    '4.13': 'capacidad_comercial_declarada', '4.15': 'necesidad_financiamiento',
    '4.18': 'objetivo_comercial_6m', '5.2': 'tecnologia_descripcion',
    '5.3': 'integracion_tecnologica', '5.4': 'trl_declarado', '5.5': 'trl_objetivo',
    '5.11': 'antiguedad_tecnologia_categoria', '5.14': 'estado_patente',
    '5.15': 'proteccion_adicional', '5.16': 'titularidad_pi_declarada',
    '6.1': 'problema_resuelve', '6.2': 'validacion_tecnica_declarada',
    '6.3': 'beneficio_declarado', '6.4': 'beneficios_por_medir',
    '6.5': 'descripcion_solucion', '6.6': 'activos_contextos_declarados',
    '6.7': 'usuario_objetivo', '6.10': 'modelo_ingresos_actual', '6.11': 'ticket_declarado',
}
EMPRESA = {'2.2': 'razon_social', '2.4': 'fecha_constitucion',
           '2.7': 'region_operacion', '2.8': 'comuna_operacion', '2.9': 'sitio_web'}


def extraer_preguntas(paginas):
    bloques = []
    for numero, pagina in enumerate(paginas, 1):
        # Retirar sólo el folio final; no números que son respuestas.
        pagina = re.sub(r'\n\s*' + str(numero) + r'\s*$', '', pagina)
        bloques.append(unicodedata.normalize('NFKC', pagina))
    texto = '\n\f\n'.join(bloques)
    marcas = list(re.finditer(r'(?m)^\s*(\d+\.\d+)\.\s+', texto))
    preguntas = {}
    for i, marca in enumerate(marcas):
        bloque = texto[marca.end():marcas[i+1].start() if i+1 < len(marcas) else len(texto)]
        bloque = re.split(r'(?m)^\d+\.\s+[A-ZÁÉÍÓÚ]', bloque)[0]
        if ':' not in bloque:
            continue
        etiqueta, respuesta = bloque.split(':', 1)
        respuesta = respuesta.strip()
        selecciones = re.findall(r'◼\s*(.*?)(?=[◼◻]|$)', respuesta, re.S)
        valor = ' | '.join(' '.join(s.split()) for s in selecciones) if ('◼' in respuesta or '◻' in respuesta) else ' '.join(respuesta.split())
        preguntas[marca[1]] = {'etiqueta': ' '.join(etiqueta.split()), 'respuesta': respuesta,
                             'valor': valor, 'pagina': texto[:marca.start()].count('\f') + 1}
    return preguntas


def extraer_formulario(contenido):
    if len(contenido) > 5 * 1024 * 1024:
        raise ValueError('El PDF supera el límite de 5 MB.')
    try:
        reader = PdfReader(BytesIO(contenido))
        if reader.is_encrypted or len(reader.pages) > 30:
            raise ValueError('Usa un PDF sin contraseña de hasta 30 páginas.')
        paginas = [p.extract_text() or '' for p in reader.pages]
    except ValueError:
        raise
    except Exception as error:
        raise ValueError('No se pudo leer el PDF. Usa el formulario original con texto seleccionable.') from error
    texto = '\n'.join(paginas)
    if 'EXALTA' not in texto.upper():
        raise ValueError('Formato no reconocido. Se admite el formulario EXALTA; para otros formatos utiliza CSV.')
    preguntas = extraer_preguntas(paginas)
    checks = {'2.1': ('NOMBRE',), '4.5': ('VENTAS', '12'), '5.4': ('ESTADO', 'PROYECTO'), '6.1': ('PROBLEMA',)}
    for codigo, tokens in checks.items():
        etiqueta = preguntas.get(codigo, {}).get('etiqueta', '').upper()
        if not all(t in etiqueta for t in tokens):
            raise ValueError(f'La estructura del formulario cambió (pregunta {codigo}). Usa CSV o adapta el mapeo.')
    perfil = dict.fromkeys(CAMPOS, '')
    incidencias = []
    for codigo, campo in MAPEO.items():
        valor = preguntas.get(codigo, {}).get('valor', '')
        if campo.startswith('trl_'):
            n = trl_numero(valor)
            valor = str(n or '')
        if campo in ('ingresos_solucion_12m', 'clientes_activos_cantidad', 'pilotos_convertidos_cantidad',
                     'pipeline_declarado', 'necesidad_financiamiento', 'ticket_declarado'):
            if valor and not re.fullmatch(r'\d+(?:\.\d+)?', valor):
                incidencias.append((codigo, campo, 'Respuesta no numérica: revisar el original; campo vacío.'))
                valor = ''
        perfil[campo] = valor
    # Narrativas mezcladas se conservan completas, sin presentar proyecciones como capacidad actual.
    perfil['tipo_registro'] = 'REAL'
    perfil['origen_perfil'] = 'formulario_exalta_declarado'
    perfil['estado_revision'] = 'PENDIENTE'
    perfil['horizonte_financiamiento_meses'] = '12-24'
    for campo in ('moneda_ingresos', 'moneda_pipeline', 'moneda_ticket', 'moneda_financiamiento'):
        incidencias.append(('', campo, 'Moneda no normalizada: confirmar; no se asume CLP.'))
    incidencias.extend([
        ('4.12', 'margen_bruto_declarado_pct', 'Pregunta ambigua; porcentaje pendiente.'),
        ('6.7', 'decisor_compra', 'Separar usuario, decisor y pagador de la narrativa.'),
        ('6.10', 'modelo_ingresos_proyectado', 'Separar modelo actual y proyecciones de la narrativa.'),
        ('3.3', 'capacidades_declaradas', 'Separar capacidades actuales y necesidades del equipo.'),
        ('6.4', 'beneficios_medidos_declarados', 'Confirmar cuáles beneficios tienen mediciones; no inferir resultados.'),
    ])
    empresa = {campo: preguntas.get(codigo, {}).get('valor', '') for codigo, campo in EMPRESA.items()}
    if empresa['fecha_constitucion']:
        from datetime import datetime
        try:
            empresa['fecha_constitucion'] = datetime.strptime(empresa['fecha_constitucion'], '%d/%m/%Y').date().isoformat()
        except ValueError:
            incidencias.append(('2.4', 'fecha_constitucion', 'Formato de fecha no reconocido; revisar respuesta original.'))
            empresa['fecha_constitucion'] = ''
    huella = sha256(contenido).hexdigest()
    return {'perfil': perfil, 'empresa': empresa, 'preguntas': preguntas,
            'incidencias': incidencias, 'sha256': huella, 'id_postulacion': 'EXALTA-' + huella[:16]}


def preparar_anexos(extraido, perfil, contenido, raiz):
    """Metadatos se guardan en la misma transacción que el perfil del postulante."""
    from datetime import datetime, timezone
    from pathlib import Path
    import json
    raiz = Path(raiz)
    fecha = datetime.now(timezone.utc).isoformat()
    postulacion = extraido['id_postulacion']
    empresa_id = perfil['id_empresa_postulante']
    tablas = {}
    def anexar(nombre, filas, clave):
        nuevo = pd.DataFrame(filas)
        path = raiz / nombre
        if path.exists():
            previo = pd.read_csv(path, dtype=str).fillna('')
            nuevo = pd.concat([previo[~previo[clave].isin(nuevo[clave])], nuevo], ignore_index=True)
        tablas[nombre] = nuevo.fillna('').to_csv(index=False).encode('utf-8-sig')
    anexar('empresas_postulantes.csv', [dict(id_empresa_postulante=empresa_id, **extraido['empresa'])], 'id_empresa_postulante')
    anexar('postulaciones.csv', [dict(id_postulacion=postulacion, id_postulante=perfil['id'],
        sha256_origen=extraido['sha256'], archivo_origen=f"datos/formularios/{extraido['sha256']}.pdf",
        programa='EXALTA', version_mapeo='1', importado_en=fecha, estado_origen='DECLARADO')], 'id_postulacion')
    respuestas = []
    for codigo, q in extraido['preguntas'].items():
        if codigo in MAPEO or codigo in EMPRESA or codigo in ('3.3', '4.12'):
            respuestas.append(dict(id_respuesta=f'{postulacion}:{codigo}', id_postulacion=postulacion,
                codigo_pregunta=codigo, etiqueta_pregunta=q['etiqueta'], respuesta_original=q['respuesta'],
                metodo_extraccion='pypdf_local', estado_revision='DECLARADO_NO_VERIFICADO'))
    anexar('respuestas_formulario.csv', respuestas, 'id_respuesta')
    anexar('incidencias_importacion.csv', [dict(id_incidencia=f'{postulacion}:{campo}', id_postulacion=postulacion,
        campo=campo, codigo_pregunta=codigo, detalle=detalle, estado='PENDIENTE')
        for codigo, campo, detalle in extraido['incidencias']], 'id_incidencia')
    anexar('trazabilidad_perfil.csv', [dict(id_traza=f'{perfil["id"]}:{perfil["version_perfil"]}:{campo}',
        id_postulante=perfil['id'], version_perfil=perfil['version_perfil'], campo=campo,
        codigo_pregunta=codigo, id_postulacion=postulacion, valor_guardado=perfil[campo],
        transformacion='extraido' if perfil[campo] == extraido['perfil'][campo] else 'editado_en_revision')
        for codigo, campo in MAPEO.items()], 'id_traza')
    anexar('historial_perfiles.csv', [dict(id_version=f'{perfil["id"]}:{perfil["version_perfil"]}',
        id_postulante=perfil['id'], version_perfil=perfil['version_perfil'], fecha=fecha,
        perfil_json=json.dumps(perfil, ensure_ascii=False))], 'id_version')
    tablas[f"datos/formularios/{extraido['sha256']}.pdf"] = contenido
    return tablas
