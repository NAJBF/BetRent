import logging
import os

logger = logging.getLogger(__name__)

CHAPA_SECRET_KEY = os.getenv("CHAPA_SECRET_KEY", "")
CHAPA_BASE_URL = "https://api.chapa.co/v1"


class ChapaService:
    """
    Service layer for Chapa payment gateway integration.
    Falls back to mock mode when CHAPA_SECRET_KEY is not set.
    """

    @staticmethod
    def is_mock_mode():
        return not CHAPA_SECRET_KEY

    @staticmethod
    def initiate_payment(amount, tx_ref, email, first_name, callback_url=""):
        """
        Initialize a Chapa payment checkout session.
        Returns: {"checkout_url": "...", "tx_ref": "..."}
        """
        if ChapaService.is_mock_mode():
            logger.info(f"[MOCK CHAPA] Initiating payment: {tx_ref} for {amount} ETB")
            return {
                "checkout_url": f"https://checkout.chapa.co/mock/{tx_ref}",
                "tx_ref": tx_ref,
            }

        # Real Chapa API call
        import httpx

        payload = {
            "amount": str(amount),
            "currency": "ETB",
            "tx_ref": tx_ref,
            "email": email,
            "first_name": first_name,
            "callback_url": callback_url,
            "return_url": callback_url,
        }

        try:
            response = httpx.post(
                f"{CHAPA_BASE_URL}/transaction/initialize",
                json=payload,
                headers={"Authorization": f"Bearer {CHAPA_SECRET_KEY}"},
                timeout=30,
            )
            data = response.json()
            if data.get("status") == "success":
                return {
                    "checkout_url": data["data"]["checkout_url"],
                    "tx_ref": tx_ref,
                }
            else:
                logger.error(f"Chapa initiation failed: {data}")
                raise Exception(f"Chapa error: {data.get('message', 'Unknown error')}")
        except httpx.RequestError as e:
            logger.error(f"Chapa request error: {e}")
            raise Exception("Payment service unavailable. Please try again.")

    @staticmethod
    def verify_payment(tx_ref):
        """
        Verify a payment by transaction reference.
        Returns: {"status": "success|failed", "amount": ..., "tx_ref": ...}
        """
        if ChapaService.is_mock_mode():
            logger.info(f"[MOCK CHAPA] Verifying payment: {tx_ref}")
            return {
                "status": "success",
                "amount": 0,
                "tx_ref": tx_ref,
            }

        import httpx

        try:
            response = httpx.get(
                f"{CHAPA_BASE_URL}/transaction/verify/{tx_ref}",
                headers={"Authorization": f"Bearer {CHAPA_SECRET_KEY}"},
                timeout=30,
            )
            data = response.json()
            if data.get("status") == "success":
                return {
                    "status": data["data"]["status"],
                    "amount": data["data"]["amount"],
                    "tx_ref": tx_ref,
                }
            else:
                return {"status": "failed", "amount": 0, "tx_ref": tx_ref}
        except httpx.RequestError as e:
            logger.error(f"Chapa verify error: {e}")
            raise Exception("Payment verification unavailable.")
