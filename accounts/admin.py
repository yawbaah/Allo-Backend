from django.contrib import admin
from django.utils.html import format_html
from .models import User, EmailCode

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'company_link', 'email_verified_badge', 'is_staff', 'created_at')
    list_filter = ('email_verified', 'is_staff', 'created_at')
    search_fields = ('email', 'company__name')
    ordering = ('-created_at',)
    
    def company_link(self, obj):
        if not obj.company:
            return "No Company"
        return format_html(
            '<strong style="color: #10b981;">{}</strong>', obj.company.name
        )
    company_link.short_description = 'Company Name'

    def email_verified_badge(self, obj):
        color = '#10b981' if obj.email_verified else '#f59e0b'
        status_text = 'VERIFIED' if obj.email_verified else 'PENDING'
        return format_html(
            '<span style="color: {}; font-weight: bold; font-size: 11px;">● {}</span>',
            color, status_text
        )
    email_verified_badge.short_description = 'Verification Status'


@admin.register(EmailCode)
class EmailCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'purpose', 'used', 'expires_at', 'created_at')
    list_filter = ('purpose', 'used', 'created_at')
    search_fields = ('user__email', 'code')