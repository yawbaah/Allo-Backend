import uuid
from django.db import models
from pgvector.django import VectorField, HnswIndex


class Source(models.Model):
    TYPE_CHOICES = [
        ('page', 'Web Page'),
        ('pdf', 'PDF'),
        ('docx', 'DOCX'),
        ('image', 'Image'),
        ('text', 'Manual Text'),  # ← add this

    ]
    STATUS_CHOICES = [
        ('crawling', 'Crawling'),
        ('processing', 'Processing'),
        ('indexed', 'Indexed'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company',
        related_name='sources',
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    url_or_path = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='processing')

    # For images
    image_description = models.TextField(blank=True)
    thumbnail_url = models.TextField(blank=True)

    chunk_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sources'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type}: {self.title}"


class DocumentChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(Source, related_name='chunks', on_delete=models.CASCADE)
    company = models.ForeignKey(
        'companies.Company',
        related_name='chunks',
        on_delete=models.CASCADE,
    )
    content = models.TextField()
    # OpenAI text-embedding-3-small = 1536 dimensions
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'document_chunks'
        indexes = [
            HnswIndex(
                name='chunk_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
            models.Index(fields=['company']),
        ]