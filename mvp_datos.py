"""Lecturas y escritura transaccional del MVP local."""
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import pandas as pd
from demo_sesion import raiz_demo


def leer_tabla(nombre, raiz=Path('.')):
    return pd.read_csv(raiz_demo(raiz) / nombre, dtype=str, encoding='utf-8-sig').fillna('')


@contextmanager
def bloqueo_importacion(raiz):
    ruta = raiz_demo(raiz) / '.importacion.lock'
    try:
        archivo = ruta.open('x')
    except FileExistsError as error:
        raise ValueError('Hay una actualización en curso. Espera e inténtalo nuevamente.') from error
    archivo.close()
    try:
        yield
    finally:
        ruta.unlink(missing_ok=True)


def guardar_archivos(archivos, raiz=Path('.')):
    """El llamador mantiene el bloqueo desde la lectura hasta el commit."""
    raiz = raiz_demo(raiz).resolve()
    for nombre in archivos:
        if not (raiz / nombre).resolve().is_relative_to(raiz):
            raise ValueError('Ruta fuera del proyecto.')
    with tempfile.TemporaryDirectory(dir=raiz) as tmp:
        stage = Path(tmp)
        for nombre, contenido in archivos.items():
            destino = stage / nombre
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(contenido)
        respaldo = raiz / 'respaldos' / ('mvp_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        respaldo.mkdir(parents=True)
        existentes = {n for n in archivos if (raiz / n).exists()}
        for n in existentes:
            (respaldo / n).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(raiz / n, respaldo / n)
        try:
            for n in archivos:
                (raiz / n).parent.mkdir(parents=True, exist_ok=True)
                (stage / n).replace(raiz / n)
        except OSError:
            for n in archivos:
                if n in existentes:
                    shutil.copy2(respaldo / n, raiz / n)
                else:
                    (raiz / n).unlink(missing_ok=True)
            raise
        return respaldo


def huella(registro):
    return hashlib.sha256(json.dumps(dict(registro), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def leer_seguimientos(raiz=Path('.')):
    path = raiz_demo(raiz) / 'seguimiento_mvp.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def guardar_seguimiento(postulante_id, cambios, raiz=Path('.')):
    raiz = raiz_demo(raiz)
    with bloqueo_importacion(raiz):
        postulantes = leer_tabla('postulantes.csv', raiz)
        if postulante_id not in set(postulantes.id):
            raise ValueError('El postulante ya no existe.')
        todos = leer_seguimientos(raiz)
        registro = todos.get(postulante_id, {})
        registro.update(cambios)
        registro['actualizado_en'] = datetime.now().isoformat(timespec='seconds')
        todos[postulante_id] = registro
        guardar_archivos({'seguimiento_mvp.json': json.dumps(todos, ensure_ascii=False, indent=2).encode()}, raiz)


def importar_banco(contenido, raiz=Path('.')):
    from banco_desafios import preparar_banco
    tablas = preparar_banco(contenido)
    archivos = {nombre: df.to_csv(index=False).encode('utf-8-sig') for nombre, df in tablas.items()}
    archivos['datos/banco/Banco_desafios_innovacion_Chile.xlsx'] = contenido
    with bloqueo_importacion(raiz):
        respaldo = guardar_archivos(archivos, raiz)
    return respaldo, len(tablas['banco_base.csv'])
