from rest_framework import serializers
from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = (
            'id',
            'sender_role',
            'content',
            'translated_content',
            'created_at',
        )
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            'id',
            'visitor_identifier',
            'visitor_lang',
            'status',
            'preview_text',
            'handoff_email_sent',
            'created_at',
            'updated_at',
            'messages',
            'message_count',
        )
        read_only_fields = fields

    def get_message_count(self, obj):
        return obj.messages.count()


class ConversationListSerializer(serializers.ModelSerializer):
    """Lighter list for the Inbox sidebar (no full message history)."""
    class Meta:
        model = Conversation
        fields = (
            'id',
            'visitor_identifier',
            'visitor_lang',
            'status',
            'preview_text',
            'created_at',
            'updated_at',
        )


class WidgetChatSerializer(serializers.Serializer):
    """Public endpoint used by widget.js — no JWT required."""
    company_id = serializers.UUIDField()
    visitor_id = serializers.CharField(max_length=100)
    message = serializers.CharField(max_length=4000)
    visitor_lang = serializers.CharField(max_length=10, required=False, default='en')
    conversation_id = serializers.UUIDField(required=False, allow_null=True)


class AgentReplySerializer(serializers.Serializer):
    content = serializers.CharField(max_length=4000)
    # Optional: agent typed in their language; we store original + translated later
    translated_content = serializers.CharField(max_length=4000, required=False, allow_blank=True)