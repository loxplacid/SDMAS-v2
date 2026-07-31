"""Tests for the SendGrid email service and EmailChannel.

Covers:
- Email service with mocked httpx (success, error, unconfigured)
- HTML template building
- EmailChannel looks up user email and calls send_email
- Fallback behaviour when SendGrid is not configured
"""

from __future__ import annotations

import json
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.domains.notifications.channels import ChannelMessage, EmailChannel
from app.domains.notifications.email_service import (
    _build_html_body,
    _html_escape,
    send_email,
)


def _with_sendgrid_key(key: str):
    """Context manager that temporarily sets the SendGrid API key."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        original = settings.sendgrid_api_key
        settings.sendgrid_api_key = key
        try:
            yield
        finally:
            settings.sendgrid_api_key = original
    return _ctx()


# ===========================================================================
# HTML template tests
# ===========================================================================


class TestHtmlTemplate:
    def test_build_html_body_contains_title_and_body(self):
        html = _build_html_body("Test Title", "This is the body text")
        assert "Test Title" in html
        assert "This is the body text" in html

    def test_build_html_body_escapes_html(self):
        html = _build_html_body("<script>alert('xss')</script>", "body")
        assert "&lt;script&gt;" in html
        assert "<script>" not in html

    def test_html_escape_basic(self):
        assert _html_escape("<>&\"") == "&lt;&gt;&amp;&quot;"

    def test_html_escape_plain_text(self):
        assert _html_escape("Hello, world!") == "Hello, world!"

    def test_html_body_has_responsive_structure(self):
        html = _build_html_body("Subject", "Content")
        assert "<!DOCTYPE html>" in html
        assert "border-radius:12px" in html


# ===========================================================================
# SendGrid email service tests (mocked httpx)
# ===========================================================================


class TestSendEmailService:
    @patch("httpx.AsyncClient")
    async def test_send_email_success(self, mock_client_cls):
        """API returns 202 — email accepted."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with _with_sendgrid_key("SG.test_key"):
            result = await send_email(
                to_email="test@example.com",
                subject="Hello",
                plain_body="Test message",
            )
            assert result is True

    @patch("httpx.AsyncClient")
    async def test_send_email_api_error(self, mock_client_cls):
        """API returns 4xx/5xx — email not accepted."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"errors": [{"message": "Invalid from"}]}'
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with _with_sendgrid_key("SG.test_key"):
            result = await send_email(
                to_email="bad@example.com",
                subject="Fail",
                plain_body="Should fail",
            )
            assert result is False

    async def test_send_email_unconfigured(self):
        """No API key configured — should log and return True."""
        with _with_sendgrid_key(""):
            result = await send_email(
                to_email="test@example.com",
                subject="Unconfigured",
                plain_body="Should log only",
            )
            assert result is True

    @patch("httpx.AsyncClient")
    async def test_send_email_network_error(self, mock_client_cls):
        """Network error — should return False gracefully."""
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        mock_client_cls.return_value = mock_client

        with _with_sendgrid_key("SG.test_key"):
            result = await send_email(
                to_email="test@example.com",
                subject="Network Error",
                plain_body="Should handle gracefully",
            )
            assert result is False

    @patch("httpx.AsyncClient")
    async def test_send_email_passes_payload(self, mock_client_cls):
        """Verify the JSON payload sent to SendGrid."""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client = AsyncMock()
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value.post = mock_post
        mock_client_cls.return_value = mock_client

        with _with_sendgrid_key("SG.test_key"):
            await send_email(
                to_email="jane@example.com",
                to_name="Jane Doe",
                subject="Fee Due",
                plain_body="Your fee is due.",
                html_body="<p>Your fee is due.</p>",
            )

        call_args = mock_post.call_args
        # URL is the first positional argument to client.post(url, ...)
        assert call_args.args[0] == "https://api.sendgrid.com/v3/mail/send"
        assert "SG.test_key" in call_args.kwargs["headers"]["Authorization"]

        payload = json.loads(call_args.kwargs["content"])
        assert payload["personalizations"][0]["to"][0]["email"] == "jane@example.com"
        assert payload["personalizations"][0]["to"][0]["name"] == "Jane Doe"
        assert payload["personalizations"][0]["subject"] == "Fee Due"


# ===========================================================================
# EmailChannel tests
# ===========================================================================


class TestEmailChannel:
    async def test_email_channel_looks_up_user_and_sends(self, db_session):
        """EmailChannel should look up user email and send via SendGrid."""
        from app.domains.auth.models import User
        from app.domains.auth.repository import UserRepository

        user_repo = UserRepository(db_session)
        user = User(
            email="student@school.edu",
            username="student1",
            display_name="Student One",
            password_hash="fakehash",
            role="student",
        )
        user = await user_repo.create(user)

        channel = EmailChannel(db_session)

        with patch(
            "app.domains.notifications.channels.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            msg = ChannelMessage(
                user_id=user.id,
                event_type="fee",
                title="Fee Due Reminder",
                message="Your fee of $500 is due.",
            )
            result = await channel.deliver(msg)

            assert result is True
            mock_send.assert_awaited_once_with(
                to_email="student@school.edu",
                to_name="Student One",
                subject="Fee Due Reminder",
                plain_body="Your fee of $500 is due.",
            )

    async def test_email_channel_missing_user(self, db_session):
        """Non-existent user ID should return False, not crash."""
        channel = EmailChannel(db_session)
        msg = ChannelMessage(
            user_id=99999,
            event_type="test",
            title="Test",
            message="Test message",
        )
        result = await channel.deliver(msg)
        assert result is False

    async def test_email_channel_user_without_email(self, db_session):
        """User without email should return False."""
        from app.domains.auth.models import User
        from app.domains.auth.repository import UserRepository

        user_repo = UserRepository(db_session)
        user = User(
            email="",
            username="noemail",
            display_name="No Email",
            password_hash="fakehash",
            role="student",
        )
        user = await user_repo.create(user)

        channel = EmailChannel(db_session)
        msg = ChannelMessage(
            user_id=user.id,
            event_type="test",
            title="Test",
            message="No email",
        )
        result = await channel.deliver(msg)
        assert result is False

    async def test_get_channel_returns_email_channel(self, db_session):
        """Channel factory should return EmailChannel with session."""
        from app.domains.notifications.channels import get_channel

        channel = get_channel("email", db_session)
        assert isinstance(channel, EmailChannel)
