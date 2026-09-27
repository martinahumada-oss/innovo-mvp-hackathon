"""Interfaz del MVP: decisiones manuales por postulante."""
from pathlib import Path
from urllib.parse import urlsplit
import pandas as pd
import streamlit as st
from banco_desafios import vigencia, evaluar_trl, preparar_banco
from importacion_csv import importar_catalogo, preparar_importacion
from importacion_formulario_ui import mostrar_formulario_pdf
from mentores import cargar_mentores, normalizar, enlace_correo, enlace_linkedin
from mvp_datos import leer_tabla, leer_seguimientos, importar_banco
from mvp_plan import guardar_desafios, guardar_contacto, cambios_pendientes, ESTADOS_CONTACTO
from mvp_pdf import generar_plan_pdf
from informe_mvp import mostrar_editor, leer_informes, firma_datos


PAGINAS = ['Inicio', '01 · Postulantes', '02 · Banco de desafíos', '03 · Mentoría y plan', '04 · Generar informe', 'Administrar datos']


def navegar(pagina):
    st.session_state['pagina'] = pagina


def mostrar_inicio(postulantes, banco):
    st.subheader('De la postulación a un informe para actuar')
    st.write('Revisa cada solución, selecciona desafíos con fundamento y prepara un informe estratégico con próximos pasos y apoyo de mentoría.')
    metricas = st.columns(4)
    informes = leer_informes()
    planes = leer_seguimientos()
    aprobados = sum(1 for _, p in postulantes.iterrows() if (r := informes.get(p.id))
        and r.get('estado') == 'APROBADO' and r.get('firma_datos') == firma_datos(p.to_dict(), banco, planes.get(p.id, {})))
    for col, titulo, valor in zip(metricas, ['Postulantes', 'Registros en el banco', 'Mentores simulados', 'Informes aprobados'],
                                  [len(postulantes), len(banco), len(cargar_mentores()), aprobados]):
        col.metric(titulo, valor, border=True)
    st.caption(f"{int(postulantes.tipo_registro.eq('REAL').sum())} postulante(s) con datos declarados y {int(postulantes.tipo_registro.eq('FICTICIO_DEMOSTRACION').sum())} ejemplos ficticios de demostración.")
    st.markdown('### Flujo de trabajo')
    pasos = [('Revisar postulante', 'Conoce la solución, su etapa y la evidencia disponible.', 'person_search'),
             ('Explorar desafíos', 'Contrasta fuentes y requisitos. Guarda una selección justificada.', 'travel_explore'),
             ('Preparar mentoría', 'Elige un mentor y prepara la conversación sobre brechas y oportunidades.', 'forum'),
             ('Generar informe', 'Redacta, revisa y aprueba el informe estratégico para compartirlo en PDF.', 'description')]
    for i, (col, (titulo, detalle, icono)) in enumerate(zip(st.columns(4), pasos), 1):
        with col, st.container(border=True, height='stretch'):
            st.caption(f'PASO {i:02d}')
            st.markdown(f'### :material/{icono}: {titulo}')
            st.write(detalle)
            st.button('Generar informe' if i == 4 else 'Abrir paso', key=f'inicio_paso_{i}',
                      type='primary' if i == 4 else 'secondary', on_click=navegar, args=(PAGINAS[i],), width='stretch')
    with st.container(border=True):
        st.markdown('### El resultado: un informe estratégico revisado')
        st.write('Síntesis ejecutiva, oportunidades seleccionadas, condiciones de validación, brechas, mentoría y hoja de ruta de 90 días.')
        st.caption('Puedes partir de un borrador basado en los datos o solicitar una propuesta de redacción con IA. El gestor revisa y aprueba la versión final.')
    with st.expander('Cargar o actualizar información'):
        st.write('Incorpora formularios de postulantes o actualiza el banco de desafíos desde Administrar datos.')
        st.button('Administrar datos', on_click=navegar, args=('Administrar datos',))


