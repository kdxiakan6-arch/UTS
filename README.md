VIDEO PRESENTASI: https://youtu.be/GANTI_DENGAN_TAUTAN_VIDEO_UNLISTED


REST API rental kendaraan: FastAPI + SQLite (aiosqlite) + BackgroundTasks + asyncio.Lock.

## Instalasi
```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                   # isi 12 data kendaraan
```

## Menjalankan
```bash
uvicorn main:app --port 8000                # 1 worker
uvicorn main:app --workers 4 --port 8000    # 4 worker
```
Swagger UI: http://127.0.0.1:8000/docs

## Pengujian race condition (B3)
Tahap 1 (tanpa lock):
```bash
python seed.py --reset-stok 1 --id 1
# Linux/Mac: STOK_MODE=nolock uvicorn main:app --port 8000
# Windows PowerShell: $env:STOK_MODE="nolock"; uvicorn main:app --port 8000
python test_race.py     # terminal kedua: dua-duanya 202, stok akhir -1
```
Tahap 2 (dengan lock, default):
```bash
python seed.py --reset-stok 1 --id 1
uvicorn main:app --port 8000
python test_race.py     # satu 202, satu 409 Conflict, stok akhir 0
```

## Benchmark (C1)
Jalankan server (1 worker, lalu 4 worker), kemudian di terminal lain:
```bash
locust -f locustfile.py ReadUser  --headless -u 20 -r 20 --host http://127.0.0.1:8000
locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000
```
Salin angka dari "RINGKASAN UNTUK TABEL LAPORAN" ke tabel laporan.
Jalankan `python seed.py --fresh` sebelum tiap putaran agar stok kembali 100.
