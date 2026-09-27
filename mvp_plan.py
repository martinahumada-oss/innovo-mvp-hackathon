"""Selección manual y seguimiento por postulante, sin inferir compatibilidad."""
from pathlib import Path
from mvp_datos import leer_tabla, leer_seguimientos, guardar_seguimiento, huella

ESTADOS_CONTACTO = ['Por contactar', 'Contactado', 'Reunión acordada', 'Mentoría realizada', 'Sin disponibilidad']


def guardar_desafios(postulante_id, ids, justificacion, sin_desafio=False, raiz=Path('.')):
    postulantes = leer_tabla('postulantes.csv', raiz).set_index('id')
    banco = leer_tabla('banco_base.csv', raiz).set_index('id', drop=False)
    if not justificacion.strip():
        raise ValueError('Explica por qué seleccionas estos registros o por qué no hay un desafío adecuado.')
    ids = list(dict.fromkeys(ids))
    if bool(ids) == bool(sin_desafio):
        raise ValueError('Selecciona al menos un registro o indica que no encontraste un desafío adecuado.')
    if postulante_id not in postulantes.index or not set(ids).issubset(banco.index):
        raise ValueError('Los datos cambiaron. Vuelve a revisar la selección.')
    # Incluir ID en la huella, igual que en la lectura de la interfaz.
    perfil = postulantes.loc[postulante_id].to_dict() | {'id': postulante_id}
    guardar_seguimiento(postulante_id, dict(desafios=ids, justificacion=justificacion.strip(),
        sin_desafio=bool(sin_desafio), huella_perfil=huella(perfil),
        huellas_desafios={i: huella(banco.loc[i].to_dict()) for i in ids}), raiz)


def cambios_pendientes(perfil, banco, seguimiento):
    if not seguimiento.get('huella_perfil'):
        return ['Falta guardar la revisión del banco de desafíos.']
    avisos = []
    if seguimiento['huella_perfil'] != huella(perfil):
        avisos.append('El perfil cambió desde la selección de desafíos.')
    por_id = banco.set_index('id', drop=False)
    for identificador in seguimiento.get('desafios', []):
        if identificador not in por_id.index:
            avisos.append(f'{identificador} ya no está en el banco.')
        elif seguimiento.get('huellas_desafios', {}).get(identificador) != huella(por_id.loc[identificador].to_dict()):
            avisos.append(f'{identificador} cambió desde la selección.')
    return avisos


def guardar_contacto(postulante_id, mentor, estado, asunto, mensaje, proxima_accion, responsable, raiz=Path('.')):
    if estado not in ESTADOS_CONTACTO:
        raise ValueError('Estado de contacto inválido.')
    if not all(str(v).strip() for v in (mentor.get('Nombre completo'), asunto, mensaje, proxima_accion, responsable)):
        raise ValueError('Completa mentor, mensaje, próxima acción y responsable.')
    guardar_seguimiento(postulante_id, dict(mentor=dict(mentor), estado_contacto=estado,
        asunto=asunto, mensaje=mensaje, proxima_accion=proxima_accion, responsable=responsable), raiz)
