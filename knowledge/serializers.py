from rest_framework import serializers
from .models import Source

class SourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Source
        fields = (
            'id', 'type', 'title', 'url_or_path', 'status', 
            'image_description', 'thumbnail_url', 'chunk_count', 
            'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'status', 'chunk_count', 'created_at', 'updated_at')