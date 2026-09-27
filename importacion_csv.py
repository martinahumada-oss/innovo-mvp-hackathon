"""Importación de postulantes, sin cálculo de matching ni scoring."""
import csv
from datetime import datetime
from io import StringIO, BytesIO
from pathlib import Path
import json
import re
import pandas as pd
from perfil_postulante import validar_perfiles
from mvp_datos import bloqueo_importacion, guardar_archivos, leer_tabla

CATALOGOS = {"Postulantes": "postulantes.csv"}

def preparar_importacion(contenido, actuales):
    if len(contenido) > 5 * 1024 * 1024:
        raise ValueError("El archivo supera el límite de 5 MB.")
    try:
        texto = contenido.decode("utf-8-sig")
        separador = csv.Sniffer().sniff(texto[:8192], delimiters=",;").delimiter
        filas = list(csv.reader(StringIO(texto), delimiter=separador))
    except (UnicodeError, csv.Error) as error:
        raise ValueError("Usa un CSV UTF-8 separado por comas o punto y coma.") from error
    if len(filas) < 2:
        raise ValueError("El archivo debe incluir encabezados y al menos un registro.")
    encabezados = [c.strip() for c in filas[0]]
    if len(set(encabezados)) != len(encabezados):
        raise ValueError("Hay columnas duplicadas.")
    if any(len(f) != len(encabezados) for f in filas[1:] if f):
        raise ValueError("Hay filas con una cantidad incorrecta de columnas.")
    faltantes = set(actuales.columns) - set(encabezados)
    extras = set(encabezados) - set(actuales.columns)
    if faltantes or extras:
        raise ValueError(f"Columnas faltantes: {', '.join(sorted(faltantes)) or 'ninguna'}. "
                         f"Columnas desconocidas: {', '.join(sorted(extras)) or 'ninguna'}.")
    nuevos = pd.DataFrame([f for f in filas[1:] if f], columns=encabezados)
    if nuevos.empty:
        raise ValueError("No hay registros para importar.")
    nuevos = nuevos.apply(lambda col: col.str.strip())[actuales.columns]
    if 'trl_declarado' in nuevos:
        validar_perfiles(nuevos)
    if nuevos['id'].eq('').any() or nuevos['nombre'].eq('').any():
        raise ValueError("ID y nombre son obligatorios en todas las filas.")
    if nuevos['id'].duplicated().any():
        raise ValueError("Cada ID debe aparecer una sola vez en el archivo.")
    if actuales['id'].duplicated().any():
        raise ValueError("El catálogo actual tiene IDs duplicados; corrígelos antes de importar.")
    anteriores = actuales.set_index('id')
    cambiados = [r['id'] for _, r in nuevos.iterrows()
                 if r['id'] not in anteriores.index
                 or not r.drop('id').equals(anteriores.loc[r['id']])]
    resultado = pd.concat([actuales[~actuales.id.isin(nuevos.id)], nuevos], ignore_index=True)
    return nuevos, resultado, cambiados


def importar_catalogo(tipo, contenido, raiz=None, anexos=None):
    raiz = Path(raiz or Path.cwd()).resolve()
    if tipo not in CATALOGOS:
        raise ValueError('El MVP solo importa perfiles de postulantes.')
    with bloqueo_importacion(raiz):
        actuales = leer_tabla('postulantes.csv', raiz)
        nuevos, resultado, cambiados = preparar_importacion(contenido, actuales)
        if not cambiados:
            return None, 0
        if not set(nuevos.tipo_registro).issubset({'REAL', 'FICTICIO_DEMOSTRACION'}):
            raise ValueError('Indica REAL o FICTICIO_DEMOSTRACION en tipo_registro.')
        previos = actuales.set_index('id')
        for _, fila in nuevos.iterrows():
            if fila.id in previos.index and fila.tipo_registro != previos.loc[fila.id, 'tipo_registro']:
                raise ValueError('No se puede convertir un ejemplo ficticio en un postulante real, ni a la inversa.')
        anexos = dict(anexos or {})
        permitidos = {'empresas_postulantes.csv', 'postulaciones.csv', 'respuestas_formulario.csv',
                      'incidencias_importacion.csv', 'trazabilidad_perfil.csv', 'historial_perfiles.csv'}
        for nombre in anexos:
            if nombre not in permitidos and not re.fullmatch(r'datos/formularios/[a-f0-9]{64}\.pdf', nombre):
                raise ValueError('Ruta de anexo no permitida.')
        for tabla, campo, clave in [('empresas_postulantes.csv', 'id_empresa_postulante', 'id_empresa_postulante'),
                                     ('postulaciones.csv', 'id_postulacion_vigente', 'id_postulacion')]:
            catalogo = pd.read_csv(BytesIO(anexos[tabla]), dtype=str).fillna('') if tabla in anexos else leer_tabla(tabla, raiz)
            if not (set(resultado[campo]) - {''}).issubset(set(catalogo[clave])):
                raise ValueError(f'{campo}: referencia inexistente.')
            if tabla == 'postulaciones.csv':
                for _, p in resultado[resultado.id_postulacion_vigente.ne('')].iterrows():
                    vinculada = catalogo[catalogo.id_postulacion.eq(p.id_postulacion_vigente)]
                    if not vinculada.id_postulante.eq(p.id).all():
                        raise ValueError('La postulación corresponde a otro postulante.')
        for i, fila in resultado[resultado.id.isin(cambiados)].iterrows():
            version = previos.loc[fila.id, 'version_perfil'] if fila.id in previos.index else '0'
            resultado.loc[i, 'version_perfil'] = str(int(version or '0') + 1)
            resultado.loc[i, 'actualizado_en'] = datetime.now().isoformat(timespec='seconds')
        historial = leer_tabla('historial_perfiles.csv', raiz) if (raiz / 'historial_perfiles.csv').exists() else pd.DataFrame()
        filas = [dict(id_version=f'{f.id}:{f.version_perfil}', id_postulante=f.id,
                      version_perfil=f.version_perfil, fecha=f.actualizado_en,
                      perfil_json=json.dumps(f.to_dict(), ensure_ascii=False))
                 for _, f in resultado[resultado.id.isin(cambiados)].iterrows()]
        historial = pd.concat([historial, pd.DataFrame(filas)], ignore_index=True).drop_duplicates('id_version', keep='last')
        anexos['historial_perfiles.csv'] = historial.to_csv(index=False).encode('utf-8-sig')
        anexos['postulantes.csv'] = resultado.to_csv(index=False).encode('utf-8-sig')
        return guardar_archivos(anexos, raiz), 0
