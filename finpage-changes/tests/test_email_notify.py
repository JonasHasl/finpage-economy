import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from email_notify import EmailNotificationError, send_change_notification_email


class FakeResponse:
    def __init__(self, status_code, payload=None, text=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class FakeSession:
    def __init__(self, status_code=200, payload=None, text=None):
        self.status_code = status_code
        self.payload = payload
        self.text = text
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.status_code, payload=self.payload, text=self.text)


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
        session = FakeSession(status_code=401, payload={"message": "Invalid API key"})
        with self.assertRaises(EmailNotificationError) as ctx:
            send_change_notification_email(
                portfolio_label="Since 2020 Model",
                from_date="2026-08-19",
                incoming=["NVDA"],
                outgoing=["INTU"],
                unchanged=[],
                environment={"RESEND_API_KEY": "bad-key"},
                session=session,
            )
        self.assertIn("401", str(ctx.exception))
        self.assertIn("Invalid API key", str(ctx.exception))

    def test_sandbox_recipient_restriction_surfaces_resend_message(self):
        session = FakeSession(
            status_code=403,
            payload={
                "message": (
                    "You can only send testing emails to your own email address "
                    "(jonas_fbh@hotmail.com). To send emails to other recipients, "
                    "please verify a domain."
                )
            },
        )
        with self.assertRaises(EmailNotificationError) as ctx:
            send_change_notification_email(
                portfolio_label="Since 2020 Model",
                from_date="2026-08-19",
                incoming=["NVDA"],
                outgoing=["INTU"],
                unchanged=[],
                environment={"RESEND_API_KEY": "test-key", "EMAIL_TO": "someone@else.com"},
                session=session,
            )
        self.assertIn("verify a domain", str(ctx.exception))

    def test_error_without_json_body_falls_back_to_raw_text(self):
        session = FakeSession(status_code=500, payload=None, text="Internal Server Error")
        with self.assertRaises(EmailNotificationError) as ctx:
            send_change_notification_email(
                portfolio_label="Since 2020 Model",
                from_date="2026-08-19",
                incoming=["NVDA"],
                outgoing=["INTU"],
                unchanged=[],
                environment={"RESEND_API_KEY": "test-key"},
                session=session,
            )
        self.assertIn("Internal Server Error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
