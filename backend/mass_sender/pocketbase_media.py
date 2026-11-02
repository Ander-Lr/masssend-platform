"""
Almacenamiento PROTEGIDO de fotos y videos de campañas en PocketBase.

Patrón visto en clase (pocketbase-storage), reforzado con la protección
de archivos exigida en el tercer parcial:

- La colección `campaign_media` es PRIVADA (sin reglas públicas) y el
  campo `file` está marcado como `protected`: la URL directa del archivo
  NO funciona desde otro navegador o sesión sin autorización.
- Solo Django, autenticado como superusuario de PocketBase, puede subir
  y descargar los archivos. El navegador los recibe a través de un
  endpoint del backend que valida al usuario (sesión o JWT) antes de
  entregar el contenido.
- Si PocketBase no está disponible, se usa el almacenamiento local de
  Django como respaldo para que el sistema no se caiga.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_admin_token_cache = {'token': None}


def _pb_url():
    return getattr(settings, 'POCKETBASE_URL', 'http://localhost:8090').rstrip('/')


def _public_url():
    return getattr(settings, 'POCKETBASE_PUBLIC_URL', _pb_url()).rstrip('/')


def _collection():
    return getattr(settings, 'POCKETBASE_COLLECTION', 'campaign_media')


def _collection_body():
    """Definición de la colección: privada y con archivo protegido."""
    return {
        'name': _collection(),
        'type': 'base',
        # Sin listRule/viewRule públicos: solo el superusuario accede.
        'listRule': None,
        'viewRule': None,
        'createRule': None,
        'updateRule': None,
        'deleteRule': None,
        'fields': [
            {'name': 'title', 'type': 'text'},
            {'name': 'campaign_id', 'type': 'number'},
            {'name': 'mime_type', 'type': 'text'},
            {
                'name': 'file',
                'type': 'file',
                'maxSelect': 1,
                'maxSize': 52428800,  # 50 MB (videos)
                # protected=True: la URL directa exige un token temporal.
                'protected': True,
            },
        ],
    }


def _admin_token():
    """Autentica el superusuario de PocketBase."""
    if _admin_token_cache['token']:
        return _admin_token_cache['token']
    email = getattr(settings, 'POCKETBASE_ADMIN_EMAIL', '')
    password = getattr(settings, 'POCKETBASE_ADMIN_PASSWORD', '')
    if not email or not password:
        return None
    try:
        response = requests.post(
            f"{_pb_url()}/api/collections/_superusers/auth-with-password",
            json={'identity': email, 'password': password},
            timeout=5,
        )
        response.raise_for_status()
        _admin_token_cache['token'] = response.json().get('token')
        return _admin_token_cache['token']
    except requests.RequestException as exc:
        logger.warning('PocketBase: no se pudo autenticar el superusuario: %s', exc)
        return None


def _ensure_collection():
    """Crea la colección privada, o la actualiza si existía como pública."""
    token = _admin_token()
    if not token:
        return False
    headers = {'Authorization': token}
    body = _collection_body()
    try:
        check = requests.get(
            f"{_pb_url()}/api/collections/{_collection()}", headers=headers, timeout=5
        )
        if check.status_code == 200:
            actual = check.json()
            file_field = next((f for f in actual.get('fields', []) if f.get('name') == 'file'), {})
            es_publica = actual.get('viewRule') == '' or not file_field.get('protected')
            if es_publica:
                # Migración: quitar reglas públicas y proteger el archivo.
                patch = requests.patch(
                    f"{_pb_url()}/api/collections/{_collection()}",
                    headers=headers, json=body, timeout=10,
                )
                patch.raise_for_status()
                logger.info('PocketBase: colección %s asegurada (privada).', _collection())
            return True
        response = requests.post(
            f"{_pb_url()}/api/collections", headers=headers, json=body, timeout=10
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning('PocketBase: no se pudo crear/asegurar la colección: %s', exc)
        return False


def subir_media_campana(django_file, campaign_id=None, title=''):
    """
    Sube la foto/video de una campaña a PocketBase.
    Devuelve la URL del archivo (basada en POCKETBASE_PUBLIC_URL, que se
    usa solo como identificador: el archivo es privado y únicamente se
    entrega por el endpoint autenticado de Django), o None si falló.
    """
    if not _ensure_collection():
        return None
    token = _admin_token()
    if not token:
        return None
    try:
        django_file.seek(0)
        response = requests.post(
            f"{_pb_url()}/api/collections/{_collection()}/records",
            headers={'Authorization': token},
            data={
                'title': title or getattr(django_file, 'name', 'media'),
                'campaign_id': campaign_id or 0,
                'mime_type': getattr(django_file, 'content_type', '') or '',
            },
            files={'file': (django_file.name, django_file, getattr(django_file, 'content_type', None))},
            timeout=30,
        )
        response.raise_for_status()
        record = response.json()
        filename = record.get('file')
        if not filename:
            return None
        url = f"{_public_url()}/api/files/{_collection()}/{record['id']}/{filename}"
        logger.info('PocketBase: media de campaña almacenado (protegido) en %s', url)
        return url
    except requests.RequestException as exc:
        logger.warning('PocketBase: fallo al subir el archivo, se usará respaldo local: %s', exc)
        return None


def es_url_pocketbase(url):
    """Indica si la URL corresponde a un archivo guardado en PocketBase."""
    if not url:
        return False
    prefix = '/api/files/'
    return url.startswith(_public_url() + prefix) or url.startswith(_pb_url() + prefix)


def descargar_media(media_url):
    """
    Descarga un archivo protegido de PocketBase usando el superusuario.
    Devuelve (bytes, content_type) o (None, None) si falla.
    """
    token = _admin_token()
    if not token:
        return None, None
    # Traducir la URL pública (navegador) a la interna (red Docker).
    path = media_url
    for base in (_public_url(), _pb_url()):
        if path.startswith(base):
            path = path[len(base):]
            break
    try:
        # Los archivos `protected` exigen un token temporal de archivos.
        token_resp = requests.post(
            f"{_pb_url()}/api/files/token",
            headers={'Authorization': token},
            timeout=5,
        )
        token_resp.raise_for_status()
        file_token = token_resp.json().get('token', '')
        response = requests.get(
            f"{_pb_url()}{path}",
            params={'token': file_token},
            timeout=30,
        )
        response.raise_for_status()
        return response.content, response.headers.get('Content-Type', 'application/octet-stream')
    except requests.RequestException as exc:
        logger.warning('PocketBase: no se pudo descargar el archivo protegido: %s', exc)
        return None, None


def estado_pocketbase():
    """Estado del servicio para el health del sistema."""
    try:
        response = requests.get(f"{_pb_url()}/api/health", timeout=3)
        response.raise_for_status()
        return {'available': True, 'url': _pb_url(), 'collection': _collection()}
    except requests.RequestException:
        return {'available': False, 'url': _pb_url(), 'collection': _collection()}
