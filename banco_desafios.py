"""Banco INNOVO: importación fiel, vigencia y requisitos documentados."""
from datetime import date, datetime
import hashlib
from io import BytesIO
import posixpath
import re
import unicodedata
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

import pandas as pd
from perfil_postulante import trl_numero

MAPA = {
    'ID': 'id', 'Tipo de registro': 'tipo_registro', 'Subtipo': 'subtipo',
    'Empresa(s) convocante(s)': 'convocantes_originales', 'Unidad, filial o faena': 'unidad',
    'Empresas vinculadas': 'empresas_vinculadas', 'Roles documentados': 'roles_documentados',
    'Sector': 'industria', 'Nombre original publicado': 'nombre_original',
    'Título de referencia': 'titulo', 'Problema, contexto y resultado buscado': 'problema',
    'Líneas declaradas por empresa': 'lineas_declaradas',
    'Líneas de innovación: clasificación editorial': 'lineas_editoriales',
    'Programa': 'programa', 'Operador': 'operador', 'Edición': 'edicion',
    'Período documentado': 'periodo', 'Año de referencia': 'anio_referencia',
    'Fecha de publicación': 'publicacion', 'Apertura / hito publicado': 'apertura',
    'Cierre publicado': 'cierre', 'Estado documentado': 'estado_documentado',
    'Alcance geográfico': 'alcance_geografico',
    'Requisitos, madurez y restricciones': 'requisitos', 'Criterios de éxito': 'criterios_exito',
    'Financiamiento, piloto y oportunidades': 'financiamiento_piloto',
    'Fuente principal': 'fuente_principal', 'Otras fuentes enlazadas': 'otras_fuentes',
    'Bases y anexos': 'bases_anexos', 'Calidad de evidencia': 'calidad_evidencia',
    'Atribución corporativa': 'atribucion', 'Fecha de revisión': 'fecha_revision',
    'Observaciones y contradicciones': 'observaciones',
    'Relación con otras ediciones': 'relacion_ediciones', 'Cambio frente a base anterior': 'cambio',
}
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def normalizar(valor):
    return ''.join(c for c in unicodedata.normalize('NFD', str(valor or '').lower())
                   if unicodedata.category(c) != 'Mn').strip()


def conocido(valor):
    t = normalizar(valor)
    return bool(t) and not any(t.startswith(x) for x in (
        'no localizado', 'no identificad', 'sin dato', 'no informado', 'sin ano', 'sin fecha'))


def leer_excel(contenido):
    """Lee valores XML de XLSX; nunca ejecuta fórmulas, macros ni enlaces externos."""
    if len(contenido) > 20 * 1024 * 1024:
        raise ValueError('El Excel supera 20 MB.')
    try:
        with ZipFile(BytesIO(contenido)) as z:
            if sum(i.file_size for i in z.infolist()) > 80 * 1024 * 1024 or len(z.infolist()) > 2000:
                raise ValueError('Excel demasiado grande al descomprimir.')
            def xml(nombre):
                datos = z.read(nombre)
                if b'<!DOCTYPE' in datos or b'<!ENTITY' in datos:
                    raise ValueError('XML con entidades no permitido.')
                return ET.fromstring(datos)
            shared = []
            if 'xl/sharedStrings.xml' in z.namelist():
                shared = [''.join(e.itertext()) for e in xml('xl/sharedStrings.xml')]
            rels = {e.attrib['Id']: e.attrib['Target']
                    for e in xml('xl/_rels/workbook.xml.rels') if e.attrib.get('TargetMode') != 'External'}
            hojas = {}
            for sheet in xml('xl/workbook.xml').find('s:sheets', NS):
                target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
                path = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
                if not path.startswith('xl/'):
                    raise ValueError('Ruta interna XLSX inválida.')
                filas = []
                for row in xml(path).findall('.//s:sheetData/s:row', NS):
                    celdas = {}
                    for c in row:
                        letras = re.match(r'[A-Z]+', c.attrib['r']).group()
                        col = 0
                        for letra in letras:
                            col = col * 26 + ord(letra) - 64
                        if col > 200:
                            raise ValueError('La hoja supera 200 columnas.')
                        v = c.find('s:v', NS)
                        valor = v.text or '' if v is not None else ''
                        if c.attrib.get('t') == 's':
                            valor = shared[int(valor)]
                        elif c.attrib.get('t') == 'inlineStr':
                            valor = ''.join(t.text or '' for t in c.findall('.//s:t', NS))
                        celdas[col - 1] = valor
                    if celdas:
                        filas.append([celdas.get(i, '') for i in range(max(celdas) + 1)])
                hojas[sheet.attrib['name']] = filas
    except (BadZipFile, KeyError, ET.ParseError, IndexError, TypeError) as error:
        raise ValueError('No se pudo leer el Excel. Usa el banco XLSX completo.') from error
    return hojas


