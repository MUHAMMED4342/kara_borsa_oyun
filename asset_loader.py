"""
asset_loader.py
---------------
Çalışma zamanında assets.dat paket dosyasından varlıkları okuyan modül.

Bu modül, asset_packer.py tarafından oluşturulan .dat formatını okur ve:
  - Dosya tablosunu belleğe yükler (tembel - ilk erişimde)
  - İstenen bir varlığın ham byte'larını döndürür
  - Ses dosyaları için geçici dosyaya yazarak pygame'in çalabileceği
    bir yol sağlar (opsiyonel)
  - Metin dosyaları için doğrudan string döndürür

asset_packer.py ile uyumlu DAT formatı:
  [4 byte] Sihirli sayı: b'KBSA'
  [4 byte] Versiyon (uint32 LE)
  [4 byte] Tablo uzunluğu (uint32 LE)
  [N byte] JSON tablo
  [...]    Ham veri

Kullanım:
  from asset_loader import AssetPack
  pack = AssetPack("assets.dat")
  raw_bytes = pack.read_bytes("sounds/para.mp3")
  text = pack.read_text("insanlar.txt")
  temp_path = pack.extract_temp("sounds/1.mp3")
"""

import io
import json
import os
import struct
import sys
import tempfile
import atexit
import shutil

MAGIC = b"KBSA"
EXPECTED_VERSION = 1


