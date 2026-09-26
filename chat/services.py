import os
import re
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from openai import OpenAI
from pgvector.django import CosineDistance
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from companies.models import Company
from knowledge.models import DocumentChunk
from .models import Conversation, Message
from .serializers import MessageSerializer

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


class SubscriptionExpiredException(Exception):
    """Exception raised when a company's subscription has expired or is delinquent."""
    pass


class UsageLimitExceededException(Exception):
    """Exception raised when a company has exhausted its monthly message quota."""
    pass


# ---------------------------------------------------------------------------
# WebSocket Broadcast Helpers
# ---------------------------------------------------------------------------

def broadcast_ws_message(conversation_id: str, message_data: dict):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"conversation_{conversation_id}",
        {
            "type": "chat_message",
            "message": message_data
        }
    )


def broadcast_dash_alert(company_id: str, conversation):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"dash_company_{str(company_id)}",
        {
            "type": "handoff_alert",
            "conversation_id": str(conversation.id),
            "visitor_identifier": conversation.visitor_identifier,
            "preview_text": conversation.preview_text,
            "status": conversation.status,
            "updated_at": conversation.updated_at.isoformat(),
        }
    )


# ---------------------------------------------------------------------------
# Escalation & Email Helpers
# ---------------------------------------------------------------------------

def _forced_topics(company: Company) -> list[str]:
    raw = (company.escalation_topics or '').strip()
    if not raw:
        return []
    return [t.strip().lower() for t in raw.split(',') if t.strip()]


def should_force_escalate(company: Company, user_message: str) -> bool:
    msg = user_message.lower()
    for topic in _forced_topics(company):
        if topic and topic in msg:
            return True
    return False


def send_handoff_email(company: Company, conversation: Conversation, user_message: str):
    """Send at most ONE email per conversation when AI escalates."""
    if conversation.handoff_email_sent or not company.notify_on_handoff:
        return

    to_email = company.notification_email or company.support_email
    if not to_email:
        return

    dashboard_url = f"{settings.FRONTEND_URL}/dashboard/inbox"
    subject = f"[Allo] Human help needed — {company.name}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background:#000;font-family:system-ui,sans-serif;color:#fff;">
      <table width="100%" style="background:#000;padding:40px 20px;">
        <tr><td align="center">
          <table width="100%" style="max-width:520px;background:#0a0a0a;border:1px solid #27272a;border-radius:8px;">
            <tr>
              <td style="padding:24px;border-bottom:1px solid #27272a;text-align:center;">
                <h1 style="margin:0;font-size:24px;letter-spacing:-0.04em;">Allo</h1>
              </td>
            </tr>
            <tr>
              <td style="padding:32px 24px;">
                <h2 style="margin:0 0 12px;font-size:18px;font-weight:500;">A visitor needs a human</h2>
                <p style="margin:0 0 8px;color:#a1a1aa;font-size:14px;">
                  <strong style="color:#fff;">{company.name}</strong> · {conversation.visitor_identifier}
                </p>
                <p style="margin:0 0 20px;color:#a1a1aa;font-size:13px;">
                  Language: {conversation.visitor_lang}
                </p>
                <div style="background:#000;border:1px solid #27272a;border-radius:6px;padding:16px;margin-bottom:24px;">
                  <p style="margin:0;font-size:15px;line-height:1.5;color:#e4e4e7;">{user_message}</p>
                </div>
                <a href="{dashboard_url}"
                   style="display:inline-block;background:#fff;color:#000;text-decoration:none;
                          padding:12px 20px;border-radius:4px;font-size:13px;font-weight:600;
                          letter-spacing:0.04em;text-transform:uppercase;">
                  Open inbox
                </a>
              </td>
            </tr>
          </table>
          <p style="margin-top:24px;font-size:12px;color:#52525b;">© {timezone.now().year} Allo</p>
        </td></tr>
      </table>
    </body>
    </html>
    """
    try:
        send_mail(
            subject=subject,
            message=f"Visitor needs human help: {user_message}\nOpen inbox: {dashboard_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to_email],
            fail_silently=False,
            html_message=html,
        )
        conversation.handoff_email_sent = True
        conversation.save(update_fields=['handoff_email_sent'])
    except Exception as e:
        print(f"[Handoff Email Error] Failed: {e}")


# ---------------------------------------------------------------------------
# REAL PGVECTOR RETRIEVAL & OPENAI RAG
# ---------------------------------------------------------------------------

def retrieve_context_vector_search(company: Company, question: str, limit: int = 5) -> list[str]:
    try:
        emb_res = client.embeddings.create(
            model="text-embedding-3-small",
            input=[question]
        )
        q_embedding = emb_res.data[0].embedding

        matching_chunks = (
            DocumentChunk.objects
            .filter(company=company)
            .annotate(distance=CosineDistance('embedding', q_embedding))
            .order_by('distance')[:limit]
        )

        results = [chunk.content for chunk in matching_chunks if chunk.distance < 0.88]
        return results
    except Exception as e:
        print(f"[Vector Search Error] {e}")
        return []


def generate_ai_reply(company: Company, question: str, context: list[str]) -> tuple[str, bool]:
    if should_force_escalate(company, question):
        return (
            "I'm connecting you with a team member who can help with this. They'll be with you shortly.",
            True,
        )

    if not context:
        q_lower = question.lower()
        if any(w in q_lower for w in ('hello', 'hi', 'hey', 'bonjour', 'salut')):
            welcome = company.widget_welcome_msg or "Hi! How can we help you today?"
            return (welcome, False)

        return (
            "I don't have enough information in my knowledge base to answer that confidently. Connecting you with a human teammate.",
            True,
        )

    context_str = "\n\n---\n\n".join(context)

    system_prompt = f"""You are the official AI assistant for {company.name}.
