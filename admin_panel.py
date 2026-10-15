"""
admin_panel.py
--------------
GitHub Gist üzerindeki skor tablosundan kullanıcı silmek için wxPython paneli.

- Token SADECE bu dosyanın yanındaki token.txt dosyasından okunur.
- Hatalar gerçek sebebiyle gösterilir (401, 403, 404, SSL, zaman aşımı...).
- "Bağlantı Testi" butonu token, kullanıcı ve yetki bilgisini kontrol eder.
- Kısayollar: F5 = Yenile, Delete = Seçiliyi sil.
"""

import os
import sys
import json
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests
import wx

# leaderboard.py ile aynı Gist ID ve dosya adı
GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"
GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
SCORE_FILE = "skorlar.json"
LIST_KEY = "score_data"
TIMEOUT = 15


def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")

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
        r = _request("GET", GIST_URL, token)
        owner = r.json().get("owner", {}).get("login")
        lines.append(f"Gist erişimi: tamam (sahip: {owner})")
        _, entries = fetch_scores(token)
        lines.append(f"{SCORE_FILE}: {len(entries)} kayıt")
    except GistError as e:
        lines.append(f"Gist testi başarısız:\n{e}")
    return "\n".join(lines)


# -------------------------------------------------------------------- GUI
class AdminPanelFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Skor Tablosu Yönetim Paneli", size=(700, 500))
        self.busy = False

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(wx.StaticText(panel, label="Kayıtlı Skorlar:"), 1,
                wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.btn_test = wx.Button(panel, label="Bağlantı Testi")
        self.btn_refresh = wx.Button(panel, label="Listeyi Yenile (F5)")
        top.Add(self.btn_test, 0, wx.ALL, 5)
        top.Add(self.btn_refresh, 0, wx.ALL, 5)
        vbox.Add(top, 0, wx.EXPAND)

        self.list_ctrl = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER
        )
        self.list_ctrl.InsertColumn(0, "Kullanıcı Adı", width=220)
        self.list_ctrl.InsertColumn(1, "Skor", width=150)
        self.list_ctrl.InsertColumn(2, "Ek Bilgi / Tarih", width=240)
        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)

        bottom = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_delete = wx.Button(panel, label="Seçili Kullanıcıyı Sil (Delete)")
        self.btn_close = wx.Button(panel, label="Çıkış")
        bottom.Add(self.btn_delete, 0, wx.ALL, 5)
        bottom.Add(self.btn_close, 0, wx.ALL, 5)
        vbox.Add(bottom, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        panel.SetSizer(vbox)
        self.CreateStatusBar()

        self.btn_test.Bind(wx.EVT_BUTTON, self.on_test)
        self.btn_refresh.Bind(wx.EVT_BUTTON, lambda e: self.load_data())
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_close.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_key)

        accel = wx.AcceleratorTable([(wx.ACCEL_NORMAL, wx.WXK_F5, self.btn_refresh.GetId())])
        self.SetAcceleratorTable(accel)

        self.Centre()
        self.load_data()

    # --- yardımcılar
    def set_busy(self, busy: bool, text: str = ""):
        self.busy = busy
        for b in (self.btn_test, self.btn_refresh, self.btn_delete):
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
        self.list_ctrl.DeleteAllItems()
        for i, e in enumerate(entries):
            self.list_ctrl.InsertItem(i, str(e.get("username", "")))
            self.list_ctrl.SetItem(i, 1, str(e.get("score", "")))
            self.list_ctrl.SetItem(i, 2, str(e.get("date", e.get("tarih", ""))))
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