class AssetPack:
    """Tek bir .dat paket dosyasından varlıkları okuyan sınıf."""

    def __init__(self, dat_path: str):
        self.dat_path = dat_path
        self._table = None
        self._data_offset = 0
        self._file_handle = None

        # Geçici dosya önbelleği: relative_key -> geçici dosya yolu
        # Pygame ses dosyalarını dosya yolundan okuduğu için geçici
        # dosyaya çıkarmak gerekebilir.
        self._temp_dir = None
        self._temp_cache = {}

        # Program kapanırken geçici dizini temizle
        atexit.register(self._cleanup)

    def _ensure_loaded(self) -> None:
        """Dosya tablosunu henüz yüklenmemişse yükler (tembel başlatma)."""
        if self._table is not None:
            return

        if not os.path.isfile(self.dat_path):
            raise FileNotFoundError(f"Varlık paketi bulunamadı: {self.dat_path}")

        with open(self.dat_path, "rb") as f:
            # Sihirli sayı
            magic = f.read(4)
            if magic != MAGIC:
                raise ValueError(
                    f"Geçersiz varlık paketi formatı: beklenen {MAGIC!r}, "
                    f"bulunan {magic!r}"
                )

            # Versiyon
            version = struct.unpack("<I", f.read(4))[0]
            if version != EXPECTED_VERSION:
                raise ValueError(
                    f"Desteklenmeyen varlık paketi versiyonu: {version} "
                    f"(beklenen: {EXPECTED_VERSION})"
                )

            # Tablo uzunluğu
            table_length = struct.unpack("<I", f.read(4))[0]

            # Tabloyu oku
            table_json = f.read(table_length)
            self._table = json.loads(table_json.decode("utf-8"))
            self._lower_map = {k.replace("\\", "/").lower(): k for k in self._table}

            # Veri bloğunun başlangıç ofseti
            self._data_offset = 4 + 4 + 4 + table_length

        print(f"[AssetPack] Yüklendi: {self.dat_path} "
              f"({len(self._table)} dosya)")

    def _resolve_key(self, relative_key: str) -> str:
        """Anahtarı normalize eder (büyük/küçük harf ve eğik çizgi duyarsız)."""
        self._ensure_loaded()
        if relative_key in self._table:
            return relative_key
        norm = relative_key.replace("\\", "/").lower()
        return self._lower_map.get(norm)

    def contains(self, relative_key: str) -> bool:
        """Verilen anahtarın pakette olup olmadığını kontrol eder."""
        self._ensure_loaded()
        return self._resolve_key(relative_key) is not None

    def list_files(self) -> list:
        """Paketteki tüm dosya anahtarlarını döner."""
        self._ensure_loaded()
        return list(self._table.keys())

    def read_bytes(self, relative_key: str) -> bytes:
        """Verilen anahtara ait dosyanın ham byte'larını döndürür."""
        self._ensure_loaded()
        actual_key = self._resolve_key(relative_key)
        if actual_key is None:
            raise KeyError(f"Varlık bulunamadı: {relative_key}")

        entry = self._table[actual_key]
        offset = self._data_offset + entry["offset"]
        size = entry["size"]

        with open(self.dat_path, "rb") as f:
            f.seek(offset)
            data = f.read(size)

        if len(data) != size:
            raise IOError(
                f"Eksik veri: {relative_key} için {size} byte bekleniyordu, "
                f"{len(data)} byte okundu"
            )

        return data

    def read_text(self, relative_key: str, encoding: str = "utf-8") -> str:
        """Verilen anahtara ait metin dosyasının içeriğini string olarak döndürür."""
        return self.read_bytes(relative_key).decode(encoding)

    def open_bytes_io(self, relative_key: str) -> io.BytesIO:
        """Verilen anahtara ait dosyayı BytesIO nesnesi olarak döndürür.
        pygame.mixer.Sound(file=...) gibi dosya benzeri nesne kabul eden
        API'ler için kullanılabilir."""
        return io.BytesIO(self.read_bytes(relative_key))

    def extract_temp(self, relative_key: str) -> str:
        """Verilen anahtara ait dosyayı geçici bir dosyaya çıkarır ve
        yolunu döndürür. Aynı anahtar tekrar istenirse önbellekten döner.

        Bu, pygame.mixer.music.load() gibi SADECE dosya yolu kabul eden
        API'ler için gereklidir.
        """
        self._ensure_loaded()
        actual_key = self._resolve_key(relative_key)
        if actual_key is None:
            raise KeyError(f"Varlık bulunamadı: {relative_key}")

        # Önbellekte varsa ve hâlâ dosya mevcutsa doğrudan dön
        if actual_key in self._temp_cache:
            cached_path = self._temp_cache[actual_key]
            if os.path.isfile(cached_path):
                return cached_path

        # Geçici dizin oluştur
        if self._temp_dir is None:
            self._temp_dir = tempfile.mkdtemp(prefix="kbsa_")

        # Orijinal dosya yapısını koru (alt klasörler dahil)
        # "sounds/para.mp3" -> temp_dir/sounds/para.mp3
        rel_parts = actual_key.replace("/", os.sep)
        temp_path = os.path.join(self._temp_dir, rel_parts)
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)

        # Dosyayı çıkar
        data = self.read_bytes(actual_key)
        with open(temp_path, "wb") as f:
            f.write(data)

        self._temp_cache[actual_key] = temp_path
        return temp_path

    def get_file_size(self, relative_key: str) -> int:
        """Verilen anahtara ait dosyanın boyutunu (byte) döndürür."""
        self._ensure_loaded()
        actual_key = self._resolve_key(relative_key)
        if actual_key is None:
            raise KeyError(f"Varlık bulunamadı: {relative_key}")
        return self._table[actual_key]["size"]

    def list_directory(self, prefix: str) -> list:
        """Verilen ön eke sahip tüm anahtarları döndürür.
        Örnek: list_directory("sounds/") -> ["sounds/1.mp3", "sounds/para.mp3", ...]
        """
        self._ensure_loaded()
        prefix_lower = prefix.lower()
        return [
            key for key in self._table
            if key.lower().startswith(prefix_lower)
        ]

    def _cleanup(self) -> None:
        """Geçici dosyaları temizler."""
        if self._temp_dir and os.path.isdir(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass


# ---- Modül seviyesi global singleton ----
# Tüm modüller (game_state, audio_manager, dialogs, ...) aynı AssetPack
# örneğini paylaşır.

_global_pack: AssetPack = None


def get_asset_pack() -> AssetPack:
    """Global AssetPack singleton'ını döndürür. Henüz oluşturulmamışsa
    assets.dat'ı bulup yükler."""
    global _global_pack
    if _global_pack is not None:
        return _global_pack

    # assets.dat'ı bul: önce exe/script dizininde, sonra _MEIPASS'ta
    candidates = []

    # PyInstaller geçici dizini
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "assets.dat"))

    # Script/exe dizini
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(exe_dir, "assets.dat"))

    for path in candidates:
        if os.path.isfile(path):
            _global_pack = AssetPack(path)
            return _global_pack

    # .dat bulunamadı - None dönecek, fallback olarak eski sistem kullanılacak
    print("[AssetPack] assets.dat bulunamadı - dosya sistemi kullanılacak (fallback modu)")
    return None


def is_dat_mode() -> bool:
    """assets.dat mevcut ve yüklenebilir mi?"""
    pack = get_asset_pack()
    return pack is not None
