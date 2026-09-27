"""
admin.panel.py
-------------------------
GitHub Gist üzerindeki skor tablosundan kullanıcı silmek için wxPython Arayüz Paneli.
"""

import os
import sys
import json
import time
import random
import threading
import requests
from typing import List, Dict, Optional, Tuple
import wx

# leaderboard.py ile aynı Gist ID ve dosya adı
GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"
GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
SCORE_FILE = "skorlar.json"

def _get_base_dir() -> str:
    """token.txt dosyasının aranacağı klasörü döndürür."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = _get_base_dir()
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")

_score_lock = threading.Lock()

def _log(msg: str) -> None:
    print(msg)

def get_token() -> Optional[str]:
    """Token'ı arar."""
    try:
        from embedded_token import get_embedded_token
        embedded = get_embedded_token()
        if embedded:
            return embedded
    except Exception:
        pass

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled_path = os.path.join(sys._MEIPASS, "token.txt")
        try:
            if os.path.exists(bundled_path):
                with open(bundled_path, "r", encoding="utf-8") as f:
                    token = f.read().strip()
                    if token:
                        return token
        except Exception:
            pass

    try:
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    return token
    except Exception:
        pass
    return None

def get_gist_content() -> Optional[Dict]:
    """GitHub Gist'ten skorlar.json içeriğini çeker."""
    token = get_token()
    if not token:
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(GIST_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            gist_data = response.json()
            files = gist_data.get("files", {})
            if SCORE_FILE in files:
                content = files[SCORE_FILE].get("content", "{}")
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"score_data": []}
            else:
                return {"score_data": []}
        else:
            return None
    except requests.exceptions.RequestException:
        return None

def update_gist_content(data: Dict) -> bool:
    """GitHub Gist'teki skorlar.json dosyasını günceller."""
    token = get_token()
    if not token:
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    try:
        response = requests.get(GIST_URL, headers=headers, timeout=10)
        if response.status_code != 200:
            return False

        gist_data = response.json()
        existing_files = gist_data.get("files", {})

        files_to_update = {}
        for filename, file_info in existing_files.items():
            if filename == SCORE_FILE:
                files_to_update[SCORE_FILE] = {
                    "content": json.dumps(data, ensure_ascii=False, indent=2)
                }
            else:
                files_to_update[filename] = {
                    "content": file_info.get("content", "")
                }

        if SCORE_FILE not in files_to_update:
            files_to_update[SCORE_FILE] = {
                "content": json.dumps(data, ensure_ascii=False, indent=2)
            }

        payload = {"files": files_to_update}
        update_response = requests.patch(GIST_URL, headers=headers, json=payload, timeout=10)
        return update_response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def delete_user_from_leaderboard(username_to_delete: str) -> Tuple[bool, str]:
    """Belirtilen kullanıcıyı skor tablosundan siler."""
    if not username_to_delete:
        return False, "Kullanıcı adı boş olamaz."

    with _score_lock:
        for _ in range(3):
            data = get_gist_content()
            if data is None:
                return False, "Gist verisi alınamadı (Bağlantı hatası)."

            score_data = data.get("score_data", [])
            initial_count = len(score_data)

            new_score_data = [entry for entry in score_data if entry.get("username") != username_to_delete]

            if len(new_score_data) == initial_count:
                return False, f"'{username_to_delete}' adında bir kullanıcı skor tablosunda bulunamadı."

            data["score_data"] = new_score_data

            if update_gist_content(data):
                return True, f"'{username_to_delete}' başarıyla silindi ve Gist güncellendi."
            
            time.sleep(0.5 + random.random())

        return False, "Güncelleme çakışma nedeniyle tamamlanamadı."


class AdminPanelFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Skor Tablosu Yönetim Paneli", size=(600, 450))
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Üst bilgi ve yenileme butonu
        top_hbox = wx.BoxSizer(wx.HORIZONTAL)
        lbl_title = wx.StaticText(panel, label="Kayıtlı Skorlar:")
        top_hbox.Add(lbl_title, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=5)

        self.btn_refresh = wx.Button(panel, label="Listeyi Yenile")
        self.btn_refresh.Bind(wx.EVT_BUTTON, self.on_refresh)
        top_hbox.Add(self.btn_refresh, flag=wx.ALL, border=5)
        vbox.Add(top_hbox, flag=wx.EXPAND)

        # Liste Kutusu (ListCtrl - Rapor Görünümü)
        self.list_ctrl = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.SUNKEN_BORDER)
        self.list_ctrl.InsertColumn(0, "Kullanıcı Adı", width=200)
        self.list_ctrl.InsertColumn(1, "Skor", width=150)
        self.list_ctrl.InsertColumn(2, "Ek Bilgi / Tarih", width=180)
        vbox.Add(self.list_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        # Alt butonlar
        bottom_hbox = wx.BoxSizer(wx.HORIZONTAL)
        
        self.btn_delete = wx.Button(panel, label="Seçili Kullanıcıyı Sil")
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)
        bottom_hbox.Add(self.btn_delete, flag=wx.ALL, border=5)

        self.btn_close = wx.Button(panel, label="Çıkış")
        self.btn_close.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        bottom_hbox.Add(self.btn_close, flag=wx.ALL, border=5)

        vbox.Add(bottom_hbox, flag=wx.ALIGN_RIGHT | wx.ALL, border=5)

        panel.SetSizer(vbox)
        
        # Verileri yükle
        self.load_data()
        self.Centre()

    def load_data(self):
        self.list_ctrl.DeleteAllItems()
        self.btn_refresh.Disable()
        self.SetCursor(wx.Cursor(wx.CURSOR_WAIT))

        # Gist'ten verileri arka planda veya doğrudan çekelim
        data = get_gist_content()
        
        self.SetCursor(wx.Cursor(wx.CURSOR_DEFAULT))
        self.btn_refresh.Enable()

        if data is None:
            wx.MessageBox("Gist verileri çekilemedi. Token'ı veya internet bağlantınızı kontrol edin.", "Hata", wx.OK | wx.ICON_ERROR)
            return

        score_data = data.get("score_data", [])
        for index, entry in enumerate(score_data):
            username = str(entry.get("username", ""))
            score = str(entry.get("score", ""))
            extra = str(entry.get("date", entry.get("tarih", ""))) # Varsa tarih veya diğer alanlar
            
            self.list_ctrl.InsertItem(index, username)
            self.list_ctrl.SetItem(index, 1, score)
            self.list_ctrl.SetItem(index, 2, extra)

        if len(score_data) > 0:
            self.list_ctrl.Focus(0)
            self.list_ctrl.Select(0)

    def on_refresh(self, event):
        self.load_data()
        wx.Bell() # Ekran okuyucu kullanıcısı için listenin güncellendiğini sesle bildir

    def on_delete(self, event):
        selected_item = self.list_ctrl.GetFirstSelected()
        if selected_item == -1:
            wx.MessageBox("Lütfen listeden silmek istediğiniz bir kullanıcıyı seçin.", "Uyarı", wx.OK | wx.ICON_WARNING)
            return

        username = self.list_ctrl.GetItemText(selected_item, 0)
        
        dlg = wx.MessageDialog(self, f"'{username}' adlı kullanıcıyı silmek istediğinize emin misiniz?", "Onay", wx.YES_NO | wx.ICON_QUESTION)
        if dlg.ShowModal() == wx.ID_YES:
            success, message = delete_user_from_leaderboard(username)
            wx.MessageBox(message, "Bilgi", wx.OK | (wx.ICON_INFORMATION if success else wx.ICON_ERROR))
            if success:
                self.load_data()
        dlg.Destroy()

if __name__ == "__main__":
    app = wx.App(False)
    frame = AdminPanelFrame()
    frame.Show()
    app.MainLoop()