
"""
ticket_manager.py
------------------
GitHub Issues ile oyun içi destek/bilet sistemi.

Oyuncu "Destek" ekranından bir bilet açtığında, bu modül
MUHAMMED4342/biletlerim reposunda bir Issue oluşturur (oyun kullanıcı
adı ve temel oyun bilgileri Issue gövdesine otomatik eklenir). Oyuncu
daha sonra aynı ekrandan biletine gelen yanıtları görebilir ve bilet
kapatılmadığı sürece tekrar tekrar yazabilir (Issue'ya yorum ekler).

TOKEN NASIL BULUNUR (leaderboard.py'daki token.txt ile AYNI mantık,
ayrı bir dosyada):
  1) PyInstaller --onefile ile derlenmiş exe'nin İÇİNE veri olarak
     gömülen "github.txt" (build sırasında eklenir; çalışma anında
     sys._MEIPASS klasörüne çıkarılır).
  2) exe'nin (ya da bu .py dosyasının) bulunduğu klasördeki
     "github.txt".

ÖNEMLİ (güvenlik): Buradaki token'a repo'nun TAMAMINA değil, SADECE
"Issues: Read and write" iznine sahip, biletlerim reposuna kilitli bir
fine-grained personal access token kullanın. Bu dosya asla git'e
commit edilmemeli (.gitignore'a ekleyin) - sadece derleme sırasında
exe'nin içine/yanına elle koyulmalı.
"""

import os
import sys
import json
import time
import threading
from typing import List, Dict, Optional, Tuple

import requests
import appdirs


GITHUB_OWNER = "MUHAMMED4342"
GITHUB_REPO = "biletlerim"
API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

TICKET_LABEL = "oyun-ici-bilet"

REQUEST_TIMEOUT = 15


# ---------------------------------------------------------------------------
# Token bulma (leaderboard.py -> get_token() ile aynı desen, ayrı dosya)
# ---------------------------------------------------------------------------

def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
GITHUB_TOKEN_FILE = os.path.join(BASE_DIR, "github.txt")

_token_cache = None


def get_github_token() -> Optional[str]:
    """github.txt içindeki token'ı okur (önce exe içine gömülü
    (_MEIPASS), sonra exe/script yanındaki dosya). Bulunduğunda süreç
    boyunca önbelleğe alınır."""
    global _token_cache
    if _token_cache:
        return _token_cache

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(sys._MEIPASS, "github.txt")
        try:
            if os.path.exists(bundled_path):
                with open(bundled_path, "r", encoding="utf-8") as f:
                    token = f.read().strip()
                if token:
                    _token_cache = token
                    return token
        except Exception as e:
            print(f"[Bilet] Gömülü github.txt okunamadı: {e}")

    try:
        if os.path.exists(GITHUB_TOKEN_FILE):
            with open(GITHUB_TOKEN_FILE, "r", encoding="utf-8") as f:
                token = f.read().strip()
            if token:
                _token_cache = token
                return token
        else:
            print(f"[Bilet] github.txt bulunamadı: {GITHUB_TOKEN_FILE}")
    except Exception as e:
        print(f"[Bilet] github.txt okunamadı: {e}")
    return None


def _headers() -> Dict[str, str]:
    token = get_github_token()
    if not token:
        raise RuntimeError(
            "GitHub bilet token'ı bulunamadı (github.txt). Destek sistemi "
            "şu an kullanılamıyor."
        )
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }


# ---------------------------------------------------------------------------
# Yerel bilet geçmişi (appdata) - hangi oyuncunun hangi issue numaralarına
# sahip olduğu ve en son kaç yorum gördüğü burada tutulur. GitHub tarafında
# tüm biletler AYNI hesaptan (token sahibi) açıldığı için "kimin bileti"
# bilgisini yalnızca burada, yerelde tutuyoruz.
# ---------------------------------------------------------------------------

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
_TICKETS_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
TICKETS_FILENAME = "tickets.json"
_TICKETS_FILE = os.path.join(_TICKETS_DIR, TICKETS_FILENAME)

_tickets_lock = threading.Lock()


def _load_all_tickets() -> Dict[str, List[Dict]]:
    try:
        if os.path.exists(_TICKETS_FILE):
            with open(_TICKETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Bilet] Yerel bilet listesi okunamadı: {e}")
    return {}


def _save_all_tickets(all_tickets: Dict[str, List[Dict]]) -> None:
    try:
        os.makedirs(_TICKETS_DIR, exist_ok=True)
        with open(_TICKETS_FILE, "w", encoding="utf-8") as f:
            json.dump(all_tickets, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Bilet] Yerel bilet listesi kaydedilemedi: {e}")


