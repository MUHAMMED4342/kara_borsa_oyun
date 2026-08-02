# -*- coding: utf-8 -*-
"""
accessibility_helper.py
------------------------
accessible_output2 kütüphanesini sarmalayan ince bir katman.

Güncelleme: Ekran okuyucu aktif olmadığında SAPI5 vb. motorların 
eski konuşmayı yarıda kesip (interrupt) yeni gelen metni anında 
seslendirmesi sağlandı.
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


def speak(text: str, interrupt: bool = True) -> None:
    """
    Verilen metni accessible_output2.outputs.auto.Auto().output() ile
    ekran okuyucuya gönderir. 
    
    interrupt=True (Varsayılan): Yeni bir metin geldiğinde, eğer önceki 
    konuşma henüz bitmediyse onu susturur ve yeni metni hemen okur.
    """
    if not text:
        return

    if _speaker is not None:
        try:
            # interrupt=True parametresi sayesinde SAPI5 konuşmayı biriktirmez, 
            # yeni tuş vuruşunda eski konuşmayı keser.
            _speaker.output(text, interrupt=interrupt)
            return
        except Exception:
            # Eğer kütüphane veya kullanılan sürücü interrupt parametresini desteklemezse
            # hata vermeden normal şekilde okumaya çalışması için fallback:
            try:
                _speaker.output(text)
                return
            except Exception:
                pass

    # Fallback: ekran okuyucu yoksa ya da hata verdiyse konsola yaz.
    print(f"[Seslendirme]: {text}")