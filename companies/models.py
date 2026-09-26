import uuid
from django.db import models
from django.utils import timezone

PLAN_LIMITS = {
    'starter': 1000,
    'growth': 5000,
    'business': 20000,
    'enterprise': 100000,
}

class Company(models.Model):
    PLAN_CHOICES = [
        ('starter', 'Starter'),
        ('growth', 'Growth'),
        ('business', 'Business'),
        ('enterprise', 'Enterprise'),
    ]
    LAUNCHER_CHOICES = [
        ('icon', 'Chat Icon'),
        ('logo-circle', 'Circle Logo'),
        ('logo-square', 'Square Logo'),
    ]
    POSITION_CHOICES = [
        ('left', 'Bottom Left'),
        ('right', 'Bottom Right'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=100, blank=True)
    size = models.CharField(max_length=50, blank=True)
    website_url = models.URLField(blank=True)
    support_email = models.EmailField(blank=True)

    notification_email = models.EmailField(blank=True)
    notify_on_handoff = models.BooleanField(default=True)

    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='starter')
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    subscription_status = models.CharField(max_length=50, default='unpaid')
    current_period_start = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)

    widget_name = models.CharField(max_length=100, default='Support')
    widget_color = models.CharField(max_length=20, default='#ffffff')
    widget_position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='right')
    widget_launcher = models.CharField(max_length=20, choices=LAUNCHER_CHOICES, default='icon')
    widget_logo_url = models.TextField(blank=True)
    widget_welcome_msg = models.TextField(default='Hi! How can we help you today?')

    escalation_topics = models.TextField(blank=True)
    business_hours = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'companies'

    def __str__(self):
        return self.name

    @property
    def max_monthly_messages(self) -> int:
        return PLAN_LIMITS.get(self.plan, 1000)

    def get_current_period_usage(self) -> int:
        from chat.models import Message
        start_date = self.current_period_start
        if not start_date:
            start_date = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return Message.objects.filter(
            conversation__company=self,
            sender_role='ai',
            created_at__gte=start_date
        ).count()

    def has_active_credits(self) -> bool:
        if self.plan == 'enterprise':
            return True
        # ONLY 'active' grants access. No trialing, no unpaid, no canceled.
        if self.subscription_status != 'active':
            return False
        return self.get_current_period_usage() < self.max_monthly_messages