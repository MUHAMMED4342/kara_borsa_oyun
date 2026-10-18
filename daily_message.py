
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

HAFTALIK ÖDÜL: mesaj gösterildiğinde, son ödülden en az 7 gün geçtiyse
oyuncunun nakdine 1.000.000 eklenir (bkz. is_reward_due, main.py).

Oyun her açılışta bu dosyayı arka planda (ayrı thread) indirir. Dosyadaki
tarih, daha önce oyuncuya gösterilmiş en son mesajın tarihinden daha
yeniyse mesaj bir kere gösterilir ve tarih yerel olarak kaydedilir; aynı
mesaj bir daha gösterilmez. İnternet yoksa veya GitHub'a erişilemezse
sessizce hiçbir şey yapılmaz (oyunun açılışını asla engellemez/geciktirmez).
"""

import hashlib
import hmac
import json
import os
import re
import threading
import urllib.request
from datetime import datetime

import app_paths

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
LAST_SEEN_FILENAME = "gunun_mesaji_son_tarih.txt"
LAST_REWARD_FILENAME = "gunun_mesaji_son_odul.dat"

# Haftalık ödül: günün mesajı gösterildiğinde, bir önceki ÖDÜLÜN verildiği
# mesaj tarihinden en az REWARD_INTERVAL_DAYS gün sonraysa oyuncuya
# REWARD_AMOUNT verilir. Yani mesajlar sık yayınlansa bile ödül en fazla
# haftada bir kez verilir. İlk kez mesaj gören oyuncu da ödülü alır.
REWARD_AMOUNT = 1_000_000.0
REWARD_INTERVAL_DAYS = 7


def _data_dir() -> str:
    # Normal/taşınabilir mod değişebildiği için her seferinde hesaplanır.
    return app_paths.user_data_dir(APP_NAME, APP_AUTHOR)


def _last_seen_path() -> str:
    return os.path.join(_data_dir(), LAST_SEEN_FILENAME)


def _last_reward_path() -> str:
    return os.path.join(_data_dir(), LAST_REWARD_FILENAME)

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
        with open(_last_seen_path(), "r", encoding="utf-8") as f:
            return _parse_date(f.read())
    except OSError:
        return None


def _write_last_seen_date(date_str: str) -> None:
    try:
        os.makedirs(_data_dir(), exist_ok=True)
        with open(_last_seen_path(), "w", encoding="utf-8") as f:
            f.write(date_str.strip())
    except OSError:
        pass


# --- Haftalık ödül kaydı: imzalı + iki yerde (dosya + Windows kayıt defteri) ---
# Skor tablosu olduğu için ödül kaydı sade bir tarih dosyası DEĞİLDİR:
#  * Kayıt, makineye özgü anahtarla HMAC imzalanır; elle düzenlenen veya
#    başka bir bilgisayardan kopyalanan kayıt geçersiz sayılır.
#  * Aynı kayıt hem dosyaya hem HKCU kayıt defterine yazılır; biri
#    silinirse diğeri ödülü yine engeller. İkisi de yoksa "ilk kez" sayılır.
#  * Geçersiz (kurcalanmış) kayıt görüldüğünde ödül VERİLMEZ ve kayıt bu
#    mesajın tarihiyle yeniden mühürlenir; yani kurcalamak ödülü
#    kazandırmaz, sadece o seferi kaybettirir (meşru donanım değişikliği
#    yaşayan oyuncu da bir sonraki haftaki ödüle normal şekilde ulaşır).
#  * Karar, yerel saate değil, sunucudaki mesajın TARİHİNE bağlıdır;
#    bilgisayar saatini geri almak işe yaramaz.
_REWARD_SECRET = b"karaborsa-weekly-reward-v1"
_REG_PATH = r"Software\KaraborsaSimulasyonu"
_REG_VALUE = "DailyRewardState"


def _machine_id() -> str:
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
        ) as key:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0])
    except Exception:
        pass
    try:
        import uuid
        return str(uuid.getnode())
    except Exception:
        return "unknown-machine"


def _sign(date_str: str) -> str:
    key = hashlib.sha256(_REWARD_SECRET + _machine_id().encode("utf-8")).digest()
    return hmac.new(key, date_str.encode("utf-8"), hashlib.sha256).hexdigest()


def _pack_reward_record(date_str: str) -> str:
    date_str = date_str.strip()
    return json.dumps({"d": date_str, "s": _sign(date_str)})


def _unpack_reward_record(raw):
    """('none', None) kayıt yok | ('ok', tarih) geçerli | ('bad', None) geçersiz."""
    if raw is None:
        return "none", None
    try:
        obj = json.loads(raw)
        date_str = str(obj["d"])
        if not hmac.compare_digest(str(obj["s"]), _sign(date_str)):
            return "bad", None
        date_obj = _parse_date(date_str)
        if date_obj is None:
            return "bad", None
        return "ok", date_obj
    except Exception:
        return "bad", None


def _read_reward_file():
    try:
        with open(_last_reward_path(), "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _read_reward_registry():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ) as key:
            return str(winreg.QueryValueEx(key, _REG_VALUE)[0])
    except Exception:
        return None


def _write_reward_everywhere(date_str: str) -> None:
    record = _pack_reward_record(date_str)
    try:
        os.makedirs(_data_dir(), exist_ok=True)
        with open(_last_reward_path(), "w", encoding="utf-8") as f:
            f.write(record)
    except OSError:
        pass
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, record)
    except Exception:
        pass


def is_reward_due(date_str: str) -> bool:
    """Bu tarihli günün mesajı için haftalık ödül verilmeli mi?
    - Hiçbir yerde kayıt yoksa (ilk kez): True.
    - Geçerli kayıt varsa: son ödülden en az REWARD_INTERVAL_DAYS gün sonra True.
    - Yalnızca geçersiz (kurcalanmış) kayıt varsa: False; kayıt bu mesajın
      tarihiyle yeniden mühürlenir (bkz. yukarıdaki açıklama)."""
    date_obj = _parse_date(date_str)
    if date_obj is None:
        return False

    states = [_unpack_reward_record(_read_reward_file()),
              _unpack_reward_record(_read_reward_registry())]
    valid_dates = [d for status, d in states if status == "ok"]

    if valid_dates:
        last = max(valid_dates)
        due = (date_obj - last).days >= REWARD_INTERVAL_DAYS
        if not due and any(status != "ok" for status, _ in states):
            # Bir kopya silinmiş/bozulmuş: geçerli olan kayıttan onar.
            _write_reward_everywhere(last.strftime("%d.%m.%Y"))
        return due

    if any(status == "bad" for status, _ in states):
        _write_reward_everywhere(date_str)
        return False

    return True


def mark_reward_given(date_str: str) -> None:
    """Ödülün VERİLDİĞİNİ kalıcı ve imzalı olarak işaretler. Nakit
    eklendikten hemen sonra çağrılmalıdır; böylece oyun çökse bile aynı
    ödül iki kez verilmez."""
    _write_reward_everywhere(date_str)


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
