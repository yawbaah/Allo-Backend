import json
import re
from channels.generic.websocket import AsyncWebsocketConsumer


def sanitize_group_name(prefix: str, identifier: str) -> str:
    clean_id = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', str(identifier))
    return f"{prefix}_{clean_id}"[:100]


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.company_id = self.scope['url_route']['kwargs']['company_id']
        self.group_name = sanitize_group_name("dash_company", self.company_id)

        try:
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        except Exception as e:
            print(f"[WebSocket Error] DashboardConsumer connect failed: {e}")
            try:
                await self.close(code=4001)
            except Exception:
                pass

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        except Exception:
            pass

    async def handoff_alert(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "handoff_alert",
                "conversation_id": event.get("conversation_id"),
                "visitor_identifier": event.get("visitor_identifier"),
                "preview_text": event.get("preview_text"),
                "status": event.get("status"),
                "updated_at": event.get("updated_at"),
            }))
        except Exception as e:
            print(f"[WebSocket Warning] handoff_alert send failed: {e}")


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.group_name = sanitize_group_name("conversation", self.conversation_id)

        try:
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        except Exception as e:
            print(f"[WebSocket Error] ChatConsumer connect failed: {e}")
            try:
                await self.close(code=4001)
            except Exception:
                pass

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        except Exception:
            pass

    async def chat_message(self, event):
        try:
            await self.send(text_data=json.dumps({
                "type": "chat_message",
                "message": event.get("message")
            }))
        except Exception as e:
            print(f"[WebSocket Warning] chat_message send failed: {e}")