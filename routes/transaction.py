"""routes/transaction.py: transaksi sewa dengan BackgroundTasks + pengamanan stok (Lock)."""
import asyncio
import os

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

import database as db
from models import TransactionAccepted, TransactionCreate, TransactionOut, TrxStatus

router = APIRouter(prefix="/transactions", tags=["Transaksi Sewa"])

# ---------------------------------------------------------------------------
# Pemotongan stok: dua versi untuk demonstrasi race condition (B3).
# Pilih versi lewat env var:  STOK_MODE=nolock (Tahap 1)  |  STOK_MODE=lock (Tahap 2, default)
# ---------------------------------------------------------------------------

# Gembok konkurensi tingkat modul. asyncio.Lock hanya "mengunci" coroutine di
# dalam SATU event loop (satu proses). Antar worker Uvicorn tidak saling melihat lock ini.
stok_lock = asyncio.Lock()


async def potong_stok_tanpa_lock(item_id: int, qty: int) -> bool:
    """VERSI 1 (rawan race condition): baca -> jeda -> tulis tanpa pengaman."""
    stok_terkini = await db.get_stok(item_id)
    # Jeda buatan: `await` menyerahkan kendali ke event loop, sehingga request lain
    # ikut membaca stok yang SAMA sebelum stok sempat dikurangi.
    await asyncio.sleep(0.01)
    if stok_terkini is None or stok_terkini < qty:
        return False
    await db.decrement_stok(item_id, qty)  # kedua request lolos -> stok bisa minus
    return True


async def potong_stok_dengan_lock(item_id: int, qty: int) -> bool:
    """VERSI 2 (aman): critical section dilindungi asyncio.Lock."""
    # Hanya satu coroutine yang boleh berada di blok ini; coroutine lain antre
    # di `async with` sampai lock dilepas. Jadi baca-cek-tulis menjadi atomik.
    async with stok_lock:
        stok_terkini = await db.get_stok(item_id)
        await asyncio.sleep(0.01)  # jeda tetap ada, tapi kini tidak berbahaya
        if stok_terkini is None or stok_terkini < qty:
            return False
        # guard=True: lapis pengaman tambahan di SQL untuk skenario multi-worker
        return await db.decrement_stok(item_id, qty, guard=True)


potong_stok = potong_stok_tanpa_lock if os.getenv("STOK_MODE", "lock") == "nolock" else potong_stok_dengan_lock


# ---------------------------------------------------------------------------
# Pekerja latar belakang (fungsi internal Python, BUKAN endpoint HTTP)
# ---------------------------------------------------------------------------
async def proses_transaksi_background(trx_id: int, item_id: int, qty: int) -> None:
    try:
        # 1. pending -> processing
        await db.update_trx_status(trx_id, "processing")
        # 2. Simulasi pekerjaan I/O (verifikasi dokumen/pembayaran). asyncio.sleep tidak
        #    memblokir event loop, jadi request lain tetap dilayani selama 3 detik ini.
        await asyncio.sleep(3)
        # 3. processing -> completed
        await db.update_trx_status(trx_id, "completed", "Penyewaan berhasil diproses")
    except Exception as exc:  # noqa: BLE001
        # Gagal: kembalikan stok agar tidak "hilang", tandai transaksi failed.
        await db.increment_stok(item_id, qty)
        await db.update_trx_status(trx_id, "failed", f"Gagal: {exc}")


# ---------------------------------------------------------------------------
# Endpoint HTTP
# ---------------------------------------------------------------------------
@router.post("", response_model=TransactionAccepted, status_code=status.HTTP_202_ACCEPTED)
async def create_transaction(data: TransactionCreate, bg: BackgroundTasks):
    # Validasi: kendaraan harus terdaftar
    vehicle = await db.get_vehicle(data.item_id)
    if vehicle is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kendaraan tidak ditemukan")

    # Validasi stok + pemotongan stok (dilindungi lock pada mode default)
    if not await potong_stok(data.item_id, data.qty):
        raise HTTPException(status.HTTP_409_CONFLICT, "Stok habis atau tidak mencukupi")

    total = vehicle["harga_per_hari"] * data.qty * data.hari
    trx_id = await db.insert_transaction(data.item_id, data.qty, data.penyewa, data.hari, total, "pending")

    # Jadwalkan pekerjaan latar belakang; respons langsung dikirim tanpa menunggu 3 detik.
    bg.add_task(proses_transaksi_background, trx_id, data.item_id, data.qty)
    return {"id": trx_id, "status": "pending", "message": "Transaksi diproses"}


@router.get("", response_model=list[TransactionOut])
async def list_transactions(
    status_filter: TrxStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
):
    return await db.list_transactions(status_filter, skip, limit)


@router.get("/{trx_id}", response_model=TransactionOut)
async def get_transaction(trx_id: int):
    trx = await db.get_transaction(trx_id)
    if trx is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaksi tidak ditemukan")
    return trx
