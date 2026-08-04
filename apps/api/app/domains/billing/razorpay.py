from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from app.domains.billing.payments import PaymentError

logger = logging.getLogger(__name__)

#: Maximum acceptable skew between the webhook signature timestamp and our
#: clock.  Events signed more than this long ago are treated as replays and
#: rejected, providing timestamp-based replay protection.
WEBHOOK_MAX_AGE_S = 300


class RazorpayProvider:
    """Payment provider adapter for Razorpay (India).

    Razorpay is the most popular payment gateway in India, supporting
    UPI, credit/debit cards, net banking, wallets, and EMI.

    Docs: https://razorpay.com/docs/api/
    """

    name = "razorpay"

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        webhook_secret: str | None = None,
    ) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret or key_secret
        self._http_base = "https://api.razorpay.com/v1"

    @property
    def _is_configured(self) -> bool:
        return bool(self._key_id and self._key_secret)

    def _auth(self) -> tuple[str, str]:
        return (self._key_id, self._key_secret)

    async def _post(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        import httpx

        url = f"{self._http_base}{path}"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url, json=data, auth=self._auth(), timeout=30.0,
            )
            if resp.status_code >= 400:
                raise PaymentError(
                    f"Razorpay {path} failed ({resp.status_code}): {resp.text}"
                )
            return resp.json()

    async def _get(self, path: str) -> dict[str, Any]:
        import httpx

        url = f"{self._http_base}{path}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, auth=self._auth(), timeout=30.0)
            if resp.status_code >= 400:
                raise PaymentError(
                    f"Razorpay {path} failed ({resp.status_code}): {resp.text}"
                )
            return resp.json()

    async def create_subscription(
        self,
        plan_id: str,
        customer_email: str,
        total_amount_inr: int,
        billing_interval: str,
        trial_days: int,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        period = (
            billing_interval
            if billing_interval in ("daily", "weekly", "monthly", "yearly")
            else "monthly"
        )
        data: dict[str, Any] = {
            "plan_id": plan_id,
            "total_count": 12 if period == "monthly" else 3,
            "quantity": 1,
            "customer_notify": 1,
        }
        if trial_days > 0:
            data["start_at"] = int(
                __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ).timestamp()
            ) + (trial_days * 86400)
        if notes:
            data["notes"] = notes

        return await self._post("/subscriptions", data)

    async def cancel_subscription(
        self, provider_subscription_id: str
    ) -> dict[str, Any]:
        return await self._post(
            f"/subscriptions/{provider_subscription_id}/cancel",
            {"cancel_at_cycle_end": 0},
        )

    async def create_payment_link(
        self,
        amount_inr: int,
        description: str,
        customer_email: str | None = None,
        notes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "amount": amount_inr,
            "currency": "INR",
            "description": description,
            "accept_partial": 0,
        }
        if customer_email:
            data["customer"] = {"email": customer_email}
        if notes:
            data["notes"] = notes

        result = await self._post("/payment_links", data)
        return {
            "url": result.get("short_url", ""),
            "id": result.get("id", ""),
        }

    async def verify_webhook(
        self, raw_body: str, signature: str
    ) -> dict[str, Any]:
        """Verify the webhook signature and return the parsed payload.

        The signature covers the raw request body, so it must be computed
        over the exact bytes received (never the re-serialized JSON).
        """
        expected = hmac.new(
            self._webhook_secret.encode("utf-8"),
            raw_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("Invalid Razorpay webhook signature")
        return json.loads(raw_body)

    @staticmethod
    def event_timestamp(event: dict[str, Any]) -> int:
        """Best-effort epoch seconds for the event, or ``0`` when unknown.

        Razorpay signs webhooks with a ``timestamp`` query parameter, but it
        is not guaranteed to be present on every payload.
        """
        try:
            return int(event.get("timestamp", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def signature_is_stale(self, event: dict[str, Any]) -> bool:
        """True when the event's signature timestamp is too old to accept.

        Razorpay does not always sign a timestamp, so this is an *opt-in*
        freshness layer: only a payload that explicitly carries a timestamp
        older than the freshness window is rejected.  Providers that do not
        include a timestamp rely on the content-derived idempotency ledger in
        ``webhook_events`` for replay protection — a replayed delivery is a
        duplicate and is dropped.
        """
        timestamp = self.event_timestamp(event)
        if timestamp <= 0:
            return False
        return (time.time() - timestamp) > WEBHOOK_MAX_AGE_S

    async def get_subscription(
        self, provider_subscription_id: str
    ) -> dict[str, Any]:
        return await self._get(f"/subscriptions/{provider_subscription_id}")
