from django.urls import path
from .views import CompanyMeView, CompanyAnalyticsView

urlpatterns = [
    path('me/', CompanyMeView.as_view(), name='company-me'),
    path('analytics/', CompanyAnalyticsView.as_view(), name='company-analytics'),
]