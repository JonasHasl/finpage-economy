import sys
import unittest
from pathlib import Path

import requests


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from email_notify import EmailNotificationError, send_change_notification_email


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.status_code)


class SendChangeNotificationEmailTests(unittest.TestCase):
    def test_sends_expected_payload(self):
        session = FakeSession()
        send_change_notification_email(
            portfolio_label="Since 2020 Model",
            from_date="2026-08-19",
            incoming=["NVDA"],
            outgoing=["INTU"],
            unchanged=["AVGO", "DELL", "MU", "PLTR", "SNDK"],
            environment={"RESEND_API_KEY": "test-key"},
            session=session,
        )

        self.assertEqual(len(session.calls), 1)
        url, kwargs = session.calls[0]
        self.assertEqual(url, "https://api.resend.com/emails")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer test-key")

        payload = kwargs["json"]
        self.assertEqual(payload["to"], ["jonas_fbh@hotmail.com"])
        self.assertIn("Since 2020 Model", payload["subject"])
        self.assertIn("NVDA", payload["text"])
        self.assertIn("INTU", payload["text"])
        self.assertIn("https://finpage.onrender.com/portfolio-daily", payload["text"])

    def test_uses_email_to_override(self):
        session = FakeSession()
        send_change_notification_email(
            portfolio_label="Since 2015 Model",
            from_date="2026-08-19",
            incoming=[],
            outgoing=[],
            unchanged=[],
            environment={"RESEND_API_KEY": "test-key", "EMAIL_TO": "someone@else.com"},
            session=session,
        )

        _, kwargs = session.calls[0]
        self.assertEqual(kwargs["json"]["to"], ["someone@else.com"])

    def test_email_to_accepts_comma_separated_list(self):
        session = FakeSession()
        send_change_notification_email(
            portfolio_label="Since 2015 Model",
            from_date="2026-08-19",
            incoming=[],
            outgoing=[],
            unchanged=[],
            environment={
                "RESEND_API_KEY": "test-key",
                "EMAIL_TO": "one@example.com, two@example.com ,three@example.com",
            },
            session=session,
        )

        _, kwargs = session.calls[0]
        self.assertEqual(
            kwargs["json"]["to"],
            ["one@example.com", "two@example.com", "three@example.com"],
        )

    def test_missing_api_key_raises_without_network_call(self):
        session = FakeSession()
        with self.assertRaises(EmailNotificationError):
            send_change_notification_email(
                portfolio_label="Since 2020 Model",
                from_date="2026-08-19",
                incoming=["NVDA"],
                outgoing=["INTU"],
                unchanged=[],
                environment={},
                session=session,
            )
        self.assertEqual(session.calls, [])

    def test_http_failure_raises_email_notification_error(self):
        session = FakeSession(status_code=401)
        with self.assertRaises(EmailNotificationError):
            send_change_notification_email(
                portfolio_label="Since 2020 Model",
                from_date="2026-08-19",
                incoming=["NVDA"],
                outgoing=["INTU"],
                unchanged=[],
                environment={"RESEND_API_KEY": "bad-key"},
                session=session,
            )


if __name__ == "__main__":
    unittest.main()
