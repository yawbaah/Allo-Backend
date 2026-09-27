import io
import os
import re
from urllib.parse import quote
import httpx
from bs4 import BeautifulSoup
from django.conf import settings
from openai import OpenAI
from pypdf import PdfReader
from docx import Document as DocxDocument

from .models import Source, DocumentChunk

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _is_http_url(s: str) -> bool:
    return bool(s) and (s.startswith('http://') or s.startswith('https://'))


def scrape_url(url: str) -> str:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as http_client:
        response = http_client.get(url)
        response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg']):
        element.extract()

    text = soup.get_text(separator=' ')
    return clean_text(text)


def extract_pdf_bytes(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    text = ""
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    return clean_text(text)


def extract_docx_bytes(data: bytes) -> str:
    doc = DocxDocument(io.BytesIO(data))
    full_text = [para.text for para in doc.paragraphs if para.text]
    return clean_text(" ".join(full_text))


def _read_file_source_to_bytes(url_or_path: str) -> bytes:
    use_r2 = getattr(settings, 'USE_R2', False)

    if _is_http_url(url_or_path):
        with httpx.Client(timeout=30.0, follow_redirects=True) as c:
            r = c.get(url_or_path)
            r.raise_for_status()
            return r.content

    normalized = url_or_path.lstrip("/")
    if normalized.startswith("media/"):
        normalized = normalized[len("media/"):]

    if use_r2:
        from .r2_storage import download_bytes
        return download_bytes(normalized)

    full_path = os.path.join(settings.MEDIA_ROOT, normalized)
    with open(full_path, 'rb') as f:
        return f.read()


def _absolute_media_url(value: str) -> str:
    if not value:
        return value
    if _is_http_url(value):
        return value.replace(" ", "%20")
    clean = value.lstrip("/")
    if clean.startswith("media/"):
        clean = clean[len("media/"):]
    safe = quote(clean, safe="/")
    use_r2 = getattr(settings, 'USE_R2', False)
    if use_r2 and getattr(settings, 'R2_PUBLIC_BASE_URL', ''):
        return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{safe}"
    backend_url = getattr(settings, 'BACKEND_URL', 'http://localhost:8000').rstrip('/')
    return f"{backend_url}/media/{safe}"


def chunk_text(text: str, max_chars: int = 1000, overlap: int = 150) -> list[str]:
    if not text:
        return []

    words = text.split(' ')
    chunks = []
    current_chunk = []
    current_len = 0

    for word in words:
        current_chunk.append(word)
        current_len += len(word) + 1

        if current_len >= max_chars:
            chunk_str = " ".join(current_chunk)
            chunks.append(chunk_str)
            overlap_words = int(overlap / 6)
            current_chunk = current_chunk[-overlap_words:] if len(current_chunk) > overlap_words else []
            current_len = sum(len(w) + 1 for w in current_chunk)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def get_openai_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [item.embedding for item in response.data]


def process_and_index_source(source_id: str):
    try:
        source = Source.objects.get(id=source_id)
        source.status = 'processing'
        source.save(update_fields=['status'])

        raw_text = ""

        if source.type == 'page':
            raw_text = scrape_url(source.url_or_path)

        elif source.type in ('pdf', 'docx'):
            data = _read_file_source_to_bytes(source.url_or_path)
            if source.type == 'pdf':
                raw_text = extract_pdf_bytes(data)
            else:
                raw_text = extract_docx_bytes(data)

        elif source.type == 'text':
            raw_text = source.image_description or source.title

        elif source.type == 'image':
            img_url = _absolute_media_url(source.thumbnail_url or source.url_or_path)
            desc = source.image_description or source.title
            raw_text = (
                f"Company Image, Logo, Visual, Photo, Picture: {source.title}. "
                f"Description: {desc}. "
                f"Image Embed: ![{source.title}]({img_url})"
            )

        if not raw_text.strip():
            print(f"[Ingestion Failed] Empty text extracted from {source.title}")
            source.status = 'failed'
            source.save(update_fields=['status'])
            return

        chunks = chunk_text(raw_text)
        if not chunks:
            source.status = 'failed'
            source.save(update_fields=['status'])
            return

        DocumentChunk.objects.filter(source=source).delete()
        embeddings = get_openai_embeddings(chunks)

        chunk_objects = []
        for text, embedding in zip(chunks, embeddings):
            chunk_objects.append(
                DocumentChunk(
                    source=source,
                    company=source.company,
                    content=text,
                    embedding=embedding
                )
            )

        DocumentChunk.objects.bulk_create(chunk_objects)

        source.status = 'indexed'
        source.chunk_count = len(chunk_objects)
        source.save(update_fields=['status', 'chunk_count'])
        print(f"[Ingestion Success] Indexed '{source.title}' with {len(chunk_objects)} chunks.")

    except Exception as e:
        print(f"[Ingestion Error] Failed to process source {source_id}: {e}")
        try:
            source = Source.objects.get(id=source_id)
            source.status = 'failed'
            source.save(update_fields=['status'])
        except Exception:
            pass