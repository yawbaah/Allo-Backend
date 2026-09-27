from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Matches /ws/dash/company/<id>/ AND /api/ws/dash/company/<id>/
    re_path(
        r'^(?:api/)?ws/dash/company/(?P<company_id>[^/]+)/?$',
        consumers.DashboardConsumer.as_asgi()
    ),
    # Matches /ws/chat/conversation/<id>/ AND /api/ws/chat/conversation/<id>/
    re_path(
        r'^(?:api/)?ws/chat/conversation/(?P<conversation_id>[^/]+)/?$',
        consumers.ChatConsumer.as_asgi()
    ),
]