# payments/program_payment_service.py
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from .pesapal_service import PesaPalService

logger = logging.getLogger(__name__)

class ProgramPaymentService(PesaPalService):
    """
    PesaPal service for Program Payments - only changes callback URL.
    Uses the same IPN as event payments.
    """
    
    def __init__(self):
        super().__init__()
        # Only override callback URL for program payments
        self.callback_url = f"{self.base_url}/api/program-payments/pesapal-callback/"
        # Keep the same IPN URL as event payments

    def _prepare_order_data(self, payment, merchant_reference: str) -> Dict[str, Any]:
        """
        Prepare order data specifically for program payments.
        """
        # Get program-specific information
        program = payment.registration.program
        registration = payment.registration
        
        # Name parsing for program registration
        first_name = "Customer"
        last_name = "User"
        try:
            name = registration.full_name
            name_parts = name.split(" ", 1)
            first_name = name_parts[0] if name_parts else first_name
            last_name = name_parts[1] if len(name_parts) > 1 else last_name
        except Exception:
            logger.debug("Name parsing fallback used for program payment id=%s", payment.id)

        # Phone formatting
        phone_number = payment.customer_phone or registration.phone_number or "254700000000"
        phone_s = str(phone_number).replace("+", "").replace(" ", "").replace("-", "")
        if phone_s.startswith("0") and len(phone_s) == 10:
            phone_s = "254" + phone_s[1:]
        elif phone_s.startswith("7") and len(phone_s) == 9:
            phone_s = "254" + phone_s
        elif not phone_s.startswith("254"):
            phone_s = "254700000000"

        # Build program-specific order data
        order_data = {
            "id": merchant_reference,
            "currency": payment.currency or "KES",
            "amount": float(payment.amount),
            "description": f"Program: {program.title}"[:99],
            "callback_url": self.callback_url,  # This is the key difference
            "notification_id": self.ipn_id,     # Same IPN as events
            "billing_address": {
                "email_address": payment.customer_email or registration.email,
                "phone_number": phone_s,
                "country_code": "KE",
                "first_name": first_name,
                "last_name": last_name,
            },
        }

        logger.info(f"📦 Program order data prepared for: {program.title}")
        return order_data