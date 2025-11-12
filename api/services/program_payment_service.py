# payments/program_payment_service.py
import logging
from typing import Optional, Dict, Any
from django.conf import settings
from .pesapal_service import PesaPalService

logger = logging.getLogger(__name__)

class ProgramPaymentService(PesaPalService):
    """
    PesaPal service for Program Payments - uses EXACT same callback as event payments.
    """

    def __init__(self):
        # Initialize parent first to get base_url and other settings
        super().__init__()
        # Use the EXACT SAME callback URL as event payments
        self.callback_url = settings.PESAPAL_CONFIG.get("CALLBACK_URL")
        logger.debug(f"ProgramPaymentService initialized with callback: {self.callback_url}")

    def _prepare_order_data(self, payment, merchant_reference: str) -> Dict[str, Any]:
        """
        Prepare order data specifically for program payments.
        Uses the exact same structure and field names as the parent class.
        """
        # Get program-specific information
        program = payment.registration.program
        registration = payment.registration
        
        # Name parsing - use same logic as parent class
        first_name = "Customer"
        last_name = "User"
        try:
            name = registration.full_name
            name_parts = name.split(" ", 1)
            first_name = name_parts[0] if name_parts else first_name
            last_name = name_parts[1] if len(name_parts) > 1 else last_name
        except Exception:
            logger.debug("Name parsing fallback used for program payment id=%s", getattr(payment, "id", "<unknown>"))

        # Phone formatting - use same logic as parent class
        phone_number = getattr(payment, "customer_phone", None) or getattr(registration, "phone_number", None) or "254700000000"
        phone_s = str(phone_number).replace("+", "").replace(" ", "").replace("-", "")
        if phone_s.startswith("0") and len(phone_s) == 10:
            phone_s = "254" + phone_s[1:]
        elif phone_s.startswith("7") and len(phone_s) == 9:
            phone_s = "254" + phone_s
        elif not phone_s.startswith("254"):
            phone_s = "254700000000"

        # Build order data - use EXACT same structure and field names as parent
        order_data = {
            "id": merchant_reference,
            "currency": getattr(payment, "currency", "KES"),
            "amount": float(getattr(payment, "amount", 0)),
            "description": f"Program: {program.title}"[:99],
            "callback_url": self.callback_url,  # Now exactly the same as event payments
            "billing_address": {
                "email_address": getattr(payment, "customer_email", None) or getattr(registration, "email", ""),
                "phone_number": phone_s,
                "country_code": "KE",
                "first_name": first_name,
                "last_name": last_name,
            },
        }

        # Add IPN ID if available (same as parent class logic)
        if self.ipn_id:
            order_data["notification_id"] = self.ipn_id

        logger.info(f"📦 Program order data prepared for: {program.title}")
        return order_data

    def submit_order(self, payment) -> Optional[Dict[str, Any]]:
        """
        Override submit_order to ensure callback_url is properly set before submission.
        """
        # Ensure callback_url is set to the same as event payments
        if not self.callback_url:
            self.callback_url = settings.PESAPAL_CONFIG.get("CALLBACK_URL")
            logger.debug(f"Callback URL reset to: {self.callback_url}")
        
        # Call parent implementation which handles the actual submission
        return super().submit_order(payment)