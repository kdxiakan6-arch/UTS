"""main.py: inisialisasi FastAPI dan registrasi router."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

import database as db
from routes import resource, transaction


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()  # buat tabel bila belum ada (aman dijalankan tiap worker)
    yield


app = FastAPI(title="API Rental Kendaraan", version="1.0.0", lifespan=lifespan)
app.include_router(resource.router)
app.include_router(transaction.router)


@app.get("/", tags=["Root"])
async def root():
    return {"message": "API Rental Kendaraan", "docs": "/docs"}
