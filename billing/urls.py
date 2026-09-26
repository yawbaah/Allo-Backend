from django.urls import path, re_path
from .views import (
    BillingDashboardView,
    CreateCheckoutSessionView,
    CreateBillingPortalView,
    StripeWebhookView,
)

urlpatterns = [
    path('dashboard/', BillingDashboardView.as_view(), name='billing-dashboard'),
    path('checkout/', CreateCheckoutSessionView.as_view(), name='billing-checkout'),
    path('portal/', CreateBillingPortalView.as_view(), name='billing-portal'),
    
    # Matches BOTH /api/billing/webhook AND /api/billing/webhook/
    re_path(r'^webhook/?$', StripeWebhookView.as_view(), name='stripe-webhook'),
]