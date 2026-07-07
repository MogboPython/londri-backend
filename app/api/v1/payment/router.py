import json

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.services.webhook import run_webhook_processing, verify_nomba_signature

router = APIRouter(prefix="/payment", tags=["Payment Webhooks"])


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Nomba payment webhook",
)
async def payment_webhook(request: Request, background_tasks: BackgroundTasks):
     # TODO: remove
    req_json = await request.json()
    print(req_json)

    raw_body = await request.body()
    body = json.loads(raw_body)

    if not verify_nomba_signature(body, dict(request.headers)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    background_tasks.add_task(run_webhook_processing, body)

    return {"status": "ok"}

# TODO: set up subscription payment
