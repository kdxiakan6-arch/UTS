"""locustfile.py: skenario pengujian beban (C1).

Skenario Read : GET /vehicles      -> 100 request, konkurensi 20  (kelas ReadUser)
Skenario Write: POST /transactions ->  50 request, konkurensi 10  (kelas WriteUser)

Jalankan (server harus sudah hidup di port 8000):
  locust -f locustfile.py ReadUser  --headless -u 20 -r 20 --host http://127.0.0.1:8000
  locust -f locustfile.py WriteUser --headless -u 10 -r 10 --host http://127.0.0.1:8000
Locust berhenti otomatis setelah jumlah request target selesai, lalu mencetak ringkasan.
"""
import random

from locust import HttpUser, events, task
from locust.exception import StopUser

TARGET = {"read": 100, "write": 50}
sent = {"read": 0, "write": 0}   # request yang sudah dikirim (agar tidak melebihi target)
done = {"read": 0, "write": 0}   # request yang sudah selesai


def _claim(kind: str) -> bool:
    """Ambil 'jatah' request; False bila target sudah tercapai."""
    if sent[kind] >= TARGET[kind]:
        return False
    sent[kind] += 1
    return True


class ReadUser(HttpUser):
    """Skenario Read: GET /vehicles (I/O-bound ringan)."""

    def on_start(self):
        self.kind = "read"

    @task
    def list_vehicles(self):
        if not _claim("read"):
            raise StopUser()
        self.client.get("/vehicles?skip=0&limit=10", name="GET /vehicles")
        done["read"] += 1
        if done["read"] >= TARGET["read"]:
            self.environment.runner.quit()


class WriteUser(HttpUser):
    """Skenario Write: POST /transactions (kendaraan id 2-12, stok seed 100 per unit)."""

    @task
    def create_transaction(self):
        if not _claim("write"):
            raise StopUser()
        payload = {"item_id": random.randint(2, 12), "qty": 1, "penyewa": "Locust", "hari": 1}
        self.client.post("/transactions", json=payload, name="POST /transactions")
        done["write"] += 1
        if done["write"] >= TARGET["write"]:
            self.environment.runner.quit()


@events.quitting.add_listener
def print_summary(environment, **kwargs):
    """Cetak metrik untuk tabel laporan: total waktu, throughput, rata-rata latensi."""
    t = environment.stats.total
    if not t.num_requests:
        return
    elapsed = max(t.last_request_timestamp - t.start_time, 0.001)
    print("\n=========== RINGKASAN UNTUK TABEL LAPORAN ===========")
    print(f"Total request     : {t.num_requests} (gagal: {t.num_failures})")
    print(f"Total waktu       : {elapsed:.2f} detik")
    print(f"Throughput        : {t.num_requests / elapsed:.2f} req/detik")
    print(f"Rata-rata latensi : {t.avg_response_time:.2f} ms")
    print("=====================================================")
