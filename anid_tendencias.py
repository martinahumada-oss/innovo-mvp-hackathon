"""Señal temática reproducible; no estima elegibilidad ni probabilidad de fondos."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import unicodedata

import pandas as pd

FUENTE = 'https://github.com/ANID-GITHUB/Historico-de-Proyectos-Adjudicados'
ARCHIVO = Path(__file__).parent / 'BDH_HISTORICA.csv'
CORTE = 2025  # Fecha de corte declarada por ANID en el README de la fuente.
SECTORES = {
    'mineria': 'mineria mining mineral minerales minera minero copper cobre relaves lixiviacion',
    'agua': 'agua water wastewater hidrica hidrico hidricos hidricas aguas desalinizacion',
    'agricultura': 'agricultura agriculture agricultural cultivos cultivo agricola agricolas riego irrigation',
    'energia': 'energia energy energetica energetico energeticos electric electricidad renewable renewables',
    'manufactura': 'manufactura manufacturing manufacturera manufacturero fabricacion factory factories',
}
SECTORES_BANCO = {
    'mineria y proveedores mineros': SECTORES['mineria'],
    'alimentos, bebidas y acuicultura': 'alimentos alimentaria food bebidas acuicultura aquaculture peces salmon',
    'energia y servicios electricos': SECTORES['energia'],
    'inmobiliario y centros comerciales': 'inmobiliario edificios buildings vivienda habitacional urbanismo',
    'servicios financieros y seguros': 'financiero financiera finanzas banking fintech seguros insurance',
    'construccion, forestal y materiales': 'construccion construction forestal forestry madera wood materiales materials',
    'salud y bienestar': 'salud health medicina medical clinica pacientes bienestar',
    'comercio, restaurantes y franquicias': 'comercio retail restaurantes restaurants comercio electronico',
    'telecomunicaciones y tecnologia': 'telecomunicaciones telecommunications comunicaciones networks informatica software',
    'logistica y transporte': 'logistica logistics transporte transport movilidad mobility',
    'agua y saneamiento': SECTORES['agua'],
    'higiene y cuidado personal': 'higiene hygiene cosmetica cosmetics cuidado personal',
}
STOP = set('para como desde sobre entre mediante desarrollo investigacion estudio analisis sistema sistemas proyecto proyectos aplicacion aplicaciones uso mediante basado basada modelo modelos proceso procesos tecnologia tecnologias solucion soluciones informacion sin datos principal general nacional internacional chile chilena regional nuevo nueva nuevos nuevas efectos efecto evaluacion caracterizacion optimizacion mejoramiento'.split())


def terminos(valor):
    if pd.isna(valor):
        return set()
    texto = ''.join(c for c in unicodedata.normalize('NFD', str(valor).lower())
                    if unicodedata.category(c) != 'Mn')
    return {t for t in re.findall(r'[a-z]+', texto) if (len(t) >= 4 or t == 'iot') and t not in STOP}


class IndiceANID:
    def __init__(self, datos, huella='prueba'):
        campos = ['CODIGO_PROYECTO', 'AGNO_FALLO', 'NOMBRE_PROYECTO', 'PALABRAS_CLAVES']
        if not set(campos).issubset(datos.columns):
            raise ValueError('Esquema ANID incompatible')
        datos = datos.copy().fillna('')
        datos['anio'] = pd.to_numeric(datos.AGNO_FALLO, errors='coerce')
        datos = datos[datos.anio.between(1982, CORTE) & datos.CODIGO_PROYECTO.ne('')]
        if datos.empty:
            raise ValueError('ANID sin años válidos')
        datos = datos.drop_duplicates('CODIGO_PROYECTO', keep='last')
        self.fin = int(datos.anio.max())
        self.datos = datos[datos.anio.ge(self.fin - 9)].reset_index(drop=True)
        self.huella = huella
        self.indice = {}
        for i, fila in self.datos.iterrows():
            for termino in terminos(fila.NOMBRE_PROYECTO + ' ' + fila.PALABRAS_CLAVES):
                self.indice.setdefault(termino, set()).add(i)
        self.recientes = set(self.datos.index[self.datos.anio.ge(self.fin - 4)])
        self.anteriores = set(self.datos.index[self.datos.anio.lt(self.fin - 4)])

    def buscar(self, palabras):
        encontrados = set()
        for palabra in palabras:
            encontrados.update(self.indice.get(palabra, set()))
        return encontrados

    def evaluar(self, startup, industria):
        palabras_startup = terminos(startup.get('tecnologia', ''))
        if 'sensores' in palabras_startup:
            palabras_startup.update(['sensor', 'sensors'])
        if 'biotecnologia' in palabras_startup:
            palabras_startup.update(['biotechnology', 'biotecnologica'])
        if 'robotica' in palabras_startup:
            palabras_startup.update(['robotics', 'robot', 'robots'])
        sector = ''.join(c for c in unicodedata.normalize('NFD', str(industria.get('nombre_industria', '')).lower())
                         if unicodedata.category(c) != 'Mn').strip()
        palabras_sector = terminos(SECTORES_BANCO.get(sector, SECTORES.get(sector, sector)))
        candidatos = self.buscar(palabras_startup) & self.buscar(palabras_sector)
        # Al menos dos términos distintos: evita que una sola palabra genérica pruebe ambos calces.
        candidatos = {i for i in candidatos if len(
            terminos(self.datos.loc[i, 'NOMBRE_PROYECTO'] + ' ' + self.datos.loc[i, 'PALABRAS_CLAVES'])
            & (palabras_startup | palabras_sector)) >= 2}
        recientes = candidatos & self.recientes
        anteriores = candidatos & self.anteriores
        cuota_reciente = len(recientes) / len(self.recientes) if self.recientes else 0
        cuota_anterior = len(anteriores) / len(self.anteriores) if self.anteriores else 0
        tendencia = 'Sin muestra suficiente'
        if len(recientes) + len(anteriores) >= 5 and self.anteriores and self.recientes:
            delta = cuota_reciente - cuota_anterior
            umbral = max(cuota_anterior * .1, 1 / len(self.recientes))
            tendencia = 'Creciente' if delta > umbral else 'Decreciente' if delta < -umbral else 'Estable'
        ejemplos = self.datos.loc[sorted(recientes)].sort_values(
            ['anio', 'CODIGO_PROYECTO'], ascending=[False, True]).head(3)
        score = round(min(100, 20 * math.log2(1 + len(recientes))), 2)
        return dict(
            score_anid=score, estado_anid='Disponible', proyectos_anid_recientes=len(recientes),
            proyectos_anid_anteriores=len(anteriores), tendencia_anid=tendencia,
            periodo_anid=f'{self.fin-4}–{self.fin}', periodo_anid_anterior=f'{self.fin-9}–{self.fin-5}',
            cuota_anid_reciente=round(cuota_reciente * 100, 4),
            cuota_anid_anterior=round(cuota_anterior * 100, 4),
            universo_anid_reciente=len(self.recientes), universo_anid_anterior=len(self.anteriores),
            fuente_anid=FUENTE, huella_anid=self.huella,
            ejemplos_anid=json.dumps([{'codigo': r.CODIGO_PROYECTO, 'anio': int(r.anio),
                'titulo': r.NOMBRE_PROYECTO} for r in ejemplos.itertuples()], ensure_ascii=False),
            explicacion_anid=f'{len(recientes)} proyectos distintos con coincidencias de startup y sector; '
                '20 × log2(1 + proyectos recientes), máximo 100. Señal léxica exploratoria, no elegibilidad.',
        )


@lru_cache(maxsize=2)
def _cargar(ruta, modificacion):
    archivo = Path(ruta)
    datos = pd.read_csv(archivo, sep=';', encoding='utf-8-sig', dtype=str, usecols=[
        'CODIGO_PROYECTO', 'AGNO_FALLO', 'NOMBRE_PROYECTO', 'PALABRAS_CLAVES'])
    return IndiceANID(datos, hashlib.sha256(archivo.read_bytes()).hexdigest())


def cargar_indice():
    try:
        return _cargar(str(ARCHIVO), ARCHIVO.stat().st_mtime_ns)
    except (OSError, ValueError, UnicodeError, pd.errors.ParserError):
        return None


def evaluar_anid(indice, startup, industria):
    if indice is None:
        return dict(score_anid=None, estado_anid='No disponible', fuente_anid=FUENTE,
                    explicacion_anid='Base ANID ausente o inválida; no se puede evaluar la alineación histórica.')
    return indice.evaluar(startup, industria)


@lru_cache(maxsize=128)
def _alineacion(tecnologia, sectores, modificacion):
    indice = cargar_indice()
    return json.dumps([dict(sector=sector, **evaluar_anid(indice, {'tecnologia': tecnologia},
                                  {'nombre_industria': sector})) for sector in sectores], ensure_ascii=False)


def alineacion_postulante(perfil, banco, seguimiento):
    """Misma rúbrica histórica, adaptada al perfil canónico. No ordena desafíos."""
    sectores = banco[banco.id.isin(seguimiento.get('desafios', []))].industria.tolist()
    if not sectores:
        sectores = [perfil.get('industria_principal_declarada') or 'Sector no informado']
    sectores = tuple(dict.fromkeys(sectores))
    tecnologia = ' '.join(str(perfil.get(k, '')) for k in ('tecnologia_descripcion', 'descripcion_solucion'))
    try:
        modificacion = ARCHIVO.stat().st_mtime_ns
    except OSError:
        modificacion = None
    return json.loads(_alineacion(tecnologia, sectores, modificacion))


def mostrar_alineacion(perfil, banco, seguimiento):
    import streamlit as st
    with st.expander('Alineación histórica con ANID', expanded=True):
        st.caption('Tecnología del postulante y sectores seleccionados. Sin selección, se usa su industria declarada.')
        filas = alineacion_postulante(perfil, banco, seguimiento)
        disponibles = [f for f in filas if f['estado_anid'] == 'Disponible']
        if disponibles:
            st.dataframe(pd.DataFrame([{'Sector': f['sector'], 'Alineación /100': f['score_anid'],
                'Proyectos relacionados': f['proyectos_anid_recientes'], 'Período': f['periodo_anid'],
                'Tendencia': f['tendencia_anid']} for f in disponibles]), hide_index=True)
            for fila in disponibles:
                st.markdown('**' + fila['sector'] + '**')
                for ejemplo in json.loads(fila['ejemplos_anid']):
                    st.write(f"{ejemplo['codigo']} · {ejemplo['anio']} · {ejemplo['titulo']}")
                if not json.loads(fila['ejemplos_anid']):
                    st.caption('Sin proyectos coincidentes en el período reciente.')
        else:
            st.info('Base ANID no disponible. Se mostrará esa ausencia en el informe; no se sustituye por cero.')
        st.caption('Rúbrica exploratoria: 20 × log2(1 + proyectos recientes), máximo 100. La tendencia compara cuotas del universo entre dos períodos de cinco años. No suma puntos a los desafíos ni confirma fondos o elegibilidad.')
        st.markdown('[Fuente: histórico de proyectos adjudicados de ANID](' + FUENTE + ')')
