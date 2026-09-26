from django.contrib import admin
from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('visitor_identifier', 'company', 'status', 'visitor_lang', 'updated_at')
    list_filter = ('status', 'visitor_lang')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'sender_role', 'created_at')
    search_fields = ('content',)