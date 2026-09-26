from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.shortcuts import get_object_or_404
from django.utils import timezone

from companies.models import Company
from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    ConversationListSerializer,
    MessageSerializer,
    WidgetChatSerializer,
    AgentReplySerializer,
)
from .services import (
    process_visitor_message,
    broadcast_ws_message,
    broadcast_dash_alert,
    UsageLimitExceededException,
)


# ---------------------------------------------------------------------------
# PUBLIC — called by widget.js (no JWT)
# ---------------------------------------------------------------------------

class WidgetChatView(APIView):
    """
    POST /api/chat/widget/
    Body: { company_id, visitor_id, message, visitor_lang?, conversation_id? }
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # public

    def post(self, request):
        serializer = WidgetChatSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        try:
            company = Company.objects.get(id=data['company_id'])
        except Company.DoesNotExist:
            return Response(
                {"error": "Invalid company_id."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            conversation, user_msg, ai_msg = process_visitor_message(
                company=company,
                visitor_id=data['visitor_id'],
                message_text=data['message'],
                visitor_lang=data.get('visitor_lang', 'en'),
                conversation_id=data.get('conversation_id'),
            )

            return Response(
                {
                    "conversation_id": str(conversation.id),
                    "status": conversation.status,
                    "messages": [
                        MessageSerializer(user_msg).data,
                        MessageSerializer(ai_msg).data,
                    ],
                },
                status=status.HTTP_200_OK,
            )

        except UsageLimitExceededException:
            # Fallback action: Inform the visitor and escalate directly to human
            # without triggering OpenAI model endpoints, preserving API cost metrics.
            return Response(
                {
                    "conversation_id": data.get('conversation_id') or "",
                    "status": "human",
                    "messages": [
                        {
                            "id": "err-limit-user",
                            "sender_role": "user",
                            "content": data['message'],
                            "created_at": timezone.now().isoformat()
                        },
                        {
                            "id": "err-limit-bot",
                            "sender_role": "ai",
                            "content": "Our automated chat systems are currently at maximum capacity. Handing your ticket to our active human support channel...",
                            "created_at": timezone.now().isoformat()
                        }
                    ],
                    "limit_reached": True
                },
                status=status.HTTP_200_OK
            )


class WidgetConfigView(APIView):
    """
    GET /api/chat/widget-config/<company_id>/
    Returns branding for the embed script (color, name, launcher, welcome).
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, company_id):
        company = get_object_or_404(Company, id=company_id)
        return Response({
            "company_id": str(company.id),
            "name": company.widget_name,
            "color": company.widget_color,
            "position": company.widget_position,
            "launcher": company.widget_launcher,
            "logo_url": company.widget_logo_url,
            "welcome_message": company.widget_welcome_msg,
        })


# ---------------------------------------------------------------------------
# DASHBOARD — agents (JWT required)
# ---------------------------------------------------------------------------

class ConversationListView(APIView):
    """GET /api/chat/conversations/ — Inbox list"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = request.user.company
        if not company:
            return Response({"error": "No company."}, status=status.HTTP_400_BAD_REQUEST)

        qs = Conversation.objects.filter(company=company)

        status_filter = request.query_params.get('status')
        if status_filter in ('ai', 'human', 'live', 'resolved'):
            qs = qs.filter(status=status_filter)

        serializer = ConversationListSerializer(qs[:100], many=True)
        return Response(serializer.data)


class ConversationDetailView(APIView):
    """GET /api/chat/conversations/<id>/ — full thread"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        company = request.user.company
        conversation = get_object_or_404(Conversation, pk=pk, company=company)
        return Response(ConversationSerializer(conversation).data)


class AgentJoinView(APIView):
    """POST /api/chat/conversations/<id>/join/ — mark thread live"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        company = request.user.company
        conversation = get_object_or_404(Conversation, pk=pk, company=company)
        conversation.status = 'live'
        conversation.save(update_fields=['status', 'updated_at'])

        broadcast_dash_alert(company.id, conversation)
        return Response(ConversationSerializer(conversation).data, status=status.HTTP_200_OK)


class AgentReplyView(APIView):
    """POST /api/chat/conversations/<id>/reply/ — human sends a message"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        company = request.user.company
        conversation = get_object_or_404(Conversation, pk=pk, company=company)

        serializer = AgentReplySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        msg = Message.objects.create(
            conversation=conversation,
            sender_role='agent',
            sender_user=request.user,
            content=data['content'],
            translated_content=data.get('translated_content', ''),
        )

        conversation.status = 'live'
        conversation.preview_text = data['content'][:240]
        conversation.save(update_fields=['status', 'preview_text', 'updated_at'])

        # Serialize and broadcast human agent response instantly to channels
        serialized_msg = MessageSerializer(msg).data
        broadcast_ws_message(str(conversation.id), serialized_msg)

        # Keep list sorting synced across dashboard views
        broadcast_dash_alert(company.id, conversation)

        return Response(serialized_msg, status=status.HTTP_201_CREATED)


class ConversationResolveView(APIView):
    """POST /api/chat/conversations/<id>/resolve/"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        company = request.user.company
        conversation = get_object_or_404(Conversation, pk=pk, company=company)
        conversation.status = 'resolved'
        conversation.save(update_fields=['status', 'updated_at'])

        broadcast_dash_alert(company.id, conversation)
        return Response(ConversationListSerializer(conversation).data, status=status.HTTP_200_OK)