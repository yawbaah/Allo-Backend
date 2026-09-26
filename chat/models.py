import uuid
from django.db import models


class Conversation(models.Model):
    STATUS_CHOICES = [
        ('ai', 'AI handled'),
        ('human', 'Needs human'),
        ('live', 'Live with agent'),
        ('resolved', 'Resolved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        'companies.Company',
        related_name='conversations',
        on_delete=models.CASCADE,
    )
    visitor_identifier = models.CharField(max_length=100)
    visitor_lang = models.CharField(max_length=10, default='en')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ai')
    preview_text = models.TextField(blank=True)

    # So we only send ONE handoff email per conversation (not per message)
    handoff_email_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'conversations'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['company', 'status']),
        ]


class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'Visitor'),
        ('ai', 'AI'),
        ('agent', 'Human Agent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        related_name='messages',
        on_delete=models.CASCADE,
    )
    sender_role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    sender_user = models.ForeignKey(
        'accounts.User',
        null=True, blank=True,
        on_delete=models.SET_NULL,
    )
    content = models.TextField()
    translated_content = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messages'
        ordering = ['created_at']