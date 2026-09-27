"""Vista de revisión antes de modificar los catálogos."""
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import streamlit as st
from formulario_pdf import MAPEO, extraer_formulario, preparar_anexos
from importacion_csv import importar_catalogo
from perfil_postulante import CAMPOS, validar_perfiles


def mostrar_formulario_pdf():
    st.markdown('### Formulario de postulación · PDF')
    st.caption('EXALTA con texto seleccionable · extracción local · máximo 5 MB. Otros formularios pueden cargarse mediante CSV.')
    archivo = st.file_uploader('Carga el formulario de la postulante', type=['pdf'], max_upload_size=5, key='formulario_pdf')
    if archivo is None:
        return
    try:
        contenido = archivo.getvalue()
        extraido = extraer_formulario(contenido)
        actuales = pd.read_csv('postulantes.csv', dtype=str).fillna('')
        postulaciones = Path('postulaciones.csv')
        anterior = None
        if postulaciones.exists():
            registros = pd.read_csv(postulaciones, dtype=str).fillna('')
            repetidos = registros[registros.sha256_origen.eq(extraido['sha256'])]
            if not repetidos.empty:
                anterior = repetidos.iloc[0].id_postulante
        opciones = ['Nuevo postulante'] + actuales.id.tolist()
        destino = st.selectbox('Registrar una solución nueva o actualizar una existente', opciones,
            index=opciones.index(anterior) if anterior in opciones else 0,
            format_func=lambda v: v if v == 'Nuevo postulante' else f'{v} · {actuales.set_index("id").loc[v, "nombre"]}',
            key='destino_' + extraido['sha256'])
        if anterior and destino != anterior:
            st.error(f'Este archivo ya pertenece a {anterior}. Selecciona esa postulante para evitar duplicados.')
            return
        postulante_id = 'S-' + extraido['sha256'][:10] if destino == 'Nuevo postulante' else destino
        existente = actuales[actuales.id.eq(postulante_id)]
        perfil = dict(extraido['perfil'])
        perfil['tipo_registro'] = 'REAL'
        perfil['id'] = postulante_id
        perfil['id_empresa_postulante'] = (existente.iloc[0].id_empresa_postulante if not existente.empty else '') or 'EP-' + postulante_id
        perfil['id_postulacion_vigente'] = extraido['id_postulacion']
        protegidos = {'id', 'id_empresa_postulante', 'id_postulacion_vigente', 'version_perfil',
                     'actualizado_en', 'origen_perfil', 'estado_revision',
                     'tipo_registro'}
        # Un PDF repetido abre la última corrección guardada, no vuelve a introducir errores ya corregidos.
        if anterior and not existente.empty:
            for campo in CAMPOS:
                if campo not in protegidos:
                    perfil[campo] = existente.iloc[0][campo]
        st.info('Las respuestas son declaraciones, no evidencia verificada. Revisa los campos vacíos y separa capacidades actuales de metas futuras. Al actualizar se reemplaza el perfil completo mostrado.')
        with st.expander('Datos que requieren revisión', expanded=True):
            st.dataframe(pd.DataFrame(extraido['incidencias'], columns=['Pregunta', 'Campo', 'Revisión']), hide_index=True)
        with st.expander('Respuestas originales para contrastar'):
            codigos = set(MAPEO) | {'3.3', '4.12'}
            st.dataframe(pd.DataFrame([{'Pregunta': k, 'Respuesta': q['valor']} for k, q in extraido['preguntas'].items()
                                      if k in codigos]), hide_index=True)
        valores = st.data_editor(pd.DataFrame([{'Campo': c, 'Valor': perfil[c]} for c in CAMPOS if c not in protegidos]),
            disabled=['Campo'], hide_index=True, height=460,
            column_config={'Valor': st.column_config.TextColumn('Valor · editable', width='large')},
            key='revision_pdf_' + extraido['sha256'] + postulante_id)
        perfil.update(dict(zip(valores.Campo, valores.Valor.fillna('').astype(str))))
        confirmado = st.checkbox('Revisé la extracción y los datos pendientes; guardar como información declarada.',
                                 key='confirmar_' + extraido['sha256'] + postulante_id)
        st.caption('Se conserva una copia local del formulario. El archivo puede contener datos personales; esta app local no incorpora control de acceso multiusuario.')
        if st.button('Guardar postulante', type='primary', disabled=not confirmado):
            validar_perfiles(pd.DataFrame([perfil]))
            if not perfil['nombre'].strip():
                raise ValueError('El nombre de la solución es obligatorio.')
            if anterior and not existente.empty and all(perfil[c] == existente.iloc[0][c] for c in CAMPOS if c not in protegidos):
                st.success('Este formulario y perfil ya están guardados. No se duplicaron registros.')
                return
            perfil['version_perfil'] = str(int(existente.iloc[0].version_perfil or '0') + 1) if not existente.empty else '1'
            perfil['actualizado_en'] = datetime.now(timezone.utc).isoformat()
            anexos = preparar_anexos(extraido, perfil, contenido, Path.cwd())
            with st.spinner('Guardando postulante y respaldo…'):
                respaldo, revisiones = importar_catalogo('Postulantes', pd.DataFrame([perfil], columns=CAMPOS).to_csv(index=False).encode('utf-8-sig'),
                                                        raiz=Path.cwd(), anexos=anexos)
            st.session_state['aviso_importacion'] = f'Perfil {postulante_id} guardado. Revisa los desafíos y el plan si el perfil cambió. Respaldo: {respaldo.name if respaldo else "sin cambios"}.'
            st.rerun()
    except (ValueError, OSError, KeyError) as error:
        st.error(f'No se guardó el formulario: {error}')
