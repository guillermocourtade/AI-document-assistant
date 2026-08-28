from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION
from app.exceptions.handlers import register_exception_handlers
from app.routers import chat, documents, system


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(system.router)
app.include_router(documents.router)
app.include_router(chat.router)
