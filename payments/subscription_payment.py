"""
Apply external / verified payments to subscription records.
"""

from payments.models import ExternalPaymentRecord
from subscriptions.models import CustomerPremiumSubscription, LandlordSubscription
from subscriptions.services import activate_customer_premium, activate_landlord_subscription


def apply_subscription_payment(transaction_id):
    """
    Verify a transaction and activate the matching subscription.
    Returns (success, message, payment_type).
    payment_type: 'landlord' | 'customer_premium' | None
    """
    try:
        record = ExternalPaymentRecord.objects.get(transaction_id=transaction_id)
    except ExternalPaymentRecord.DoesNotExist:
        return False, "Transaction not found. Payment may not have been recorded yet.", None

    if record.payment_status == ExternalPaymentRecord.Status.FAILED:
        return False, "Payment failed. Please try again or contact support.", None

    if record.payment_status == ExternalPaymentRecord.Status.PENDING:
        return False, "Payment is still pending. Please wait for confirmation.", None

    if record.processed:
        payment_type = _detect_payment_type(transaction_id)
        return True, "Payment already verified and subscription is active.", payment_type

    landlord_sub = LandlordSubscription.objects.filter(
        transaction_ref=transaction_id
    ).select_related("plan", "user").first()

    if landlord_sub:
        if landlord_sub.payment_status == LandlordSubscription.PaymentStatus.COMPLETED:
            record.processed = True
            record.save(update_fields=["processed"])
            return True, "Landlord plan payment verified. Subscription is active.", "landlord"
        activate_landlord_subscription(landlord_sub)
        record.processed = True
        record.save(update_fields=["processed"])
        return True, "Landlord plan payment verified. Subscription activated.", "landlord"

    customer_sub = CustomerPremiumSubscription.objects.filter(
        transaction_ref=transaction_id
    ).select_related("user").first()

    if customer_sub:
        if customer_sub.payment_status == CustomerPremiumSubscription.PaymentStatus.COMPLETED:
            record.processed = True
            record.save(update_fields=["processed"])
            return True, "Premium subscription is already active.", "customer_premium"
        activate_customer_premium(customer_sub)
        record.processed = True
        record.save(update_fields=["processed"])
        return True, "Premium customer payment verified. You can now view premium listings.", "customer_premium"

    # External record exists as completed but no subscription matched — try direct subscription lookup
    landlord_sub = LandlordSubscription.objects.filter(transaction_ref=transaction_id).first()
    if landlord_sub and record.payment_status == ExternalPaymentRecord.Status.COMPLETED:
        activate_landlord_subscription(landlord_sub)
        record.processed = True
        record.save(update_fields=["processed"])
        return True, "Landlord plan payment verified. Subscription activated.", "landlord"

    customer_sub = CustomerPremiumSubscription.objects.filter(transaction_ref=transaction_id).first()
    if customer_sub and record.payment_status == ExternalPaymentRecord.Status.COMPLETED:
        activate_customer_premium(customer_sub)
        record.processed = True
        record.save(update_fields=["processed"])
        return True, "Premium customer payment verified.", "customer_premium"

    return False, "No subscription found for this transaction ID.", None


def _detect_payment_type(transaction_id):
    if LandlordSubscription.objects.filter(transaction_ref=transaction_id).exists():
        return "landlord"
    if CustomerPremiumSubscription.objects.filter(transaction_ref=transaction_id).exists():
        return "customer_premium"
    return None
