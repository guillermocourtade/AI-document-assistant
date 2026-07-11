from fastapi import FastAPI
from app.routers import system, chat

app = FastAPI()

app.include_router(system.router)
app.include_router(chat.router)