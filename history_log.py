# -*- coding: utf-8 -*-
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

# Bellekte tutulacak maksimum kayıt sayısı (sınırsız büyümesin diye).
MAX_ENTRIES = 500

_lock = threading.Lock()
_entries: List[Dict] = []


def log_history(text: str, day: int = None) -> None:
    """Yeni bir mesajı geçmiş kaydına ekler."""
    if not text:
        return
    with _lock:
        _entries.append({
            "time": datetime.datetime.now().strftime("%H:%M:%S"),
            "day": day,
            "text": text,
        })
        # Çok büyümesin diye en eski kayıtları at.
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