Answer customer questions accurately using ONLY the provided context below.

CRITICAL RULES:
1. Do NOT guess or hallucinate. If the context does not contain the answer, state that you don't have enough information and will connect them with a human teammate.
2. IMAGE INSTRUCTION: If the user asks to see a logo, picture, product photo, or visual, and an image markdown link (e.g. `![Title](http://...)`) is provided in the context, render the Markdown image directly in your response!
3. Keep your answer professional, concise, and helpful.
4. Answer in the same language as the customer's question.

CONTEXT:
{context_str}"""

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.2,
            max_tokens=400,
        )
        answer = completion.choices[0].message.content.strip()

        should_escalate = (
            "connect you with a human" in answer.lower() or
            "don't have enough information" in answer.lower() or
            "do not have enough information" in answer.lower()
        )
        return answer, should_escalate

    except Exception as e:
        print(f"[OpenAI Chat Error] {e}")
        return ("I'm having trouble retrieving an answer right now. Let me connect you with a human.", True)


def process_visitor_message(
    company: Company,
    visitor_id: str,
    message_text: str,
    visitor_lang: str = 'en',
    conversation_id=None,
) -> tuple[Conversation, Message, Message]:

    # 1. If their subscription status is not 'active', lock them out entirely
    if company.subscription_status != 'active':
        raise SubscriptionExpiredException(f"Company {company.id} subscription is inactive.")

    # 2. If they have run out of monthly credits, raise quota limit exception
    if not company.has_active_credits():
        raise UsageLimitExceededException(f"Company {company.id} has reached its plan message limits.")

    conversation = None
    if conversation_id:
        conversation = Conversation.objects.filter(id=conversation_id, company=company).first()

    if not conversation:
        conversation = Conversation.objects.create(
            company=company,
            visitor_identifier=visitor_id,
            visitor_lang=visitor_lang or 'en',
            status='ai',
            preview_text=message_text[:240],
        )
    else:
        conversation.preview_text = message_text[:240]
        if visitor_lang:
            conversation.visitor_lang = visitor_lang

    user_msg = Message.objects.create(
        conversation=conversation,
        sender_role='user',
        content=message_text,
    )

    # Broadcast the user message over the WebSocket group instantly
    broadcast_ws_message(str(conversation.id), MessageSerializer(user_msg).data)

    context = retrieve_context_vector_search(company, message_text)
    answer, escalate = generate_ai_reply(company, message_text, context)

    ai_msg = Message.objects.create(
        conversation=conversation,
        sender_role='ai',
        content=answer,
    )

    # INCREMENT USAGE COUNTER
    company.increment_usage()

    # Broadcast the AI reply over the WebSocket group instantly
    broadcast_ws_message(str(conversation.id), MessageSerializer(ai_msg).data)

    if escalate:
        conversation.status = 'human'
        send_handoff_email(company, conversation, message_text)
        # Broadcast escalation alert to agent's dashboard
        broadcast_dash_alert(company.id, conversation)

    conversation.updated_at = timezone.now()
    conversation.save()

    return conversation, user_msg, ai_msg