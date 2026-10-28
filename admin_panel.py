"""
admin_panel.py
--------------
GitHub Gist üzerindeki skor tablosunu ve yasak listesini yönetmek için
wxPython paneli.

YASAKLAR (bilgisayar bazlı): "Seçili Kullanıcıyı Yasakla" ile sebep, bitiş
günü (süresiz veya N gün) ve kapsam (skor tablosu / destek bileti) girilir.
Yasak, Gist'teki "yasaklar.json" dosyasına yazılır; oyun her açılışta bu
listeyi indirir, eşleşen bilgisayarı yasaklar ve oyuncuya sebebi açılışta
mesaj olarak gösterir. "Yasak Listesi" ile yasaklar kaldırılır.
Cihaz kimliği: skor kaydında "device_id" alanı varsa kendiliğinden dolar.
BİLETLER (F8): açık/kapalı destek biletleri listelenir; kullanıcı adı ve cihaz
kimliği bilet metninden okunur, aynı cihazdan kaç bilet geldiği gösterilir.
Spam yapan birini buradan tek adımda yasaklayabilir (destek bileti kapsamı)
ve açık biletlerini toplu kapatabilirsiniz. github.txt (Issues yetkili token)
bu dosyanın yanında olmalı; yoksa token.txt denenir.

- Token SADECE bu dosyanın yanındaki token.txt dosyasından okunur.
- Hatalar gerçek sebebiyle gösterilir (401, 403, 404, SSL, zaman aşımı...).
- "Bağlantı Testi" butonu token, kullanıcı ve yetki bilgisini kontrol eder.
- Kısayollar: F5 = Yenile, Delete = Seçiliyi sil.
"""

import os
import re
import sys
import json
import threading
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
import wx

# leaderboard.py ile aynı Gist ID ve dosya adı
GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"
GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
SCORE_FILE = "skorlar.json"
LIST_KEY = "score_data"
BAN_FILE = "yasaklar.json"

# Destek biletleri: oyundaki ticket_manager.py ile AYNI depo (GitHub Issues)
TICKET_REPO = "MUHAMMED4342/biletlerim"
TICKET_API = f"https://api.github.com/repos/{TICKET_REPO}"
TICKET_LABEL = "oyun-ici-bilet"
TIMEOUT = 15


def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")
GITHUB_TOKEN_FILE = os.path.join(BASE_DIR, "github.txt")

_lock = threading.Lock()


class GistError(Exception):
    """Kullanıcıya gösterilecek anlaşılır hata."""


# ----------------------------------------------------------------- TOKEN
def read_token() -> str:
    """token.txt'den token okur. Sorun varsa GistError fırlatır."""
    if not os.path.exists(TOKEN_FILE):
        raise GistError(
            f"token.txt bulunamadı.\nBeklenen konum:\n{TOKEN_FILE}"
        )
    try:
        # utf-8-sig: Not Defteri'nin eklediği görünmez BOM karakterini siler
        with open(TOKEN_FILE, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    except OSError as e:
        raise GistError(f"token.txt okunamadı: {e}")

    # Boşluk, satır sonu ve yanlışlıkla eklenmiş tırnakları temizle
    token = raw.strip().strip('"').strip("'").strip()
    # "token xxxx" veya "Bearer xxxx" yazılmışsa öneki at
    for prefix in ("token ", "Bearer ", "bearer "):
        if token.startswith(prefix):
            token = token[len(prefix):].strip()
    # İçinde boşluk/satır kalmışsa ilk parçayı al
    token = "".join(token.split())

    if not token:
        raise GistError("token.txt boş.")
    return token


def mask_token(token: str) -> str:
    if len(token) <= 8:
        return "*" * len(token)
    return f"{token[:4]}...{token[-4:]} (uzunluk: {len(token)})"


# ------------------------------------------------------------------ HTTP
def _headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "skor-admin-panel",
    }


def _request(method: str, url: str, token: str, **kwargs) -> requests.Response:
    """İstek atar; hataları anlaşılır Türkçe mesajlara çevirir."""
    try:
        r = requests.request(
            method, url, headers=_headers(token), timeout=TIMEOUT, **kwargs
        )
    except requests.exceptions.SSLError as e:
        raise GistError(
            "SSL hatası. Sertifika doğrulanamadı (proxy/antivirüs veya "
            f"PyInstaller'da certifi eksik olabilir).\n{e}"
        )
    except requests.exceptions.Timeout:
        raise GistError("Bağlantı zaman aşımına uğradı. İnterneti kontrol edin.")
    except requests.exceptions.ConnectionError as e:
        raise GistError(f"Bağlantı kurulamadı. İnternet/proxy kontrol edin.\n{e}")
    except requests.exceptions.RequestException as e:
        raise GistError(f"İstek hatası: {e}")

    if r.status_code in (200, 201):
        return r

    try:
        detail = r.json().get("message", r.text[:200])
    except ValueError:
        detail = r.text[:200]

    explanations = {
        401: "Token geçersiz, süresi dolmuş veya iptal edilmiş.",
        403: "Yetki yetersiz ya da istek limiti aşıldı. Klasik token'da "
             "'gist' yetkisi işaretli olmalı.",
        404: "Gist bulunamadı. Gist ID yanlış olabilir ya da gist gizli ve "
             "token'ın hesabı erişemiyor (token, gist sahibinin hesabından "
             "alınmalı).",
        422: "GitHub gönderilen veriyi kabul etmedi.",
    }
    hint = explanations.get(r.status_code, "Beklenmeyen yanıt.")
    raise GistError(f"HTTP {r.status_code}: {hint}\nGitHub mesajı: {detail}")


# ------------------------------------------------------------ GIST VERİSİ
def fetch_scores(token: str) -> Tuple[Any, List[Dict]]:
    """
    (ham_veri, kayıt_listesi) döndürür.
    JSON hem {"score_data": [...]} hem de doğrudan [...] olabilir.
    """
    r = _request("GET", GIST_URL, token)
    files = r.json().get("files", {})

    if SCORE_FILE not in files:
        names = ", ".join(files.keys()) or "(hiç dosya yok)"
        raise GistError(
            f"Gist içinde '{SCORE_FILE}' dosyası yok.\nMevcut dosyalar: {names}"
        )

    info = files[SCORE_FILE]
    content = info.get("content", "")
    # Büyük dosyalar API'de kesilir; tam içeriği raw_url'den al
    if info.get("truncated") and info.get("raw_url"):
        content = _request("GET", info["raw_url"], token).text

    try:
        raw = json.loads(content) if content.strip() else {LIST_KEY: []}
    except json.JSONDecodeError as e:
        raise GistError(f"{SCORE_FILE} geçerli bir JSON değil: {e}")

    if isinstance(raw, list):
        entries = raw
    elif isinstance(raw, dict):
        entries = raw.get(LIST_KEY, [])
        if not isinstance(entries, list):
            raise GistError(f"'{LIST_KEY}' bir liste değil.")
    else:
        raise GistError("Beklenmeyen JSON yapısı.")

    entries = [e for e in entries if isinstance(e, dict)]
    return raw, entries


