"""Datos temporales independientes por sesión, sin cambiar el cwd del servidor."""
from pathlib import Path
import shutil
import tempfile
import streamlit as st


def raiz_demo(raiz):
    if Path(raiz) != Path('.'):
        return Path(raiz)
    if '_directorio_demo' not in st.session_state:
        temporal = tempfile.TemporaryDirectory(prefix='innovo_demo_')
        base = Path(__file__).resolve().parent
        destino = Path(temporal.name)
        for nombre in ['postulantes.csv', 'postulaciones.csv', 'empresas_postulantes.csv', 'banco_base.csv']:
            shutil.copy2(base / nombre, destino / nombre)
        st.session_state['_directorio_demo'] = temporal
    return Path(st.session_state['_directorio_demo'].name)
