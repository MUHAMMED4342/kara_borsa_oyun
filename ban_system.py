"""
ban_system.py
-------------
Skor tablosu ve destek bileti sistemi için BİLGİSAYAR (cihaz) bazlı yasak.

Akış
~~~~
* Yönetici (admin_panel.py) yasakları GitHub Gist içindeki "yasaklar.json"
  dosyasına yazar: cihaz kimliği ve/veya kullanıcı adı, sebep, bitiş günü
  (boşsa süresiz), kapsam (skor tablosu / destek bileti).
* Oyun her açılışta bu listeyi indirir (sync). Listede bu bilgisayarla
  eşleşen bir yasak varsa YEREL KAYDA yazılır: imzalı dosya + Windows kayıt
  defteri + ikinci bir dosya (üç yerde birden). Yasak kullanıcı adına
  değil bu kaydın cihaz kimliğine bağlıdır; kullanıcı adı değiştirmek işe
  yaramaz.
* Skor göndermeden / bilet açmadan önce check_online() çağrılır: liste
  yeniden indirilir ve yerel kayıtla birleştirilir. Yerel kayıt silinse bile
  yasak, listede durduğu sürece geri gelir.
* Yönetici yasağı listeden kaldırınca bir sonraki başarılı senkronizasyonda
  yerel kayıt da temizlenir. Süresi dolan yasak da kendiliğinden kalkar
  (bitiş gününün SONUNA kadar geçerlidir).

Bilinen sınırlar
~~~~~~~~~~~~~~~~
Cihaz kimliği Windows MachineGuid'inin özetidir; kimliği değiştiren
(ör. Windows'u yeniden kuran) biri yeni cihaz sayılır. Oyun açık kaynak
olduğu için kararlı biri yerel korumaları aşabilir; gerçek güvence
yasak listesinin sunucu tarafında uygulanmasıdır.
"""

import hashlib
import hmac
import json
import os
import threading
import urllib.request
from datetime import date, datetime
from email.utils import parsedate_to_datetime

import app_paths

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"

# leaderboard.py / admin_panel.py ile aynı Gist
GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"
GIST_API = f"https://api.github.com/gists/{GIST_ID}"
BAN_FILE = "yasaklar.json"

STATE_FILENAME = "yasak_durumu.dat"
_REG_PATH = r"Software\KaraborsaSimulasyonu"
_REG_VALUE = "BanState"
_SECRET = b"karaborsa-ban-state-v1"
REQUEST_TIMEOUT = 6

SCOPE_LEADERBOARD = "leaderboard"
SCOPE_TICKETS = "tickets"

_lock = threading.Lock()
_device_id_cache = None


# ------------------------------------------------------------ cihaz kimliği
def _machine_guid() -> str:
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
        return "mac-" + str(uuid.getnode())
    except Exception:
        return "unknown-machine"


def get_device_id() -> str:
    """Bu bilgisayarın kararlı, geri döndürülemeyen kimliği (32 hex)."""
    global _device_id_cache
    if _device_id_cache is None:
        raw = ("karaborsa-device-v1|" + _machine_guid()).encode("utf-8")
        _device_id_cache = hashlib.sha256(raw).hexdigest()[:32]
    return _device_id_cache


# ------------------------------------------------------------------ tarih
def parse_date(date_str):
    date_str = (date_str or "").strip()
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def is_active(ban: dict, today: date = None) -> bool:
    """Yasak bitiş gününün sonuna kadar geçerlidir; bitiş boşsa süresizdir."""
    today = today or date.today()
    until = (ban.get("until") or "").strip()
    if not until:
        return True
    until_date = parse_date(until)
    if until_date is None:
        return True  # bozuk tarih: güvenli taraf, yasak geçerli say
    return today <= until_date


# --------------------------------------------------- yerel (imzalı) kayıt
def _sign(payload: str) -> str:
    key = hashlib.sha256(_SECRET + get_device_id().encode("utf-8")).digest()
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _pack(bans: list) -> str:
    payload = json.dumps(bans, ensure_ascii=False, sort_keys=True)
    return json.dumps({"b": payload, "s": _sign(payload)})


def _unpack(raw):
    """Geçerliyse yasak listesi, kayıt yoksa/bozuksa None."""
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        payload = obj["b"]
        if not hmac.compare_digest(str(obj["s"]), _sign(payload)):
            return None
        bans = json.loads(payload)
        return [b for b in bans if isinstance(b, dict) and b.get("id")]
    except Exception:
        return None


def _state_paths() -> list:
    paths = []
    try:
        paths.append(os.path.join(
            app_paths.user_data_dir(APP_NAME, APP_AUTHOR), STATE_FILENAME))
    except Exception:
        pass
    roaming = os.environ.get("APPDATA")
    if roaming:
        paths.append(os.path.join(roaming, "Karaborsa", "sistem", STATE_FILENAME))
    return paths


def _read_registry():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH, 0, winreg.KEY_READ) as key:
            return str(winreg.QueryValueEx(key, _REG_VALUE)[0])
    except Exception:
        return None


