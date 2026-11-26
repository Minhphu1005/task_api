import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger("taskhub.notifications")


@dataclass(slots=True)
class NotificationRecord:
    """Record of a dispatched notification (useful for auditing and testing)."""

    recipient_email: str
    subject: str
    body: str


sent_notifications: list[NotificationRecord] = []


def send_task_assigned_email(
    *,
    recipient_email: str,
    recipient_name: str,
    task_title: str,
    project_id: int,
    assigned_by: str,
) -> None:
    """Send an email notification when a user is assigned to a task."""
    settings = get_settings()
    subject = f"[TaskHub] You were assigned to: {task_title}"
    body = (
        f"Hi {recipient_name},\n\n"
        f"{assigned_by} assigned you to task '{task_title}' in project #{project_id}.\n\n"
        "Best regards,\nTaskHub"
    )

    sent_notifications.append(
        NotificationRecord(recipient_email=recipient_email, subject=subject, body=body)
    )

    if not settings.smtp_enabled:
        logger.info(
            "Notification queued (SMTP disabled) -> to=%s subject=%r",
            recipient_email,
            subject,
        )
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = recipient_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as server:
            if settings.smtp_user and settings.smtp_password:
                server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Sent task assignment email to %s", recipient_email)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", recipient_email, exc)
