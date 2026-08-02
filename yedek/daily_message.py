# -*- coding: utf-8 -*-
"""
daily_message.py
-----------------
"GÜNÜN MESAJI" özelliği.

Geliştirici, GitHub'daki düz metin dosyasını güncelleyerek oyunculara
mesaj/duyuru bırakabilir:

    https://raw.githubusercontent.com/MUHAMMED4342/gunun_mesaji/main/mesaj

Dosyanın İLK SATIRI tarih (gg.aa.yyyy, örn. "21.7.2026"), geri kalan
satırlar mesajın kendisidir:

    21.7.2026
    Mesaj metni buraya...
    İkinci satır da olabilir...

Oyun her açılışta bu dosyayı arka planda (ayrı thread) indirir. Dosyadaki
tarih, daha önce oyuncuya gösterilmiş en son mesajın tarihinden daha
yeniyse mesaj bir kere gösterilir ve tarih yerel olarak kaydedilir; aynı
mesaj bir daha gösterilmez. İnternet yoksa veya GitHub'a erişilemezse
sessizce hiçbir şey yapılmaz (oyunun açılışını asla engellemez/geciktirmez).
"""

import os
import threading
import urllib.request
from datetime import datetime

import appdirs

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
LAST_SEEN_PATH = os.path.join(DATA_DIR, "gunun_mesaji_son_tarih.txt")

MESSAGE_URL = "https://raw.githubusercontent.com/MUHAMMED4342/gunun_mesaji/main/mesaj"
REQUEST_TIMEOUT = 6  # saniye - internet yavaş/yoksa oyunu bekletmemek için


def _parse_date(date_str: str):
    """'21.7.2026' / '21.07.2026' gibi bir tarihi datetime.date'e çevirir.
    Ayrıştırılamazsa None döner."""
    date_str = (date_str or "").strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _read_last_seen_date():
    try:
        with open(LAST_SEEN_PATH, "r", encoding="utf-8") as f:
            return _parse_date(f.read())
    except OSError:
        return None


def _write_last_seen_date(date_str: str) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LAST_SEEN_PATH, "w", encoding="utf-8") as f:
            f.write(date_str.strip())
    except OSError:
        pass


def fetch_daily_message():
    """
    GitHub'dan günün mesajını indirir. Ağ hatası, zaman aşımı veya
    beklenmeyen bir format olursa None döner (oyunun akışını hiçbir
    zaman bozmaz). Başarılıysa (tarih_metni, tarih, mesaj_metni) döner.
    """
    try:
        with urllib.request.urlopen(MESSAGE_URL, timeout=REQUEST_TIMEOUT) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    lines = raw.splitlines()
    if not lines:
        return None

    date_str = lines[0].strip()
    date_obj = _parse_date(date_str)
    if date_obj is None:
        return None

    message_text = "\n".join(lines[1:]).strip()
    if not message_text:
        return None

    return date_str, date_obj, message_text


def mark_seen(date_str: str) -> None:
    """Bir mesajın kullanıcıya GÖSTERİLDİĞİNİ kalıcı olarak işaretler.
    check_for_new_message'ın callback'i çağrıldıktan ve mesaj gerçekten
    ekranda gösterildikten SONRA çağrılmalıdır; aksi halde (ör. oyuncu
    hapisteyken gösterim ertelenirse) mesaj hiç görülmeden 'okunmuş'
    sayılabilir."""
    _write_last_seen_date(date_str)


def check_for_new_message(on_new_message) -> None:
    """
    Arka planda (ayrı thread) günün mesajını kontrol eder. Daha önce
    gösterilmemiş (yani kayıtlı son tarihten daha yeni) bir mesaj
    bulunursa on_new_message(date_str, message_text) çağrılır. Mesaj
    burada henüz "görülmüş" olarak İŞARETLENMEZ - bunun için gösterim
    tamamlandıktan sonra mark_seen(date_str) çağrılmalıdır.

    ÖNEMLİ: on_new_message ana (UI) thread'inde DEĞİL, arka plan
    thread'inde çağrılır. Çağıran taraf UI güncellemesi için
    wx.CallAfter kullanmalıdır.
    """
    def worker():
        result = fetch_daily_message()
        if result is None:
            return
        date_str, date_obj, message_text = result

        last_seen = _read_last_seen_date()
        if last_seen is not None and date_obj <= last_seen:
            return

        on_new_message(date_str, message_text)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
