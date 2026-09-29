from django.contrib import admin
from django.utils.safestring import mark_safe
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 
        'plan_badge', 
        'subscription_status_badge', 
        'usage_progress', 
        'user_count', 
        'stripe_customer_link',
        'created_at'
    )
    list_filter = ('plan', 'subscription_status', 'created_at')
    search_fields = ('name', 'stripe_customer_id', 'stripe_subscription_id', 'support_email')
    ordering = ('-created_at',)
    
    readonly_fields = (
        'stripe_customer_id', 
        'stripe_subscription_id', 
        'subscription_status',
        'current_period_start', 
        'current_period_end',
        'created_at'
    )

    def plan_badge(self, obj):
        color_map = {
            'starter': '#3b82f6',
            'growth': '#10b981',
            'business': '#8b5cf6',
            'enterprise': '#f59e0b'
        }
        color = color_map.get(obj.plan, '#6b7280')
        return mark_safe(
            f'<span style="background: {color}; color: #fff; padding: 3px 10px; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 10px;">{obj.plan}</span>'
        )
    plan_badge.short_description = 'Subscription Plan'

    def subscription_status_badge(self, obj):
        is_active = obj.subscription_status == 'active'
        background = '#10b981' if is_active else '#ef4444'
        text = 'ACTIVE' if is_active else obj.subscription_status.upper()
        return mark_safe(
            f'<span style="background: {background}; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 10px;">{text}</span>'
        )
    subscription_status_badge.short_description = 'Stripe Status'

    def usage_progress(self, obj):
        usage = obj.get_current_period_usage()
        limit = obj.max_monthly_messages
        percentage = min(round((usage / limit) * 100), 100) if limit > 0 else 0
        bar_color = '#ef4444' if percentage >= 90 else '#3b82f6'
        
        return mark_safe(
            f'<div style="width: 140px;">'
            f'<div style="font-size: 11px; margin-bottom: 3px; font-weight: bold;">{usage:,} / {limit:,} msgs</div>'
            f'<div style="width: 100%; background: #e5e7eb; height: 6px; border-radius: 3px; overflow: hidden;">'
            f'<div style="width: {percentage}%; background: {bar_color}; height: 100%;"></div>'
            f'</div>'
            f'</div>'
        )
    usage_progress.short_description = 'Real-time Quota'

    def user_count(self, obj):
        count = obj.users.count()
        return mark_safe(f'<strong style="font-size: 12px;">{count}</strong>')
    user_count.short_description = 'Users'

    def stripe_customer_link(self, obj):
        if not obj.stripe_customer_id:
            return mark_safe('<span style="color: #9ca3af;">No Stripe ID</span>')
        url = f"https://dashboard.stripe.com/customers/{obj.stripe_customer_id}"
        return mark_safe(
            f'<a href="{url}" target="_blank" style="color: #3b82f6; font-weight: 500; text-decoration: underline;">{obj.stripe_customer_id} ↗</a>'
        )
    stripe_customer_link.short_description = 'Stripe Link'