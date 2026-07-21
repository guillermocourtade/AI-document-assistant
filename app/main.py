from fastapi import FastAPI

from app.config import APP_NAME, APP_VERSION
from app.exceptions.handlers import register_exception_handlers
from app.routers import chat, documents, system


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

register_exception_handlers(app)

app.include_router(system.router)
app.include_router(documents.router)
app.include_router(chat.router)