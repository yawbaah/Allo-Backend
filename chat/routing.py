from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Dashboard updates route
    re_path(r'^ws/dash/company/(?P<company_id>[^/]+)/$', consumers.DashboardConsumer.as_asgi()),
    # Core visitor/agent thread-specific exchange route
    re_path(r'^ws/chat/conversation/(?P<conversation_id>[^/]+)/$', consumers.ChatConsumer.as_asgi()),
]