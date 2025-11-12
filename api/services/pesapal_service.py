# payments/pesapal_service.py
import logging
import time
import uuid
import traceback
from typing import Optional, Any, Dict

import requests
from requests.adapters import HTTPAdapter, Retry
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Cache keys and TTLs
_TOKEN_CACHE_KEY = "pesapal_access_token"
_TOKEN_TTL_FALLBACK = 300  # seconds if API doesn't provide expires_in
_IPN_ID_CACHE_KEY = "pesapal_ipn_id"
_IPN_ID_TTL = 60 * 60 * 24  # 24 hours

# Request settings
REQUEST_TIMEOUT = 30  # seconds per request (same as your original)
RETRY_STRATEGY = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])


class PesaPalService:
    """
    Secure wrapper around PesaPal endpoints using your original method names/behaviour.

    Improvements:
    - Uses requests.Session with retries & timeouts
    - Caches access token and IPN id in Django cache
    - Uses Django logging (no secrets in logs)
    - Keeps same public API as your original service
    """

    def __init__(self):
        self.consumer_key = settings.PESAPAL_CONSUMER_KEY
        self.consumer_secret = settings.PESAPAL_CONSUMER_SECRET
        self.base_url = settings.PESAPAL_CONFIG["BASE_URL"].rstrip("/")
        self.callback_url = settings.PESAPAL_CONFIG.get("CALLBACK_URL")
        self.ipn_url = settings.PESAPAL_CONFIG.get("IPN_URL")
        self.access_token: Optional[str] = None
        self.ipn_id: Optional[str] = None

        # Prepare session with retries
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=RETRY_STRATEGY)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # -------------------------
    # Access token management
    # -------------------------
    def _cache_set_token(self, token: str, ttl: int):
        try:
            cache.set(_TOKEN_CACHE_KEY, token, timeout=ttl)
        except Exception:
            logger.debug("Failed to cache Pesapal token (non-fatal).")

    def _cache_get_token(self) -> Optional[str]:
        try:
            return cache.get(_TOKEN_CACHE_KEY)
        except Exception:
            logger.debug("Failed to read Pesapal token from cache.")
            return None

    def get_access_token(self) -> Optional[str]:
        """
        Get PesaPal access token with caching & error handling.
        Returns token string or None on failure.
        """
        # Try cached token first
        cached = self._cache_get_token()
        if cached:
            self.access_token = cached
            return cached

        url = f"{self.base_url}/api/Auth/RequestToken"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        payload = {"consumer_key": self.consumer_key, "consumer_secret": self.consumer_secret}

        try:
            logger.debug("Requesting Pesapal access token.")
            resp = self.session.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            logger.debug("Pesapal token response status=%s", resp.status_code)
            resp.raise_for_status()
            token_data = resp.json()

            token = token_data.get("token")
            expires_in = token_data.get("expires_in", _TOKEN_TTL_FALLBACK)

            if token:
                # cache token
                self.access_token = token
                try:
                    expires = int(expires_in)
                except Exception:
                    expires = _TOKEN_TTL_FALLBACK
                self._cache_set_token(token, ttl=max(30, expires - 10))
                logger.info("Obtained Pesapal access token (cached ttl=%s)", expires)
                return token
            else:
                logger.error("Pesapal token response missing 'token'. keys=%s", list(token_data.keys()))
                return None

        except requests.exceptions.HTTPError as e:
            status = getattr(e.response, "status_code", None)
            logger.error("HTTP error obtaining Pesapal token: status=%s", status)
            return None
        except requests.exceptions.Timeout:
            logger.error("Timeout while requesting Pesapal token.")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Connection error requesting Pesapal token.")
            return None
        except Exception as e:
            logger.exception("Unexpected error requesting Pesapal token: %s", e)
            return None

    # -------------------------
    # IPN registration
    # -------------------------
    def _cache_set_ipn_id(self, ipn_id: str):
        try:
            cache.set(_IPN_ID_CACHE_KEY, ipn_id, timeout=_IPN_ID_TTL)
        except Exception:
            logger.debug("Failed to cache Pesapal IPN id (non-fatal).")

    def _cache_get_ipn_id(self) -> Optional[str]:
        try:
            return cache.get(_IPN_ID_CACHE_KEY)
        except Exception:
            logger.debug("Failed to read Pesapal IPN id from cache.")
            return None

    def register_ipn(self) -> Optional[str]:
        """
        Register IPN URL with PesaPal and return ipn_id. Caches value to avoid repeated registration.
        """
        # check cache first
        cached = self._cache_get_ipn_id()
        if cached:
            self.ipn_id = cached
            return cached

        # ensure we have access token
        token = self.access_token or self.get_access_token()
        if not token:
            logger.error("Cannot register IPN - no access token.")
            return None

        url = f"{self.base_url}/api/URLSetup/RegisterIPN"
        headers = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {token}"}
        ipn_data = {"url": self.ipn_url, "ipn_notification_type": "POST"}

        try:
            logger.debug("Registering IPN with Pesapal (not logging the ipn url).")
            resp = self.session.post(url, json=ipn_data, headers=headers, timeout=REQUEST_TIMEOUT)
            logger.debug("Pesapal IPN register status=%s", resp.status_code)
            resp.raise_for_status()
            body = resp.json()
            ipn_id = body.get("ipn_id")
            if ipn_id:
                self.ipn_id = ipn_id
                self._cache_set_ipn_id(ipn_id)
                logger.info("Pesapal IPN registered and cached (ipn_id present).")
                return ipn_id
            logger.error("Pesapal IPN registration returned no ipn_id. keys=%s", list(body.keys()))
            return None
        except requests.exceptions.HTTPError as e:
            logger.error("HTTP error registering IPN: status=%s", getattr(e.response, "status_code", None))
            return None
        except Exception as e:
            logger.exception("Unexpected error registering IPN: %s", e)
            return None

    # -------------------------
    # Order submission
    # -------------------------
    def submit_order(self, payment) -> Optional[Dict[str, Any]]:
        """
        Submit payment order to PesaPal. Returns parsed JSON response or None on failure.
        Keeps original behavior: generates merchant_reference UUID, registers IPN if missing,
        prepares order_data using _prepare_order_data, handles many fallback cases.
        """
        merchant_reference = None
        try:
            logger.info("Submitting order to Pesapal for payment id=%s", getattr(payment, "id", "<unknown>"))

            # Ensure token available
            if not self.access_token:
                self.access_token = self.get_access_token()
            if not self.access_token:
                logger.error("Failed to obtain access token - aborting submit_order.")
                self._update_payment_with_fallback(payment, "auth_failed", "auth_failed")
                return None

            # Generate merchant_reference (your original behavior)
            merchant_reference = str(uuid.uuid4())

            # Ensure ipn_id available (register if necessary, but first try cache)
            if not self.ipn_id:
                cached_ipn = self._cache_get_ipn_id()
                if cached_ipn:
                    self.ipn_id = cached_ipn
                else:
                    self.ipn_id = self.register_ipn()

            url = f"{self.base_url}/api/Transactions/SubmitOrderRequest"
            headers = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}

            order_data = self._prepare_order_data(payment, merchant_reference)
            if self.ipn_id:
                order_data["notification_id"] = self.ipn_id

            logger.debug("Sending SubmitOrderRequest to Pesapal (not logging full payload).")
            resp = self.session.post(url, json=order_data, headers=headers, timeout=REQUEST_TIMEOUT)
            logger.debug("Pesapal order submission status=%s", resp.status_code)

            if resp.status_code != 200:
                logger.error("Pesapal API error submitting order: status=%s", resp.status_code)
                self._update_payment_with_fallback(payment, merchant_reference, "api_error")
                return None

            try:
                order_response = resp.json()
            except ValueError:
                logger.error("Failed to parse Pesapal order response as JSON.")
                self._update_payment_with_fallback(payment, merchant_reference, "parse_error")
                return None

            error = order_response.get("error")
            if error is not None:
                logger.error("Pesapal returned error in order_response: %s", str(error)[:200])
                self._update_payment_with_fallback(payment, merchant_reference, "pesapal_error")
                return None

            redirect_url = order_response.get("redirect_url")
            if not redirect_url:
                logger.error("Pesapal order response missing redirect_url.")
                self._update_payment_with_fallback(payment, merchant_reference, "no_redirect")
                return None

            # update payment as in original logic
            self._update_payment_success(payment, merchant_reference, order_response)
            logger.info("Payment successfully initiated; merchant_reference=%s", merchant_reference)
            return order_response

        except Exception as e:
            logger.exception("Unexpected error in submit_order: %s", e)
            # fallback update (preserve original behavior)
            try:
                if merchant_reference:
                    self._update_payment_with_fallback(payment, merchant_reference, "unexpected_error")
                else:
                    self._update_payment_with_fallback(payment, str(uuid.uuid4()), "unexpected_error")
            except Exception:
                logger.exception("Failed to update payment fallback after unexpected error.")
            return None

    # -------------------------
    # Helper: prepare order payload (keeps same semantics)
    # -------------------------
    def _prepare_order_data(self, payment, merchant_reference: str) -> Dict[str, Any]:
        """
        Prepare order data for PesaPal API. Keeps same phone formatting logic you had,
        but avoids printing the raw inputs.
        """
        # Attempt to split provided registration name field as you had
        first_name = "Customer"
        last_name = "User"
        try:
            name = getattr(payment, "registration", None) and getattr(payment.registration, "full_name", None)
            if not name:
                name = getattr(payment, "full_name", "") or ""
            name_parts = name.split(" ", 1)
            first_name = name_parts[0] if name_parts else first_name
            last_name = name_parts[1] if len(name_parts) > 1 else last_name
        except Exception:
            logger.debug("Name parsing fallback used for payment id=%s", getattr(payment, "id", "<unknown>"))

        # Phone formatting (preserve semantics)
        phone_number = getattr(payment, "customer_phone", None) or getattr(payment, "phone", None) or "254700000000"
        phone_s = str(phone_number).replace("+", "").replace(" ", "").replace("-", "")
        if phone_s.startswith("0") and len(phone_s) == 10:
            phone_s = "254" + phone_s[1:]
        elif phone_s.startswith("7") and len(phone_s) == 9:
            phone_s = "254" + phone_s
        elif not phone_s.startswith("254"):
            phone_s = "254700000000"

        # Build order data; keep exactly the same keys you used
        order_data = {
            "id": merchant_reference,
            "currency": getattr(payment, "currency", "KES"),
            "amount": float(getattr(payment, "amount", 0)),
            "description": str(getattr(payment, "registration", None) and getattr(payment.registration, "event", None) and getattr(payment.registration.event, "title", "") or f"Payment for {merchant_reference}")[:99],
            "callback_url": self.callback_url,
            "billing_address": {
                "email_address": getattr(payment, "customer_email", None) or getattr(payment, "email", ""),
                "phone_number": phone_s,
                "country_code": "KE",
                "first_name": first_name,
                "last_name": last_name,
            },
        }

        return order_data

    # -------------------------
    # Payment update helpers (keeps same semantics)
    # -------------------------
    def _update_payment_success(self, payment, merchant_reference: str, order_response: Dict[str, Any]):
        """
        Update payment with successful PesaPal response.
        Mirrors your original implementation but uses logger instead of prints.
        """
        try:
            pesapal_tracking_id = order_response.get("order_tracking_id") or order_response.get("pesapal_transaction_tracking_id")
            redirect_url = order_response.get("redirect_url", "")

            # keep original field names you used
            payment.pesapal_order_tracking_id = pesapal_tracking_id
            payment.pesapal_merchant_reference = merchant_reference
            payment.pesapal_payment_url = redirect_url
            payment.payment_status = "initiated"
            payment.payment_initiated_at = timezone.now()
            payment.save()
            logger.debug("Payment updated: tracking_id=%s merchant_reference=%s", pesapal_tracking_id, merchant_reference)
        except Exception:
            logger.exception("Failed to update payment success for merchant_reference=%s", merchant_reference)

    def _update_payment_with_fallback(self, payment, merchant_reference: str, error_type: str):
        """
        Update payment with fallback values when PesaPal fails.
        Keeps same fields and behavior as original.
        """
        try:
            payment.pesapal_order_tracking_id = None
            payment.pesapal_merchant_reference = merchant_reference
            payment.pesapal_payment_url = ""
            payment.payment_status = "failed"
            payment.payment_initiated_at = timezone.now()
            payment.save()
            logger.info("Payment saved with fallback (error=%s) merchant_reference=%s", error_type, merchant_reference)
        except Exception:
            logger.exception("Failed to update payment fallback for merchant_reference=%s", merchant_reference)

    # -------------------------
    # Transaction status & IPN validation
    # -------------------------
    def get_transaction_status(self, order_tracking_id: str):
        """
        Check transaction status. Returns JSON dict or None.
        """
        try:
            if not self.access_token:
                self.access_token = self.get_access_token()
            if not self.access_token:
                logger.error("No access token for get_transaction_status")
                return None

            url = f"{self.base_url}/api/Transactions/GetTransactionStatus"
            params = {"orderTrackingId": order_tracking_id}
            headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
            resp = self.session.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.exception("Status check error for orderTrackingId=%s: %s", order_tracking_id, e)
            return None

    def validate_ipn(self, order_tracking_id: str):
        """
        Validate IPN notification by calling ConfirmTransaction.
        Returns JSON or None.
        """
        try:
            if not self.access_token:
                self.access_token = self.get_access_token()
            if not self.access_token:
                logger.error("No access token for validate_ipn")
                return None

            url = f"{self.base_url}/api/Transactions/ConfirmTransaction"
            headers = {"Accept": "application/json", "Authorization": f"Bearer {self.access_token}"}
            data = {"orderTrackingId": order_tracking_id}
            resp = self.session.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.exception("IPN validation error for orderTrackingId=%s: %s", order_tracking_id, e)
            return None