def save_scores(token: str, raw: Any, entries: List[Dict]) -> None:
    """Orijinal JSON yapısını koruyarak sadece skorlar dosyasını günceller."""
    if isinstance(raw, list):
        new_raw: Any = entries
    else:
        new_raw = dict(raw)
        new_raw[LIST_KEY] = entries

    payload = {
        "files": {
            SCORE_FILE: {"content": json.dumps(new_raw, ensure_ascii=False, indent=2)}
        }
    }
    _request("PATCH", GIST_URL, token, json=payload)


def delete_user(username: str) -> str:
    """Kullanıcıyı siler, sonuç mesajı döndürür; hata olursa GistError."""
    if not username:
        raise GistError("Kullanıcı adı boş olamaz.")

    token = read_token()
    with _lock:
        raw, entries = fetch_scores(token)
        remaining = [e for e in entries if e.get("username") != username]
        removed = len(entries) - len(remaining)
        if removed == 0:
            raise GistError(f"'{username}' skor tablosunda bulunamadı.")
        save_scores(token, raw, remaining)
    return f"'{username}' silindi ({removed} kayıt). Gist güncellendi."


# --------------------------------------------------------------- YASAKLAR
def _fetch_gist_files(token: str) -> Dict[str, Any]:
    return _request("GET", GIST_URL, token).json().get("files", {})


def _file_text(files: Dict[str, Any], name: str, token: str) -> str:
    info = files.get(name)
    if not info:
        return ""
    content = info.get("content", "")
    if info.get("truncated") and info.get("raw_url"):
        content = _request("GET", info["raw_url"], token).text
    return content or ""


def _bans_from_files(files: Dict[str, Any], token: str) -> Tuple[Dict, List[Dict]]:
    content = _file_text(files, BAN_FILE, token)
    try:
        raw = json.loads(content) if content.strip() else {}
    except json.JSONDecodeError as e:
        raise GistError(f"{BAN_FILE} geçerli bir JSON değil: {e}")
    if not isinstance(raw, dict):
        raw = {}
    bans = raw.get("bans", [])
    if not isinstance(bans, list):
        raise GistError("'bans' bir liste değil.")
    return raw, [b for b in bans if isinstance(b, dict)]


def _scores_from_files(files: Dict[str, Any], token: str) -> Tuple[Any, List[Dict]]:
    content = _file_text(files, SCORE_FILE, token)
    try:
        raw = json.loads(content) if content.strip() else {LIST_KEY: []}
    except json.JSONDecodeError as e:
        raise GistError(f"{SCORE_FILE} geçerli bir JSON değil: {e}")
    entries = raw if isinstance(raw, list) else raw.get(LIST_KEY, [])
    return raw, [e for e in entries if isinstance(e, dict)]


def _scores_content(raw: Any, entries: List[Dict]) -> str:
    new_raw: Any = entries if isinstance(raw, list) else {**raw, LIST_KEY: entries}
    return json.dumps(new_raw, ensure_ascii=False, indent=2)


def _bans_content(raw: Dict, bans: List[Dict]) -> str:
    return json.dumps({**raw, "version": 1, "bans": bans}, ensure_ascii=False, indent=2)


def list_bans() -> List[Dict]:
    token = read_token()
    _, bans = _bans_from_files(_fetch_gist_files(token), token)
    return bans


def add_ban(username: str, device: str, reason: str, days: Optional[int],
            leaderboard: bool, tickets: bool, remove_scores: bool) -> str:
    """Yasak ekler. days=None -> süresiz. Aynı cihaz/kullanıcı için eski yasak
    yenisiyle değiştirilir. remove_scores: kullanıcının skor kayıtları da
    silinir (aynı istekte, tek PATCH ile)."""
    username = (username or "").strip()
    device = (device or "").strip().lower()
    if not username and not device:
        raise GistError("Kullanıcı adı veya cihaz kimliğinden en az biri gerekli.")
    if not (leaderboard or tickets):
        raise GistError("En az bir kapsam seçin (skor tablosu / destek bileti).")

    token = read_token()
    with _lock:
        files = _fetch_gist_files(token)
        bans_raw, bans = _bans_from_files(files, token)

        today = date.today()
        until = "" if days is None else (today + timedelta(days=int(days))).strftime("%d.%m.%Y")
        ban = {
            "id": uuid.uuid4().hex[:12],
            "device": device,
            "username": username,
            "reason": (reason or "").strip(),
            "created": today.strftime("%d.%m.%Y"),
            "until": until,
            "leaderboard": bool(leaderboard),
            "tickets": bool(tickets),
        }

        def same(b: Dict) -> bool:
            bd = (b.get("device") or "").strip().lower()
            bu = (b.get("username") or "").strip().lower()
            return (bool(device) and bd == device) or (bool(username) and bu == username.lower())

        bans = [b for b in bans if not same(b)] + [ban]
        payload_files = {BAN_FILE: {"content": _bans_content(bans_raw, bans)}}

        removed = 0
        if remove_scores:
            raw_scores, entries = _scores_from_files(files, token)

            def is_target(e: Dict) -> bool:
                ed = (str(e.get("device_id") or "")).strip().lower()
                return ((bool(username) and e.get("username") == username)
                        or (bool(device) and ed == device))

            remaining = [e for e in entries if not is_target(e)]
            removed = len(entries) - len(remaining)
            if removed:
                payload_files[SCORE_FILE] = {"content": _scores_content(raw_scores, remaining)}

        _request("PATCH", GIST_URL, token, json={"files": payload_files})

    target = username or device
    duration = f"{until} tarihine kadar" if until else "süresiz"
    msg = f"'{target}' yasaklandı ({duration})."
    if remove_scores:
        msg += f" Skor tablosundan {removed} kayıt silindi."
    return msg


