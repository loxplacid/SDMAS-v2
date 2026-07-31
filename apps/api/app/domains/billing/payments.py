from __future__ import annotations

import abc
import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PaymentProvider(Protocol):
    """Protocol that every payment provider adapter must satisfy.

    All monetary amounts are in **Indian Rupee paise** (1 INR = 100 paise)
    to avoid floating-point rounding errors.
    """

    name: str

    async def create_subscription(
        self,
        plan_id: str,
        customer_email: str,
        total_amount_inr: int,
        billing_interval: str,
        trial_days: int,
    ) -> dict[str, Any]:
        """Create a recurring subscription at the provider.

        Returns a dict with at least ``provider_subscription_id``.
        """

    async def cancel_subscription(
        self, provider_subscription_id: str
    ) -> dict[str, Any]:
        """Cancel a recurring subscription at the provider."""

    async def create_payment_link(
        self,
        amount_inr: int,
        description: str,
        customer_email: str | None = None,
    ) -> dict[str, Any]:
        """Generate a one-time payment link.

        Returns a dict with ``url`` and ``id``.
        """

    async def verify_webhook(
        self, raw_body: str, signature: str
    ) -> dict[str, Any]:
        """Validate and parse an incoming webhook payload.

        Returns the parsed event as a dict on success.
        Raises ``ValueError`` on invalid signature.
        """

    async def get_subscription(
        self, provider_subscription_id: str
    ) -> dict[str, Any]:
        """Retrieve subscription details from the provider."""


class PaymentError(Exception):
    """Raised when a payment provider operation fails."""


# ---------------------------------------------------------------------------
# Registry: maps provider name -> provider instance
# ---------------------------------------------------------------------------

_providers: dict[str, PaymentProvider] = {}


def register_provider(name: str, provider: PaymentProvider) -> None:
    _providers[name] = provider
    logger.debug("Payment provider '%s' registered", name)


def get_provider(name: str | None) -> PaymentProvider | None:
    if name is None:
        return None
    return _providers.get(name)


def get_available_providers() -> list[str]:
    return list(_providers.keys())
