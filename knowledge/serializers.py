from urllib.parse import quote
from django.conf import settings
from rest_framework import serializers
from .models import Source


def _absolutize(value: str | None) -> str:
    if not value:
        return value or ""
    if value.startswith("http://") or value.startswith("https://"):
        return value.replace(" ", "%20")
    if value.startswith("manual://"):
        return value
    clean = value.lstrip("/")
    if clean.startswith("media/"):
        clean = clean[len("media/"):]
    safe = quote(clean, safe="/")
    use_r2 = getattr(settings, "USE_R2", False)
    if use_r2 and getattr(settings, "R2_PUBLIC_BASE_URL", ""):
        return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{safe}"
    backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000").rstrip("/")
    return f"{backend_url}/media/{safe}"


class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = (
            'id', 'type', 'title', 'url_or_path', 'status',
            'image_description', 'thumbnail_url', 'chunk_count',
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'status', 'chunk_count', 'created_at', 'updated_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('thumbnail_url'):
            data['thumbnail_url'] = _absolutize(data['thumbnail_url'])
        if instance.type in ('image', 'pdf', 'docx') and data.get('url_or_path'):
            v = data['url_or_path']
            if not v.startswith('http') and not v.startswith('manual://'):
                data['url_or_path'] = _absolutize(v)
        return data