# -*- coding: utf-8 -*-
"""
admin_panel.py
--------------
GitHub Gist skor tablosu yönetim paneli (wxPython)
- Ok tuşları SADECE listede gezinir
- Odak asla butonlara kaymaz
- Ekran okuyucu dostu
"""

import os
import sys
import json
import threading
import wx
import requests
from typing import List, Dict, Optional, Tuple

# ============================================================
# 1. YOL AYARLARI (Gömülü dosya için)
# ============================================================

def resource_path(relative_path):
    """Gömülü dosyaların yolunu döndürür (PyInstaller için)."""
    try:
        # PyInstaller ile çalıştırılıyorsa
        base_path = sys._MEIPASS
    except Exception:
        # Normal Python ortamında çalıştırılıyorsa
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = _get_base_dir()
TOKEN_FILE = resource_path("token.txt")  # Gömülü dosya

GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"
GIST_URL = f"https://api.github.com/gists/{GIST_ID}"
SCORE_FILE = "skorlar.json"


# ============================================================
# 2. GITHUB GIST İŞLEMLERİ
# ============================================================

class GistManager:
    """GitHub Gist işlemleri."""
    
    def __init__(self):
        self.token = self._get_token()
        self._lock = threading.Lock()
        
    def _get_token(self) -> Optional[str]:
        try:
            # Önce gömülü dosyadan oku
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, "r", encoding="utf-8") as f:
                    token = f.read().strip()
                    if token:
                        return token
            
            # Eğer gömülü dosya yoksa, eski yöntemleri dene
            # (Bu kısım sadece geliştirme aşamasında çalışır)
            token_file_local = os.path.join(BASE_DIR, "token.txt")
            if os.path.exists(token_file_local):
                with open(token_file_local, "r", encoding="utf-8") as f:
                    token = f.read().strip()
                    if token:
                        return token
                        
        except Exception as e:
            print(f"Token okuma hatası: {e}")
        return None
    
    def get_entries(self) -> Optional[List[Dict]]:
        """Skor tablosunu çeker."""
        with self._lock:
            if not self.token:
                return None
            
            try:
                headers = {
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                response = requests.get(GIST_URL, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    gist_data = response.json()
                    files = gist_data.get("files", {})
                    if SCORE_FILE in files:
                        content = files[SCORE_FILE].get("content", "{}")
                        data = json.loads(content)
                        return data.get("score_data", [])
                return []
                
            except:
                return None
    
    def delete_entry(self, username: str) -> Tuple[bool, str]:
        """Kullanıcıyı siler."""
        with self._lock:
            if not self.token:
                return False, "Token bulunamadı!"
            
            try:
                headers = {
                    "Authorization": f"token {self.token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                response = requests.get(GIST_URL, headers=headers, timeout=15)
                if response.status_code != 200:
                    return False, f"Gist okunamadı: HTTP {response.status_code}"
                
                gist_data = response.json()
                files = gist_data.get("files", {})
                
                if SCORE_FILE not in files:
                    return False, "skorlar.json bulunamadı!"
                
                content = files[SCORE_FILE].get("content", "{}")
                data = json.loads(content)
                score_data = data.get("score_data", [])
                
                found = False
                new_score_data = []
                for entry in score_data:
                    if entry.get("username") == username:
                        found = True
                    else:
                        new_score_data.append(entry)
                
                if not found:
                    return False, f"'{username}' bulunamadı!"
                
                data["score_data"] = new_score_data
                
                files_to_update = {}
                for filename, file_info in files.items():
                    if filename == SCORE_FILE:
                        files_to_update[SCORE_FILE] = {
                            "content": json.dumps(data, ensure_ascii=False, indent=2)
                        }
                    else:
                        files_to_update[filename] = {
                            "content": file_info.get("content", "")
                        }
                
                payload = {"files": files_to_update}
                update_response = requests.patch(
                    GIST_URL,
                    headers=headers,
                    json=payload,
                    timeout=15
                )
                
                if update_response.status_code == 200:
                    return True, f"'{username}' başarıyla silindi!"
                else:
                    return False, f"Güncelleme başarısız: HTTP {update_response.status_code}"
                    
            except:
                return False, "Bağlantı hatası!"


# ============================================================
# 3. ÖZEL LİSTE KONTROLÜ - OK TUŞLARI SADECE LİSTEDE
# ============================================================

class ScoreListCtrl(wx.ListCtrl):
    """
    Özel liste kontrolü:
    - Ok tuşları SADECE listede gezinir
    - Tab ile butonlara geçilir
    - Enter ile seçili öğeyi siler (isteğe bağlı)
    """
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Olayları yakala
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.Bind(wx.EVT_SET_FOCUS, self._on_focus)
        self.Bind(wx.EVT_KILL_FOCUS, self._on_kill_focus)
        
        self._parent = parent
        self._has_focus = False
    
    def _on_key_down(self, event):
        """Tuş olaylarını yakala - ok tuşlarını listede tut."""
        keycode = event.GetKeyCode()
        count = self.GetItemCount()
        
        if count == 0:
            event.Skip()
            return
        
        # === OK TUŞLARI - SADECE LİSTEDE GEZİNME ===
        if keycode in [wx.WXK_UP, wx.WXK_DOWN, wx.WXK_PAGEUP, wx.WXK_PAGEDOWN]:
            current = self.GetFirstSelected()
            
            # Seçili yoksa ilk öğeyi seç
            if current == -1:
                if keycode == wx.WXK_UP:
                    new_idx = count - 1  # Yukarı -> sona git
                else:
                    new_idx = 0  # Aşağı -> ilk
            else:
                if keycode == wx.WXK_UP:
                    new_idx = max(0, current - 1)
                elif keycode == wx.WXK_DOWN:
                    new_idx = min(count - 1, current + 1)
                elif keycode == wx.WXK_PAGEUP:
                    new_idx = max(0, current - 10)
                else:  # PAGEDOWN
                    new_idx = min(count - 1, current + 10)
            
            # Seçimi değiştir
            self.Select(new_idx)
            self.Focus(new_idx)
            self.EnsureVisible(new_idx)
            
            # Olayı manuel tetikle (parent'a haber ver)
            evt = wx.ListEvent(wx.wxEVT_LIST_ITEM_SELECTED, self.GetId())
            evt.SetIndex(new_idx)
            wx.PostEvent(self.GetParent(), evt)
            
            # Sesli geri bildirim (opsiyonel)
            try:
                wx.Bell()  # Hafif bip sesi
            except:
                pass
            
            return
        
        # === HOME / END ===
        if keycode == wx.WXK_HOME:
            if count > 0:
                self.Select(0)
                self.Focus(0)
                self.EnsureVisible(0)
                evt = wx.ListEvent(wx.wxEVT_LIST_ITEM_SELECTED, self.GetId())
                evt.SetIndex(0)
                wx.PostEvent(self.GetParent(), evt)
            return
        
        if keycode == wx.WXK_END:
            if count > 0:
                self.Select(count - 1)
                self.Focus(count - 1)
                self.EnsureVisible(count - 1)
                evt = wx.ListEvent(wx.wxEVT_LIST_ITEM_SELECTED, self.GetId())
                evt.SetIndex(count - 1)
                wx.PostEvent(self.GetParent(), evt)
            return
        
        # === ENTER - Seçiliyi sil (isteğe bağlı) ===
        if keycode == wx.WXK_RETURN:
            if self.GetFirstSelected() != -1:
                # Parent'ın silme fonksiyonunu çağır
                if hasattr(self._parent, '_on_delete'):
                    wx.CallAfter(self._parent._on_delete)
            return
        
        # === TAB - Butonlara geçişe izin ver ===
        if keycode == wx.WXK_TAB:
            event.Skip()
            return
        
        # Diğer tuşlar
        event.Skip()
    
    def _on_focus(self, event):
        """Odak geldiğinde."""
        self._has_focus = True
        # Eğer hiç seçili yoksa ilk öğeyi seç
        if self.GetItemCount() > 0 and self.GetFirstSelected() == -1:
            self.Select(0)
            self.Focus(0)
        event.Skip()
    
    def _on_kill_focus(self, event):
        """Odak gittiğinde."""
        self._has_focus = False
        event.Skip()
    
    def SelectNext(self):
        """Bir sonraki öğeyi seç (programatik)."""
        current = self.GetFirstSelected()
        count = self.GetItemCount()
        if count == 0:
            return
        new_idx = 0 if current == -1 else min(count - 1, current + 1)
        self.Select(new_idx)
        self.Focus(new_idx)
        self.EnsureVisible(new_idx)


# ============================================================
# 4. ANA PANEL
# ============================================================

class AdminPanel(wx.Frame):
    """Ana yönetim paneli."""
    
    def __init__(self):
        super().__init__(
            None,
            title="Skor Tablosu Yönetimi",
            size=(850, 600),
            style=wx.DEFAULT_FRAME_STYLE
        )
        
        # Değişkenler
        self.gist = GistManager()
        self.entries = []
        self.selected_username = None
        self.is_loading = False
        self.is_deleting = False
        
        # UI
        self._init_ui()
        
        # Başlangıç
        wx.CallAfter(self._refresh_data)
        
        # Merkeze
        self.Centre()
        
        # Odak listeye
        self.list_ctrl.SetFocus()
    
    def _init_ui(self):
        """Arayüz."""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # ---- BAŞLIK ----
        title = wx.StaticText(panel, label="📊 SKOR TABLOSU YÖNETİMİ")
        title_font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        title.SetForegroundColour(wx.Colour(0, 100, 200))
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # ---- DURUM PANELİ ----
        status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Token
        token_box = wx.StaticBox(panel, label="🔑 Token")
        token_sizer = wx.StaticBoxSizer(token_box, wx.HORIZONTAL)
        self.token_label = wx.StaticText(panel, label="")
        token_sizer.Add(self.token_label, 0, wx.ALL, 5)
        status_sizer.Add(token_sizer, 0, wx.RIGHT, 10)
        
        # Kayıt
        count_box = wx.StaticBox(panel, label="📝 Kayıt")
        count_sizer = wx.StaticBoxSizer(count_box, wx.HORIZONTAL)
        self.count_label = wx.StaticText(panel, label="0")
        count_sizer.Add(self.count_label, 0, wx.ALL, 5)
        status_sizer.Add(count_sizer, 0, wx.RIGHT, 10)
        
        # Seçili
        sel_box = wx.StaticBox(panel, label="🎯 Seçili")
        sel_sizer = wx.StaticBoxSizer(sel_box, wx.HORIZONTAL)
        self.sel_label = wx.StaticText(panel, label="Yok")
        sel_sizer.Add(self.sel_label, 0, wx.ALL, 5)
        status_sizer.Add(sel_sizer, 0, wx.RIGHT, 10)
        
        main_sizer.Add(status_sizer, 0, wx.ALL, 10)
        
        # ---- ARAÇ ÇUBUĞU ----
        toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = wx.Button(panel, label="🔄 Yenile", size=(100, 35))
        self.delete_btn = wx.Button(panel, label="🗑️ Sil", size=(100, 35))
        self.exit_btn = wx.Button(panel, label="❌ Çıkış", size=(100, 35))
        
        self.refresh_btn.SetToolTip("F5 - Skor tablosunu yeniler")
        self.delete_btn.SetToolTip("Delete - Seçili kullanıcıyı siler")
        self.exit_btn.SetToolTip("Esc - Paneli kapatır")
        
        toolbar_sizer.Add(self.refresh_btn, 0, wx.RIGHT, 10)
        toolbar_sizer.Add(self.delete_btn, 0, wx.RIGHT, 10)
        toolbar_sizer.Add(self.exit_btn, 0, 0)
        
        # Kısayol bilgisi
        shortcut_info = wx.StaticText(
            panel,
            label="Kısayollar: F5=Yenile | Delete=Sil | Esc=Çıkış | ↑↓=Gezin | Enter=Sil"
        )
        shortcut_info.SetForegroundColour(wx.Colour(80, 80, 80))
        shortcut_info.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        toolbar_sizer.AddStretchSpacer()
        toolbar_sizer.Add(shortcut_info, 0, wx.ALIGN_CENTER_VERTICAL)
        
        main_sizer.Add(toolbar_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # ---- LİSTE ----
        self.list_ctrl = ScoreListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES | wx.BORDER_SUNKEN
        )
        
        # Sütunlar
        self.list_ctrl.AppendColumn("Kullanıcı Adı", width=180)
        self.list_ctrl.AppendColumn("Toplam Para", width=150)
        self.list_ctrl.AppendColumn("Nakit", width=130)
        self.list_ctrl.AppendColumn("Temiz Para", width=130)
        self.list_ctrl.AppendColumn("Gün", width=80)
        
        main_sizer.Add(self.list_ctrl, 1, wx.ALL | wx.EXPAND, 10)
        
        # ---- DURUM ÇUBUĞU ----
        self.status_bar = wx.StatusBar(self)
        self.status_bar.SetFieldsCount(1)
        self.SetStatusBar(self.status_bar)
        self.status_bar.SetStatusText("✅ Hazır - ↑↓ tuşları ile gezinebilirsiniz")
        
        # ---- OLAYLAR ----
        self.refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        self.delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
        self.exit_btn.Bind(wx.EVT_BUTTON, self._on_exit)
        
        # Liste seçim olayları
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_select)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_deselect)
        
        # Global klavye
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key)
        
        # Pencere kapatma
        self.Bind(wx.EVT_CLOSE, self._on_close)
        
        # ---- PANEL ----
        panel.SetSizer(main_sizer)
        main_sizer.Fit(self)
        
        # Token durumu
        if self.gist.token:
            self.token_label.SetLabel("✅ Mevcut")
            self.token_label.SetForegroundColour(wx.Colour(0, 150, 0))
        else:
            self.token_label.SetLabel("❌ Yok")
            self.token_label.SetForegroundColour(wx.Colour(200, 0, 0))
    
    def _refresh_data(self, event=None):
        """Verileri yenile."""
        if self.is_loading:
            return
        
        self.is_loading = True
        self.refresh_btn.Disable()
        self.status_bar.SetStatusText("⏳ Yükleniyor...")
        
        def load_thread():
            try:
                entries = self.gist.get_entries()
                wx.CallAfter(self._on_data_loaded, entries)
            except Exception as e:
                wx.CallAfter(self._on_data_error, str(e))
        
        threading.Thread(target=load_thread, daemon=True).start()
    
    def _on_data_loaded(self, entries):
        """Veriler yüklendi."""
        self.is_loading = False
        self.refresh_btn.Enable()
        
        if entries is None:
            self.status_bar.SetStatusText("❌ Bağlantı hatası!")
            self.entries = []
            self.count_label.SetLabel("0")
        else:
            self.entries = entries
            self.count_label.SetLabel(str(len(entries)))
            self.status_bar.SetStatusText(f"✅ {len(entries)} kayıt yüklendi")
        
        self._update_list()
        self.list_ctrl.SetFocus()
    
    def _on_data_error(self, error_msg):
        """Hata."""
        self.is_loading = False
        self.refresh_btn.Enable()
        self.status_bar.SetStatusText(f"❌ Hata: {error_msg}")
    
    def _update_list(self):
        """Listeyi güncelle."""
        self.list_ctrl.Freeze()
        
        try:
            self.list_ctrl.DeleteAllItems()
            
            sorted_entries = sorted(
                self.entries,
                key=lambda x: x.get("total", x.get("score", 0)),
                reverse=True
            )
            
            for idx, entry in enumerate(sorted_entries):
                username = entry.get("username", "Bilinmeyen")
                total = entry.get("total", entry.get("score", 0))
                cash = entry.get("cash", 0)
                clean = entry.get("clean_money", 0)
                day = entry.get("day", 0)
                
                index = self.list_ctrl.InsertItem(idx, username)
                self.list_ctrl.SetItem(index, 1, self._format_money(total))
                self.list_ctrl.SetItem(index, 2, self._format_money(cash))
                self.list_ctrl.SetItem(index, 3, self._format_money(clean))
                self.list_ctrl.SetItem(index, 4, str(day))
            
            # Sütun genişlikleri
            for col in range(5):
                self.list_ctrl.SetColumnWidth(col, wx.LIST_AUTOSIZE)
            
            # İlk öğeyi seç
            if self.list_ctrl.GetItemCount() > 0:
                self.list_ctrl.Select(0)
                self.list_ctrl.Focus(0)
                
        finally:
            self.list_ctrl.Thaw()
    
    def _format_money(self, value) -> str:
        """Para formatı."""
        try:
            value = float(value)
            if value >= 1000000:
                return f"{value/1000000:.2f}M"
            elif value >= 1000:
                return f"{value/1000:.1f}K"
            else:
                return f"{value:,.0f}"
        except:
            return "0"
    
    def _on_select(self, event):
        """Seçim değişti."""
        index = event.GetIndex()
        self.selected_username = self.list_ctrl.GetItemText(index)
        self.sel_label.SetLabel(self.selected_username)
        self.status_bar.SetStatusText(f"🎯 Seçili: {self.selected_username}")
    
    def _on_deselect(self, event):
        """Seçim kaldırıldı."""
        self.selected_username = None
        self.sel_label.SetLabel("Yok")
    
    def _on_refresh(self, event=None):
        """Yenile."""
        self._refresh_data()
    
    def _on_delete(self, event=None):
        """Sil."""
        if not self.selected_username:
            wx.MessageBox(
                "Lütfen önce listeden bir kullanıcı seçin.\n\n↑↓ tuşları ile gezinin.",
                "Uyarı",
                wx.OK | wx.ICON_WARNING
            )
            self.list_ctrl.SetFocus()
            return
        
        if self.is_deleting:
            return
        
        # Onay
        dlg = wx.MessageDialog(
            self,
            f"'{self.selected_username}' adlı kullanıcıyı SİLMEK istediğinize emin misiniz?\n\nBu işlem GERİ ALINAMAZ!",
            "Silme Onayı",
            wx.YES_NO | wx.ICON_QUESTION | wx.YES_DEFAULT
        )
        result = dlg.ShowModal()
        dlg.Destroy()
        
        if result != wx.ID_YES:
            self.list_ctrl.SetFocus()
            return
        
        # Sil
        self.is_deleting = True
        self.delete_btn.Disable()
        self.status_bar.SetStatusText(f"⏳ Siliniyor: {self.selected_username}")
        
        username = self.selected_username
        
        def delete_thread():
            try:
                success, message = self.gist.delete_entry(username)
                wx.CallAfter(self._on_delete_done, success, message)
            except Exception as e:
                wx.CallAfter(self._on_delete_done, False, str(e))
        
        threading.Thread(target=delete_thread, daemon=True).start()
    
    def _on_delete_done(self, success, message):
        """Silme tamamlandı."""
        self.is_deleting = False
        self.delete_btn.Enable()
        
        if success:
            wx.MessageBox(f"✅ {message}", "Başarılı", wx.OK | wx.ICON_INFORMATION)
            self.selected_username = None
            self.sel_label.SetLabel("Yok")
            self._refresh_data()
        else:
            wx.MessageBox(f"❌ {message}", "Hata", wx.OK | wx.ICON_ERROR)
            self.status_bar.SetStatusText(f"❌ {message}")
        
        self.list_ctrl.SetFocus()
    
    def _on_exit(self, event=None):
        """Çıkış."""
        self.Close()
    
    def _on_key(self, event):
        """Global kısayollar."""
        keycode = event.GetKeyCode()
        
        # F5 = Yenile
        if keycode == wx.WXK_F5:
            self._on_refresh()
            return
        
        # Delete = Sil (sadece listede odak varken)
        if keycode == wx.WXK_DELETE:
            # Eğer liste odakta değilse, listeye odak ver
            if not self.list_ctrl.HasFocus():
                self.list_ctrl.SetFocus()
            self._on_delete()
            return
        
        # Escape = Çıkış
        if keycode == wx.WXK_ESCAPE:
            self._on_exit()
            return
        
        # Tab tuşuna izin ver (butonlara geçiş)
        if keycode == wx.WXK_TAB:
            event.Skip()
            return
        
        event.Skip()
    
    def _on_close(self, event):
        """Kapatma."""
        if self.is_loading or self.is_deleting:
            dlg = wx.MessageDialog(
                self,
                "İşlem devam ediyor. Çıkmak istediğinize emin misiniz?",
                "Çıkış",
                wx.YES_NO | wx.ICON_QUESTION
            )
            if dlg.ShowModal() != wx.ID_YES:
                dlg.Destroy()
                event.Veto()
                return
            dlg.Destroy()
        
        event.Skip()


# ============================================================
# 5. UYGULAMA
# ============================================================

class AdminApp(wx.App):
    def OnInit(self):
        self.SetAppName("SkorYonetim")
        frame = AdminPanel()
        frame.Show()
        return True


def main():
    app = AdminApp()
    app.MainLoop()


if __name__ == "__main__":
    main()