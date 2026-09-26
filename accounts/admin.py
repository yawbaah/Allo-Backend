from django.contrib import admin
from .models import User, EmailCode


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'company', 'is_active', 'is_staff', 'email_verified', 'created_at')
    search_fields = ('email',)
    ordering = ('-created_at',)


@admin.register(EmailCode)
class EmailCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'purpose', 'used', 'expires_at', 'created_at')
    search_fields = ('user__email', 'code')