"""
auth_manager.py
----------------
PocketBase (kendi barındırdığımız, Railway üzerinde çalışan) ile
kullanıcı adı + şifre tabanlı kayıt/giriş işlemlerini ve buluta
(PocketBase veritabanı) kayıt senkronizasyonunu yönetir.

Bu modül save_manager.py'daki yerel (cihaza bağlı) kayıt sistemini
DEĞİŞTİRMEZ; onun üzerine, hesaba (kullanıcı adına) bağlı bir bulut
yedeği ekler. Böylece:
  - Giriş yapmadan / hesap oluşturmadan oyuna kesinlikle girilemez
    (bkz. main.py -> App.OnInit, dialogs.py -> AuthDialog).
  - Oyuncu farklı bir bilgisayara geçse, oyunu silip yeniden kurup
    aynı hesapla tekrar giriş yapsa bile ilerlemesi PocketBase'de
    saklandığı için kaybolmaz.

PocketBase tarafında gerekli koleksiyon/kural kurulumu için bu
projeyle birlikte verilen kurulum talimatlarına bakın (Railway'de
PocketBase şablonu + admin panelinden 'users' ve 'saves'
koleksiyonlarının ayarlanması, 'users' koleksiyonunun Identity/Password
ayarlarında kimlik alanlarına 'username'in eklenmesi). Oyuncu hem bir
kullanıcı adı hem de gerçek bir e-posta adresi girer: kullanıcı adı
oyun içindeki kimliği ve giriş bilgisidir, e-posta ise sadece kayıt
altına alınır (admin panelinden görülebilir) - şifre sıfırlama gibi
bir amaçla kullanılmaz.
"""

import os
import re
import json
import time
import datetime
import threading
import appdirs
import requests


# --- BURAYI DÜZENLEYİN --------------------------------------------------
# Railway'de PocketBase'i dağıttıktan sonra size verilen genel adresi
# (https://xxxx.up.railway.app gibi, SONUNDA / OLMADAN) buraya yapıştırın.
POCKETBASE_URL = os.environ.get(
    "KARABORSA_POCKETBASE_URL",
    "https://pocketbase-railway-production-56ef.up.railway.app",
)
# -------------------------------------------------------------------------

USERS_COLLECTION = "users"
SAVES_COLLECTION = "saves"

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
SESSION_FILENAME = "session.json"
_SESSION_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
_SESSION_PATH = os.path.join(_SESSION_DIR, SESSION_FILENAME)

REQUEST_TIMEOUT = 15

# Buluta ardışık gönderimler arasında beklenecek EN AZ süre (saniye).
# Bu, Railway/PocketBase kullanım kotasının (kredi) her tek oyun
# içi işlemde (alım/satım, gün ilerletme vb.) boşa harcanmasını
# önler. Yerel diske kayıt (save_manager) bundan ETKİLENMEZ - o her
# zaman anında olur, veri kaybı riski yoktur. Sadece "buluta senkron"
# adımı yavaşlatılır; oyunu kapatırken (main.py -> on_close) yine de
# ZORUNLU olarak (force=True ile) gönderilir, o yüzden en güncel hal
# her zaman buluta ulaşır.
MIN_CLOUD_PUSH_INTERVAL_SECONDS = 90
_last_cloud_push_at = 0.0
_push_state_lock = threading.Lock()


