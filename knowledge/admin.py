from django.contrib import admin
from .models import Source, DocumentChunk


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'type', 'status', 'chunk_count', 'created_at')
    list_filter = ('type', 'status')
    search_fields = ('title', 'url_or_path')


@admin.register(DocumentChunk)
class DocumentChunkAdmin(admin.ModelAdmin):
    list_display = ('source', 'company', 'created_at')
    search_fields = ('content',)