"""Transactional email delivery (INT-003).

Kept intentionally minimal for the MVP: a single `send_email` function
behind which a real production email provider can be dropped in later
without touching any caller. In the `test` environment, messages are
captured in-process (`test_outbox`) instead of sent, so contract tests can
assert on exactly what would have been emailed (e.g. extracting a
password-reset token) without a real mail server. Every other environment
sends real SMTP when `settings.smtp_host` is configured — local dev points
this at Mailhog (quickstart.md: "check your local mail catcher"), and it
always also logs, so nothing is silently lost if no relay is configured
(e.g. a minimal CI setup).
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from testpilot.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SentEmail:
    to: str
    subject: str
    body: str


test_outbox: list[SentEmail] = []


def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()

    if settings.environment == "test":
        test_outbox.append(SentEmail(to=to, subject=subject, body=body))
        return

    logger.info("email to=%s subject=%s\n%s", to, subject, body)

    if settings.smtp_host is None:
        return

    message = EmailMessage()
    message["From"] = settings.email_from_address
    message["To"] = to
    message["Subject"] = subject
    # cte="8bit" (not the quoted-printable default) so link/token characters
    # like "=" and "?" are never soft-wrapped or escaped (e.g. "token=3Dabc"
    # instead of "token=abc") — a real-world mail relay would still handle
    # 8bit content fine over modern SMTP (8BITMIME), and it keeps the body a
    # reset link can be regex-extracted from byte-for-byte.
    message.set_content(body, cte="8bit")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.send_message(message)