def mostrar_perfil(perfil):
    st.subheader('01 · Revisar postulante')
    st.caption('Revisa la solución y sus datos pendientes antes de buscar desafíos en el paso 02.')
    a, b, c = st.columns(3)
    a.metric('TRL declarado', perfil['trl_declarado'] or 'Pendiente', border=True)
    b.metric('TRL objetivo', perfil['trl_objetivo'] or 'Pendiente', border=True)
    c.metric('Ingresos de 12 meses', (perfil['ingresos_solucion_12m'] + ' ' + perfil['moneda_ingresos']).strip() or 'Pendiente', border=True)
    st.caption('Datos declarados. El TRL objetivo es una meta. Una moneda vacía queda pendiente.')
    for col, label, campo in zip(st.columns(2), ['Solución propuesta', 'Problema que aborda'], ['descripcion_solucion', 'problema_resuelve']):
        with col, st.container(border=True):
            st.markdown('### ' + label)
            valor = perfil.get(campo) or 'Pendiente de completar'
            if len(valor) > 420:
                corte = valor.rfind(' ', 0, 420)
                st.write(valor[:corte] + '…')
                with st.expander('Leer descripción completa'):
                    st.write(valor)
            else:
                st.write(valor)
    with st.expander('Tecnología, validación y brechas'):
        for label, campo in [('Tecnología', 'tecnologia_descripcion'), ('Capacidades', 'capacidades_declaradas'),
            ('Validación declarada', 'validacion_tecnica_declarada'), ('Estado comercial', 'estado_comercial'), ('Brechas del equipo', 'brechas_equipo_declaradas')]:
            st.write(f"**{label}:** {perfil.get(campo) or 'Pendiente de completar'}")
    st.button('Continuar al banco de desafíos', on_click=navegar, args=('02 · Banco de desafíos',), type='primary')
    if False:  # La demo pública mantiene los perfiles de ejemplo.
        protegidos = {'id', 'id_empresa_postulante', 'id_postulacion_vigente', 'version_perfil', 'actualizado_en', 'origen_perfil', 'tipo_registro'}
        with st.form('editar_' + perfil['id']):
            cambios = st.data_editor(pd.DataFrame([{'Campo': c, 'Valor': v} for c, v in perfil.items() if c not in protegidos]),
                disabled=['Campo'], hide_index=True, height=440, key='perfil_editor_' + perfil['id'])
            if st.form_submit_button('Guardar cambios del postulante', type='primary'):
                nuevo = dict(perfil)
                nuevo.update(dict(zip(cambios.Campo, cambios.Valor.fillna('').astype(str))))
                importar_catalogo('Postulantes', pd.DataFrame([nuevo], columns=list(perfil)).to_csv(index=False).encode('utf-8-sig'))
                st.session_state['aviso'] = 'Perfil guardado. Revisa la selección de desafíos si cambió la información.'
                st.rerun()
    with st.expander('Origen y trazabilidad'):
        st.write(f"Origen: {perfil['origen_perfil']} · Versión: {perfil['version_perfil']} · Revisión: {perfil['estado_revision']}")
        postulaciones = leer_tabla('postulaciones.csv')
        st.dataframe(postulaciones[postulaciones.id_postulante.eq(perfil['id'])], hide_index=True)


