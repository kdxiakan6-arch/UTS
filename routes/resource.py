"""routes/resource.py: endpoint CRUD resource utama (kendaraan)."""
import sqlite3

from fastapi import APIRouter, HTTPException, Query, status

import database as db
from models import VehicleCreate, VehicleOut, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["Kendaraan"])


@router.get("", response_model=list[VehicleOut])
async def list_vehicles(skip: int = Query(0, ge=0), limit: int = Query(10, ge=1, le=100)):
    # Operasi aiosqlite: `await` melepas event loop selama menunggu I/O disk.
    return await db.list_vehicles(skip, limit)


@router.get("/{vehicle_id}", response_model=VehicleOut)
async def get_vehicle(vehicle_id: int):
    vehicle = await db.get_vehicle(vehicle_id)
    if vehicle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kendaraan tidak ditemukan")
    return vehicle


@router.post("", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
async def create_vehicle(data: VehicleCreate):
    try:
        new_id = await db.insert_vehicle(data.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plat nomor sudah terdaftar")
    return await db.get_vehicle(new_id)


@router.put("/{vehicle_id}", response_model=VehicleOut)
async def update_vehicle(vehicle_id: int, data: VehicleUpdate):
    try:
        found = await db.update_vehicle(vehicle_id, data.model_dump())
    except sqlite3.IntegrityError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plat nomor sudah terdaftar")
    if not found:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kendaraan tidak ditemukan")
    return await db.get_vehicle(vehicle_id)  # data terbaru


@router.delete("/{vehicle_id}")
async def delete_vehicle(vehicle_id: int):
    if not await db.delete_vehicle(vehicle_id):  # hard delete
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kendaraan tidak ditemukan")
    return {"message": f"Kendaraan {vehicle_id} dihapus permanen"}
