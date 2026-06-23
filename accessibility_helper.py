# -*- coding: utf-8 -*-
"""
accessibility_helper.py
------------------------
accessible_output2 kütüphanesini sarmalayan ince bir katman.

Neden ayrı bir modül?
- accessible_output2 bazı sistemlerde (NVDA/JAWS kurulu olmayan, ya da
  kütüphane yüklenmemiş ortamlarda) import edilemeyebilir. Bu modül
  bu durumda programın çökmesini önler ve mesajları konsola yazarak
  geliştirme/sınama sırasında da geri bildirim sağlar (graceful degradation).
- Tüm uygulama boyunca tek bir `speak()` fonksiyonu kullanılır, böylece
  ekran okuyucu çağrısı tek bir yerden yönetilir.
"""

try:
    import accessible_output2.outputs.auto as ao
    _speaker = ao.Auto()
    SCREEN_READER_AVAILABLE = True
except Exception:
    # accessible_output2 kurulu değilse veya başlatılamazsa
    # sessizce devre dışı bırak; uygulama konsola yazarak çalışmaya devam eder.
    _speaker = None
    SCREEN_READER_AVAILABLE = False


def speak(text: str) -> None:
    """
    Verilen metni accessible_output2.outputs.auto.Auto().output() ile
    ekran okuyucuya gönderir. Ekran okuyucu kullanılamıyorsa metni
    konsola yazdırır (fallback).
    """
    if not text:
        return

    if _speaker is not None:
        try:
            _speaker.output(text)
            return
        except Exception:
            # Ekran okuyucu çağrısı başarısız olsa da uygulama akışı bozulmasın.
            pass

    # Fallback: ekran okuyucu yoksa ya da hata verdiyse konsola yaz.
    print(f"[Seslendirme]: {text}")
