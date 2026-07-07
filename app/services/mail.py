from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import NameEmail

from app.core.config import settings

template_path = Path(__file__).resolve().parents[2] / 'templates'

conf = ConnectionConfig(
    MAIL_USERNAME = settings.SMTP_USERNAME,
    MAIL_PASSWORD = settings.SMTP_PASSWORD,
    MAIL_FROM = settings.SMTP_SENDER,
    MAIL_PORT = settings.SMTP_PORT,
    MAIL_SERVER = settings.SMTP_HOST,
    MAIL_FROM_NAME = settings.EMAIL_FROM_NAME,
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER = template_path,
)

fm = FastMail(conf)

async def send_email_async(
        subject: str,
        email_to: str,
        body: Optional[dict[str, Any]],
        template: str
):

    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        template_body=body,
        subtype=MessageType.html,
    )

    await fm.send_message(message, template_name=template)

def send_email_background(
        background_tasks: BackgroundTasks,
        subject: str,
        email_to: str, # NameEmail,
        body: dict,
        template: str
):

    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        template_body=body,
        subtype=MessageType.html,
    )

    background_tasks.add_task(fm.send_message, message, template_name=template)