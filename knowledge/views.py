import re
import uuid
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from django.core.files.storage import default_storage

from .models import Source
from .serializers import SourceSerializer
from .tasks import process_and_index_source_task
from billing.permissions import HasPaidSubscription


def _safe_filename(original: str) -> str:
    original = (original or "file").strip().replace(" ", "_")
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', original)
    if not safe or safe in (".", ".."):
        safe = "file"
    prefix = uuid.uuid4().hex[:8]
    return f"{prefix}_{safe}"[:200]


def _public_url_for_key(save_path: str) -> str:
    use_r2 = getattr(settings, 'USE_R2', False)
    if use_r2:
        try:
            url = default_storage.url(save_path)
            if url.startswith("//"):
                return "https:" + url
            if url.startswith("http://") or url.startswith("https://"):
                return url.replace(" ", "%20")
        except Exception:
            pass
        base = getattr(settings, 'R2_PUBLIC_BASE_URL', '').rstrip('/')
        if base:
            return f"{base}/{save_path.replace(' ', '%20')}"
        return save_path
    backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')
    return f"{backend_url}/media/{save_path}"


def _key_from_stored_url(value: str) -> str:
    if not value:
        return ""
    if value.startswith("manual://"):
        return ""
    base = getattr(settings, 'R2_PUBLIC_BASE_URL', '').rstrip('/')
    if base and value.startswith(base):
        return value[len(base):].lstrip("/")
    if "/media/" in value:
        return value.split("/media/")[-1].lstrip("/")
    if value.startswith("http://") or value.startswith("https://"):
        return ""
    return value.lstrip("/")


class SourceListView(APIView):
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
            process_and_index_source_task.delay(str(source.id))
            return Response(SourceSerializer(source).data, status=status.HTTP_202_ACCEPTED)

        # ---------- FILE / IMAGE ----------
        if 'file' in request.FILES:
            f = request.FILES['file']
            original_name = f.name or "upload"
            source_type = request.data.get('type') or 'pdf'
            ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''

            if source_type not in ('pdf', 'docx', 'image'):
                if ext == 'pdf':
                    source_type = 'pdf'
                elif ext in ('doc', 'docx'):
                    source_type = 'docx'
                else:
                    source_type = 'image'

            safe_name = _safe_filename(original_name)
            save_path = default_storage.save(f'sources/{company.id}/{safe_name}', f)

            if source_type == 'image':
                thumbnail_url = _public_url_for_key(save_path)
            else:
                thumbnail_url = ''

            source = Source.objects.create(
                company=company,
                type=source_type,
                title=original_name[:255],
                url_or_path=save_path,
                image_description=request.data.get('description', ''),
                thumbnail_url=thumbnail_url,
                status='processing',
            )
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
        process_and_index_source_task.delay(str(source.id))
        return Response(SourceSerializer(source).data, status=status.HTTP_202_ACCEPTED)


class SourceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPaidSubscription]

    def delete(self, request, pk):
        company = getattr(request.user, 'company', None)
        try:
            source = Source.objects.get(pk=pk, company=company)
        except Source.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Best-effort file cleanup from local disk or R2
        for val in [source.url_or_path, source.thumbnail_url]:
            key = _key_from_stored_url(val or "")
            if key:
                try:
                    if default_storage.exists(key):
                        default_storage.delete(key)
                except Exception:
                    pass

        source.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)