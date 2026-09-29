import os
from datetime import datetime, timezone as dt_timezone
import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from companies.models import Company

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe_webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')


def get_stripe_prices():
    return {
        'starter': os.getenv('STRIPE_PRICE_STARTER'),
        'growth': os.getenv('STRIPE_PRICE_GROWTH'),
        'business': os.getenv('STRIPE_PRICE_BUSINESS'),
    }


def send_welcome_and_activation_email(company, email_address, plan_name):
    subject = f"Your Allo {plan_name.capitalize()} Plan is Now Active! 💳"
    dashboard_url = f"{settings.FRONTEND_URL}/dashboard"
    knowledge_url = f"{settings.FRONTEND_URL}/dashboard/knowledge"

    limits_map = {"starter": "1,000", "growth": "5,000", "business": "20,000"}
    limit_value = limits_map.get(plan_name.lower(), "1,000")

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background-color:#000000;font-family:system-ui,-apple-system,sans-serif;color:#ffffff;">
      <table width="100%" style="background-color:#000000;padding:40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" style="max-width:540px;background-color:#09090b;border:1px solid #27272a;border-radius:12px;overflow:hidden;">
              <tr>
                <td style="padding:32px 24px;border-bottom:1px solid #27272a;text-align:center;">
                  <h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.05em;color:#ffffff;font-family:Georgia,serif;">Allo</h1>
                </td>
              </tr>
              <tr>
                <td style="padding:40px 32px;">
                  <h2 style="margin:0 0 16px;font-size:22px;font-weight:500;letter-spacing:-0.02em;">Subscription Activated! 🎉</h2>
                  <p style="margin:0 0 24px;color:#a1a1aa;font-size:15px;line-height:1.6;">
                    Hi there, <br><br>
                    Thank you for partnering with Allo. We have successfully processed your payment. Your <strong>{plan_name.capitalize()} Plan</strong> subscription has been fully activated for <strong>{company.name}</strong>.
                  </p>
                  
                  <div style="background-color:#000000;border:1px solid #27272a;border-radius:8px;padding:20px;margin-bottom:32px;">
                    <table width="100%">
                      <tr>
                        <td style="padding-bottom:10px;font-size:14px;color:#a1a1aa;">Active Plan:</td>
                        <td style="padding-bottom:10px;font-size:14px;color:#ffffff;text-align:right;font-weight:600;">{plan_name.capitalize()}</td>
                      </tr>
                      <tr>
                        <td style="padding-bottom:10px;font-size:14px;color:#a1a1aa;">Message Quota:</td>
                        <td style="padding-bottom:10px;font-size:14px;color:#ffffff;text-align:right;font-weight:600;">{limit_value} AI Messages / month</td>
                      </tr>
                      <tr>
                        <td style="font-size:14px;color:#a1a1aa;">Platform Status:</td>
                        <td style="font-size:14px;color:#22c55e;text-align:right;font-weight:600;">UNLOCKED</td>
                      </tr>
                    </table>
                  </div>

                  <p style="margin:0 0 32px;color:#a1a1aa;font-size:15px;line-height:1.6;">
                    Your workspace limits have been updated instantly. You can now start crawling websites, parsing documents, training your bot, and deploying the script snippet.
                  </p>

                  <div style="text-align:center;margin-bottom:16px;">
                    <a href="{knowledge_url}" 
                       style="display:inline-block;background-color:#ffffff;color:#000000;text-decoration:none;
                              padding:14px 28px;border-radius:6px;font-size:14px;font-weight:600;
                              text-transform:uppercase;letter-spacing:0.05em;margin-right:10px;">
                      Train Knowledge Base
                    </a>
                  </div>
                </td>
              </tr>
              <tr>
                <td style="padding:24px;border-top:1px solid #27272a;background-color:#020202;text-align:center;">
                  <p style="margin:0;font-size:12px;color:#52525b;">
                    If you have any questions or need custom configurations, reply directly to this email.
                  </p>
                </td>
              </tr>
            </table>
            <p style="margin-top:24px;font-size:12px;color:#52525b;">© {datetime.now().year} Allo. All rights reserved.</p>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    try:
        send_mail(
            subject=subject,
            message=f"Thank you for choosing Allo! Your {plan_name.capitalize()} Plan is now active. Access your workspace at: {dashboard_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_address],
            fail_silently=False,
            html_message=html_content,
        )
        print(f"📧 [MAIL SYSTEM] Welcome and activation email sent to: {email_address}")
    except Exception as e:
        print(f"⚠️ [MAIL SYSTEM WARNING] Could not send email to {email_address}: {e}")


