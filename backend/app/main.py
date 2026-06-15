"""FastAPI application — wrapped by Mangum for API Gateway HTTP API."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from app import settings
from app.routers import (
    admin_routes,
    auth_routes,
    chat_routes,
    feedback_routes,
    lens_routes,
    user_routes,
)

app = FastAPI(title="FinWing API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(lens_routes.router)
app.include_router(chat_routes.router)
app.include_router(feedback_routes.router)
app.include_router(admin_routes.router)


@app.get("/health")
def health():
    return {"status": "ok", "env": settings.ENV}


@app.exception_handler(Exception)
def unhandled(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL", "message": "Something went wrong. Please try again."},
    )


handler = Mangum(app)
