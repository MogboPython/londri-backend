import json

from fastapi import BackgroundTasks, Depends
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from app import get_twilio_client, logger
from app.core.config import settings

content_templates = {
    "otp": "HXc8c283ba4b8ce188f93840a263bcfa7f",
    "order_update": "HX7749c02a8ea736f950ef02d53bc2732e",
}

def _normalize_whatsapp_number(phone_number: str) -> str:
    if not phone_number.startswith("+"):
        raise ValueError(f"Phone number must be in E.164 format: {phone_number}")
    return f"whatsapp:{phone_number}"


class WhatsAppService:
    def __init__(self, twilio_client: Client) -> None:
        self.twilio_client = twilio_client
        self.from_number = settings.TWILIO_WHATSAPP_FROM

    def _send(self, *, content_sid: str, content_variables: dict, to: str) -> None:
        try:
            to_number = _normalize_whatsapp_number(to)
            message = self.twilio_client.messages.create(
                from_=self.from_number,
                content_sid=content_sid,
                content_variables=json.dumps(content_variables),
                to=to_number,
            )
            logger.info("WhatsApp message queued: sid=%s to=%s", message.sid, to_number)
        except (TwilioRestException, ValueError):
            logger.exception("Failed to send WhatsApp message to %s", to)

    def send_otp_to_number(
        self,
        background_tasks: BackgroundTasks,
        phone_number: str,
        otp: str,
    ) -> None:
        background_tasks.add_task(
            self._send,
            content_sid=content_templates["otp"],
            content_variables={"1": otp},
            to=phone_number,
        )

    def send_order_update_to_number(
        self,
        background_tasks: BackgroundTasks,
        name: str,
        phone_number: str,
        order_id: str,
        order_update: str,
    ) -> None:
        background_tasks.add_task(
            self._send,
            content_sid=content_templates["order_update"],
            content_variables={
                "first_name": name,
                "order_number": order_id,
                "status": order_update,
            },
            to=phone_number,
        )

def get_whatsapp_service(twilio_client: Client = Depends(get_twilio_client)) -> WhatsAppService:
    return WhatsAppService(twilio_client)
