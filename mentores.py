"""Directorio local de mentores INNOVO; selección del gestor, sin ranking."""
import csv
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote, urlencode, urlsplit

ARCHIVO_MENTORES = Path(__file__).parent / 'mentores_demo.csv'


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold())
                   if not unicodedata.combining(c))


def cargar_mentores(ruta=ARCHIVO_MENTORES):
    with Path(ruta).open(encoding='utf-8-sig', newline='') as archivo:
        lector = csv.DictReader(archivo)
        if not {'Nombre completo', 'Correo Electrónico', 'Industria'}.issubset(lector.fieldnames or []):
            raise ValueError('El directorio no contiene las columnas de mentores esperadas.')
        return sorted(({k.strip(): (v or '').strip() for k, v in fila.items() if k}
                       for fila in lector if fila.get('Nombre completo', '').strip()),
                      key=lambda m: normalizar(m['Nombre completo']))


def enlace_linkedin(valor):
    valor = valor.strip()
    if valor.startswith('www.'):
        valor = 'https://' + valor
    url = urlsplit(valor)
    return valor if url.scheme in ('https', 'http') and url.hostname in ('linkedin.com', 'www.linkedin.com') else ''


def enlace_correo(correo, asunto, mensaje):
    if not re.fullmatch(r'[^\s@,;?]+@[^\s@,;?]+\.[^\s@,;?]+', correo):
        return ''
    return 'mailto:' + quote(correo, safe='@') + '?' + urlencode({'subject': asunto, 'body': mensaje}, quote_via=quote)


