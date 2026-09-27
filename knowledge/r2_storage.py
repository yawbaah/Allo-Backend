import io
import logging
import mimetypes
from urllib.parse import quote, unquote

import boto3
import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

_client = None


def get_r2_client():
    global _client
    if _client is not None:
        return _client
    _client = boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name=getattr(settings, "R2_REGION_NAME", "auto"),
    )
    return _client


def get_public_url(key: str) -> str:
    base = getattr(settings, "R2_PUBLIC_BASE_URL", "").rstrip("/")
    safe_key = quote(key.lstrip("/"), safe="/")
    return f"{base}/{safe_key}"


def key_from_url_or_key(value: str) -> str:
    if not value:
        return value
    base = getattr(settings, "R2_PUBLIC_BASE_URL", "").rstrip("/")
    if base and value.startswith(base):
        return unquote(value[len(base):].lstrip("/"))
    if value.startswith("http://") or value.startswith("https://"):
        # external URL, not ours - return as-is for caller to handle
        return value
    v = unquote(value.lstrip("/"))
    if v.startswith("media/"):
        v = v[len("media/"):]
    return v


def upload_fileobj(fileobj, key: str, content_type: str | None = None) -> str:
    if not content_type:
        guessed, _ = mimetypes.guess_type(key)
        content_type = guessed or "application/octet-stream"
    try:
        fileobj.seek(0)
    except Exception:
        pass
    client = get_r2_client()
    client.upload_fileobj(
        fileobj,
        settings.R2_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return get_public_url(key)


def download_bytes(value: str) -> bytes:
    if value.startswith("http://") or value.startswith("https://"):
        base = getattr(settings, "R2_PUBLIC_BASE_URL", "").rstrip("/")
        if not base or not value.startswith(base):
            with httpx.Client(timeout=30.0, follow_redirects=True) as c:
                r = c.get(value)
                r.raise_for_status()
                return r.content
        key = key_from_url_or_key(value)
    else:
        key = key_from_url_or_key(value)

    client = get_r2_client()
    buf = io.BytesIO()
    client.download_fileobj(settings.R2_BUCKET_NAME, key, buf)
    return buf.getvalue()