from django.contrib import admin
from django.utils.html import format_html
from .models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    # Core display columns
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
    
    # Custom read-only section for sensitive Stripe records
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
            'starter': '#3b82f6',    # Blue
            'growth': '#10b981',     # Green
            'business': '#8b5cf6',   # Purple
            'enterprise': '#f59e0b'  # Amber
        }
        color = color_map.get(obj.plan, '#6b7280')
        return format_html(
            '<span style="background: {}; color: #fff; padding: 3px 10px; border-radius: 4px; font-weight: bold; text-transform: uppercase; font-size: 10px;">{}</span>',
            color, obj.plan
        )
    plan_badge.short_description = 'Subscription Plan'

    def subscription_status_badge(self, obj):
        is_active = obj.subscription_status == 'active'
        background = '#10b981' if is_active else '#ef4444'
        text = 'ACTIVE' if is_active else obj.subscription_status.upper()
        return format_html(
            '<span style="background: {}; color: #fff; padding: 3px 8px; border-radius: 4px; font-weight: 600; font-size: 10px;">{}</span>',
            background, text
        )
    subscription_status_badge.short_description = 'Stripe Status'

    def usage_progress(self, obj):
        usage = obj.get_current_period_usage()
        limit = obj.max_monthly_messages
        percentage = min(round((usage / limit) * 100), 100) if limit > 0 else 0
        
        # Color changes to red as they approach the limit
        bar_color = '#ef4444' if percentage >= 90 else '#3b82f6'
        
        return format_html(
            '<div style="width: 140px;">'
            '<div style="font-size: 11px; margin-bottom: 3px; font-weight: bold;">{} / {} msgs</div>'
            '<div style="width: 100%; background: #e5e7eb; height: 6px; border-radius: 3px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; height: 100%;"></div>'
            '</div>'
            '</div>',
            f"{usage:,}", f"{limit:,}", percentage, bar_color
        )
    usage_progress.short_description = 'Real-time Quota'

    def user_count(self, obj):
        count = obj.users.count()
        return format_html('<strong style="font-size: 12px;">{}</strong>', count)
    user_count.short_description = 'Users'

    def stripe_customer_link(self, obj):
        if not obj.stripe_customer_id:
            return format_html('<span style="color: #9ca3af;">No Stripe ID</span>')
        url = f"https://dashboard.stripe.com/customers/{obj.stripe_customer_id}"
        return format_html(
            '<a href="{}" target="_blank" style="color: #3b82f6; font-weight: 500; text-decoration: underline;">{} ↗</a>',
            url, obj.stripe_customer_id
        )
    stripe_customer_link.short_description = 'Stripe Link'