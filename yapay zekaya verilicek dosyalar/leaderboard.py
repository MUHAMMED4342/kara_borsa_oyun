# -*- coding: utf-8 -*-
"""
leaderboard.py
--------------
GitHub Gist ile skor tablosu entegrasyonu.
"""

import os
import sys
import json
import time
import random
import threading
import requests
from typing import List, Dict, Optional, Tuple

from formatting import format_tl

# Gist bilgileri
GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"
GIST_URL = f"https://api.github.com/gists/{GIST_ID}"


def _get_base_dir() -> str:
    """
    token.txt / ayar / log dosyalarının aranacağı klasörü döndürür.

    ÖNEMLİ: PyInstaller ile --onefile olarak derlenmiş bir .exe'de,
    programın "çalışma dizini" (os.getcwd()) HER ZAMAN exe'nin
    bulunduğu klasör OLMAYABİLİR (kısayolun "Başlangıç konumu"na,
    nereden çalıştırıldığına vb. göre değişir). Relative "token.txt"
    yolu bu yüzden exe halinde bazen bulunamıyordu. Bunun yerine her
    zaman exe'nin (frozen ise sys.executable, değilse bu .py
    dosyasının) bulunduğu klasörü kullanıyoruz.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")
SCORE_FILE = "skorlar.json"  # Bu, gist İÇİNDEKİ dosya adı; yerel yol değil.


def _get_appdata_dir() -> str:
    """
    Ayar (skor_ayarlari.json) ve log (skor_log.txt) dosyalarının
    saklanacağı klasörü döndürür. Bunlar kullanıcının göreceği bir yer
    değil (oyun klasörünü/masaüstünü kirletmemesi için), Windows'un
    standart uygulama verisi klasörüne (%LOCALAPPDATA%) yazılır.
    token.txt buna dahil DEĞİL: o hâlâ kullanıcının kendi elle koyduğu
    exe'nin yanındaki klasörde aranıyor.
    """
    appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if appdata:
        base = os.path.join(appdata, "KaraborsaSimulasyonu")
    else:
        # Windows dışı bir ortam ya da APPDATA tanımsızsa yedek konum.
        base = os.path.join(os.path.expanduser("~"), ".karaborsa_simulasyonu")
    try:
        os.makedirs(base, exist_ok=True)
        return base
    except Exception:
        # Klasör oluşturulamazsa (izin vb.) en azından exe'nin yanına düş.
        return BASE_DIR


APPDATA_DIR = _get_appdata_dir()
SETTINGS_FILE = os.path.join(APPDATA_DIR, "skor_ayarlari.json")
LOG_FILE = os.path.join(APPDATA_DIR, "skor_log.txt")

# Aynı process içinde iki gönderimin aynı anda gist'i okuyup
# birbirinin yazdığını ezmesini engelleyen kilit.
_score_lock = threading.Lock()
_log_lock = threading.Lock()


def _log(msg: str) -> None:
    """
    print() ile aynı mesajı hem konsola (varsa) hem de exe'nin yanındaki
    skor_log.txt dosyasına yazar. Uygulama console=False (pencereli)
    olarak derlendiği için print() çıktısı hiçbir yerde görünmüyordu;
    bu dosya sayesinde sorun olduğunda skor_log.txt açılarak gerçek
    hata görülebilir.
    """
    print(msg)
    try:
        with _log_lock:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
    except Exception:
        # Log dosyasına yazılamaması gönderimi engellememeli.
        pass


def _load_settings() -> Dict:
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        _log(f"[Hata] Ayarlar okunamadı: {e}")
    return {}


def _save_settings(settings: Dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        _log(f"[Hata] Ayarlar kaydedilemedi: {e}")


# Global değişken: Skor gönderimi aktif mi?
# Başlangıç değeri diskteki ayardan okunur (yoksa varsayılan: aktif).
skor_gonderimi_aktif = _load_settings().get("skor_gonderimi_aktif", True)


def set_score_submission_enabled(enabled: bool) -> None:
    """
    Skor gönderimini açar/kapatır ve bu tercihi diske kaydeder.
    ÖNEMLİ: skor_gonderimi_aktif değişkenini değiştirmek isteyen her
    modül (main.py, dialogs.py vb.) mutlaka bu fonksiyonu çağırmalı;
    `from leaderboard import skor_gonderimi_aktif` ile alınan kopyayı
    doğrudan değiştirmek SADECE o modülün kendi kopyasını değiştirir,
    buradaki gerçek durumu etkilemez.
    """
    global skor_gonderimi_aktif
    skor_gonderimi_aktif = enabled
    settings = _load_settings()
    settings["skor_gonderimi_aktif"] = enabled
    _save_settings(settings)


def is_score_submission_enabled() -> bool:
    """Güncel skor gönderimi durumunu döndürür (her zaman gerçek değeri okur)."""
    return skor_gonderimi_aktif


def get_token() -> Optional[str]:
    """
    Token'ı şu sırayla arar:
      1) embedded_token.py içine gömülü (obfuscated) token (doldurulduysa)
      2) build.spec ile exe'nin İÇİNE veri olarak gömülen token.txt
         (PyInstaller onefile'da bu dosyalar çalışma anında sys._MEIPASS
         klasörüne çıkarılır, exe'nin yanındaki klasöre değil)
      3) exe'nin/script'in yanındaki token.txt (elle koyduysanız, ör.
         gömülü olanı değiştirmeden hızlıca farklı bir token denemek için)
    """
    try:
        from embedded_token import get_embedded_token
        embedded = get_embedded_token()
        if embedded:
            _log("[Bilgi] Gömülü (embedded_token.py) token kullanılıyor.")
            return embedded
    except Exception as e:
        _log(f"[Hata] Gömülü token okunamadı: {e}")

    # PyInstaller onefile modunda veri dosyaları (datas=[...]) çalışma
    # anında sys._MEIPASS altına çıkarılır.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(sys._MEIPASS, "token.txt")
        try:
            if os.path.exists(bundled_path):
                with open(bundled_path, "r", encoding="utf-8") as f:
                    token = f.read().strip()
                    if token:
                        _log("[Bilgi] exe içine gömülü (bundled) token.txt kullanılıyor.")
                        return token
        except Exception as e:
            _log(f"[Hata] Gömülü token.txt okunamadı: {e}")

    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    _log(f"[Bilgi] Token okundu (yanındaki token.txt): {token[:15]}... (uzunluk: {len(token)})")
                    return token
        else:
            _log(f"[Hata] Hiçbir yerde token bulunamadı (gömülü token, bundled token.txt, {TOKEN_FILE})!")
    except Exception as e:
        _log(f"[Hata] Token okunamadı: {e}")
    return None


def get_gist_content() -> Optional[Dict]:
    """
    GitHub Gist'ten skorlar.json içeriğini çeker.
    Dönen format: {"score_data": [...]} veya hata durumunda None
    """
    token = get_token()
    if not token:
        _log("[Hata] GitHub token bulunamadı. token.txt dosyasını kontrol edin.")
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        _log(f"[Bilgi] Gist'ten veri çekiliyor: {GIST_URL}")
        response = requests.get(GIST_URL, headers=headers, timeout=10)
        _log(f"[Bilgi] HTTP Durum Kodu: {response.status_code}")

        if response.status_code == 200:
            gist_data = response.json()
            files = gist_data.get("files", {})

            if SCORE_FILE in files:
                content = files[SCORE_FILE].get("content", "{}")
                _log(f"[Bilgi] skorlar.json içeriği alındı.")
                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    _log(f"[Hata] skorlar.json içeriği geçersiz JSON formatında: {e}")
                    return {"score_data": []}
            else:
                _log("[Bilgi] skorlar.json dosyası Gist'te bulunamadı. Yeni dosya oluşturulacak.")
                return {"score_data": []}
        elif response.status_code == 404:
            _log("[Hata] Gist bulunamadı. Gist ID'yi kontrol edin.")
            _log(f"Gist ID: {GIST_ID}")
            return None
        elif response.status_code == 401:
            _log("[Hata] Yetkisiz erişim (401). Token geçersiz veya süresi dolmuş.")
            _log(f"Token başlangıcı: {token[:15]}...")
            _log("Çözüm: Yeni bir GitHub Personal Access Token oluşturun ve 'gist' yetkisi verin.")
            _log("https://github.com/settings/tokens/new")
            return None
        else:
            _log(f"[Hata] Gist okunamadı. HTTP {response.status_code}")
            _log(f"Response: {response.text[:200]}")
            return None
    except requests.exceptions.RequestException as e:
        _log(f"[Hata] Ağ bağlantı hatası: {e}")
        return None


def update_gist_content(data: Dict) -> bool:
    """
    GitHub Gist'teki skorlar.json dosyasını günceller.
    """
    token = get_token()
    if not token:
        _log("[Hata] GitHub token bulunamadı. token.txt dosyasını kontrol edin.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        _log("[Bilgi] Gist güncelleniyor...")

        # Önce mevcut Gist'i al
        response = requests.get(GIST_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            _log(f"[Hata] Gist bilgileri alınamadı. HTTP {response.status_code}")
            return False

        gist_data = response.json()
        existing_files = gist_data.get("files", {})

        # Güncellenecek dosya listesini hazırla
        files_to_update = {}
        for filename, file_info in existing_files.items():
            if filename == SCORE_FILE:
                files_to_update[SCORE_FILE] = {
                    "content": json.dumps(data, ensure_ascii=False, indent=2)
                }
            else:
                # Diğer dosyaları olduğu gibi bırak
                files_to_update[filename] = {
                    "content": file_info.get("content", "")
                }

        # Eğer skorlar.json yoksa ekle
        if SCORE_FILE not in files_to_update:
            files_to_update[SCORE_FILE] = {
                "content": json.dumps(data, ensure_ascii=False, indent=2)
            }

        # Gist'i güncelle
        payload = {"files": files_to_update}
        update_response = requests.patch(GIST_URL, headers=headers, json=payload, timeout=10)

        if update_response.status_code == 200:
            _log("[Bilgi] Skor tablosu başarıyla güncellendi.")
            return True
        else:
            _log(f"[Hata] Gist güncellenemedi. HTTP {update_response.status_code}")
            _log(f"Response: {update_response.text[:200]}")
            return False

    except requests.exceptions.RequestException as e:
        _log(f"[Hata] Ağ bağlantı hatası: {e}")
        return False


def get_leaderboard() -> Optional[List[Dict]]:
    """
    Skor tablosunu en çok paradan en aza doğru sıralı olarak döndürür.
    Sıralama ölçütü: toplam para (nakit + temiz para) — gün sayısı artık
    hesaba katılmıyor, en çok parası olan en üstte.
    Her kayıt: {"username": str, "total": float, "cash": float, "day": int, "clean_money": float}

    Dönüş:
      - Liste (boş olabilir): veri başarıyla çekildi.
      - None: veri çekilemedi (ör. internet yok, token hatalı vb.) —
        bu durum "henüz kayıt yok" ile KARIŞTIRILMAMALI.
    """
    _log("[Bilgi] Skor tablosu çekiliyor...")
    data = get_gist_content()
    if data is None:
        # Veri çekilemedi (ağ hatası, token hatası, vb.) — bunu boş
        # tablo ile karıştırmamak için None döndürüyoruz.
        _log("[Bilgi] Skor tablosu çekilemedi (bağlantı/erişim hatası).")
        return None
    if "score_data" in data:
        entries = data["score_data"]

        def _total_of(entry: Dict) -> float:
            # Eski kayıtlarda "total" alanı olmayabilir (ör. eski formülle
            # hesaplanmış "score" alanı); geriye dönük uyumluluk için
            # bulunan ilk değeri kullan.
            if "total" in entry:
                return entry.get("total", 0)
            if "score" in entry:
                return entry.get("score", 0)
            return entry.get("cash", 0) + entry.get("clean_money", 0)

        sorted_entries = sorted(entries, key=_total_of, reverse=True)
        _log(f"[Bilgi] {len(sorted_entries)} kayıt bulundu.")
        return sorted_entries
    _log("[Bilgi] Kayıt bulunamadı veya veri boş.")
    return []


def _merge_entry(score_data: List[Dict], username: str, total: float,
                  cash: float, day: int, clean_money: float) -> Tuple[List[Dict], bool, str]:
    """
    Verilen listeye (username, total) girdisini ekler/günceller.
    Dönüş: (yeni_liste, değişiklik_yapıldı_mı, mesaj)

    ÖNEMLİ: Skor tablosu bir "en yüksek skor" tablosu DEĞİL, oyuncunun
    GÜNCEL/GERÇEK durumunu gösteren bir tablo olmalı. Bu yüzden yeni
    toplam eskisinden düşük olsa bile (ör. oyuncu 50.000 TL'den 2.000
    TL'ye düşmüşse) kayıt her zaman güncellenir; oyuncunun para durumu
    ne ise tabloda o görünür.
    """
    for entry in score_data:
        if entry.get("username") == username:
            entry.update({
                "total": total,
                "cash": cash,
                "day": day,
                "clean_money": clean_money,
                "last_updated": __import__("datetime").datetime.now().isoformat()
            })
            # Eski formülle hesaplanmış "score" alanı varsa temizle,
            # karışıklık olmasın.
            entry.pop("score", None)
            _log(f"[Bilgi] Kullanıcı güncellendi: {username} -> Yeni toplam: {format_tl(total)} TL")
            return score_data, True, f"Bakiyeniz gönderildi! Toplam: {format_tl(total)} TL"

    score_data.append({
        "username": username,
        "total": total,
        "cash": cash,
        "day": day,
        "clean_money": clean_money,
        "last_updated": __import__("datetime").datetime.now().isoformat()
    })
    _log(f"[Bilgi] Yeni kullanıcı eklendi: {username}, Toplam: {format_tl(total)} TL")
    return score_data, True, f"Bakiyeniz gönderildi! Toplam: {format_tl(total)} TL"


def _entry_matches(score_data: List[Dict], username: str, total: float) -> bool:
    """Gist'teki güncel veride bizim yazdığımız (username, total) çiftinin
    gerçekten orada olup olmadığını kontrol eder. Yoksa, aramızda başka bir
    bilgisayarın yazması PATCH'imizi ezmiş demektir."""
    for entry in score_data:
        if entry.get("username") == username:
            current = entry.get("total", entry.get("score", 0))
            # Küçük ondalık farkları tolere et.
            return abs(current - total) < 0.01
    return False


# Farklı bilgisayarlardan aynı anda gelen gönderimlerde, iki process aynı
# gist'i okuyup ikisi de kendi haliyle PATCH atarsa biri diğerini ezebilir
# (GitHub Gist API "conditional/atomic update" desteklemiyor). Bunun
# etkisini azaltmak için: PATCH sonrası tekrar okuyup bizim girdimizin
# gerçekten orada olduğunu doğruluyoruz; değilse kısa bir bekleme ile
# baştan (fetch -> merge -> patch) deniyoruz.
_MAX_RETRIES = 4


def send_score(username: str, cash: float, day: int, clean_money: float = 0) -> Tuple[bool, str]:
    """
    Oyun sonunda oyuncunun TOPLAM PARASINI (nakit + temiz para) GitHub
    Gist'teki skor tablosuna gönderir. Tablo artık sadece paraya göre
    sıralanıyor (gün sayısı sıralamayı etkilemiyor). Kullanıcı zaten
    listede varsa ve yeni toplamı daha yüksekse günceller.
    """
    _log(f"[Bilgi] Gönderim başlatıldı. Kullanıcı: {username}, Gün: {day}, Nakit: {cash}")

    if not skor_gonderimi_aktif:
        return False, "Skor gönderimi devre dışı."

    if not username:
        return False, "Kullanıcı adı boş."

    # Sıralama ölçütü: toplam para.
    total = cash + clean_money
    _log(f"[Bilgi] Toplam para: {format_tl(total)} TL")

    with _score_lock:
        last_error = "Gönderilemedi. Bağlantı hatası."

        for attempt in range(1, _MAX_RETRIES + 1):
            # 1) Güncel veriyi çek
            data = get_gist_content()
            if data is None:
                return False, "Gist verileri alınamadı. Token kontrol edin."

            score_data = data.get("score_data", [])

            # 2) Kendi girdimizi ekle/güncelle
            score_data, changed, msg = _merge_entry(score_data, username, total, cash, day, clean_money)
            if not changed:
                # Zaten daha yüksek bir toplamımız var, gönderime gerek yok.
                return True, msg

            data["score_data"] = score_data

            # 3) Gist'e yaz
            if not update_gist_content(data):
                last_error = "Gönderilemedi. Bağlantı hatası."
                time.sleep(0.5 + random.random())
                continue

            # 4) Doğrula: gerçekten bizim yazdığımız veri orada mı?
            #    (Aramızda başka bir bilgisayar yazıp bizi ezmiş olabilir.)
            verify_data = get_gist_content()
            if verify_data and _entry_matches(verify_data.get("score_data", []), username, total):
                return True, msg

            _log(f"[Bilgi] Doğrulama başarısız (muhtemelen başka bir gönderimle çakıştı), "
                  f"tekrar deneniyor... ({attempt}/{_MAX_RETRIES})")
            last_error = "Gönderildi ama başka bir gönderimle çakıştığı için doğrulanamadı."
            time.sleep(0.5 + random.random())

        return False, last_error
