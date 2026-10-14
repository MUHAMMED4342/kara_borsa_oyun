"""
asset_packer.py
---------------
Tüm oyun varlıklarını (ses dosyaları, metin dosyaları, HTML dosyaları,
locale JSON dosyaları) tek bir 'assets.dat' paket dosyasına toplar.

DAT dosya formatı:
  [4 byte] Sihirli sayı: b'KBSA' (KaraBorsa Assets)
  [4 byte] Versiyon numarası (uint32, little-endian) => 1
  [4 byte] Dosya tablosu uzunluğu (uint32, little-endian)
  [N byte] Dosya tablosu (JSON, UTF-8 kodlanmış)
  [... ]   Ham dosya verileri (her dosya arka arkaya)

Dosya tablosu JSON yapısı:
  {
    "relative/path/to/file.mp3": {
      "offset": <int>,   # Verinin başladığı byte ofseti (dosya tablosundan sonra)
      "size": <int>       # Dosya boyutu (byte)
    },
    ...
  }

Kullanım:
  python asset_packer.py [--output assets.dat] [--source-dir .]

Bu script paketleme işlemi bittikten sonra SOUNDS klasörünü silmez,
sadece .dat dosyasını oluşturur. İsterseniz sonra elle silebilirsiniz.
"""

import argparse
import json
import os
import struct
import sys


MAGIC = b"KBSA"
VERSION = 1

# Paketlenecek dosya desenleri (kaynak dizine göre göreli)
ASSET_PATTERNS = {
    # Ses dosyaları
    "SOUNDS": [".mp3", ".ogg", ".wav"],
    # Locale dosyaları
    "locales": [".json"],
}

# Tek başına paketlenecek dosyalar (proje kök dizininden göreli)
SINGLE_FILES = [
    "insanlar.txt",
    "iller.txt",
    "ilceler.txt",
    "iller_us.txt",
    "ilceler_us.txt",
    "iller_uk.txt",
    "ilceler_uk.txt",
    "iller_au.txt",
    "ilceler_au.txt",
    "kullanimsartlari.txt",
    "gizlilik politikası.txt",
    "mesaj.txt",
    "token.txt",
    "github.txt",
    "versiyon.txt",
    "tr_help.html",
    "en_help.html",
    "release_notes.html",
]


def collect_files(source_dir: str) -> list:
    """Paketlenecek tüm dosyaları (abs_path, relative_key) çiftleri olarak toplar.

    relative_key, .dat dosyasındaki anahtar olacak - resource_path()
    tarafından kullanılan aynı göreli yollar:
      - sounds/1.mp3
      - sounds/button.wav
      - locales/en.json
      - insanlar.txt
      - vb.
    """
    files = []

    # Klasör bazlı varlıklar
    for folder, extensions in ASSET_PATTERNS.items():
        folder_path = os.path.join(source_dir, folder)
        if not os.path.isdir(folder_path):
            print(f"[Uyarı] Klasör bulunamadı, atlanıyor: {folder_path}")
            continue

        for fname in os.listdir(folder_path):
            ext = os.path.splitext(fname)[1].lower()
            if ext in extensions:
                abs_path = os.path.join(folder_path, fname)
                # Anahtar her zaman küçük harfli 'sounds/' olacak
                # (resource_path 'sounds/xxx' şeklinde kullanıyor)
                relative_key = f"{folder.lower()}/{fname}"
                files.append((abs_path, relative_key))

    # Tekil dosyalar
    for fname in SINGLE_FILES:
        abs_path = os.path.join(source_dir, fname)
        if os.path.isfile(abs_path):
            files.append((abs_path, fname))
        else:
            print(f"[Uyarı] Dosya bulunamadı, atlanıyor: {abs_path}")

    return files


def pack(source_dir: str, output_path: str) -> None:
    """Tüm varlıkları tek bir .dat dosyasına paketler."""
    files = collect_files(source_dir)

    if not files:
        print("[Hata] Paketlenecek dosya bulunamadı!")
        sys.exit(1)

    print(f"[Paketleyici] {len(files)} dosya paketlenecek...")

    # Önce tüm dosya verilerini ve tabloyu oluştur
    table = {}
    data_chunks = []
    current_offset = 0

    for abs_path, relative_key in sorted(files, key=lambda x: x[1]):
        with open(abs_path, "rb") as f:
            content = f.read()

        size = len(content)
        table[relative_key] = {
            "offset": current_offset,
            "size": size,
        }
        data_chunks.append(content)
        current_offset += size

        size_kb = size / 1024
        print(f"  + {relative_key} ({size_kb:.1f} KB)")

    # Tabloyu JSON olarak kodla
    table_json = json.dumps(table, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    table_length = len(table_json)

    # .dat dosyasını yaz
    with open(output_path, "wb") as out:
        # Başlık
        out.write(MAGIC)
        out.write(struct.pack("<I", VERSION))
        out.write(struct.pack("<I", table_length))

        # Dosya tablosu
        out.write(table_json)

        # Ham veriler
        for chunk in data_chunks:
            out.write(chunk)

    total_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n[Paketleyici] Tamamlandı: {output_path} ({total_size_mb:.2f} MB)")
    print(f"[Paketleyici] {len(files)} dosya başarıyla paketlendi.")


def main():
    parser = argparse.ArgumentParser(
        description="Kara Borsa Oyunu varlık paketleyicisi"
    )
    parser.add_argument(
        "--source-dir", "-s",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="Kaynak dizin (proje kök klasörü)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Çıktı .dat dosyası yolu (varsayılan: <source-dir>/assets.dat)",
    )
    args = parser.parse_args()

    if args.output is None:
        args.output = os.path.join(args.source_dir, "assets.dat")

    pack(args.source_dir, args.output)


if __name__ == "__main__":
    main()