def send_dunning_warning_email(company, email_address):
    subject = "Action Required: Your Allo subscription is past due ⚠️"
    billing_url = f"{settings.FRONTEND_URL}/dashboard/billing"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0;padding:0;background-color:#000000;font-family:system-ui,-apple-system,sans-serif;color:#ffffff;">
      <table width="100%" style="background-color:#000000;padding:40px 20px;">
        <tr>
          <td align="center">
            <table width="100%" style="max-width:540px;background-color:#09090b;border:1px solid #ef4444;border-radius:12px;overflow:hidden;">
              <tr>
                <td style="padding:32px 24px;border-bottom:1px solid #27272a;text-align:center;">
                  <h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.05em;color:#ffffff;font-family:Georgia,serif;">Allo</h1>
                </td>
              </tr>
              <tr>
                <td style="padding:40px 32px;">
                  <h2 style="margin:0 0 16px;font-size:20px;font-weight:500;letter-spacing:-0.02em;color:#fca5a5;">Subscription Payment Failed / Past Due ⚠️</h2>
                  <p style="margin:0 0 24px;color:#a1a1aa;font-size:15px;line-height:1.6;">
                    Hello, <br><br>
                    Our system was unable to process your recurring subscription payment for <strong>{company.name}</strong>.
                  </p>
                  
                  <div style="background-color:rgba(239, 68, 68, 0.08);border:1px solid #ef4444;border-radius:8px;padding:20px;margin-bottom:32px;">
                    <p style="margin:0;color:#fca5a5;font-size:14px;line-height:1.5;">
                      <strong>CRITICAL WIDGET STATUS: LOCKED</strong><br>
                      Due to an unpaid invoice, your live website chatbot widget has ceased serving automatic answers. 
                    </p>
                  </div>

                  <p style="margin:0 0 32px;color:#a1a1aa;font-size:15px;line-height:1.6;">
                    Please update your payment card information or settle the outstanding invoice immediately to restore services.
                  </p>

                  <div style="text-align:center;">
                    <a href="{billing_url}" 
                       style="display:inline-block;background-color:#ef4444;color:#ffffff;text-decoration:none;
                              padding:14px 28px;border-radius:6px;font-size:14px;font-weight:600;
                              text-transform:uppercase;letter-spacing:0.05em;">
                      Update Payment Details
                    </a>
                  </div>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """
    try:
        send_mail(
            subject=subject,
            message=f"Action Required: Your Allo payment has failed. Update billing details at: {billing_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_address],
            fail_silently=False,
            html_message=html_content,
        )
        print(f"📧 [MAIL SYSTEM] Dunning warning email dispatched to: {email_address}")
    except Exception as e:
        print(f"⚠️ [MAIL SYSTEM ERROR] Could not dispatch dunning email to {email_address}: {e}")


class BillingDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            # Safe fallback for users without a company (returns 200 rather than 400)
            return Response({
                "plan": "starter",
                "subscription_status": "unpaid",
                "message_usage": 0,
                "message_limit": 1000,
                "usage_percentage": 0,
                "current_period_end": None,
                "has_active_credits": False,
            }, status=status.HTTP_200_OK)

        usage = company.get_current_period_usage()
        max_limit = company.max_monthly_messages

        return Response({
            "plan": company.plan,
            "subscription_status": company.subscription_status,
            "message_usage": usage,
            "message_limit": max_limit,
            "usage_percentage": round((usage / max_limit) * 100) if max_limit > 0 else 0,
            "current_period_end": company.current_period_end,
            "has_active_credits": company.has_active_credits(),
        }, status=status.HTTP_200_OK)


class CreateCheckoutSessionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return Response({"error": "No company associated with this user."}, status=status.HTTP_400_BAD_REQUEST)

        plan_choice = request.data.get('plan')
        stripe_prices = get_stripe_prices()

        if plan_choice not in stripe_prices:
            return Response({"error": f"Invalid plan selected: {plan_choice}."}, status=status.HTTP_400_BAD_REQUEST)

        price_id = stripe_prices.get(plan_choice)
        if not price_id:
            return Response(
                {"error": f"Price ID for '{plan_choice}' is not set in backend .env."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        try:
            if not company.stripe_customer_id:
                customer = stripe.Customer.create(
                    email=request.user.email,
                    name=company.name,
                    metadata={
                        "company_id": str(company.id),
                        "company_name": company.name,
                    }
                )
                company.stripe_customer_id = customer.id
                company.save(update_fields=['stripe_customer_id'])

            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            session = stripe.checkout.Session.create(
                customer=company.stripe_customer_id,
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                managed_payments={'enabled': False},
                success_url=f"{frontend_url}/dashboard/billing?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{frontend_url}/dashboard/billing",
                metadata={
                    "company_id": str(company.id),
                    "plan": plan_choice,
                }
            )
            return Response({"checkout_url": session.url}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"[Stripe Checkout Error] {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreateBillingPortalView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if not company or not company.stripe_customer_id:
            return Response(
                {"error": "No active billing history found. Please purchase a plan first to register your customer profile."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
            portal_session = stripe.BillingPortal.Session.create(
                customer=company.stripe_customer_id,
                return_url=f"{frontend_url}/dashboard/billing",
            )
            return Response({"portal_url": portal_session.url}, status=status.HTTP_200_OK)

        except stripe.error.StripeError as e:
            print(f"[Stripe Portal Error] {e}")
            return Response(
                {"error": "Billing portal is temporarily unavailable. If you haven't completed your initial subscription payment, please select a plan first."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"[General Portal Error] {e}")
            return Response({"error": "An unexpected server error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')

        if not stripe_webhook_secret:
            print("❌ [STRIPE WEBHOOK ERROR] Webhook secret missing in .env configuration.")
            return Response({"error": "Webhook secret not configured in .env."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, stripe_webhook_secret
            )
        except ValueError:
            print("❌ [STRIPE WEBHOOK ERROR] Invalid payload structure received.")
            return Response({"error": "Invalid payload format."}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            print("❌ [STRIPE WEBHOOK ERROR] Verification failed. Check your Webhook Signing Secret.")
            return Response({"error": "Invalid webhook signature."}, status=status.HTTP_400_BAD_REQUEST)

        event_dict = event.to_dict() if hasattr(event, 'to_dict') else dict(event)
        event_type = event_dict.get('type')
        data_object = event_dict.get('data', {}).get('object', {})

        print(f"\n🔔 [STRIPE EVENT RECEIVED] Processing: '{event_type}'")

        if event_type == "checkout.session.completed":
            metadata = data_object.get('metadata') or {}
            company_id = metadata.get('company_id')
            plan_name = metadata.get('plan') or 'starter'
            sub_id = data_object.get('subscription')
            cust_id = data_object.get('customer')

            customer_details = data_object.get('customer_details') or {}
            customer_email = customer_details.get('email')

            print(f"   [Checkout Metadata] Company ID: {company_id} | Plan: {plan_name}")
            print(f"   [Checkout Payload] Customer: {cust_id} | Subscription: {sub_id}")

            company = None
            if company_id:
                company = Company.objects.filter(id=company_id).first()

            if not company and cust_id:
                company = Company.objects.filter(stripe_customer_id=cust_id).first()

            if company:
                company.stripe_customer_id = cust_id
                company.stripe_subscription_id = sub_id
                company.plan = plan_name
                company.subscription_status = 'active'

                if sub_id:
                    try:
                        subscription = stripe.Subscription.retrieve(sub_id)
                        sub_dict = subscription.to_dict() if hasattr(subscription, 'to_dict') else dict(subscription)
                        company.subscription_status = sub_dict.get('status', 'active')

                        start_ts = sub_dict.get('current_period_start')
                        end_ts = sub_dict.get('current_period_end')

                        if start_ts:
                            company.current_period_start = datetime.fromtimestamp(start_ts, tz=dt_timezone.utc)
                        if end_ts:
                            company.current_period_end = datetime.fromtimestamp(end_ts, tz=dt_timezone.utc)
                    except Exception as e:
                        print(f"⚠️ [Stripe Sub Retrieve Warning] {e}")

                company.save()
                print(f"✅ [STRIPE WEBHOOK SUCCESS] Company '{company.name}' unlocked and set to 'active' on {company.plan} plan.")

                recipient_email = None
                associated_user = company.users.first()
                if associated_user:
                    recipient_email = associated_user.email
                elif customer_email:
                    recipient_email = customer_email
                else:
                    recipient_email = company.support_email

                if recipient_email:
                    send_welcome_and_activation_email(company, recipient_email, company.plan)
            else:
                print(f"❌ [STRIPE WEBHOOK ERROR] No matching company found for company_id: {company_id}")

        elif event_type in ["customer.subscription.updated", "customer.subscription.deleted"]:
            sub_id = data_object.get('id')
            sub_status = data_object.get('status')
            print(f"   [Subscription Event] ID: {sub_id} | Status: {sub_status}")

            company = Company.objects.filter(stripe_subscription_id=sub_id).first()
            if company:
                old_period_start = company.current_period_start
                company.subscription_status = sub_status

                period_start = data_object.get('current_period_start')
                period_end = data_object.get('current_period_end')

                if period_start:
                    new_period_start = datetime.fromtimestamp(period_start, tz=dt_timezone.utc)
                    if old_period_start and new_period_start > old_period_start:
                        company.reset_usage()
                        print(f"🔄 [BILLING CYCLE RESET] Usage counter reset for '{company.name}'.")
                    company.current_period_start = new_period_start

                if period_end:
                    company.current_period_end = datetime.fromtimestamp(period_end, tz=dt_timezone.utc)

                if event_type == "customer.subscription.deleted" or sub_status in ["canceled", "unpaid", "past_due"]:
                    company.subscription_status = 'unpaid'

                    recipient_email = None
                    associated_user = company.users.first()
                    if associated_user:
                        recipient_email = associated_user.email
                    else:
                        recipient_email = company.support_email

                    if recipient_email:
                        send_dunning_warning_email(company, recipient_email)

                    print(f"📉 [STRIPE WEBHOOK] Subscription is delinquent or deleted. Company '{company.name}' locked.")
                else:
                    items_data = data_object.get('items', {}).get('data', [])
                    if items_data:
                        price_id = items_data[0].get('price', {}).get('id')
                        stripe_prices = get_stripe_prices()
                        for plan_key, p_id in stripe_prices.items():
                            if p_id and p_id == price_id:
                                company.plan = plan_key
                                break
                    print(f"🔄 [STRIPE WEBHOOK] Company '{company.name}' subscription updated to '{company.subscription_status}'.")

                company.save()
            else:
                print(f"❌ [STRIPE WEBHOOK ERROR] Company with Subscription '{sub_id}' not found.")

        return Response({"status": "success"}, status=status.HTTP_200_OK)