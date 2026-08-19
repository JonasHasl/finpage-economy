"""Email notifications for algo-helper portfolio composition changes."""

from __future__ import annotations

import os

import requests

RESEND_API_URL = "https://api.resend.com/emails"
PORTFOLIO_LINK = "https://finpage.onrender.com/portfolio-daily"


class EmailNotificationError(RuntimeError):
    """Raised when a change-notification email could not be sent."""


def _ticker_list(tickers) -> str:
    return ", ".join(tickers) if tickers else "None"


def _parse_recipients(raw_value: str) -> list[str]:
    return [address.strip() for address in raw_value.split(",") if address.strip()]


def _build_payload(*, sender, recipients, portfolio_label, from_date, incoming, outgoing, unchanged):
    subject = f"Algo portfolio change submitted: {portfolio_label} (effective {from_date})"

    text_body = (
        f"A new composition change was submitted for {portfolio_label}.\n\n"
        f"Effective date: {from_date}\n\n"
        f"Incoming tickers: {_ticker_list(incoming)}\n"
        f"Outgoing tickers: {_ticker_list(outgoing)}\n"
        f"Unchanged tickers: {_ticker_list(unchanged)}\n\n"
        f"View the portfolio: {PORTFOLIO_LINK}\n"
    )

    html_body = (
        '<div style="font-family: Arial, sans-serif; color: #27425c;">'
        '<h2 style="color:#0f2744;">Algo portfolio change submitted</h2>'
        f'<p><strong>Portfolio:</strong> {portfolio_label}</p>'
        f'<p><strong>Effective date:</strong> {from_date}</p>'
        f'<p><strong>Incoming tickers:</strong> {_ticker_list(incoming)}</p>'
        f'<p><strong>Outgoing tickers:</strong> {_ticker_list(outgoing)}</p>'
        f'<p><strong>Unchanged tickers:</strong> {_ticker_list(unchanged)}</p>'
        f'<p><a href="{PORTFOLIO_LINK}">View portfolio-daily page</a></p>'
        '</div>'
    )

    return {
        "from": sender,
        "to": recipients,
        "subject": subject,
        "text": text_body,
        "html": html_body,
    }


def send_change_notification_email(
    *,
    portfolio_label: str,
    from_date: str,
    incoming,
    outgoing,
    unchanged,
    environment: dict | None = None,
    session: requests.Session | None = None,
) -> None:
    """Send an email summarizing an algo-helper portfolio composition change.

    Requires RESEND_API_KEY to be configured; EMAIL_FROM and EMAIL_TO are
    optional overrides for the sender and recipient addresses. EMAIL_TO may
    be a single address or a comma-separated list of addresses.
    """
    environment = environment or os.environ
    api_key = environment.get("RESEND_API_KEY")
    if not api_key:
        raise EmailNotificationError(
            "RESEND_API_KEY is not configured; skipping email notification."
        )

    sender = environment.get("EMAIL_FROM", "Finpage Algo Helper <onboarding@resend.dev>")
    recipients = _parse_recipients(environment.get("EMAIL_TO", "jonas_fbh@hotmail.com"))
    if not recipients:
        raise EmailNotificationError("EMAIL_TO is configured but contains no valid addresses.")
    http = session or requests

    payload = _build_payload(
        sender=sender,
        recipients=recipients,
        portfolio_label=portfolio_label,
        from_date=from_date,
        incoming=incoming,
        outgoing=outgoing,
        unchanged=unchanged,
    )

    try:
        response = http.post(
            RESEND_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise EmailNotificationError(f"Could not send change-notification email: {exc}") from exc
