"""
app_log.py
----------
Oyunun TÜM konsol çıktısını (auth_manager, save_manager, audio_manager,
main.py vb. içindeki onlarca print("[Hata] ...") satırı DAHİL) tek bir
log dosyasında toplar.

Bu satırlar önceden sadece konsola yazılıyordu - özellikle konsolsuz
çalışan bir .exe'de bu çıktılar hiçbir yere kaydedilmeden anında
kayboluyordu. Tek tek her print() çağrısını değiştirmek yerine,
sys.stdout ve sys.stderr'i hem orijinaline hem de bu dosyaya birden
yazan bir "Tee" ile değiştiriyoruz - böylece TÜM modüllerdeki mevcut
print() çağrıları, hiçbiri değiştirilmeden, otomatik olarak bu dosyaya
da düşüyor.

Bilet gönderirken bu dosyanın son kısmı (bkz. get_log_tail) tek
tuşla mesaja eklenebilir - destek ekibinin sorunu teşhis etmesini
kolaylaştırır.
"""

import os
import sys
import time
import appdirs


APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
LOG_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
LOG_FILE_PATH = os.path.join(LOG_DIR, "karaborsa.log")

# Dosya sonsuza kadar büyümesin diye bir üst sınır koyuyoruz; aşılırsa
# dosya sıfırlanıp yeniden başlanır (basit bir rotasyon).
MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MB

_initialized = False


class _Tee:
    """Yazılan her şeyi hem orijinal akışa (konsol varsa) hem de log
    dosyasına aynı anda yazar. write()/flush() dışında bir şey
    uygulamıyor - sys.stdout'un yerine geçebilmesi için yeterli."""

    def __init__(self, original_stream, log_file):
        self._original = original_stream
        self._log_file = log_file

    def write(self, data):
        try:
            if self._original:
                self._original.write(data)
        except Exception:
            pass
        try:
            self._log_file.write(data)
            self._log_file.flush()
        except Exception:
            pass

    def flush(self):
        try:
            if self._original:
                self._original.flush()
        except Exception:
            pass
        try:
            self._log_file.flush()
        except Exception:
            pass


def init_logging() -> None:
    """Uygulama açılışında, MÜMKÜN OLDUĞUNCA ERKEN (main.py'nin en
    başında) BİR KEZ çağrılır. sys.stdout ve sys.stderr'i log
    dosyasına da yazacak şekilde değiştirir.

    Loglama herhangi bir sebeple başlatılamazsa (yazma izni yok vb.)
    sessizce atlanır - bu oyunun açılışını ASLA engellememeli."""
    global _initialized
    if _initialized:
        return

    try:
        os.makedirs(LOG_DIR, exist_ok=True)

        if os.path.exists(LOG_FILE_PATH) and os.path.getsize(LOG_FILE_PATH) > MAX_LOG_BYTES:
            os.remove(LOG_FILE_PATH)

        log_file = open(LOG_FILE_PATH, "a", encoding="utf-8", buffering=1)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        log_file.write(f"\n===== Oyun açıldı: {timestamp} =====\n")

        sys.stdout = _Tee(sys.stdout, log_file)
        sys.stderr = _Tee(sys.stderr, log_file)
        _initialized = True
    except Exception:
        pass


def get_log_tail(max_chars: int = 8000) -> str:
    """Log dosyasının SON kısmını (varsayılan ~8000 karakter) döndürür
    - bilet mesajına eklemek için. Dosya yoksa/okunamazsa boş string
    döner."""
    try:
        if not os.path.exists(LOG_FILE_PATH):
            return ""
        with open(LOG_FILE_PATH, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            read_size = min(size, max_chars)
            f.seek(max(0, size - read_size))
            return f.read()
    except Exception as e:
        return f"(Log dosyası okunamadı: {e})"
