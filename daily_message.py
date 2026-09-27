
"""
daily_message.py
-----------------
"GÜNÜN MESAJI" özelliği.

Geliştirici, GitHub'daki düz metin dosyasını güncelleyerek oyunculara
mesaj/duyuru bırakabilir:

    https://raw.githubusercontent.com/MUHAMMED4342/gunun_mesaji/main/mesaj

Dosyanın İLK SATIRI tarih (gg.aa.yyyy, örn. "21.7.2026"), geri kalan
satırlar mesajın kendisidir. Mesaj artık BİRDEN FAZLA dilde yazılabilir:
her dil bloğu çift tırnak içine alınır ve "<dil_kodu>:" ile başlar
(dil kodu i18n.py'deki dil koduyla aynı olmalı, örn. "tr", "en"):

    21.09.2026
    "en:
    hello how are you?"
    "tr:
    merhaba, nasılsınız?"

Oyun, oyuncunun o anki arayüz diline uygun bloğu gösterir. O dilde blok
yoksa sırasıyla İngilizce ("en"), sonra dosyadaki ilk blok denenir. Eski
biçimde (dil etiketi olmadan, düz metin) yazılmış bir dosya da desteklenir:
böyle bir dosya her dilde aynı şekilde gösterilir (geriye dönük uyumluluk).

Oyun her açılışta bu dosyayı arka planda (ayrı thread) indirir. Dosyadaki
tarih, daha önce oyuncuya gösterilmiş en son mesajın tarihinden daha
yeniyse mesaj bir kere gösterilir ve tarih yerel olarak kaydedilir; aynı
mesaj bir daha gösterilmez. İnternet yoksa veya GitHub'a erişilemezse
sessizce hiçbir şey yapılmaz (oyunun açılışını asla engellemez/geciktirmez).
"""

import os
import re
import threading
import urllib.request
from datetime import datetime

import appdirs

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
DATA_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
LAST_SEEN_PATH = os.path.join(DATA_DIR, "gunun_mesaji_son_tarih.txt")

MESSAGE_URL = "https://raw.githubusercontent.com/MUHAMMED4342/gunun_mesaji/main/mesaj"
REQUEST_TIMEOUT = 6  


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


# "<dil_kodu>:" ile başlayan bir dil bloğunun BAŞLANGICINI yakalar (açan
# tırnak + dil kodu + iki nokta). Bloklar birbirinden bu başlangıç
# işaretleriyle ayrılır - kapanış tırnağı ARANMAZ, çünkü metin
# içeriğinin kendisi (ör. gizlilik politikası/kullanım şartları gibi
# uzun metinler) de tırnak işareti İÇEREBİLİR ("Devam Et" gibi). Bu
# yüzden her bloğun içeriği, kendi başlangıcından BİR SONRAKİ BLOĞUN
# başlangıcına (ya da metnin sonuna) kadar olan kısımdır; sondaki TEK
# bir kapanış tırnağı varsa (sınırlayıcı olarak konmuşsa) o silinir,
# içerik ORTASINDAKİ hiçbir tırnağa DOKUNULMAZ.
_LANG_BLOCK_START_RE = re.compile(
    r'"\s*([a-zA-Z0-9_-]{2,10})\s*:\s*',
)


def parse_language_blocks(body: str) -> dict:
    """Tarih satırından sonraki gövdeyi diline göre ayrıştırır.

    Dil etiketli bloklar varsa {dil_kodu: metin} sözlüğü döner (dil
    kodları küçük harfe çevrilir). Hiç dil bloğu bulunamazsa (eski/düz
    metin biçimi), gövdenin tamamını tek bir "_default" anahtarı altında
    döner; bu, her dilde aynı şekilde gösterilir."""
    body = body.strip()
    if not body:
        return {}

    starts = list(_LANG_BLOCK_START_RE.finditer(body))
    if not starts:
        return {"_default": body}

    messages = {}
    for i, m in enumerate(starts):
        lang_code = m.group(1).strip().lower()
        content_start = m.end()
        content_end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        text = body[content_start:content_end].strip()
        if text.endswith('"'):
            text = text[:-1].rstrip()
        if text:
            messages[lang_code] = text
    return messages if messages else {"_default": body}


def resolve_message(messages: dict, lang_code: str):
    """Bir {dil_kodu: metin} sözlüğünden o anki arayüz diline en uygun
    metni seçer. Sırasıyla: tam eşleşme -> "_default" -> "en" -> dosyadaki
    ilk metin denenir. Hiçbir şey yoksa None döner."""
    if not messages:
        return None
    lang_code = (lang_code or "").strip().lower()
    if lang_code in messages:
        return messages[lang_code]
    if "_default" in messages:
        return messages["_default"]
    if "en" in messages:
        return messages["en"]
    return next(iter(messages.values()), None)


def fetch_daily_message():
    """
    GitHub'dan günün mesajını indirir. Ağ hatası, zaman aşımı veya
    beklenmeyen bir format olursa None döner (oyunun akışını hiçbir
    zaman bozmaz). Başarılıysa (tarih_metni, tarih, {dil_kodu: mesaj})
    döner.
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

    messages = parse_language_blocks("\n".join(lines[1:]))
    if not messages:
        return None

    return date_str, date_obj, messages


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
    bulunursa on_new_message(date_str, messages) çağrılır; messages,
    resolve_message() ile o anki arayüz diline çevrilebilecek bir
    {dil_kodu: metin} sözlüğüdür. Mesaj burada henüz "görülmüş" olarak
    İŞARETLENMEZ - bunun için gösterim tamamlandıktan sonra
    mark_seen(date_str) çağrılmalıdır.

    ÖNEMLİ: on_new_message ana (UI) thread'inde DEĞİL, arka plan
    thread'inde çağrılır. Çağıran taraf UI güncellemesi için
    wx.CallAfter kullanmalıdır.
    """
    def worker():
        result = fetch_daily_message()
        if result is None:
            return
        date_str, date_obj, messages = result

        last_seen = _read_last_seen_date()
        if last_seen is not None and date_obj <= last_seen:
            return

        on_new_message(date_str, messages)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