def list_local_tickets(username: str) -> List[Dict]:
    """Bu kullanıcının açtığı biletlerin yerel kaydını döner (en yeni
    en üstte). Her öğe: number, title, url, created_at,
    last_seen_comment_count, state."""
    with _tickets_lock:
        all_tickets = _load_all_tickets()
    tickets = all_tickets.get(username, [])
    return sorted(tickets, key=lambda t: t.get("number", 0), reverse=True)


def _add_local_ticket(username: str, ticket: Dict) -> None:
    with _tickets_lock:
        all_tickets = _load_all_tickets()
        all_tickets.setdefault(username, [])
        all_tickets[username].append(ticket)
        _save_all_tickets(all_tickets)


def _update_local_ticket(username: str, number: int, **fields) -> None:
    with _tickets_lock:
        all_tickets = _load_all_tickets()
        for t in all_tickets.get(username, []):
            if t.get("number") == number:
                t.update(fields)
                break
        _save_all_tickets(all_tickets)


def mark_ticket_seen(username: str, number: int, comment_count: int) -> None:
    """Kullanıcı bileti açıp yanıtları gördüğünde çağrılır; bir daha
    aynı yorumlar için 'yeni yanıt var' uyarısı çıkmaz."""
    _update_local_ticket(username, number, last_seen_comment_count=comment_count)


# ---------------------------------------------------------------------------
# GitHub API çağrıları
# ---------------------------------------------------------------------------