def _load_local() -> list:
    """Üç kayıt yerindeki GEÇERLİ kayıtların birleşimi (id'ye göre)."""
    merged = {}
    sources = [_read_registry()]
    for p in _state_paths():
        try:
            with open(p, "r", encoding="utf-8") as f:
                sources.append(f.read())
        except OSError:
            sources.append(None)
    for raw in sources:
        bans = _unpack(raw)
        for b in bans or []:
            merged[b["id"]] = b
    return list(merged.values())


def _save_local(bans: list) -> None:
    record = _pack(bans)
    for p in _state_paths():
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(record)
        except OSError:
            pass
    try:
        import winreg
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, _REG_PATH, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _REG_VALUE, 0, winreg.REG_SZ, record)
    except Exception:
        pass


# ------------------------------------------------------------- uzak liste
def fetch_remote():
    """(yasak_listesi, sunucu_tarihi) döner; ağ/format hatasında (None, None).
    Kimlik doğrulama GEREKMEZ (Gist okuma)."""
    try:
        req = urllib.request.Request(
            GIST_API,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "karaborsa-simulasyonu"},
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            date_header = resp.headers.get("Date")
        server_date = None
        if date_header:
            try:
                server_date = parsedate_to_datetime(date_header).date()
            except Exception:
                server_date = None
        files = body.get("files", {})
        info = files.get(BAN_FILE)
        if not info:
            return [], server_date  # dosya yok = hiç yasak yok
        content = (info.get("content") or "").strip()
        data = json.loads(content) if content else {}
        bans = data.get("bans", []) if isinstance(data, dict) else []
        bans = [b for b in bans if isinstance(b, dict) and b.get("id")]
        return bans, server_date
    except Exception:
        return None, None


def _matches(ban: dict, username: str) -> bool:
    device = (ban.get("device") or "").strip().lower()
    if device and device == get_device_id():
        return True
    name = (ban.get("username") or "").strip().lower()
    return bool(name) and name == (username or "").strip().lower()


def sync(username: str = "") -> list:
    """Uzak listeyi indirip yerel kaydı günceller; AKTİF yasakları döner.
    İndirme başarısızsa yerel kayıt olduğu gibi (süresi dolanlar hariç)
    kullanılır."""
    with _lock:
        local = {b["id"]: b for b in _load_local()}
        remote, server_date = fetch_remote()
        today = server_date or date.today()

        if remote is not None:
            remote_ids = {b["id"] for b in remote}
            # Yönetici kaldırdıysa yerel kayıt da kalkar.
            local = {i: b for i, b in local.items() if i in remote_ids}
            for b in remote:
                if _matches(b, username):
                    local[b["id"]] = b      # eşleşen yasak yerele yazılır
                # Eşleşmiyor ama yerelde zaten varsa kalır (kullanıcı adı
                # değiştirilse bile cihaz yasağı sürer).
                elif b["id"] in local:
                    local[b["id"]] = b      # güncel sebep/bitiş

        active = {i: b for i, b in local.items() if is_active(b, today)}
        _save_local(list(active.values()))
        return list(active.values())


def sync_async(username: str, on_done) -> None:
    """Arka planda sync() çalıştırır; on_done(aktif_yasaklar) ARKA PLAN
    thread'inde çağrılır (arayüzde wx.CallAfter kullanın)."""
    def worker():
        try:
            bans = sync(username)
        except Exception:
            bans = []
        try:
            on_done(bans)
        except Exception:
            pass
    threading.Thread(target=worker, daemon=True).start()


# ---------------------------------------------------------------- sorgular
def is_banned(scope: str):
    """YEREL kayıta göre bu kapsamda geçerli bir yasak varsa o yasağı
    (sözlük) döner, yoksa None. Ağ kullanmaz; hızlıdır."""
    try:
        today = date.today()
        for b in _load_local():
            if b.get(scope) and is_active(b, today):
                return b
    except Exception:
        pass
    return None


def check_online(scope: str, username: str = ""):
    """Eylemden (skor gönderme / bilet açma) HEMEN ÖNCE çağrılır: listeyi
    yeniden indirir, yerel kayıtla birleştirir ve bu kapsamdaki yasağı döner
    (yoksa None). Bloklayıcıdır; arka plan thread'inde çağırın."""
    try:
        sync(username)
    except Exception:
        pass
    return is_banned(scope)


# ------------------------------------------------------------------ mesaj
def describe(ban: dict) -> str:
    """Yasağı oyuncunun dilinde anlatan mesaj: kapsam, sebep, süre."""
    from i18n import t
    lb, tk = bool(ban.get(SCOPE_LEADERBOARD)), bool(ban.get(SCOPE_TICKETS))
    if lb and tk:
        scopes = t("ban.scope_both")
    elif tk:
        scopes = t("ban.scope_tickets")
    else:
        scopes = t("ban.scope_leaderboard")
    reason = (ban.get("reason") or "").strip() or t("ban.no_reason")
    until = (ban.get("until") or "").strip()
    duration = t("ban.duration_until", date=until) if until else t("ban.duration_permanent")
    return t("ban.message", scopes=scopes, reason=reason, duration=duration)


def describe_all(bans: list) -> str:
    return "\n\n".join(describe(b) for b in bans)
