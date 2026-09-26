from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan', 'support_email', 'widget_name', 'created_at')
    search_fields = ('name', 'support_email', 'website_url')
    list_filter = ('plan', 'widget_launcher')