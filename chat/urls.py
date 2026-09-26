from django.urls import path
from .views import (
    WidgetChatView,
    WidgetConfigView,
    ConversationListView,
    ConversationDetailView,
    AgentJoinView,
    AgentReplyView,
    ConversationResolveView,
)

urlpatterns = [
    # Public widget
    path('widget/', WidgetChatView.as_view(), name='widget-chat'),
    path('widget-config/<uuid:company_id>/', WidgetConfigView.as_view(), name='widget-config'),

    # Dashboard inbox
    path('conversations/', ConversationListView.as_view(), name='conversation-list'),
    path('conversations/<uuid:pk>/', ConversationDetailView.as_view(), name='conversation-detail'),
    path('conversations/<uuid:pk>/join/', AgentJoinView.as_view(), name='conversation-join'),
    path('conversations/<uuid:pk>/reply/', AgentReplyView.as_view(), name='conversation-reply'),
    path('conversations/<uuid:pk>/resolve/', ConversationResolveView.as_view(), name='conversation-resolve'),
]