def mostrar_banco(perfil, banco, seguimiento):
    st.subheader('02 · Revisar banco de desafíos')
    st.caption('Contrasta requisitos y guarda una selección justificada. Orden por ID del banco.')
    from anid_tendencias import mostrar_alineacion
    mostrar_alineacion(perfil, banco, seguimiento)
    datos = banco.copy()
    datos['vigencia'] = datos.apply(vigencia, axis=1)
    a, b = st.columns(2)
    sectores = a.multiselect('Sector', sorted(datos.industria.unique()), key='sectores')
    tipos = b.multiselect('Tipo de registro', sorted(datos.tipo_registro.unique()), key='tipos')
    estados = a.multiselect('Vigencia documentada', sorted(datos.vigencia.unique()), key='vigencias')
    buscar = b.text_input('Buscar título, problema o empresa', key='buscar_banco')
    for campo, opciones in [('industria', sectores), ('tipo_registro', tipos), ('vigencia', estados)]:
        if opciones:
            datos = datos[datos[campo].isin(opciones)]
    if buscar.strip():
        textos = datos[['titulo', 'problema', 'nombre_empresa']].agg(' '.join, axis=1).map(normalizar)
        datos = datos[textos.str.contains(normalizar(buscar.strip()), regex=False)]
    datos = datos.sort_values('id')
    st.caption(f'{len(datos)} de {len(banco)} registros. Focos y programas no equivalen a desafíos específicos.')
    if datos.empty:
        st.info('No hay registros con esos filtros. Amplía la búsqueda o documenta que no encontraste un desafío adecuado.')
    else:
        st.dataframe(datos[['id', 'titulo', 'industria', 'tipo_registro', 'vigencia']], hide_index=True)
        por_id = datos.set_index('id')
        identificador = st.selectbox('Abrir registro', datos.id.tolist(),
            format_func=lambda i: i + ' · ' + por_id.loc[i, 'titulo'], key='detalle_banco')
        r = por_id.loc[identificador]
        with st.container(border=True):
            st.subheader(r.titulo, anchor=False)
            st.write(r.problema)
            st.write(f"**Responsable documentado:** {r.nombre_empresa or 'Pendiente de atribución'}")
            st.caption(f'Atribución: {r.atribucion} · Vigencia: {r.vigencia} · {r.estado_documentado}')
            st.write(f'**Requisitos:** {r.requisitos}')
            trl, explicacion = evaluar_trl(r.requisitos, perfil['trl_declarado'])
            (st.warning if trl == 'NO_CUMPLE' else st.info)(explicacion)
            st.write(f'**Fuente:** {r.fuente_principal}')
            url = urlsplit(r.fuente_principal)
            if url.scheme in ('https', 'http') and url.netloc and ' ' not in r.fuente_principal:
                st.link_button('Abrir fuente del registro', r.fuente_principal)
            st.caption(f'Revisión del banco: {r.fecha_revision} · Evidencia: {r.calidad_evidencia}')
            st.write(f'**Observaciones:** {r.observaciones or "Sin observaciones"}')
    st.markdown('### Selección para el postulante')
    st.caption('La selección se conserva al cambiar filtros. Puedes continuar a mentoría sin un desafío adecuado.')
    for aviso in cambios_pendientes(perfil, banco, seguimiento) if seguimiento else []:
        st.warning(aviso)
    nombres = banco.set_index('id').titulo.to_dict()
    with st.form('seleccion_' + perfil['id']):
        seleccion = st.multiselect('Registros para revisar con el mentor', sorted(nombres),
            default=[i for i in seguimiento.get('desafios', []) if i in nombres],
            format_func=lambda i: i + ' · ' + nombres[i], key='elegidos_' + perfil['id'])
        sin_desafio = st.checkbox('No encontré un desafío adecuado', value=seguimiento.get('sin_desafio', False), key='sin_desafio_' + perfil['id'])
        motivo = st.text_area('Justificación y brechas a validar', value=seguimiento.get('justificacion', ''), key='motivo_' + perfil['id'])
        if st.form_submit_button('Guardar revisión del banco', type='primary'):
            guardar_desafios(perfil['id'], seleccion, motivo, sin_desafio)
            st.session_state['aviso'] = 'Revisión guardada. Continúa en «03 · Mentoría y plan».'
            st.rerun()
    if seguimiento.get('huella_perfil'):
        with st.container(horizontal=True):
            st.button('Continuar a mentoría', on_click=navegar, args=('03 · Mentoría y plan',))
            st.button('Preparar informe', on_click=navegar, args=('04 · Generar informe',), type='primary')