class AuthError(Exception):
    """Kimlik doğrulama / ağ hatalarını kullanıcıya gösterilecek
    Türkçe bir mesajla birlikte taşımak için kullanılır."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.message = message
        self.code = code


def _headers(access_token=None):
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _parse_error(response) -> str:
    try:
        data = response.json()
    except Exception:
        return response.text or f"HTTP {response.status_code}"

    msg = data.get("message") or str(data)

    # PocketBase alan bazlı doğrulama hatalarını da (varsa) mesaja ekle
    field_errors = data.get("data") or {}
    details = []
    for field, info in field_errors.items():
        if isinstance(info, dict) and info.get("message"):
            details.append(info["message"])
    if details:
        msg = f"{msg} ({'; '.join(details)})"

    translations = {
        "failed to authenticate": "Kullanıcı adı veya şifre hatalı.",
        "invalid login credentials": "Kullanıcı adı veya şifre hatalı.",
        "the username is invalid or already in use": "Bu kullanıcı adı zaten alınmış. Lütfen 'Giriş Yap' butonunu deneyin ya da başka bir kullanıcı adı seçin.",
        "value must be unique": "Bu kullanıcı adı zaten alınmış. Lütfen 'Giriş Yap' butonunu deneyin ya da başka bir kullanıcı adı seçin.",
        "the password must be at least": "Şifre en az 8 karakter olmalı.",
        "failed to create record": "Hesap oluşturulamadı. Bilgileri kontrol edip tekrar deneyin.",
        "old password": "Mevcut şifreniz hatalı.",
        "oldpassword": "Mevcut şifreniz hatalı.",
    }
    msg_str = str(msg).lower()
    for key, tr in translations.items():
        if key in msg_str:
            return tr
    return msg


def _validate_email(email: str) -> str:
    email = (email or "").strip()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise AuthError("Geçerli bir e-posta adresi girin (örn: isim@example.com).")
    return email


def _validate_username(username: str) -> str:
    username = (username or "").strip()
    if not re.match(r"^[a-zA-Z0-9_]{3,20}$", username):
        raise AuthError(
            "Kullanıcı adı 3-20 karakter olmalı ve sadece harf, "
            "rakam ile alt çizgi (_) içerebilir."
        )
    return username


# ---------------------------------------------------------------------------
# Aktif oturum (uygulama çalışırken bellekte tutulan) - save_manager bu
# oturuma bakarak kayıtları buluta gönderir
# ---------------------------------------------------------------------------

_current_session = {"access_token": None, "user_id": None, "username": None}
_lock = threading.Lock()


def set_current_session(session: dict) -> None:
    global _current_session
    record = (session or {}).get("record") or {}
    with _lock:
        _current_session = {
            "access_token": (session or {}).get("token"),
            "user_id": record.get("id"),
            "username": record.get("username"),
        }
    print(f"[Oturum] Ayarlandı -> user_id={_current_session['user_id']!r} username={_current_session['username']!r} token_var={bool(_current_session['access_token'])}")


def get_current_session() -> dict:
    with _lock:
        return dict(_current_session)


def is_logged_in() -> bool:
    sess = get_current_session()
    return bool(sess.get("access_token") and sess.get("user_id"))


def clear_current_session() -> None:
    set_current_session(None)


# ---------------------------------------------------------------------------
# Oturumun cihazda önbelleklenmesi (bir sonraki açılışta otomatik
# yenilemeyi denemek için - şifre ASLA burada saklanmaz)
# ---------------------------------------------------------------------------

def save_session(session: dict) -> None:
    try:
        os.makedirs(_SESSION_DIR, exist_ok=True)
        to_store = {
            "token": session.get("token"),
            "record": session.get("record"),
        }
        with open(_SESSION_PATH, "w", encoding="utf-8") as f:
            json.dump(to_store, f)
    except Exception:
        pass


def load_cached_session() -> dict:
    try:
        with open(_SESSION_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def clear_session() -> None:
    try:
        if os.path.exists(_SESSION_PATH):
            os.remove(_SESSION_PATH)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Kimlik doğrulama (PocketBase REST API)
# ---------------------------------------------------------------------------

def sign_up(username: str, password: str, email: str) -> dict:
    """Yeni hesap oluşturur ve ardından otomatik giriş yapar. Başarılıysa
    session dict (token, record) döner. email, gerçek bir e-posta
    adresi olmalı - sadece kayıt altına alınır, admin panelinden
    görülebilir; oyuncu bundan sonra HER ZAMAN kullanıcı adıyla giriş
    yapar."""
    username = _validate_username(username)
    email = _validate_email(email)
    if not password or len(password) < 8:
        raise AuthError("Şifre en az 8 karakter olmalı.")

    payload = {
        "username": username,
        "email": email,
        "emailVisibility": True,
        "password": password,
        "passwordConfirm": password,
    }

    try:
        resp = requests.post(
            f"{POCKETBASE_URL}/api/collections/{USERS_COLLECTION}/records",
            headers=_headers(),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise AuthError(f"Sunucuya bağlanılamadı: {e}")

    if resp.status_code >= 400:
        print(f"[Kayıt] Hesap oluşturma BAŞARISIZ. HTTP {resp.status_code} -> ham cevap: {resp.text}")
        raise AuthError(_parse_error(resp))

    created = resp.json()
    print(f"[Kayıt] Hesap oluşturuldu. user_id={created.get('id')!r} username={created.get('username')!r} - şimdi otomatik giriş deneniyor...")

    # Kayıt başarılı oldu, şimdi otomatik giriş yap
    return sign_in(username, password)


def sign_in(username: str, password: str) -> dict:
    """Kullanıcı adı + şifre ile giriş yapar. Başarılıysa session dict
    döner, başarısızsa AuthError fırlatır (Türkçe, kullanıcıya
    gösterilebilir mesajla)."""
    username = (username or "").strip()
    if not username or not password:
        raise AuthError("Kullanıcı adı ve şifre gerekli.")

    try:
        resp = requests.post(
            f"{POCKETBASE_URL}/api/collections/{USERS_COLLECTION}/auth-with-password",
            headers=_headers(),
            json={"identity": username, "password": password},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise AuthError(f"Sunucuya bağlanılamadı: {e}")

    if resp.status_code >= 400:
        print(f"[Giriş] BAŞARISIZ. HTTP {resp.status_code} -> ham cevap: {resp.text}")
        raise AuthError(_parse_error(resp))

    data = resp.json()
    print(f"[Giriş] Başarılı. user_id={data.get('record', {}).get('id')!r} username={data.get('record', {}).get('username')!r}")
    return {"token": data["token"], "record": data.get("record")}


def refresh_session(cached_token: str) -> dict:
    """Önbellekteki (henüz süresi dolmamış) token ile yeni bir token
    alır. Başarısız olursa (token geçersiz/süresi dolmuş) AuthError
    fırlatır; bu durumda çağıran taraf kullanıcıyı MUTLAKA tekrar
    giriş ekranına yönlendirmelidir (bkz. main.py).

    ÖNEMLİ: sunucuya hiç ulaşılamaması (internet yok, DNS hatası,
    zaman aşımı) ile sunucunun token'ı GERÇEKTEN reddetmesi (401/403,
    hesap silinmiş vb.) birbirinden ayrılır. İlkinde code="network"
    ile bir AuthError fırlatılır - bu, "oturum geçersiz" anlamına
    GELMEZ, sadece şu an sunucuya erişilemediği anlamına gelir.
    Çağıran taraf (try_restore_session) bu ayrımı kullanarak
    internet yokken oturumu SİLMEDEN, önbellekteki bilgilerle
    çevrimdışı devam etmeye izin verir."""
    if not cached_token:
        raise AuthError("Kayıtlı oturum yok.")

    try:
        resp = requests.post(
            f"{POCKETBASE_URL}/api/collections/{USERS_COLLECTION}/auth-refresh",
            headers=_headers(cached_token),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise AuthError(f"Sunucuya bağlanılamadı: {e}", code="network")

    if resp.status_code >= 400:
        raise AuthError(_parse_error(resp))

    data = resp.json()
    return {"token": data["token"], "record": data.get("record")}


def sign_out() -> None:
    # PocketBase'de sunucu taraflı bir "logout" uç noktası yok (token
    # süresi dolana kadar geçerlidir); burada sadece cihazdaki önbelleği
    # ve bellekteki oturumu temizliyoruz.
    clear_session()
    clear_current_session()


def try_restore_session() -> dict:
    """Uygulama açılışında önbellekteki oturumu sessizce yenilemeyi
    dener. Geçerli bir oturum varsa session dict, yoksa None döner.
    None dönerse çağıran taraf (main.py) girişi ZORUNLU tutmalı ve
    AuthDialog'u göstermelidir - burada asla sessizce içeri
    alınmaz.

    İSTİSNA: sunucuya hiç ulaşılamıyorsa (internet yok), bu ZORUNLU
    girişe SEBEP OLMAZ. Daha önce bu cihazda bir kez giriş yapılmışsa,
    önbellekteki (belki eski) oturumla ÇEVRİMDIŞI devam edilir - oyun
    yerel diske (save_manager) zaten kaydediyor, bulut senkronu sadece
    internet gelince fırsat buldukça yapılır. Oturum SADECE sunucu
    onu gerçekten reddederse (401/403, hesap silinmiş vb.) silinir."""
    cached = load_cached_session()
    if not cached or not cached.get("token"):
        return None
    try:
        session = refresh_session(cached["token"])
        save_session(session)
        return session
    except AuthError as e:
        if e.code == "network":
            print(f"[Oturum] İnternete ulaşılamadı, önbellekteki oturumla çevrimdışı devam ediliyor: {e.message}")
            offline_session = dict(cached)
            offline_session["_offline"] = True
            return offline_session
        clear_session()
        return None


def update_username(new_username: str) -> str:
    """O an giriş yapmış olan hesabın kullanıcı adını (gerçek PocketBase
    hesabı, yani giriş kimliği) değiştirir. Nakit/envanter/vb. hiçbir
    şeyi etkilemez - sadece hesabın adı değişir. Başarılı olursa
    temizlenmiş yeni kullanıcı adını döner ve bellekteki/diskteki
    oturum önbelleğini de günceller (böylece oyuncu oyunu yeniden
    başlatmadan da yeni adıyla devam edebilir). Başarısız olursa
    (örn. bu ad başka biri tarafından kullanılıyorsa) AuthError
    fırlatır."""
    new_username = _validate_username(new_username)

    sess = get_current_session()
    access_token = sess.get("access_token")
    user_id = sess.get("user_id")
    if not access_token or not user_id:
        raise AuthError("Önce giriş yapmanız gerekiyor.")

    try:
        resp = requests.patch(
            f"{POCKETBASE_URL}/api/collections/{USERS_COLLECTION}/records/{user_id}",
            headers=_headers(access_token),
            json={"username": new_username},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise AuthError(f"Sunucuya bağlanılamadı: {e}")

    if resp.status_code >= 400:
        raise AuthError(_parse_error(resp))

    updated_record = resp.json()
    # Bellekteki ve diskteki oturumu, yeni kullanıcı adını yansıtacak
    # şekilde güncelle
    updated_session = {"token": access_token, "record": updated_record}
    set_current_session(updated_session)
    save_session(updated_session)

    return updated_record.get("username", new_username)


def update_password(old_password: str, new_password: str) -> None:
    """O an giriş yapmış olan hesabın şifresini değiştirir.

    PocketBase'de, zaten giriş yapmış bir kullanıcı KENDİ şifresini
    değiştirirken 'oldPassword' alanını da göndermek ZORUNDADIR (bu
    olmadan sunucu isteği reddeder). Şifre başarıyla değiştiğinde
    PocketBase o hesaba ait ÖNCEKİ TÜM token'ları geçersiz kılar; bu
    yüzden burada işlem başarılı olur olmaz yeni şifreyle otomatik
    tekrar giriş yapılıp bellekteki/diskteki oturum tazelenir - aksi
    halde oyuncu şifresini değiştirdiği anda "oturumu düşmüş" gibi
    bir duruma girerdi.

    Başarısız olursa (mevcut şifre yanlış, yeni şifre çok kısa vb.)
    AuthError fırlatır."""
    if not new_password or len(new_password) < 8:
        raise AuthError("Yeni şifre en az 8 karakter olmalı.")
    if not old_password:
        raise AuthError("Mevcut şifrenizi girmeniz gerekiyor.")

    sess = get_current_session()
    access_token = sess.get("access_token")
    user_id = sess.get("user_id")
    username = sess.get("username")
    if not access_token or not user_id:
        raise AuthError("Önce giriş yapmanız gerekiyor.")

    try:
        resp = requests.patch(
            f"{POCKETBASE_URL}/api/collections/{USERS_COLLECTION}/records/{user_id}",
            headers=_headers(access_token),
            json={
                "oldPassword": old_password,
                "password": new_password,
                "passwordConfirm": new_password,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as e:
        raise AuthError(f"Sunucuya bağlanılamadı: {e}")

    if resp.status_code >= 400:
        raise AuthError(_parse_error(resp))

    # Şifre değişince eski token PocketBase tarafında geçersiz kılınır;
    # yeni şifreyle tekrar giriş yapıp oturumu (hem bellek hem disk)
    # tazeliyoruz ki oyuncu kesintisiz devam edebilsin.
    new_session = sign_in(username, new_password)
    set_current_session(new_session)
    save_session(new_session)


# ---------------------------------------------------------------------------
# Buluta kayıt senkronizasyonu (PocketBase koleksiyonu: saves)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _find_save_record_id(access_token: str, user_id: str) -> str:
    """Bu kullanıcıya ait mevcut 'saves' kaydının PocketBase record id'sini
    döner, yoksa None döner."""
    resp = requests.get(
        f"{POCKETBASE_URL}/api/collections/{SAVES_COLLECTION}/records",
        headers=_headers(access_token),
        params={"filter": f"(owner='{user_id}')", "perPage": 1},
        timeout=REQUEST_TIMEOUT,
    )
    if resp.status_code >= 400:
        return None
    items = resp.json().get("items") or []
    return items[0]["id"] if items else None


def push_cloud_save(access_token: str, user_id: str, save_data: dict) -> bool:
    """Kayıt verisini (save_manager'daki dict ile aynı yapı) PocketBase'deki
    saves koleksiyonuna upsert eder (varsa günceller, yoksa oluşturur).
    Ağ hatası durumunda oyunu bloklamamak için sessizce False döner."""
    if not access_token or not user_id:
        print(f"[Bulut Kayıt] İPTAL: access_token={bool(access_token)} user_id={user_id!r} - oturum eksik, gönderilmiyor.")
        return False
    try:
        payload = {"owner": user_id, "save_data": save_data}
        print(f"[Bulut Kayıt] Gönderiliyor... user_id={user_id!r} token_var={bool(access_token)}")
        existing_id = _find_save_record_id(access_token, user_id)
        print(f"[Bulut Kayıt] Mevcut kayıt aranıyor -> bulunan_id={existing_id!r}")

        if existing_id:
            resp = requests.patch(
                f"{POCKETBASE_URL}/api/collections/{SAVES_COLLECTION}/records/{existing_id}",
                headers=_headers(access_token),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        else:
            resp = requests.post(
                f"{POCKETBASE_URL}/api/collections/{SAVES_COLLECTION}/records",
                headers=_headers(access_token),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        print(f"[Bulut Kayıt] Sunucu cevabı: HTTP {resp.status_code} -> {resp.text[:300]}")
        return resp.status_code < 400
    except requests.RequestException as e:
        print(f"[Bulut Kayıt] AĞ HATASI: {e}")
        return False


def push_active_save_async(save_data: dict, force: bool = False) -> None:
    """push_cloud_save'i, o an aktif olan oturumla, arka planda (ayrı
    bir thread'de) çalıştırır. Oturum yoksa veya internet yoksa oyunu
    bloklamaz / hata fırlatmaz - kayıt her durumda yerel diske
    (save_manager) zaten yazılmış olur, bulut senkronu ek bir
    güvencedir.

    Kullanım kotasını (Railway/PocketBase kredisi) korumak için ard
    arda gelen çağrılar arasında en az MIN_CLOUD_PUSH_INTERVAL_SECONDS
    kadar bekler; bu süre dolmadan gelen çağrılar sessizce atlanır
    (yerel kayıt yine de yapılmıştır, sadece bulut senkronu ertelenir).
    force=True verilirse (örn. oyun kapatılırken) bu bekleme atlanır ve
    gönderim mutlaka yapılır."""
    import traceback
    caller = traceback.extract_stack()[-2]
    print(f"[Bulut Kayıt] push_active_save_async çağrıldı -> {caller.filename}:{caller.lineno} ({caller.name}) force={force}")

    sess = get_current_session()
    if not sess.get("access_token") or not sess.get("user_id"):
        print(f"[Bulut Kayıt] İPTAL: access_token={bool(sess.get('access_token'))} user_id={sess.get('user_id')!r} - oturum eksik, gönderilmiyor.")
        return

    global _last_cloud_push_at
    with _push_state_lock:
        elapsed = time.monotonic() - _last_cloud_push_at
        if not force and elapsed < MIN_CLOUD_PUSH_INTERVAL_SECONDS:
            print(f"[Bulut Kayıt] Atlandı (kota koruması): son gönderimden sadece {elapsed:.0f}sn geçti, en az {MIN_CLOUD_PUSH_INTERVAL_SECONDS}sn bekleniyor.")
            return
        _last_cloud_push_at = time.monotonic()

    def worker():
        push_cloud_save(sess["access_token"], sess["user_id"], save_data)

    threading.Thread(target=worker, daemon=True).start()


def fetch_cloud_save(access_token: str, user_id: str) -> dict:
    """Bu kullanıcıya (hesaba) ait en güncel bulut kaydını döner, yoksa
    veya ağ hatası varsa None döner."""
    if not access_token or not user_id:
        return None
    try:
        resp = requests.get(
            f"{POCKETBASE_URL}/api/collections/{SAVES_COLLECTION}/records",
            headers=_headers(access_token),
            params={"filter": f"(owner='{user_id}')", "perPage": 1},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code >= 400:
            return None
        items = resp.json().get("items") or []
        if not items:
            return None
        return items[0].get("save_data")
    except requests.RequestException:
        return None
