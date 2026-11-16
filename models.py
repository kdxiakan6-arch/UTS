"""models.py: skema Pydantic untuk validasi request dan serialisasi response."""
from typing import Literal

from pydantic import BaseModel, Field


class VehicleBase(BaseModel):
    nama: str = Field(..., min_length=1, max_length=100, examples=["Toyota Avanza"])
    jenis: str = Field(..., min_length=1, max_length=50, examples=["MPV"])
    plat_nomor: str = Field(..., min_length=3, max_length=15, examples=["KB 1234 AB"])
    harga_per_hari: float = Field(..., gt=0, examples=[350000])
    stok: int = Field(..., ge=0, examples=[5], description="Jumlah unit tersedia")


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(VehicleBase):
    pass


class VehicleOut(VehicleBase):
    id: int
    stok: int


class TransactionCreate(BaseModel):
    item_id: int = Field(..., description="ID kendaraan yang disewa")
    qty: int = Field(..., ge=1, description="Jumlah unit")
    penyewa: str = Field("Anonim", min_length=1, max_length=100)
    hari: int = Field(1, ge=1, le=365, description="Lama sewa (hari)")


class TransactionAccepted(BaseModel):
    id: int
    status: str
    message: str


TrxStatus = Literal["pending", "processing", "completed", "failed"]


class TransactionOut(BaseModel):
    id: int
    item_id: int
    qty: int
    penyewa: str
    hari: int
    total_harga: float
    status: TrxStatus
    pesan: str | None = None
    created_at: str
    updated_at: str