def mostrar_mentoria(perfil, banco, seguimiento):
    st.subheader('03 · Contactar mentor y acordar próximos pasos')
    mentores = cargar_mentores()
    st.caption(f'{len(mentores)} perfiles ficticios para demostrar el contacto con mentorías.')
    if not seguimiento.get('huella_perfil'):
        st.info('Primero guarda la revisión del banco en el paso 02. Puedes explorar el directorio mientras tanto.')
    buscar = st.text_input('Buscar mentor, industria o especialidad', key='buscar_mentor')
    categorias = st.multiselect('Categoría de mentor', sorted({m['Categoría Mentor'] for m in mentores}))
    filtrados = [m for m in mentores if (not categorias or m['Categoría Mentor'] in categorias)
        and all(p in normalizar(' '.join(m.get(k, '') for k in ('Nombre completo', 'Industria', 'Expertise técnica', 'Biografia')))
                for p in normalizar(buscar).split())]
    guardado = seguimiento.get('mentor', {})
    if guardado:
        st.caption(f"Mentor guardado: {guardado['Nombre completo']} · {seguimiento.get('estado_contacto', 'Por contactar')}")
    if not filtrados:
        st.info('No hay mentores con esos filtros.')
    else:
        por_nombre = {m['Nombre completo']: m for m in filtrados}
        nombres = list(por_nombre)
        predeterminado = nombres.index(guardado['Nombre completo']) if guardado.get('Nombre completo') in nombres else 0
        elegido = st.selectbox('Mentor para contactar', nombres, index=predeterminado, key='mentor_' + perfil['id'])
        mentor = por_nombre[elegido]
        mismo = elegido == guardado.get('Nombre completo')
        with st.container(border=True):
            st.subheader(elegido, anchor=False)
            st.write(mentor.get('Biografia') or 'Biografía no registrada.')
            for label, campo in [('Industria', 'Industria'), ('Especialidades', 'Expertise técnica'),
                ('Institución', '¿En que empresa/emprendimiento/institución trabajas?'),
                ('Cargo', '¿Cuál es tu actual cargo?'), ('Correo', 'Correo Electrónico'), ('Teléfono', 'Teléfono de contacto')]:
                st.write(f"**{label}:** {mentor.get(campo) or 'No registrado'}")
            if linkedin := enlace_linkedin(mentor.get('Perfil de LinkedIn', '')):
                st.link_button('Ver LinkedIn del mentor', linkedin)
        demo = perfil['tipo_registro'] == 'FICTICIO_DEMOSTRACION'
        prefijo = perfil['id'] + elegido
        asunto_base = ('[DEMOSTRACIÓN] ' if demo else '') + 'Solicitud de mentoría INNOVO USACH - ' + perfil['nombre']
        mensaje_base = (f"Hola {elegido},\n\nDesde INNOVO USACH queremos consultar tu disponibilidad para conversar sobre {perfil['nombre']}. "
            f"La solución aborda: {perfil['problema_resuelve']}.\n\n"
            f"Nos gustaría revisar: {seguimiento.get('justificacion') or 'oportunidades y brechas de validación'}.\n\n"
            '¿Tendrías disponibilidad para una primera reunión?\n\nGracias.')
        if demo:
            mensaje_base = 'EJEMPLO FICTICIO DE DEMOSTRACIÓN. No corresponde a una solicitud real.\n\n' + mensaje_base
        with st.form('contacto_' + prefijo):
            asunto = st.text_input('Asunto', value=seguimiento.get('asunto', asunto_base) if mismo else asunto_base, key='asunto_' + prefijo)
            mensaje = st.text_area('Mensaje para revisar', value=seguimiento.get('mensaje', mensaje_base) if mismo else mensaje_base, height=220, key='mensaje_' + prefijo)
            estado = st.selectbox('Estado informado por el gestor', ESTADOS_CONTACTO,
                index=ESTADOS_CONTACTO.index(seguimiento.get('estado_contacto', 'Por contactar')) if mismo else 0, key='estado_' + prefijo)
            accion = st.text_area('Próxima acción y plazo acordado o por confirmar', value=seguimiento.get('proxima_accion',
                'Consultar disponibilidad del mentor, revisar las brechas y acordar una primera reunión. Plazo por confirmar.'), key='accion_' + prefijo)
            responsable = st.text_input('Responsable del seguimiento', value=seguimiento.get('responsable', ''), key='responsable_' + prefijo)
            st.caption('Guardar o abrir el correo no cambia automáticamente el estado a contactado.')
            if st.form_submit_button('Guardar contacto y plan', type='primary'):
                guardar_contacto(perfil['id'], mentor, estado, asunto, mensaje, accion, responsable)
                st.session_state['aviso'] = 'Contacto y próximos pasos guardados.'
                st.rerun()
    if guardado:
        st.markdown('### Comunicación guardada')
        correo = enlace_correo(guardado.get('Correo Electrónico', ''), seguimiento['asunto'], seguimiento['mensaje'])
        if correo:
            st.link_button('Abrir correo preparado', correo, disabled=perfil['tipo_registro'] == 'FICTICIO_DEMOSTRACION')
        else:
            st.info('Este mentor no tiene un correo válido registrado. Consulta su LinkedIn en la ficha.')
        st.caption('El envío se hace desde tu aplicación de correo. Para postulantes ficticios, usa el borrador descargable de demostración.')
        st.download_button('Descargar mensaje guardado', seguimiento['asunto'] + '\n\n' + seguimiento['mensaje'], file_name=f"contacto_{perfil['id']}.txt", mime='text/plain')
    st.button('Continuar al informe estratégico', on_click=navegar, args=('04 · Generar informe',), type='primary')


