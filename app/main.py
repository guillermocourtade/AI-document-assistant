from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "AI Document Assistant API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}