def remove_ban(ban_id: str) -> str:
    token = read_token()
    with _lock:
        files = _fetch_gist_files(token)
        bans_raw, bans = _bans_from_files(files, token)
        remaining = [b for b in bans if b.get("id") != ban_id]
        if len(remaining) == len(bans):
            raise GistError("Yasak listede bulunamadı (zaten kaldırılmış olabilir).")
        _request("PATCH", GIST_URL, token,
                 json={"files": {BAN_FILE: {"content": _bans_content(bans_raw, remaining)}}})
    return "Yasak kaldırıldı. Oyuncunun bilgisayarında bir sonraki açılışta/gönderimde kalkar."


# --------------------------------------------------------------- BİLETLER
def _clean_token(raw: str) -> str:
    token = raw.strip().strip('"').strip("'").strip()
    for prefix in ("token ", "Bearer ", "bearer "):
        if token.startswith(prefix):
            token = token[len(prefix):].strip()
    return "".join(token.split())


def read_ticket_token() -> str:
    """Bilet deposu (Issues) için token: önce github.txt, yoksa token.txt."""
    for path in (GITHUB_TOKEN_FILE, TOKEN_FILE):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    token = _clean_token(f.read())
            except OSError:
                continue
            if token:
                return token
    raise GistError(
        "Bilet token'ı bulunamadı.\nBeklenen konum:\n"
        f"{GITHUB_TOKEN_FILE}\n(Issues: Read and write izinli token; yoksa token.txt denenir.)"
    )


_DEVICE_RE = re.compile(r"\*\*Device ID:\*\*\s*([0-9A-Fa-f]{8,64})")
_USER_RE = re.compile(r"\*\*Oyun kullanıcı adı:\*\*\s*(.+)")
_TITLE_USER_RE = re.compile(r"\(([^()]+)\)\s*$")


def parse_ticket(issue: Dict) -> Dict:
    """GitHub issue'sundan kullanıcı adı ve cihaz kimliğini çıkarır."""
    body = issue.get("body") or ""
    title = issue.get("title") or ""
    m = _USER_RE.search(body)
    username = m.group(1).strip() if m else ""
    if not username:
        m = _TITLE_USER_RE.search(title)
        username = m.group(1).strip() if m else ""
    m = _DEVICE_RE.search(body)
    device = m.group(1).lower() if m else ""
    return {
        "number": issue.get("number"),
        "title": re.sub(r"^\[Bilet\]\s*", "", title),
        "username": username,
        "device": device,
        "created": (issue.get("created_at") or "")[:10],
        "state": issue.get("state", "open"),
        "comments": issue.get("comments", 0),
        "url": issue.get("html_url", ""),
    }


def list_tickets(include_closed: bool = False, max_pages: int = 3) -> List[Dict]:
    """Biletleri (en yeni üstte) döner. Her kayıt: number, title, username,
    device, created, state, comments, url, same_device (aynı cihazdan gelen
    toplam bilet sayısı; spam tespiti için)."""
    token = read_ticket_token()
    state = "all" if include_closed else "open"
    tickets: List[Dict] = []
    for page in range(1, max_pages + 1):
        url = (f"{TICKET_API}/issues?state={state}&labels={TICKET_LABEL}"
               f"&per_page=100&page={page}")
        items = _request("GET", url, token).json()
        if not isinstance(items, list) or not items:
            break
        tickets += [parse_ticket(i) for i in items if "pull_request" not in i]
        if len(items) < 100:
            break
    counts: Dict[str, int] = {}
    for t in tickets:
        if t["device"]:
            counts[t["device"]] = counts.get(t["device"], 0) + 1
    for t in tickets:
        t["same_device"] = counts.get(t["device"], 1) if t["device"] else 1
    return tickets


PLAYER_MARKER = "<!--oyuncu-->"   # ticket_manager.py ile aynı
_HIDDEN_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _clean_body(text: str) -> str:
    return _HIDDEN_RE.sub("", text or "").strip()


def fetch_thread(number: int) -> Dict:
    """Bir biletin ilk mesajını ve tüm yorumlarını döner. Yorumlarda
    is_player: oyuncunun yorumu (gizli işaretli) mu, yönetim cevabı mı."""
    token = read_ticket_token()
    issue = _request("GET", f"{TICKET_API}/issues/{number}", token).json()
    comments: List[Dict] = []
    for page in range(1, 6):
        items = _request(
            "GET", f"{TICKET_API}/issues/{number}/comments?per_page=100&page={page}", token
        ).json()
        if not isinstance(items, list) or not items:
            break
        for c in items:
            raw = c.get("body") or ""
            comments.append({
                "id": c.get("id"),
                "author": (c.get("user") or {}).get("login", "?"),
                "body": _clean_body(raw),
                "created": (c.get("created_at") or "")[:16].replace("T", " "),
                "is_player": PLAYER_MARKER in raw,
            })
        if len(items) < 100:
            break
    info = parse_ticket(issue)
    return {"info": info, "state": issue.get("state", "open"),
            "body": _clean_body(issue.get("body")), "comments": comments}


def format_thread(th: Dict) -> str:
    """Konuşmayı okunur metne çevirir: her mesaj 'Kim - tarih' satırı + metin."""
    info = th["info"]
    parts = [f"Oyuncu ({info['username'] or '?'}) - {info['created']}\n{th['body']}"]
    for c in th["comments"]:
        who = "Oyuncu" if c["is_player"] else "Yönetim"
        parts.append(f"{who} - {c['created']}\n{c['body']}")
    return "\n\n".join(parts)


def post_reply(number: int, text: str, close: bool = False) -> str:
    """Bilete yönetim cevabı yazar (oyuncu bunu oyunda 'Yönetim cevabı'
    olarak görür ve yeni yanıt bildirimi alır). close=True ise ardından
    bileti kapatır."""
    text = (text or "").strip()
    if not text:
        raise GistError("Boş yanıt gönderilemez.")
    token = read_ticket_token()
    _request("POST", f"{TICKET_API}/issues/{number}/comments", token, json={"body": text})
    msg = f"#{number} numaralı bilete yanıt gönderildi."
    if close:
        _request("PATCH", f"{TICKET_API}/issues/{number}", token, json={"state": "closed"})
        msg += " Bilet kapatıldı."
    return msg