def create_ticket(username: str, subject: str, message: str,
                   extra_info: Optional[Dict] = None) -> Dict:
    """Yeni bir bilet (GitHub Issue) açar. Başarılı olursa
    {"number":.., "url":.., "title":..} döner; hata durumunda
    RuntimeError fırlatır (çağıran taraf yakalayıp kullanıcıya Türkçe
    göstermeli)."""
    subject = (subject or "").strip() or "Konu belirtilmedi"
    message = (message or "").strip()

    info_lines = [f"**Oyun kullanıcı adı:** {username}"]
    if extra_info:
        for key, value in extra_info.items():
            info_lines.append(f"**{key}:** {value}")

    body = "\n".join(info_lines) + "\n\n---\n\n" + message

    payload = {
        "title": f"[Bilet] {subject} ({username})",
        "body": body,
        "labels": [TICKET_LABEL],
    }

    resp = requests.post(f"{API_BASE}/issues", headers=_headers(),
                          json=payload, timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 400:
        raise RuntimeError(_parse_error(resp))

    data = resp.json()
    ticket = {
        "number": data["number"],
        "title": subject,
        "url": data.get("html_url"),
        "created_at": data.get("created_at"),
        "state": data.get("state", "open"),
        "last_seen_comment_count": 0,
        # Bu bilette OYUNCUNUN kendisinin gönderdiği yorumların GitHub
        # comment id'leri. Tüm API çağrıları aynı token/hesaptan yapıldığı
        # için GitHub "author" alanı oyuncu ile yönetimi birbirinden
        # AYIRT ETMEZ; bu yüzden "kim yazdı" bilgisini yalnızca burada,
        # yerelde tutuyoruz (bkz. add_reply ve get_local_ticket).
        "own_comment_ids": [],
    }
    _add_local_ticket(username, ticket)
    return ticket


def get_local_ticket(username: str, number: int) -> Optional[Dict]:
    """Belirli bir biletin GÜNCEL yerel kaydını döner (own_comment_ids
    dahil). Arayüz, bir yorumun 'Siz' mi yoksa 'Yönetim cevabı' mı
    olduğunu her gösterimde bu kayıttan taze okumalı."""
    for t in list_local_tickets(username):
        if t.get("number") == number:
            return t
    return None


def fetch_ticket_thread(number: int) -> Dict:
    """Bir biletin (issue) güncel durumunu ve tüm yorumlarını çeker.
    Dönüş: {"state":.., "title":.., "body":.., "comments": [ {..}, .. ]}"""
    issue_resp = requests.get(f"{API_BASE}/issues/{number}",
                               headers=_headers(), timeout=REQUEST_TIMEOUT)
    if issue_resp.status_code >= 400:
        raise RuntimeError(_parse_error(issue_resp))
    issue = issue_resp.json()

    comments_resp = requests.get(f"{API_BASE}/issues/{number}/comments",
                                  headers=_headers(), timeout=REQUEST_TIMEOUT)
    if comments_resp.status_code >= 400:
        raise RuntimeError(_parse_error(comments_resp))
    raw_comments = comments_resp.json()

    comments = []
    for c in raw_comments:
        author = (c.get("user") or {}).get("login", "?")
        comments.append({
            "id": c.get("id"),
            "author": author,
            "body": c.get("body", ""),
            "created_at": c.get("created_at"),
        })

    return {
        "state": issue.get("state", "open"),
        "title": issue.get("title", ""),
        "body": issue.get("body", ""),
        "comments": comments,
    }


def add_reply(username: str, number: int, message: str) -> Dict:
    """Bilet KAPALI DEĞİLSE, ilgili issue'ya oyuncu adına bir yorum
    ekler. Bilet kapatılmışsa RuntimeError fırlatır (tekrar açmak için
    yeni bilet oluşturulmalı). Gönderilen yorumun id'si, arayüzün bunu
    daha sonra 'Siz' olarak etiketleyebilmesi için yerel kayda
    (own_comment_ids) eklenir."""
    message = (message or "").strip()
    if not message:
        raise RuntimeError("Boş mesaj gönderilemez.")

    issue_resp = requests.get(f"{API_BASE}/issues/{number}",
                               headers=_headers(), timeout=REQUEST_TIMEOUT)
    if issue_resp.status_code >= 400:
        raise RuntimeError(_parse_error(issue_resp))
    if issue_resp.json().get("state") == "closed":
        raise RuntimeError("Bu bilet kapatılmış, yeni yanıt eklenemez. "
                            "Lütfen yeni bir bilet açın.")

    resp = requests.post(f"{API_BASE}/issues/{number}/comments",
                          headers=_headers(), json={"body": message},
                          timeout=REQUEST_TIMEOUT)
    if resp.status_code >= 400:
        raise RuntimeError(_parse_error(resp))

    data = resp.json()
    comment_id = data.get("id")
    if comment_id is not None:
        _add_own_comment_id(username, number, comment_id)
    return data


def _add_own_comment_id(username: str, number: int, comment_id: int) -> None:
    with _tickets_lock:
        all_tickets = _load_all_tickets()
        for t in all_tickets.get(username, []):
            if t.get("number") == number:
                own_ids = t.setdefault("own_comment_ids", [])
                if comment_id not in own_ids:
                    own_ids.append(comment_id)
                break
        _save_all_tickets(all_tickets)


def _parse_error(resp) -> str:
    try:
        data = resp.json()
        msg = data.get("message", f"HTTP {resp.status_code}")
    except Exception:
        msg = f"HTTP {resp.status_code}"
    if resp.status_code in (401, 403):
        return f"GitHub'a bağlanılamadı (yetki hatası): {msg}"
    if resp.status_code == 404:
        return "Bilet bulunamadı (silinmiş olabilir)."
    return f"GitHub hatası: {msg}"


# ---------------------------------------------------------------------------
# Arka planda "yeni yanıt var mı" kontrolü (thread + wx.CallAfter ile
# çağırana haber verir; wx bağımlılığı burada YOK, callback ana thread'e
# taşımak çağıranın sorumluluğunda - bkz. main.py)
# ---------------------------------------------------------------------------

def check_for_new_replies_async(username: str, on_result) -> None:
    """Kullanıcının AÇIK biletlerini arka planda tek tek kontrol eder.
    Yeni yorum bulunan biletlerin listesini on_result([...]) ile
    çağırana bildirir (ayrı thread'den çağrılır - wx.CallAfter ile
    ana thread'e taşınmalı). Ağ hatası olursa sessizce (boş liste ile)
    döner; oyunu bloklamaz."""

    def worker():
        results = []
        tickets = [t for t in list_local_tickets(username) if t.get("state") != "closed"]
        for t in tickets:
            try:
                thread = fetch_ticket_thread(t["number"])
            except Exception as e:
                print(f"[Bilet] '{t.get('number')}' kontrol edilemedi: {e}")
                continue

            new_state = thread["state"]
            comment_count = len(thread["comments"])
            seen = t.get("last_seen_comment_count", 0)

            if new_state != t.get("state"):
                _update_local_ticket(username, t["number"], state=new_state)

            if comment_count > seen:
                results.append({
                    "number": t["number"],
                    "title": t.get("title", ""),
                    "new_comment_count": comment_count - seen,
                    "state": new_state,
                })

        on_result(results)

    threading.Thread(target=worker, daemon=True).start()
