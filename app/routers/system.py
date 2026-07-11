from fastapi import APIRouter
from app.config import APP_NAME, APP_VERSION, APP_ENV

router = APIRouter()

@router.get("/")
def get_root():
    return {"Miapp": APP_NAME,
            "version": APP_VERSION,
            "environment": APP_ENV}


@router.get("/health")
def health_check():
    return {"status": "ok", 
            "app": APP_NAME}

@router.get("/about")
def about():
    return {"message": "This is an AI Document Assistant API built with FastAPI."}
