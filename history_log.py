
"""
history_log.py
---------------
Oyun içinde ekran okuyucuya söylenen (speak() ile seslendirilen) her mesajı
biriktiren basit, thread-safe bir geçmiş kaydı.

Bu modülü doğrudan çağırmanıza gerek yok: main.py, dialogs.py ve
game_state.py içindeki `speak()` fonksiyonu otomatik olarak buraya da
kayıt atacak şekilde sarmalandı (bkz. o dosyalardaki `speak` tanımı).
"""

import threading
import datetime
from typing import List, Dict


MAX_ENTRIES = 500

# Geçmişe YAZILMAYAN anonslar (çeviri anahtarının başlangıcına göre).
# Geçmiş, oyunda OLAN BİTENLERİ (gün başlangıcı, kâr, olaylar, alım-satım,
# açık artırma, hapis...) içermeli; arayüz konuşmalarını (yükleniyor,
# hoş geldiniz, "Nakit: ...", seçim/uyarı/ayar bildirimleri, ses seviyesi)
# içermemeli. Anahtarı bilinmeyen (birleştirilmiş) metinler yazılır.
NOISE_KEY_PREFIXES = (
    "welcome.", "loadgame.", "app.", "cheat.", "menu.", "settings.", "terms.",
    "country.", "language.", "leaderboard.", "warehouse.", "newticket.",
    "tickets.", "audio.", "common.", "status.", "state.inventory_",
    "state.wallet", "state.release_notes", "product.category_announce",
    "land.select", "land.market_select", "company.select", "company.enter_name",
    "employees.select", "bankloan.option_select", "bankloan.select_package",
    "gambling.select", "gambling.enter", "gambling.add_bet_first",
    "gambling.insufficient", "gambling.bet_added", "gambling.bet_removed",
    "auction.no_active_auction", "auction.select_owned_first",
    "auction.speak_intro", "auction.status_announcement",
    "auction.time_up_cannot_bid", "loan.need_", "jail.exit_blocked",
    "log.score_sent",
)


def is_noise(text: str) -> bool:
    """Metin, bilinen 'gereksiz' bir çeviri anahtarından geldiyse True."""
    try:
        import i18n
        key = i18n.key_for_text(text)
    except Exception:
        return False
    return bool(key) and key.startswith(NOISE_KEY_PREFIXES)


def format_entry(entry: Dict) -> str:
    """Bir kaydın ekranda/ekran okuyucuda görünen hâli: SADECE mesaj
    (zaman damgası ve gün eki yok)."""
    return entry.get("text", "")

_lock = threading.Lock()
_entries: List[Dict] = []


def log_history(text: str, day: int = None) -> None:
    """Yeni bir mesajı geçmiş kaydına ekler."""
    if not text or is_noise(text):
        return
    with _lock:
        _entries.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "day": day,
            "text": text,
        })
        
        if len(_entries) > MAX_ENTRIES:
            del _entries[0: len(_entries) - MAX_ENTRIES]


def get_history() -> List[Dict]:
    """Tüm geçmiş kayıtlarını (en eskiden en yeniye) döndürür."""
    with _lock:
        return list(_entries)


def clear_history() -> None:
    """Geçmiş kaydını temizler (yeni oyuna başlarken kullanılabilir)."""
    with _lock:
        _entries.clear()