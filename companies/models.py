import os
import uuid
from django.db import models
from django.utils import timezone

# Configurable limit for testing. Set ALLO_DEV_MSG_LIMIT=5 in .env to test quickly.
DEV_LIMIT = int(os.getenv('ALLO_DEV_MSG_LIMIT', '0'))

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

    # INDEPENDENT USAGE COUNTER (decoupled from Stripe)
    monthly_message_count = models.IntegerField(default=0)

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
        # If dev limit is set in .env, override plan limits for testing
        if DEV_LIMIT > 0:
            return DEV_LIMIT
        return PLAN_LIMITS.get(self.plan, 1000)

    def get_current_period_usage(self) -> int:
        return self.monthly_message_count

    def increment_usage(self):
        """Atomically increments the message counter by 1."""
        Company.objects.filter(pk=self.pk).update(
            monthly_message_count=models.F('monthly_message_count') + 1
        )
        self.refresh_from_db()

    def reset_usage(self):
        """Resets the counter when a new billing period begins."""
        self.monthly_message_count = 0
        self.save(update_fields=['monthly_message_count'])

    def has_active_credits(self) -> bool:
        if self.plan == 'enterprise':
            return True
        if self.subscription_status != 'active':
            return False
        return self.monthly_message_count < self.max_monthly_messages