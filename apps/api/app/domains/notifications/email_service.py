"""Email delivery service using the SendGrid v3 Mail Send API.

Uses ``httpx`` (already installed as a dev dependency) to call the
SendGrid REST API directly rather than pulling in the heavy ``sendgrid``
Python package.  This keeps the dependency footprint small and works
identically in async contexts.

Usage::

    from app.domains.notifications.email_service import send_email

    success = await send_email(
        to_email="user@example.com",
        to_name="Jane Doe",
        subject="Fee Due Reminder",
        plain_body="Your fee is due.",
        html_body="<p>Your fee is due.</p>",
    )

Configuration (via ``app.config.settings``):
    - ``sendgrid_api_key`` — SendGrid API key (empty = log only)
    - ``email_from_address`` — sender address
    - ``email_from_name`` — sender display name
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"
SENDGRID_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# HTML template builder
# ---------------------------------------------------------------------------


def _build_html_body(title: str, body: str) -> str:
    """Wrap a notification message in a minimal, responsive HTML email template."""
    safe_title = _html_escape(title)
    safe_body = _html_escape(body).replace("\n", "<br>")

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f5f7;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f5f7;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">
          <tr>
            <td style="padding:32px 32px 0 32px;">
              <h1 style="margin:0 0 8px 0;font-size:20px;font-weight:700;color:#1a1a2e;line-height:1.3;">
                {safe_title}
              </h1>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 32px 32px 32px;">
              <p style="margin:0;font-size:15px;color:#4a4a6a;line-height:1.6;">
                {safe_body}
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:16px 32px;border-top:1px solid #e8e8ef;">
              <p style="margin:0;font-size:12px;color:#9a9ab0;">
                This is an automated notification from SDMAS.
                Please do not reply to this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _html_escape(text: str) -> str:
    """Minimal HTML entity escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# SendGrid API helper
# ---------------------------------------------------------------------------


def _build_payload(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: str,
    to_name: Optional[str] = None,
) -> dict:
    """Build the JSON payload for the SendGrid v3 Mail Send endpoint."""
    payload: dict = {
        "personalizations": [
            {
                "to": [
                    {
                        "email": to_email,
                    }
                ],
                "subject": subject,
            }
        ],
        "from": {
            "email": settings.email_from_address,
            "name": settings.email_from_name,
        },
        "content": [
            {
                "type": "text/plain",
                "value": plain_body,
            },
            {
                "type": "text/html",
                "value": html_body,
            },
        ],
    }

    if to_name:
        payload["personalizations"][0]["to"][0]["name"] = to_name

    return payload


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def send_email(
    to_email: str,
    subject: str,
    plain_body: str,
    html_body: Optional[str] = None,
    to_name: Optional[str] = None,
) -> bool:
    """Send an email via the SendGrid v3 Mail Send API.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        plain_body: Plain-text version of the email body.
        html_body: Optional HTML version of the email body.  If omitted,
            a simple HTML wrapper is generated from ``plain_body``.
        to_name: Optional recipient display name.

    Returns:
        ``True`` when the API accepted the message (HTTP 202),
        ``False`` on any error (logged but not raised).

    Behaviour when SendGrid is not configured (``sendgrid_api_key`` is
    empty): logs the message and returns ``True`` so the caller treats
    it as a soft pass.
    """
    if not settings.sendgrid_api_key:
        logger.info(
            "[EMAIL][UNCONFIGURED] To %s <%s>: %s — %s",
            to_name or "(no name)",
            to_email,
            subject,
            plain_body[:120],
        )
        return True

    resolved_html = html_body or _build_html_body(subject, plain_body)
    payload = _build_payload(to_email, subject, plain_body, resolved_html, to_name)

    try:
        import httpx

        async with httpx.AsyncClient(timeout=SENDGRID_TIMEOUT) as client:
            response = await client.post(
                SENDGRID_API_URL,
                headers={
                    "Authorization": f"Bearer {settings.sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(payload),
            )

        if response.status_code == 202:
            logger.info(
                "Email accepted by SendGrid for %s <%s>: %s",
                to_name or "(no name)",
                to_email,
                subject,
            )
            return True

        logger.error(
            "SendGrid API returned %d for email to %s: %s",
            response.status_code,
            to_email,
            response.text[:500],
        )
        return False

    except ImportError:
        logger.warning(
            "httpx not installed — cannot send email. Install with: uv add httpx"
        )
        return False
    except Exception:
        logger.exception("Failed to send email to %s: %s", to_email, subject)
        return False
