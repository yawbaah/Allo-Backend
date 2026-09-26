from datetime import timedelta
import os
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from django.core.files.storage import default_storage
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Company
from .serializers import CompanySerializer
from chat.models import Conversation, Message
from knowledge.models import Source, DocumentChunk


class CompanyMeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "No company associated with this user."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "No company associated with this user."}, status=status.HTTP_404_NOT_FOUND)

        # 1. Handle permanent logo file upload if provided
        if 'logo_file' in request.FILES:
            logo_file = request.FILES['logo_file']

            # Clean up old logo file from disk if it exists
            if company.widget_logo_url:
                try:
                    old_path = company.widget_logo_url.split('/media/')[-1]
                    if default_storage.exists(old_path):
                        default_storage.delete(old_path)
                except Exception:
                    pass

            save_path = default_storage.save(f'logos/{company.id}/{logo_file.name}', logo_file)
            backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')
            company.widget_logo_url = f"{backend_url}/media/{save_path}"
            company.save(update_fields=['widget_logo_url'])

        # 2. Update text and configuration fields
        serializer = CompanySerializer(company, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(CompanySerializer(company).data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CompanyAnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "No company associated with user."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)

        # 1. Total & Monthly Conversations
        all_conversations = Conversation.objects.filter(company=company)
        total_conversations_count = all_conversations.count()

        # 2. AI Resolution Rate
        ai_resolved_count = all_conversations.filter(status='ai').count()
        human_handoff_count = all_conversations.filter(status__in=['human', 'live']).count()

        if total_conversations_count > 0:
            ai_resolution_pct = round((ai_resolved_count / total_conversations_count) * 100)
        else:
            ai_resolution_pct = 100

        # 3. Knowledge Base Stats
        sources_count = Source.objects.filter(company=company, status='indexed').count()
        chunks_count = DocumentChunk.objects.filter(company=company).count()

        # 4. Message Volume (This Month)
        messages_this_month = Message.objects.filter(
            conversation__company=company,
            created_at__gte=thirty_days_ago
        ).count()

        # 5. Last 7 Days Conversation Activity Chart
        weekly_activity = []
        days_map = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i in range(6, -1, -1):
            day_date = (now - timedelta(days=i)).date()
            day_name = days_map[day_date.weekday()]
            count = all_conversations.filter(created_at__date=day_date).count()
            weekly_activity.append({"day": day_name, "value": count, "date": str(day_date)})

        # 6. Recent 5 Conversations
        recent_qs = all_conversations.order_by('-updated_at')[:5]
        recent_conversations = []
        for conv in recent_qs:
            recent_conversations.append({
                "id": str(conv.id),
                "visitor": conv.visitor_identifier,
                "preview": conv.preview_text or "No message preview",
                "status": conv.status,
                "time": conv.updated_at.isoformat(),
            })

        return Response({
            "total_conversations": total_conversations_count,
            "ai_resolution_rate": ai_resolution_pct,
            "pages_indexed": sources_count,
            "chunks_indexed": chunks_count,
            "messages_this_month": messages_this_month,
            "human_handoffs": human_handoff_count,
            "avg_response_time": "1.2s",
            "weekly_activity": weekly_activity,
            "recent_conversations": recent_conversations,
        }, status=status.HTTP_200_OK)