from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProviderMessage:
    to: str
    subject: Optional[str] = None
    body: Optional[str] = None
    html_body: Optional[str] = None
    attachments: Optional[list[dict[str, Any]]] = None
    metadata: Optional[dict[str, Any]] = None


@dataclass
class DeliveryResult:
    success: bool
    provider: str
    provider_message_id: Optional[str] = None
    error_message: Optional[str] = None


class BaseProvider(ABC):
    @abstractmethod
    async def send(self, message: ProviderMessage) -> DeliveryResult:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...


class EmailProvider(BaseProvider):
    async def send(self, message: ProviderMessage) -> DeliveryResult:
        logger.info(
            "[EMAIL][UNCONFIGURED] To: %s, Subject: %s",
            message.to, message.subject,
        )
        return DeliveryResult(success=True, provider="email")

    async def health(self) -> bool:
        return True


class SMSProvider(BaseProvider):
    async def send(self, message: ProviderMessage) -> DeliveryResult:
        logger.info(
            "[SMS][UNCONFIGURED] To: %s, Body: %s",
            message.to, (message.body or "")[:80],
        )
        return DeliveryResult(success=True, provider="sms")

    async def health(self) -> bool:
        return True


class PushProvider(BaseProvider):
    async def send(self, message: ProviderMessage) -> DeliveryResult:
        logger.info(
            "[PUSH][UNCONFIGURED] To: %s, Title: %s",
            message.to, message.subject,
        )
        return DeliveryResult(success=True, provider="push")

    async def health(self) -> bool:
        return True


class WhatsAppProvider(BaseProvider):
    async def send(self, message: ProviderMessage) -> DeliveryResult:
        logger.info(
            "[WHATSAPP][UNCONFIGURED] To: %s, Body: %s",
            message.to, (message.body or "")[:80],
        )
        return DeliveryResult(success=True, provider="whatsapp")

    async def health(self) -> bool:
        return True


class ProviderFactory:
    _providers: dict[str, BaseProvider] = {}

    @classmethod
    def get_provider(cls, channel: str) -> BaseProvider:
        if channel not in cls._providers:
            cls._providers[channel] = cls._create(channel)
        return cls._providers[channel]

    @classmethod
    def _create(cls, channel: str) -> BaseProvider:
        mapping: dict[str, type[BaseProvider]] = {
            "email": EmailProvider,
            "sms": SMSProvider,
            "push": PushProvider,
            "whatsapp": WhatsAppProvider,
        }
        provider_cls = mapping.get(channel)
        if not provider_cls:
            raise ValueError(f"Unknown channel: {channel}")
        logger.info("Created %s provider (no vendor hardcoded)", channel)
        return provider_cls()

    @classmethod
    def register(cls, channel: str, provider: BaseProvider) -> None:
        cls._providers[channel] = provider

    @classmethod
    def reset(cls) -> None:
        cls._providers.clear()

    @classmethod
    def available_channels(cls) -> list[str]:
        return ["email", "sms", "push", "whatsapp"]
