from fastapi import FastAPI
from app.config import APP_NAME, APP_VERSION, APP_ENV
from Models.message import Message

app = FastAPI()


@app.get("/")
def get_root():
    return {"Miapp": APP_NAME,
            "version": APP_VERSION,
            "environment": APP_ENV}


@app.get("/health")
def health_check():
    return {"status": "ok", 
            "app": APP_NAME}

@app.get("/about")
def about():
    return {"message": "This is an AI Document Assistant API built with FastAPI."}

@app.post("/chat")
def chat(message: Message):
    return {"received": message.message}