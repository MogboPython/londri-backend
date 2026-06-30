from pathlib import Path
from typing import Any, Optional
from fastapi import BackgroundTasks

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from pydantic import NameEmail

from app.core.config import get_settings

settings = get_settings()

conf = ConnectionConfig(
    MAIL_USERNAME =  str(settings.SMTP_USERNAME),
    MAIL_PASSWORD = settings.SMTP_PASSWORD,
    MAIL_FROM = settings.SMTP_USERNAME,
    MAIL_PORT = settings.SMTP_PORT,
    MAIL_SERVER = settings.SMTP_SERVER,
    MAIL_FROM_NAME = settings.SMTP_FROM_NAME,
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS=True,
    TEMPLATE_FOLDER = Path(__file__).resolve().parents[1] / 'templates',
)

async def send_email_async(
        subject: str,
        email_to: NameEmail,
        body: Optional[dict[str, Any]],
        template: str
):

    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        template_body=body,
        subtype=MessageType.html,
    )
    fm = FastMail(conf)

    await fm.send_message(message, template_name=template)

def send_email_background(
        background_tasks: BackgroundTasks,
        subject: str,
        email_to: NameEmail,
        body: dict,
        template: str
):

    message = MessageSchema(
        subject=subject,
        recipients=[email_to],
        template_body=body,
        subtype=MessageType.html,
    )
    fm = FastMail(conf)
    background_tasks.add_task(fm.send_message, message, template_name=template)