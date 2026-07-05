from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import create_app, settings
from app.api.v1.router import api_v1_router

app = create_app()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):  # noqa: ARG001
    detail = exc.errors()[0]["msg"]
    return JSONResponse(status_code=422, content={"detail": detail})


app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
