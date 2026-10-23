"""
main.py
Standalone FastAPI app for the market growth analysis.

Run:   python main.py
Open:  http://127.0.0.1:8000        (dashboard)
       http://127.0.0.1:8000/docs   (API docs)
"""
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse

from market_analysis.router import router as market_router

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Market Growth Analysis", version="1.0.0")
app.include_router(market_router)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
