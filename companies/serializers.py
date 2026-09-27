from urllib.parse import quote
from django.conf import settings
from rest_framework import serializers
from .models import Company


def _absolutize_logo(value: str | None) -> str:
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value.replace(" ", "%20")
    if value.startswith("blob:") or value.startswith("data:"):
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


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('widget_logo_url'):
            data['widget_logo_url'] = _absolutize_logo(data['widget_logo_url'])
        return data