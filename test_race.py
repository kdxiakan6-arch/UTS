"""test_race.py: kirim 2 request serentak ke POST /transactions untuk stok tersisa 1."""
import asyncio

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> None:
    url = f"{BASE}/transactions"
    payload = {"item_id": 1, "qty": 1, "penyewa": "Tester", "hari": 1}

    async with httpx.AsyncClient(timeout=30) as client:
        # Kirim dua request secara serentak (asyncio.gather)
        req1 = client.post(url, json=payload)
        req2 = client.post(url, json=payload)
        res1, res2 = await asyncio.gather(req1, req2)

        print("Respon Request 1:", res1.status_code, res1.json())
        print("Respon Request 2:", res2.status_code, res2.json())

        stok = (await client.get(f"{BASE}/vehicles/1")).json()["stok"]
        print("Stok akhir kendaraan id=1:", stok)


if __name__ == "__main__":
    asyncio.run(main())
