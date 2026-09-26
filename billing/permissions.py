from rest_framework import permissions

class HasPaidSubscription(permissions.BasePermission):
    message = "Payment required. Activate your subscription at /dashboard/billing to unlock this feature."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        company = getattr(user, 'company', None)
        if not company:
            return False

        # ONLY 'active' Stripe subscriptions grant access
        return company.subscription_status == 'active'