from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from django.core.files.storage import default_storage

from .models import Source
from .serializers import SourceSerializer
from .tasks import process_and_index_source_task
from billing.permissions import HasPaidSubscription  # <-- Import our paywall


class SourceListView(APIView):
    # Enforce standard authentication AND strict paid subscription checks
    permission_classes = [permissions.IsAuthenticated, HasPaidSubscription]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'error': 'No company associated with user.'}, status=400)

        sources = Source.objects.filter(company=company).order_by('-created_at')
        return Response(SourceSerializer(sources, many=True).data)

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({'error': 'No company associated with user.'}, status=400)

        # ---------- MANUAL TEXT ----------
        if request.data.get('type') == 'text' or (
            not request.FILES and request.data.get('content')
        ):
            title = (request.data.get('title') or 'Manual note').strip()[:255]
            content = (request.data.get('content') or '').strip()
            if not content:
                return Response({'error': 'content is required for text sources.'}, status=400)

            source = Source.objects.create(
                company=company,
                type='text',
                title=title,
                url_or_path='manual://text',
                image_description=content,
                status='processing',
            )
            # Dispatch to Celery background task
            process_and_index_source_task.delay(str(source.id))
            return Response(SourceSerializer(source).data, status=status.HTTP_202_ACCEPTED)

        # ---------- FILE / IMAGE ----------
        if 'file' in request.FILES:
            f = request.FILES['file']
            source_type = request.data.get('type') or 'pdf'
            name = f.name
            ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''

            if source_type not in ('pdf', 'docx', 'image'):
                if ext == 'pdf':
                    source_type = 'pdf'
                elif ext in ('doc', 'docx'):
                    source_type = 'docx'
                else:
                    source_type = 'image'

            save_path = default_storage.save(f'sources/{company.id}/{name}', f)
            backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')
            thumbnail_url = (
                f'{backend_url}/media/{save_path}' if source_type == 'image' else ''
            )

            source = Source.objects.create(
                company=company,
                type=source_type,
                title=name,
                url_or_path=save_path,
                image_description=request.data.get('description', ''),
                thumbnail_url=thumbnail_url,
                status='processing',
            )
            # Dispatch to Celery background task
            process_and_index_source_task.delay(str(source.id))
            return Response(SourceSerializer(source).data, status=status.HTTP_202_ACCEPTED)

        # ---------- URL CRAWL ----------
        url = (request.data.get('url') or request.data.get('url_or_path') or '').strip()
        if not url:
            return Response({'error': 'Provide url, file, or text content.'}, status=400)

        title = url.replace('https://', '').replace('http://', '').split('/')[0] or url
        source = Source.objects.create(
            company=company,
            type='page',
            title=title[:255],
            url_or_path=url,
            status='crawling',
        )
        # Dispatch to Celery background task
        process_and_index_source_task.delay(str(source.id))
        return Response(SourceSerializer(source).data, status=status.HTTP_202_ACCEPTED)


class SourceDetailView(APIView):
    # Enforce standard authentication AND strict paid subscription checks
    permission_classes = [permissions.IsAuthenticated, HasPaidSubscription]

    def delete(self, request, pk):
        company = getattr(request.user, 'company', None)
        try:
            source = Source.objects.get(pk=pk, company=company)
        except Source.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        source.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)