def close_tickets(numbers: List[int]) -> str:
    """Verilen numaralı biletleri kapatır (spam temizliği)."""
    token = read_ticket_token()
    closed, failed = 0, []
    for n in numbers:
        try:
            _request("PATCH", f"{TICKET_API}/issues/{n}", token,
                     json={"state": "closed", "state_reason": "not_planned"})
            closed += 1
        except GistError as e:
            failed.append(f"#{n}: {str(e).splitlines()[0]}")
    msg = f"{closed} bilet kapatıldı."
    if failed:
        msg += "\nKapatılamayanlar:\n" + "\n".join(failed)
    return msg


def run_diagnostics() -> str:
    """Token ve bağlantı testi; rapor metni döndürür."""
    lines = [f"Token dosyası: {TOKEN_FILE}"]
    try:
        token = read_token()
    except GistError as e:
        return "\n".join(lines + [f"HATA: {e}"])
    lines.append(f"Token okundu: {mask_token(token)}")

    try:
        r = _request("GET", "https://api.github.com/user", token)
        lines.append(f"Hesap: {r.json().get('login')}")
        scopes = r.headers.get("X-OAuth-Scopes")
        if scopes is None:
            lines.append("Yetkiler: görünmüyor (fine-grained token olabilir; "
                         "gist için klasik token kullanın)")
        else:
            lines.append(f"Yetkiler: {scopes or '(yok)'}")
            if "gist" not in scopes:
                lines.append("UYARI: 'gist' yetkisi yok!")
    except GistError as e:
        return "\n".join(lines + [f"Token testi başarısız:\n{e}"])

    try:
        tk = list_tickets(include_closed=False, max_pages=1)
        lines.append(f"Bilet deposu ({TICKET_REPO}): erişim tamam, {len(tk)} açık bilet (ilk sayfa)")
    except GistError as e:
        lines.append(f"Bilet deposu testi başarısız:\n{e}")

    try:
        r = _request("GET", GIST_URL, token)
        owner = r.json().get("owner", {}).get("login")
        lines.append(f"Gist erişimi: tamam (sahip: {owner})")
        _, entries = fetch_scores(token)
        lines.append(f"{SCORE_FILE}: {len(entries)} kayıt")
        try:
            lines.append(f"{BAN_FILE}: {len(list_bans())} yasak")
        except GistError as e:
            lines.append(f"{BAN_FILE} okunamadı: {e}")
    except GistError as e:
        lines.append(f"Gist testi başarısız:\n{e}")
    return "\n".join(lines)


# -------------------------------------------------------------------- GUI
class BanDialog(wx.Dialog):
    """Yasak bilgilerini girme penceresi (kullanıcı, cihaz, sebep, süre, kapsam)."""

    def __init__(self, parent, username: str = "", device: str = "",
                 leaderboard: bool = True, tickets: bool = False, remove_scores: bool = True):
        super().__init__(parent, title="Yasakla", size=(520, 560),
                         style=wx.DEFAULT_DIALOG_STYLE)
        panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        # Her etiket, kendi kontrolünden HEMEN ÖNCE oluşturulur (ekran okuyucu
        # adı + Tab sırası için); araya başka kontrol/etiket girmez.
        def field(label, make_ctrl, proportion=0):
            v.Add(wx.StaticText(panel, label=label), 0, wx.LEFT | wx.TOP, 10)
            ctrl = make_ctrl()
            v.Add(ctrl, proportion, wx.EXPAND | wx.ALL, 6)
            return ctrl

        self.username_ctrl = field("Kullanıcı adı:", lambda: wx.TextCtrl(panel, value=username))

        self.device_ctrl = field(
            "Cihaz kimliği (bilgisayar yasağı; biletteki 'Device ID' veya skor kaydındaki 'device_id'):",
            lambda: wx.TextCtrl(panel, value=device))
        v.Add(wx.StaticText(
            panel, label="Cihaz kimliği boşsa yasak kullanıcı adına bağlanır; oyuncu o adla "
                         "oyunu açınca yasak bilgisayarına işlenir."), 0, wx.LEFT | wx.RIGHT, 10)

        def make_reason():
            ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
            ctrl.SetMinSize((-1, 80))
            return ctrl
        self.reason_ctrl = field(
            "Yasaklanma sebebi (oyuncuya açılışta mesaj olarak gösterilir):", make_reason)

        self.permanent_cb = wx.CheckBox(panel, label="Süresiz yasak")
        v.Add(self.permanent_cb, 0, wx.LEFT | wx.TOP, 10)
        v.Add(wx.StaticText(panel, label="Yasak süresi (gün):"), 0, wx.LEFT | wx.TOP, 10)
        self.days_spin = wx.SpinCtrl(panel, min=1, max=3650, initial=7)
        v.Add(self.days_spin, 0, wx.ALL, 6)
        self.until_label = wx.StaticText(panel, label="")
        v.Add(self.until_label, 0, wx.LEFT | wx.BOTTOM, 10)

        self.lb_cb = wx.CheckBox(panel, label="Skor tablosundan yasakla")
        self.lb_cb.SetValue(leaderboard)
        self.tk_cb = wx.CheckBox(panel, label="Destek bileti göndermeyi engelle")
        self.tk_cb.SetValue(tickets)
        self.rm_cb = wx.CheckBox(panel, label="Bu kullanıcının skor tablosundaki kayıtlarını da sil")
        self.rm_cb.SetValue(remove_scores)
        for cb in (self.lb_cb, self.tk_cb, self.rm_cb):
            v.Add(cb, 0, wx.LEFT | wx.TOP, 10)

        btns = wx.StdDialogButtonSizer()
        self.ok_btn = wx.Button(panel, wx.ID_OK, "Yasakla")
        self.cancel_btn = wx.Button(panel, wx.ID_CANCEL, "Vazgeç")
        btns.AddButton(self.ok_btn)
        btns.AddButton(self.cancel_btn)
        btns.Realize()
        v.Add(btns, 0, wx.ALIGN_RIGHT | wx.ALL, 10)

        panel.SetSizer(v)
        self.permanent_cb.Bind(wx.EVT_CHECKBOX, lambda e: self._refresh_until())
        self.days_spin.Bind(wx.EVT_SPINCTRL, lambda e: self._refresh_until())
        self.days_spin.Bind(wx.EVT_TEXT, lambda e: self._refresh_until())
        self.ok_btn.Bind(wx.EVT_BUTTON, self.on_ok)
        self._refresh_until()
        self.reason_ctrl.SetFocus() if username or device else self.username_ctrl.SetFocus()
        self.Centre()

    def _days(self) -> Optional[int]:
        return None if self.permanent_cb.GetValue() else int(self.days_spin.GetValue())

    def _refresh_until(self):
        self.days_spin.Enable(not self.permanent_cb.GetValue())
        days = self._days()
        if days is None:
            self.until_label.SetLabel("Yasak süresiz olacak.")
        else:
            end = (date.today() + timedelta(days=days)).strftime("%d.%m.%Y")
            self.until_label.SetLabel(f"Yasak bitiş günü: {end} (o günün sonuna kadar geçerli)")

    def on_ok(self, event):
        if not (self.username_ctrl.GetValue().strip() or self.device_ctrl.GetValue().strip()):
            wx.MessageBox("Kullanıcı adı veya cihaz kimliğinden en az birini girin.",
                          "Eksik bilgi", wx.OK | wx.ICON_WARNING, self)
            return
        if not (self.lb_cb.GetValue() or self.tk_cb.GetValue()):
            wx.MessageBox("En az bir kapsam seçin (skor tablosu / destek bileti).",
                          "Eksik bilgi", wx.OK | wx.ICON_WARNING, self)
            return
        event.Skip()  # EVT_BUTTON ID_OK -> pencereyi kapatır

    def get_values(self) -> Dict[str, Any]:
        return {
            "username": self.username_ctrl.GetValue().strip(),
            "device": self.device_ctrl.GetValue().strip(),
            "reason": self.reason_ctrl.GetValue().strip(),
            "days": self._days(),
            "leaderboard": self.lb_cb.GetValue(),
            "tickets": self.tk_cb.GetValue(),
            "remove_scores": self.rm_cb.GetValue(),
        }


