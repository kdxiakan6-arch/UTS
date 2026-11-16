
import argparse
import asyncio

import database as db

VEHICLES = [
    ("Toyota Avanza", "MPV", "KB 1001 AA", 350000, 100),
    ("Honda Brio", "City Car", "KB 1002 AB", 300000, 100),
    ("Toyota Innova Reborn", "MPV", "KB 1003 AC", 550000, 100),
    ("Daihatsu Xenia", "MPV", "KB 1004 AD", 330000, 100),
    ("Suzuki Ertiga", "MPV", "KB 1005 AE", 340000, 100),
    ("Mitsubishi Xpander", "MPV", "KB 1006 AF", 400000, 100),
    ("Toyota Fortuner", "SUV", "KB 1007 AG", 900000, 100),
    ("Honda Vario 160", "Motor", "KB 2001 BA", 100000, 100),
    ("Yamaha NMAX", "Motor", "KB 2002 BB", 130000, 100),
    ("Honda Beat", "Motor", "KB 2003 BC", 80000, 100),
    ("Toyota Hiace", "Van", "KB 3001 CA", 1100000, 100),
    ("Isuzu Elf", "Minibus", "KB 3002 CB", 1300000, 100),
]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-stok", type=int, help="set stok ke nilai ini")
    parser.add_argument("--id", type=int, default=1, help="id kendaraan untuk --reset-stok")
    parser.add_argument("--fresh", action="store_true", help="hapus semua data lalu seed ulang")
    args = parser.parse_args()

    await db.init_db()

    if args.reset_stok is not None:
        async with db.get_conn() as conn:
            await conn.execute("UPDATE vehicles SET stok=? WHERE id=?", (args.reset_stok, args.id))
            await conn.commit()
        print(f"Stok kendaraan id={args.id} diset ke {args.reset_stok}")
        return

    if args.fresh:
        async with db.get_conn() as conn:
            await conn.execute("DELETE FROM transactions")
            await conn.execute("DELETE FROM vehicles")
            await conn.execute("DELETE FROM sqlite_sequence")
            await conn.commit()

    if await db.list_vehicles(0, 1):
        print("Data sudah ada; gunakan --fresh untuk seed ulang.")
        return

    for nama, jenis, plat, harga, stok in VEHICLES:
        await db.insert_vehicle(
            {"nama": nama, "jenis": jenis, "plat_nomor": plat, "harga_per_hari": harga, "stok": stok}
        )
    print(f"Berhasil menambahkan {len(VEHICLES)} kendaraan.")


if __name__ == "__main__":
    asyncio.run(main())
