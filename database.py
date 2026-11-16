"""database.py: koneksi aiosqlite, inisialisasi tabel, dan seluruh query.

Semua operasi DB bersifat async (non-blocking) memakai aiosqlite, sehingga
event loop FastAPI tetap bisa melayani request lain selama menunggu I/O.
Setiap operasi membuka koneksi sendiri (aman untuk multi-worker Uvicorn,
karena tiap proses worker punya event loop dan koneksinya sendiri).
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime

import aiosqlite

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rental.db"))

# Resource utama: kendaraan. Kolom `stok` = jumlah unit tersedia (kolom kuantitas).
# Catatan: sengaja TANPA CHECK(stok >= 0) agar overselling (stok minus) bisa
# diperagakan pada Tahap 1 test_race.py. Perlindungan stok diatur oleh Lock + validasi.
CREATE_VEHICLES_TABLE = """
CREATE TABLE IF NOT EXISTS vehicles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nama TEXT NOT NULL,
    jenis TEXT NOT NULL,
    plat_nomor TEXT NOT NULL UNIQUE,
    harga_per_hari REAL NOT NULL,
    stok INTEGER NOT NULL
);
"""

# Resource transaksi: penyewaan kendaraan.
CREATE_TRANSACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    qty INTEGER NOT NULL,
    penyewa TEXT NOT NULL,
    hari INTEGER NOT NULL,
    total_harga REAL NOT NULL,
    status TEXT NOT NULL,
    pesan TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@asynccontextmanager
async def get_conn():
    """Buka koneksi aiosqlite; timeout menunggu lock file SQLite (multi-worker)."""
    async with aiosqlite.connect(DB_PATH, timeout=30) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def init_db() -> None:
    async with get_conn() as conn:
        await conn.execute("PRAGMA journal_mode=WAL")  # baca/tulis lebih lancar saat multi-worker
        await conn.execute(CREATE_VEHICLES_TABLE)
        await conn.execute(CREATE_TRANSACTIONS_TABLE)
        await conn.commit()


# ------------------------------------------------------------------ CRUD kendaraan
async def list_vehicles(skip: int, limit: int) -> list[dict]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM vehicles ORDER BY id LIMIT ? OFFSET ?", (limit, skip))
        return [dict(r) for r in await cur.fetchall()]


async def get_vehicle(vehicle_id: int) -> dict | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def insert_vehicle(data: dict) -> int:
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO vehicles (nama, jenis, plat_nomor, harga_per_hari, stok) VALUES (?,?,?,?,?)",
            (data["nama"], data["jenis"], data["plat_nomor"], data["harga_per_hari"], data["stok"]),
        )
        await conn.commit()
        return cur.lastrowid


async def update_vehicle(vehicle_id: int, data: dict) -> bool:
    async with get_conn() as conn:
        cur = await conn.execute(
            "UPDATE vehicles SET nama=?, jenis=?, plat_nomor=?, harga_per_hari=?, stok=? WHERE id=?",
            (data["nama"], data["jenis"], data["plat_nomor"], data["harga_per_hari"], data["stok"], vehicle_id),
        )
        await conn.commit()
        return cur.rowcount > 0


async def delete_vehicle(vehicle_id: int) -> bool:
    """Hard delete: baris dihapus permanen dari basis data."""
    async with get_conn() as conn:
        cur = await conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
        await conn.commit()
        return cur.rowcount > 0


# ------------------------------------------------------------------ operasi stok
async def get_stok(item_id: int) -> int | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT stok FROM vehicles WHERE id = ?", (item_id,))
        row = await cur.fetchone()
        return row["stok"] if row else None


async def decrement_stok(item_id: int, qty: int, guard: bool = False) -> bool:
    """Kurangi stok.

    guard=False : UPDATE tanpa syarat (dipakai versi tanpa lock -> bisa minus).
    guard=True  : UPDATE atomik di level SQL (`AND stok >= qty`) sebagai lapis
                  pengaman tambahan, karena asyncio.Lock hanya berlaku di dalam
                  SATU proses (tidak melindungi antar-worker Uvicorn).
    """
    async with get_conn() as conn:
        if guard:
            cur = await conn.execute(
                "UPDATE vehicles SET stok = stok - ? WHERE id = ? AND stok >= ?", (qty, item_id, qty)
            )
        else:
            cur = await conn.execute("UPDATE vehicles SET stok = stok - ? WHERE id = ?", (qty, item_id))
        await conn.commit()
        return cur.rowcount > 0


async def increment_stok(item_id: int, qty: int) -> None:
    """Kembalikan stok (dipakai bila transaksi gagal)."""
    async with get_conn() as conn:
        await conn.execute("UPDATE vehicles SET stok = stok + ? WHERE id = ?", (qty, item_id))
        await conn.commit()


# ------------------------------------------------------------------ transaksi
async def insert_transaction(item_id: int, qty: int, penyewa: str, hari: int,
                             total_harga: float, status: str = "pending") -> int:
    now = _now()
    async with get_conn() as conn:
        cur = await conn.execute(
            "INSERT INTO transactions (item_id, qty, penyewa, hari, total_harga, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (item_id, qty, penyewa, hari, total_harga, status, now, now),
        )
        await conn.commit()
        return cur.lastrowid


async def update_trx_status(trx_id: int, status: str, pesan: str | None = None) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE transactions SET status=?, pesan=COALESCE(?, pesan), updated_at=? WHERE id=?",
            (status, pesan, _now(), trx_id),
        )
        await conn.commit()


async def get_transaction(trx_id: int) -> dict | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM transactions WHERE id = ?", (trx_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_transactions(status: str | None, skip: int, limit: int) -> list[dict]:
    query, params = "SELECT * FROM transactions", []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, skip]
    async with get_conn() as conn:
        cur = await conn.execute(query, params)
        return [dict(r) for r in await cur.fetchall()]