class BanListDialog(wx.Dialog):
    """Mevcut yasakları listeler; seçiliyi kaldırır."""

    def __init__(self, parent: "AdminPanelFrame"):
        super().__init__(parent, title="Yasak Listesi", size=(820, 460),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = parent
        self.bans: List[Dict] = []
        panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(panel, label="Yasaklar:"), 0, wx.LEFT | wx.TOP, 8)
        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER)
        for i, (name, w) in enumerate((("Kullanıcı", 130), ("Cihaz", 110), ("Sebep", 230),
                                       ("Bitiş", 100), ("Kapsam", 190))):
            self.list_ctrl.InsertColumn(i, name, width=w)
        v.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 6)
        h = wx.BoxSizer(wx.HORIZONTAL)
        self.remove_btn = wx.Button(panel, label="Yasağı Kaldır (Delete)")
        self.refresh_btn = wx.Button(panel, label="Yenile")
        self.close_btn = wx.Button(panel, wx.ID_CANCEL, "Kapat")
        for b in (self.remove_btn, self.refresh_btn, self.close_btn):
            h.Add(b, 0, wx.ALL, 5)
        v.Add(h, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(v)

        self.remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self.load())
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key)
        self.Centre()
        self.load()

    def on_key(self, event):
        if event.GetKeyCode() == wx.WXK_DELETE:
            self.on_remove(None)
        else:
            event.Skip()

    @staticmethod
    def _scope_text(b: Dict) -> str:
        parts = []
        if b.get("leaderboard"):
            parts.append("Skor tablosu")
        if b.get("tickets"):
            parts.append("Destek bileti")
        return ", ".join(parts)

    def load(self):
        def done(bans, error):
            if error:
                self.frame.show_error(error)
                return
            self.bans = bans
            self.list_ctrl.DeleteAllItems()
            for i, b in enumerate(bans):
                self.list_ctrl.InsertItem(i, str(b.get("username", "")))
                self.list_ctrl.SetItem(i, 1, str(b.get("device", ""))[:10])
                self.list_ctrl.SetItem(i, 2, str(b.get("reason", "")))
                self.list_ctrl.SetItem(i, 3, str(b.get("until") or "Süresiz"))
                self.list_ctrl.SetItem(i, 4, self._scope_text(b))
            if bans:
                self.list_ctrl.Select(0)
                self.list_ctrl.Focus(0)
                self.list_ctrl.SetFocus()
            self.frame.SetStatusText(f"{len(bans)} yasak listelendi.")

        self.frame.run_async(list_bans, done)

    def on_remove(self, event):
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1 or idx >= len(self.bans):
            wx.MessageBox("Lütfen kaldırmak istediğiniz yasağı seçin.", "Uyarı",
                          wx.OK | wx.ICON_WARNING, self)
            return
        ban = self.bans[idx]
        who = ban.get("username") or str(ban.get("device", ""))[:10]
        if wx.MessageBox(f"'{who}' için yasak kaldırılsın mı?", "Onay",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            return

        def done(message, error):
            if error:
                self.frame.show_error(error)
                return
            wx.MessageBox(message, "Bilgi", wx.OK | wx.ICON_INFORMATION, self)
            self.load()

        self.frame.run_async(lambda: remove_ban(ban["id"]), done)


class TicketThreadDialog(wx.Dialog):
    """Bir biletin konuşmasını okur ve yanıtlar. Oluşturma sırası = Tab sırası
    ve ekran okuyucu etiketi: etiket -> konuşma -> etiket -> yanıt kutusu ->
    düğmeler."""

    def __init__(self, owner: "TicketListDialog", ticket: Dict):
        super().__init__(owner, title=f"Bilet #{ticket['number']} - {ticket['title']}",
                         size=(820, 640), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.owner = owner
        self.frame = owner.frame
        self.ticket = ticket
        self.thread: Optional[Dict] = None
        panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self.conv_label = wx.StaticText(panel, label="Konuşma:")
        self.conv_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP)
        self.conv_text.SetMinSize((-1, 280))
        self.reply_label = wx.StaticText(panel, label="Yanıtınız (Ctrl+Enter ile gönderilir):")
        self.reply_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.reply_text.SetMinSize((-1, 110))
        self.send_btn = wx.Button(panel, label="Yanıtla")
        self.send_close_btn = wx.Button(panel, label="Yanıtla ve Kapat")
        self.ban_btn = wx.Button(panel, label="Sahibini Yasakla")
        self.close_btn = wx.Button(panel, label="Bileti Kapat")
        self.refresh_btn = wx.Button(panel, label="Yenile")
        self.exit_btn = wx.Button(panel, wx.ID_CANCEL, "Kapat")

        v.Add(self.conv_label, 0, wx.LEFT | wx.TOP, 8)
        v.Add(self.conv_text, 1, wx.EXPAND | wx.ALL, 6)
        v.Add(self.reply_label, 0, wx.LEFT | wx.TOP, 8)
        v.Add(self.reply_text, 0, wx.EXPAND | wx.ALL, 6)
        h = wx.BoxSizer(wx.HORIZONTAL)
        for b in (self.send_btn, self.send_close_btn, self.ban_btn,
                  self.close_btn, self.refresh_btn, self.exit_btn):
            h.Add(b, 0, wx.ALL, 5)
        v.Add(h, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(v)

        self.send_btn.Bind(wx.EVT_BUTTON, lambda e: self.send(False))
        self.send_close_btn.Bind(wx.EVT_BUTTON, lambda e: self.send(True))
        self.ban_btn.Bind(wx.EVT_BUTTON, lambda e: self.owner.ban_ticket_owner(self.ticket, self))
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_ticket)
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self.load())
        self.reply_text.Bind(wx.EVT_KEY_DOWN, self.on_reply_key)
        self.Centre()
        self.load()

    def on_reply_key(self, event):
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and event.ControlDown():
            self.send(False)
        else:
            event.Skip()

    def load(self, focus_reply: bool = False):
        number = self.ticket["number"]

        def done(thread, error):
            if error:
                self.frame.show_error(error)
                return
            self.thread = thread
            self.conv_text.SetValue(format_thread(thread))
            self.conv_text.SetInsertionPointEnd()   # imleç en son mesajda
            state = "AÇIK" if thread["state"] == "open" else "KAPALI"
            self.SetTitle(f"Bilet #{number} - {self.ticket['title']} ({state})")
            self.frame.SetStatusText(f"Bilet #{number}: {len(thread['comments'])} yorum, {state}.")
            (self.reply_text if focus_reply else self.conv_text).SetFocus()

        self.frame.run_async(lambda: fetch_thread(number), done)

    def send(self, close: bool):
        text = self.reply_text.GetValue().strip()
        if not text:
            wx.MessageBox("Önce bir yanıt yazın.", "Uyarı", wx.OK | wx.ICON_WARNING, self)
            self.reply_text.SetFocus()
            return
        number = self.ticket["number"]

        def done(message, error):
            if error:
                self.frame.show_error(error)
                return
            self.reply_text.SetValue("")
            wx.Bell()
            self.frame.SetStatusText(message)
            self.load(focus_reply=True)
            self.owner.load()

        self.frame.run_async(lambda: post_reply(number, text, close), done)

    def on_close_ticket(self, event):
        number = self.ticket["number"]
        if wx.MessageBox(f"#{number} numaralı bilet kapatılsın mı?", "Onay",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            return

        def done(message, error):
            if error:
                self.frame.show_error(error)
                return
            self.frame.SetStatusText(message)
            self.load()
            self.owner.load()

        self.frame.run_async(lambda: close_tickets([number]), done)


class TicketListDialog(wx.Dialog):
    """Destek biletlerini listeler; sahibini yasaklar, açık biletlerini kapatır.
    Oluşturma sırası = Tab sırası ve ekran okuyucu etiketi: etiket -> liste ->
    onay kutusu -> düğmeler."""

    def __init__(self, parent: "AdminPanelFrame"):
        super().__init__(parent, title="Destek Biletleri", size=(980, 520),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.frame = parent
        self.tickets: List[Dict] = []
        panel = wx.Panel(self)
        v = wx.BoxSizer(wx.VERTICAL)

        self.list_label = wx.StaticText(panel, label="Biletler:")
        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER)
        for i, (name, w) in enumerate((("No", 55), ("Kullanıcı", 120), ("Konu", 240),
                                       ("Cihaz", 90), ("Aynı cihazdan bilet", 120),
                                       ("Yorum", 60), ("Tarih", 90), ("Durum", 70))):
            self.list_ctrl.InsertColumn(i, name, width=w)
        self.closed_cb = wx.CheckBox(panel, label="Kapalı biletleri de göster")
        self.open_btn = wx.Button(panel, label="Oku / Yanıtla (Enter)")
        self.ban_btn = wx.Button(panel, label="Sahibini Yasakla (B)")
        self.close_one_btn = wx.Button(panel, label="Seçili Bileti Kapat")
        self.close_all_btn = wx.Button(panel, label="Bu Kişinin Tüm Açık Biletlerini Kapat")
        self.refresh_btn = wx.Button(panel, label="Yenile")
        self.exit_btn = wx.Button(panel, wx.ID_CANCEL, "Kapat")

        v.Add(self.list_label, 0, wx.LEFT | wx.TOP, 8)
        v.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 6)
        v.Add(self.closed_cb, 0, wx.LEFT | wx.BOTTOM, 10)
        h = wx.BoxSizer(wx.HORIZONTAL)
        for b in (self.open_btn, self.ban_btn, self.close_one_btn, self.close_all_btn, self.refresh_btn, self.exit_btn):
            h.Add(b, 0, wx.ALL, 5)
        v.Add(h, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        panel.SetSizer(v)

        self.open_btn.Bind(wx.EVT_BUTTON, self.on_open)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_open)
        self.ban_btn.Bind(wx.EVT_BUTTON, self.on_ban)
        self.close_one_btn.Bind(wx.EVT_BUTTON, self.on_close_one)
        self.close_all_btn.Bind(wx.EVT_BUTTON, self.on_close_all)
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self.load())
        self.closed_cb.Bind(wx.EVT_CHECKBOX, lambda e: self.load())
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key)
        self.Centre()
        self.load()

    def on_key(self, event):
        if event.GetKeyCode() in (ord("B"), ord("b")) and not event.HasModifiers():
            self.on_ban(None)
        else:
            event.Skip()

    def _selected(self) -> Optional[Dict]:
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1 or idx >= len(self.tickets):
            wx.MessageBox("Lütfen listeden bir bilet seçin.", "Uyarı", wx.OK | wx.ICON_WARNING, self)
            return None
        return self.tickets[idx]

    def load(self):
        include_closed = self.closed_cb.GetValue()

        def done(tickets, error):
            if error:
                self.frame.show_error(error)
                return
            self.tickets = tickets
            self.list_ctrl.DeleteAllItems()
            for i, t in enumerate(tickets):
                self.list_ctrl.InsertItem(i, str(t["number"]))
                self.list_ctrl.SetItem(i, 1, t["username"])
                self.list_ctrl.SetItem(i, 2, t["title"])
                self.list_ctrl.SetItem(i, 3, t["device"][:10])
                self.list_ctrl.SetItem(i, 4, str(t["same_device"]))
                self.list_ctrl.SetItem(i, 5, str(t["comments"]))
                self.list_ctrl.SetItem(i, 6, t["created"])
                self.list_ctrl.SetItem(i, 7, "Açık" if t["state"] == "open" else "Kapalı")
            if tickets:
                self.list_ctrl.Select(0)
                self.list_ctrl.Focus(0)
                self.list_ctrl.SetFocus()
            self.frame.SetStatusText(f"{len(tickets)} bilet listelendi.")

        self.frame.run_async(lambda: list_tickets(include_closed), done)

    def _same_owner_open(self, t: Dict) -> List[int]:
        def same(x: Dict) -> bool:
            if t["device"] and x["device"] == t["device"]:
                return True
            return bool(t["username"]) and x["username"] == t["username"]
        return [x["number"] for x in self.tickets if x["state"] == "open" and same(x)]

    def on_open(self, event):
        t = self._selected()
        if t:
            dlg = TicketThreadDialog(self, t)
            dlg.ShowModal()
            dlg.Destroy()
            self.load()

    def on_ban(self, event):
        t = self._selected()
        if t:
            self.ban_ticket_owner(t)

    def ban_ticket_owner(self, t: Dict, parent=None):
        host = parent or self
        if not (t["device"] or t["username"]):
            wx.MessageBox("Bu biletten kullanıcı adı veya cihaz kimliği okunamadı.", "Uyarı",
                          wx.OK | wx.ICON_WARNING, host)
            return
        dlg = BanDialog(host, t["username"], t["device"],
                        leaderboard=False, tickets=True, remove_scores=False)
        ok = dlg.ShowModal() == wx.ID_OK
        values = dlg.get_values() if ok else None
        dlg.Destroy()
        if not ok:
            return

        open_numbers = self._same_owner_open(t)

        def done(message, error):
            if error:
                self.frame.show_error(error)
                return
            wx.MessageBox(message, "Bilgi", wx.OK | wx.ICON_INFORMATION, host)
            if open_numbers and wx.MessageBox(
                    f"Bu kişinin {len(open_numbers)} açık bileti var. Hepsi kapatılsın mı?",
                    "Biletleri kapat", wx.YES_NO | wx.ICON_QUESTION, host) == wx.YES:
                self.frame.run_async(lambda: close_tickets(open_numbers), self._after_close)
            else:
                self.load()

        self.frame.run_async(lambda: add_ban(**values), done)

    def on_close_one(self, event):
        t = self._selected()
        if t:
            self.frame.run_async(lambda: close_tickets([t["number"]]), self._after_close)

    def on_close_all(self, event):
        t = self._selected()
        if not t:
            return
        numbers = self._same_owner_open(t)
        if not numbers:
            wx.MessageBox("Bu kişinin açık bileti yok.", "Bilgi", wx.OK | wx.ICON_INFORMATION, self)
            return
        if wx.MessageBox(f"{len(numbers)} açık bilet kapatılsın mı?", "Onay",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            return
        self.frame.run_async(lambda: close_tickets(numbers), self._after_close)

    def _after_close(self, message, error):
        if error:
            self.frame.show_error(error)
            return
        wx.MessageBox(message, "Bilgi", wx.OK | wx.ICON_INFORMATION, self)
        self.load()


class AdminPanelFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Skor Tablosu Yönetim Paneli", size=(700, 500))
        self.busy = False
        self.entries: List[Dict] = []

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # EKRAN OKUYUCU: wxPython'da bir kontrolün erişilebilir adı, ondan HEMEN
        # ÖNCE oluşturulan StaticText'ten gelir; Tab sırası da oluşturma
        # sırasıdır. Bu yüzden sıra: etiket -> liste -> düğmeler. (Görünüm
        # düzeni sizer'larla ayrıca kurulur, oluşturma sırasından bağımsızdır.)
        self.list_label = wx.StaticText(panel, label="Kayıtlı Skorlar:")
        self.list_ctrl = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER
        )
        self.list_ctrl.InsertColumn(0, "Kullanıcı Adı", width=220)
        self.list_ctrl.InsertColumn(1, "Skor", width=150)
        self.list_ctrl.InsertColumn(2, "Ek Bilgi / Tarih", width=200)
        self.list_ctrl.InsertColumn(3, "Cihaz", width=110)

        self.btn_test = wx.Button(panel, label="Bağlantı Testi")
        self.btn_refresh = wx.Button(panel, label="Listeyi Yenile (F5)")
        self.btn_ban = wx.Button(panel, label="Seçili Kullanıcıyı Yasakla (F6)")
        self.btn_banlist = wx.Button(panel, label="Yasak Listesi (F7)")
        self.btn_tickets = wx.Button(panel, label="Biletler (F8)")
        self.btn_delete = wx.Button(panel, label="Seçili Kullanıcıyı Sil (Delete)")
        self.btn_close = wx.Button(panel, label="Çıkış")

        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(self.list_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        top.Add(self.btn_test, 0, wx.ALL, 5)
        top.Add(self.btn_refresh, 0, wx.ALL, 5)
        vbox.Add(top, 0, wx.EXPAND)
        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        bottom = wx.BoxSizer(wx.HORIZONTAL)
        bottom.Add(self.btn_ban, 0, wx.ALL, 5)
        bottom.Add(self.btn_banlist, 0, wx.ALL, 5)
        bottom.Add(self.btn_tickets, 0, wx.ALL, 5)
        bottom.Add(self.btn_delete, 0, wx.ALL, 5)
        bottom.Add(self.btn_close, 0, wx.ALL, 5)
        vbox.Add(bottom, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        panel.SetSizer(vbox)
        self.CreateStatusBar()

        self.btn_test.Bind(wx.EVT_BUTTON, self.on_test)
        self.btn_refresh.Bind(wx.EVT_BUTTON, lambda e: self.load_data())
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_ban.Bind(wx.EVT_BUTTON, self.on_ban)
        self.btn_banlist.Bind(wx.EVT_BUTTON, self.on_banlist)
        self.btn_tickets.Bind(wx.EVT_BUTTON, self.on_tickets)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key)

        # Kısayollar: F5 yenile, F6 yasakla, F7 yasak listesi, F8 biletler
        self.Bind(wx.EVT_MENU, lambda e: self.load_data(), id=self.btn_refresh.GetId())
        self.Bind(wx.EVT_MENU, self.on_ban, id=self.btn_ban.GetId())
        self.Bind(wx.EVT_MENU, self.on_banlist, id=self.btn_banlist.GetId())
        self.Bind(wx.EVT_MENU, self.on_tickets, id=self.btn_tickets.GetId())
        accel = wx.AcceleratorTable([
            (wx.ACCEL_NORMAL, wx.WXK_F5, self.btn_refresh.GetId()),
            (wx.ACCEL_NORMAL, wx.WXK_F6, self.btn_ban.GetId()),
            (wx.ACCEL_NORMAL, wx.WXK_F7, self.btn_banlist.GetId()),
            (wx.ACCEL_NORMAL, wx.WXK_F8, self.btn_tickets.GetId()),
        ])
        self.SetAcceleratorTable(accel)

        self.Centre()
        self.load_data()

    # --- yardımcılar
    def set_busy(self, busy: bool, text: str = ""):
        self.busy = busy
        for b in (self.btn_test, self.btn_refresh, self.btn_delete, self.btn_ban, self.btn_banlist, self.btn_tickets):
            b.Enable(not busy)
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT if busy else wx.CURSOR_DEFAULT))
        self.SetStatusText(text)

    def run_async(self, work, on_done):
        """work() arka planda çalışır; on_done(sonuç, hata) ana iş parçacığında."""
        def target():
            try:
                result, error = work(), None
            except GistError as e:
                result, error = None, str(e)
            except Exception as e:  # beklenmeyen hata da görünsün
                result, error = None, f"Beklenmeyen hata: {type(e).__name__}: {e}"
            wx.CallAfter(on_done, result, error)

        threading.Thread(target=target, daemon=True).start()

    def show_error(self, message: str):
        self.SetStatusText("Hata")
        wx.MessageBox(message, "Hata", wx.OK | wx.ICON_ERROR, self)

    # --- veri yükleme
    def load_data(self):
        if self.busy:
            return
        self.set_busy(True, "Yükleniyor...")

        def work():
            return fetch_scores(read_token())[1]

        def done(entries, error):
            self.set_busy(False)
            if error:
                self.list_ctrl.DeleteAllItems()
                self.show_error(error)
                return
            self.fill_list(entries)
            self.SetStatusText(f"{len(entries)} kayıt yüklendi.")
            wx.Bell()  # ekran okuyucu kullanıcısı için sesli bildirim

        self.run_async(work, done)

    def fill_list(self, entries: List[Dict]):
        self.entries = entries
        self.list_ctrl.DeleteAllItems()
        for i, e in enumerate(entries):
            self.list_ctrl.InsertItem(i, str(e.get("username", "")))
            self.list_ctrl.SetItem(i, 1, str(e.get("cash", e.get("total", e.get("score", "")))))
            self.list_ctrl.SetItem(i, 2, str(e.get("last_updated", e.get("date", e.get("tarih", "")))))
            self.list_ctrl.SetItem(i, 3, str(e.get("device_id", ""))[:10])
        if entries:
            self.list_ctrl.Select(0)
            self.list_ctrl.Focus(0)
            self.list_ctrl.SetFocus()

    # --- olaylar
    def on_test(self, event):
        if self.busy:
            return
        self.set_busy(True, "Bağlantı test ediliyor...")

        def done(report, error):
            self.set_busy(False, "Test tamamlandı.")
            wx.MessageBox(report or error, "Bağlantı Testi", wx.OK | wx.ICON_INFORMATION, self)

        self.run_async(run_diagnostics, done)

    def on_key(self, event):
        if event.GetKeyCode() == wx.WXK_DELETE:
            self.on_delete(None)
        else:
            event.Skip()

    def on_ban(self, event):
        if self.busy:
            return
        username, device = "", ""
        idx = self.list_ctrl.GetFirstSelected()
        if idx != -1:
            username = self.list_ctrl.GetItemText(idx, 0)
            if idx < len(self.entries):
                device = str(self.entries[idx].get("device_id", "") or "")
        dlg = BanDialog(self, username, device)
        ok = dlg.ShowModal() == wx.ID_OK
        values = dlg.get_values() if ok else None
        dlg.Destroy()
        if not ok:
            return

        who = values["username"] or values["device"]
        scope = " ve ".join(x for x, f in (("skor tablosu", values["leaderboard"]),
                                          ("destek bileti", values["tickets"])) if f)
        if wx.MessageBox(f"'{who}' için {scope} yasağı uygulansın mı?", "Onay",
                         wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) != wx.YES:
            return

        self.set_busy(True, "Yasak uygulanıyor...")

        def done(message, error):
            self.set_busy(False)
            if error:
                self.show_error(error)
                return
            wx.MessageBox(message, "Bilgi", wx.OK | wx.ICON_INFORMATION, self)
            self.load_data()

        self.run_async(lambda: add_ban(**values), done)

    def on_tickets(self, event):
        if self.busy:
            return
        dlg = TicketListDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def on_banlist(self, event):
        if self.busy:
            return
        dlg = BanListDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def on_delete(self, event):
        if self.busy:
            return
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Lütfen silmek istediğiniz kullanıcıyı seçin.",
                          "Uyarı", wx.OK | wx.ICON_WARNING, self)
            return

        username = self.list_ctrl.GetItemText(idx, 0)
        dlg = wx.MessageDialog(
            self, f"'{username}' adlı kullanıcıyı silmek istediğinize emin misiniz?",
            "Onay", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        confirmed = dlg.ShowModal() == wx.ID_YES
        dlg.Destroy()
        if not confirmed:
            return

        self.set_busy(True, "Siliniyor...")

        def done(message, error):
            self.set_busy(False)
            if error:
                self.show_error(error)
                return
            wx.MessageBox(message, "Bilgi", wx.OK | wx.ICON_INFORMATION, self)
            self.load_data()

        self.run_async(lambda: delete_user(username), done)


if __name__ == "__main__":
    app = wx.App(False)
    AdminPanelFrame().Show()
    app.MainLoop()