def administrar_datos():
    st.info('La demo pública usa datos de ejemplo. La importación está disponible en la versión local.')
    return
    st.subheader('Administrar datos del MVP')
    modo = st.segmented_control('Entrada de datos', ['Formulario PDF', 'Postulantes CSV', 'Banco de desafíos'], default='Formulario PDF')
    if modo == 'Formulario PDF':
        mostrar_formulario_pdf()
    elif modo == 'Postulantes CSV':
        actuales = leer_tabla('postulantes.csv')
        st.caption('ID existente: actualiza el perfil. ID nuevo: añade un postulante. Los registros ausentes se conservan.')
        st.download_button('Descargar catálogo de postulantes', actuales.to_csv(index=False).encode('utf-8-sig'), file_name='postulantes.csv', mime='text/csv')
        st.download_button('Descargar plantilla', actuales.head(0).to_csv(index=False).encode('utf-8-sig'), file_name='plantilla_postulantes.csv', mime='text/csv')
        st.info('tipo_registro: REAL o FICTICIO_DEMOSTRACION. Para crear un perfil desde CSV sin organización ni formulario vinculados, deja vacíos sus IDs de referencia.')
        archivo = st.file_uploader('Cargar postulantes CSV', type=['csv'], max_upload_size=5)
        if archivo:
            nuevos, resultado, cambios = preparar_importacion(archivo.getvalue(), actuales)
            st.dataframe(nuevos, hide_index=True)
            st.caption(f'{len(cambios)} perfiles modificados · {len(resultado)} postulantes tras guardar')
            if st.button('Aplicar postulantes', disabled=not cambios, type='primary'):
                importar_catalogo('Postulantes', archivo.getvalue())
                st.session_state['aviso'] = 'Postulantes actualizados con respaldo.'
                st.rerun()
    elif modo == 'Banco de desafíos':
        st.caption('Excel completo con hojas Base, Empresas, Relaciones y Fuentes. Se conservan fuentes y atribución.')
        archivo = st.file_uploader('Actualizar banco desde Excel', type=['xlsx'], max_upload_size=20)
        if archivo:
            tablas = preparar_banco(archivo.getvalue())
            st.dataframe(tablas['banco_base.csv'][['id', 'titulo', 'tipo_registro', 'industria']], hide_index=True)
            st.info('Reemplaza el banco con respaldo. Las selecciones afectadas deberán revisarse antes de descargar su plan.')
            if st.button('Aplicar banco de desafíos', type='primary'):
                importar_banco(archivo.getvalue())
                st.session_state['aviso'] = 'Banco actualizado con respaldo.'
                st.rerun()


def main():
    st.info('Demo de hackatón · Postulantes y mentores ficticios. Los cambios pertenecen a esta sesión; descarga el PDF antes de salir.')
    logo, titulo = st.columns([1, 7], vertical_alignment='center')
    with logo:
        if Path('logo_innovo.png').exists():
            st.image('logo_innovo.png', width=115)
    with titulo:
        st.caption('INNOVO USACH · GESTIÓN DE OPORTUNIDADES')
        st.title('Del postulante al informe', anchor=False)
        st.caption('Desafíos con evidencia, mentoría y decisiones revisadas por el gestor.')
    if aviso := st.session_state.pop('aviso', None) or st.session_state.pop('aviso_importacion', None):
        st.success(aviso)
    postulantes = leer_tabla('postulantes.csv')
    banco = leer_tabla('banco_base.csv')
    pagina = st.radio('Recorrido del MVP', PAGINAS, key='pagina', horizontal=True, label_visibility='collapsed')
    if pagina == 'Inicio':
        mostrar_inicio(postulantes, banco)
        return
    if pagina == 'Administrar datos':
        administrar_datos()
        return
    if postulantes.empty:
        st.info('Carga un formulario o un CSV en Administrar datos para comenzar.')
        return
    nombres = postulantes.set_index('id')
    if 'postulante_activo' not in st.session_state and st.session_state.get('ultimo_postulante') in nombres.index:
        st.session_state['postulante_activo'] = st.session_state['ultimo_postulante']
    sid = st.selectbox('Postulante activo', postulantes.id.tolist(), key='postulante_activo',
        format_func=lambda i: nombres.loc[i, 'nombre'] + (' · FICTICIO · DEMOSTRACIÓN' if nombres.loc[i, 'tipo_registro'] == 'FICTICIO_DEMOSTRACION' else ' · Datos declarados'))
    st.session_state['ultimo_postulante'] = sid
    perfil = postulantes[postulantes.id.eq(sid)].iloc[0].to_dict()
    if perfil['tipo_registro'] == 'FICTICIO_DEMOSTRACION':
        st.warning('FICTICIO · DEMOSTRACIÓN. Las cifras, validaciones y actividades de este postulante son simuladas.')
    seguimiento = leer_seguimientos().get(sid, {})
    if pagina == '01 · Postulantes':
        mostrar_perfil(perfil)
    elif pagina == '02 · Banco de desafíos':
        mostrar_banco(perfil, banco, seguimiento)
    elif pagina == '03 · Mentoría y plan':
        mostrar_mentoria(perfil, banco, seguimiento)
    elif pagina == '04 · Generar informe':
        mostrar_editor(perfil, banco, seguimiento)