def preparar_banco(contenido):
    hojas = leer_excel(contenido)
    tablas = {}
    for nombre, columnas in [('Base', set(MAPA)), ('Empresas', {'Empresa', 'Rol acreditado'}),
                              ('Relaciones', {'ID', 'Empresa', 'Rol'}), ('Fuentes', {'URL', 'Registros'})]:
        filas = hojas.get(nombre, [])
        if not filas or not columnas.issubset(set(filas[0])):
            raise ValueError(f'Falta la hoja {nombre} o sus columnas requeridas.')
        cabecera = filas[0]
        if len(cabecera) != len(set(cabecera)):
            raise ValueError(f'Columnas duplicadas en {nombre}.')
        tablas[nombre] = pd.DataFrame([dict(zip(cabecera, f)) for f in filas[1:] if any(f)]).fillna('')
    base = tablas['Base'].rename(columns=MAPA)
    if base.empty or len(base) > 10000 or base.id.eq('').any() or base.id.duplicated().any():
        raise ValueError('Base debe tener entre 1 y 10000 registros con IDs únicos y no vacíos.')
    if base.titulo.eq('').any():
        raise ValueError('Cada registro debe tener título de referencia.')
    if not set(base.tipo_registro).issubset({'Desafío específico', 'Foco temático', 'Programa sin desafíos detallados'}):
        raise ValueError('Tipo de registro desconocido; revisa el mapeo antes de importar.')
    if not set(base.atribucion).issubset({'Confirmada', 'Pendiente', 'Patrocinio sin demanda propia'}):
        raise ValueError('Atribución desconocida; revisa el mapeo antes de importar.')
    empresas, relaciones = tablas['Empresas'], tablas['Relaciones']
    if empresas.Empresa.eq('').any() or empresas.Empresa.duplicated().any():
        raise ValueError('Empresas contiene nombres vacíos o duplicados.')
    if not set(relaciones.ID).issubset(set(base.id)) or not set(relaciones.Empresa).issubset(set(empresas.Empresa)):
        raise ValueError('Relaciones contiene referencias inexistentes.')
    if relaciones.duplicated(['ID', 'Empresa', 'Rol']).any():
        raise ValueError('Hay relaciones duplicadas.')
    for ids in tablas['Fuentes'].Registros:
        if not {x.strip() for x in ids.split(';') if x.strip()}.issubset(set(base.id)):
            raise ValueError('Fuentes contiene referencias inexistentes.')
    responsables = relaciones[relaciones.Rol.eq('Convocante/demandante')].groupby('ID').Empresa.agg(lambda s: '; '.join(sorted(s)))
    base['nombre_empresa'] = base.id.map(responsables).fillna('')
    base.loc[base.atribucion.ne('Confirmada'), 'nombre_empresa'] = ''
    if (base.atribucion.eq('Confirmada') & base.nombre_empresa.eq('')).any():
        raise ValueError('Una atribución confirmada no tiene relación con un responsable.')
    base['hash_banco'] = hashlib.sha256(contenido).hexdigest()
    archivos = {'banco_base.csv': base, 'banco_empresas.csv': empresas,
                'banco_relaciones.csv': relaciones, 'banco_fuentes.csv': tablas['Fuentes']}
    for nombre in ('Pendientes', 'Revisiones', 'Cobertura'):
        if nombre in hojas:
            archivos[f'banco_{nombre.lower()}_original.csv'] = pd.DataFrame(hojas[nombre]).fillna('')
    return archivos


def fecha_exacta(texto):
    for formato in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(texto).strip(), formato).date()
        except ValueError:
            pass
    return None


def vigencia(registro, hoy=None):
    hoy = hoy or date.today()
    estado = normalizar(registro.get('estado_documentado', ''))
    # No convertir una fecha incidental o contradictoria en cierre.
    if 'sin cierre' in estado or 'sin confirmar' in estado:
        return 'DESCONOCIDA'
    cierre = fecha_exacta(registro.get('cierre', ''))
    if any(t in estado for t in ('historic', 'cerrada', 'finalizada', 'ganador', 'vencido')) or (cierre and cierre < hoy):
        return 'HISTORICA'
    revision = fecha_exacta(registro.get('fecha_revision', ''))
    if ('abierta' in estado and 'no acreditada' not in estado and cierre and cierre >= hoy
            and revision and 0 <= (hoy - revision).days <= 30):
        return 'ABIERTA_DOCUMENTADA'
    return 'DESCONOCIDA'


def evaluar_trl(requisitos, declarado):
    texto = normalizar(requisitos)
    if not conocido(requisitos):
        return 'DESCONOCIDO', 'Requisitos no localizados en el banco.'
    if 'sin minimo trl' in texto or 'todo el espectro de trl' in texto:
        return 'NO_APLICA', 'Sin mínimo TRL documentado; revisar las demás restricciones.'
    if 'categoria' in texto or len(re.findall(r'\btrl\b', texto)) > 1:
        return 'DESCONOCIDO', 'Requisito TRL con alternativas; requiere lectura del gestor.'
    rango = re.search(r'\btrl\s*([1-9])\s*[–—-]\s*([1-9])\b', texto)
    minimo = re.search(r'\btrl\s*(?:≥|>=)\s*([1-9])\b', texto)
    if not rango and not minimo:
        return 'DESCONOCIDO', 'No hay un límite TRL inequívoco para evaluar automáticamente.'
    valor = trl_numero(declarado)
    if valor is None:
        return 'DESCONOCIDO', 'Falta TRL declarado de la solución.'
    inferior = int((rango or minimo).group(1))
    superior = int(rango.group(2)) if rango else 9
    if inferior > superior:
        return 'DESCONOCIDO', 'Rango TRL contradictorio.'
    cumple = inferior <= valor <= superior
    return ('CUMPLE_DECLARADO' if cumple else 'NO_CUMPLE'), f'TRL declarado {valor}; requisito {inferior}–{superior}. Las demás restricciones siguen pendientes.'
