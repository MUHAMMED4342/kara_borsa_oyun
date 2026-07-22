# dialogs.py - Tüm wx.Dialog pencereleri (Arsa, Ana Menü, Kayıt Yükle,
# Şirket, Muhbir, Kredi, Bankacılık, Hapis, Skor Tablosu)
# -*- coding: utf-8 -*-

import os
import random
import time
import wx
import threading
import webbrowser  # Tarayıcıda iletişim sayfasını açmak için eklendi

from game_data import COMPANY_TYPES, LAND_TYPES, EMPLOYEE_HIRE_FEE, EMPLOYEE_BASE_SALARY, INFORMANT_CONFIG
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl
from audio_manager import AudioManager
from save_manager import list_saves, delete_save
from game_state import resource_path, open_help, open_release_notes, ID_LOAD, ID_NEW, ROULETTE_BET_LABELS

# Skor tablosu için import
# ÖNEMLİ: skor_gonderimi_aktif'i doğrudan "from leaderboard import ..." ile
# almıyoruz; bu modülün import edilmesiyle birlikte leaderboard.py'deki
# gerçek durumu okuyup/yazabilmek için modülün kendisini import ediyoruz.
import leaderboard
from leaderboard import get_leaderboard, get_gist_content


def speak(text: str):
    """Ekran okuyucuya seslendirir VE aynı mesajı geçmiş kaydına ekler."""
    _tts_speak(text)
    log_history(text)


# ---------------------------------------------------------------------------
# RULET ÇARKI SESİ - SÜRE TESPİTİ
# ---------------------------------------------------------------------------
# çark.mp3 çalmaya başladıktan sonra, ses bitene kadar bekleyip SONRA
# sonucu ekran okuyucuya bildirmemiz gerekiyor. Bunun için mp3 dosyasının
# süresini mümkünse `mutagen` kütüphanesiyle (pip install mutagen) otomatik
# okuyoruz. mutagen kurulu değilse ya da süre okunamazsa aşağıdaki sabit
# (SPIN_SOUND_FALLBACK_SECONDS) kullanılır.
#
# ÖNEMLİ: mutagen kurulu değilse, bu sabiti kendi cark.mp3 dosyanızın
# GERÇEK süresine (saniye) göre elle güncelleyin; aksi halde anons ses
# bitmeden ya da bittikten epey sonra yapılır.
SPIN_SOUND_FALLBACK_SECONDS = 4.0


def _get_spin_sound_duration(path: str) -> float:
    if os.path.exists(path):
        try:
            from mutagen.mp3 import MP3
            length = MP3(path).info.length
            if length and length > 0:
                return length
        except Exception:
            pass
    return SPIN_SOUND_FALLBACK_SECONDS


class LandManagementDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title="Arsa Yönetimi", size=(650, 550))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="ARSA YÖNETİMİ")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        sizer.Add(wx.StaticText(panel, label="Arsalarınız:"), 0, wx.LEFT | wx.TOP, 10)
        self.land_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.land_list.SetMinSize((500, 150))
        sizer.Add(self.land_list, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Piyasadaki Arsalar:"), 0, wx.LEFT | wx.TOP, 10)
        self.market_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.market_list.SetMinSize((500, 100))
        sizer.Add(self.market_list, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.buy_btn = wx.Button(panel, label="Satın Al")
        self.sell_btn = wx.Button(panel, label="Sat")
        btn_sizer1.Add(self.buy_btn, 0, wx.ALL, 5)
        btn_sizer1.Add(self.sell_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer1, 0, wx.ALIGN_CENTER, 5)

        info_note = wx.StaticText(panel, label="Arsa kredisi için ana ekrandaki \"Kredi Çek\" butonunu kullanın.")
        sizer.Add(info_note, 0, wx.LEFT | wx.BOTTOM, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((500, 80))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.buy_btn.Bind(wx.EVT_BUTTON, self.on_buy_land)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell_land)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.land_list.Bind(wx.EVT_LISTBOX, self.on_land_select)
        self.market_list.Bind(wx.EVT_LISTBOX, self.on_market_select)

    def _update_ui(self):
        self.land_list.Clear()
        for i, land in enumerate(self.state.lands):
            land_type = land["type"]
            price = self.state.get_land_price(land_type)
            purchase_price = land["purchase_price"]
            profit = price - purchase_price
            profit_str = f"(+{profit:,.0f} TL)" if profit >= 0 else f"({profit:,.0f} TL)"
            has_loan = land.get("has_loan", False)
            if has_loan:
                debt = land.get("loan_debt", land.get("loan_amount", 0.0) * 1.15)
                days_left = land.get("loan_days_until_installment", 30)
                loan_str = f" [Kredili, borç: {debt:,.0f} TL, taksite {days_left} gün]"
            else:
                loan_str = ""
            self.land_list.Append(f"{i+1}. {land_type} - {price:,.0f} TL {profit_str}{loan_str}")

        self.market_list.Clear()
        for land_type, data in LAND_TYPES.items():
            price = self.state.get_land_price(land_type)
            count = self.state.get_land_count(land_type)
            label = f"{land_type} - {price:,.0f} TL (Sahip: {count} adet) - {data['description']}"
            self.market_list.Append(label, land_type)

        total_land_value = sum(self.state.get_land_price(land["type"]) for land in self.state.lands)
        status = (
            f"Toplam Arsa Sayısı: {len(self.state.lands)} | "
            f"Toplam Değer: {total_land_value:,.0f} TL\n"
            f"Nakit: {self.state.cash:,.0f} TL"
        )
        self.status_text.SetValue(status)

        has_land = len(self.state.lands) > 0
        self.sell_btn.Enable(has_land)

    def on_land_select(self, event):
        idx = self.land_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.state.lands):
            land = self.state.lands[idx]
            land_type = land["type"]
            price = self.state.get_land_price(land_type)
            purchase_price = land["purchase_price"]
            profit = price - purchase_price
            days_held = self.state.day - land["purchase_day"]
            speak(f"{land_type} - Güncel fiyat: {price:,.0f} TL, Alış: {purchase_price:,.0f} TL, {days_held} gün tutuluyor")

    def on_market_select(self, event):
        idx = self.market_list.GetSelection()
        if idx != wx.NOT_FOUND:
            land_type = self.market_list.GetClientData(idx)
            price = self.state.get_land_price(land_type)
            data = LAND_TYPES[land_type]
            speak(f"{land_type} - Fiyat: {price:,.0f} TL, {data['description']}")

    def on_buy_land(self, event):
        idx = self.market_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Lütfen bir arsa tipi seçin")
            return
        
        land_type = self.market_list.GetClientData(idx)
        
        success, msg = self.state.buy_land(land_type)
        speak(msg)
        if success:
            self._update_ui()
            self.parent.auto_save()

    def on_sell_land(self, event):
        idx = self.land_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Lütfen satmak istediğiniz arsayı seçin")
            return
        
        land = self.state.lands[idx]
        if land.get("has_loan", False):
            speak("Bu arsa üzerinde kredi var. Önce krediyi kapatın.")
            return
        
        if wx.MessageBox("Bu arsayı satmak istediğinize emin misiniz?", "Onay", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            success, msg = self.state.sell_land(idx)
            speak(msg)
            if success:
                self._update_ui()
                self.parent.auto_save()


# ============================================================
# MENU SINIFLARI
# ============================================================

class MainMenu(wx.Dialog):
    def __init__(self, parent=None):
        # Yüksekliği (size) yeni İletişim butonu sığacak şekilde 450'den 480'e çıkardık.
        super().__init__(parent, title="Karaborsa", size=(350, 480))
        self.parent = parent
        self.username = None
        self.audio = AudioManager()
        self.sound_navigate = resource_path("sounds/button.wav")
        self.sound_select = resource_path("sounds/DROPDOWNBUTTONGRID.mp3")
        self._last_spoken_index = -1
        
        self._build_ui()
        self._bind_events()
    
    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title = wx.StaticText(panel, label="KARABORSA")
        title.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 15)
        
        # Ana menü seçenekleri (İletişim eklendi)
        menu_items = [
            "Yeni Oyun",
            "Devam Et",
            "Skor Tablosunu Görüntüle",
            "Yardım",
            "Yenilikler",
            "İletişim",
            "Çıkış"
        ]
        
        # Skor gönderimi durumunu gösteren seçenek (toggle)
        status = "Etkin" if leaderboard.is_score_submission_enabled() else "Devre Dışı"
        menu_items.insert(3, f"Skor Gönderimi: {status}")
        
        self.menu_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.menu_list.SetItems(menu_items)
        self.menu_list.SetSelection(0)
        sizer.Add(self.menu_list, 1, wx.EXPAND | wx.ALL, 20)
        
        info = wx.StaticText(panel, label="Yukarı/Aşağı seç, Enter onayla")
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 10)
        
        panel.SetSizer(sizer)
        self.menu_list.SetFocus()
    
    def _bind_events(self):
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def on_close(self, event):
        self.EndModal(wx.ID_CANCEL)
    
    def on_key_down(self, event: wx.KeyEvent):
        keycode = event.GetKeyCode()
        item_count = self.menu_list.GetCount()
        idx = self.menu_list.GetSelection()
        if idx == wx.NOT_FOUND:
            idx = 0
        
        if keycode == wx.WXK_DOWN:
            if idx < item_count - 1:
                idx += 1
                self.menu_list.SetSelection(idx)
                self.play_sound(self.sound_navigate)
        elif keycode == wx.WXK_UP:
            if idx > 0:
                idx -= 1
                self.menu_list.SetSelection(idx)
                self.play_sound(self.sound_navigate)
        elif keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_sound(self.sound_select)
            self.execute_selection(idx)
        elif keycode == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()
    
    def execute_selection(self, idx=None):
        if idx is None:
            idx = self.menu_list.GetSelection()
            if idx == wx.NOT_FOUND:
                idx = 0
        
        # Menü indeksleri:
        # 0: Yeni Oyun
        # 1: Devam Et
        # 2: Skor Tablosunu Görüntüle
        # 3: Skor Gönderimi Toggle
        # 4: Yardım
        # 5: Yenilikler
        # 6: İletişim
        # 7: Çıkış
        
        if idx == 0:
            self.start_new_game()
        elif idx == 1:
            self.continue_game()
        elif idx == 2:
            self.show_leaderboard()
        elif idx == 3:
            self.toggle_score_submission()
        elif idx == 4:
            open_help()
        elif idx == 5:
            open_release_notes()
        elif idx == 6:
            self.open_contact_page()
        elif idx == 7:
            self.EndModal(wx.ID_CANCEL)

    def open_contact_page(self):
        """İletişim web sayfasını varsayılan tarayıcıda açar."""
        webbrowser.open("https://bilgisayar-xi.vercel.app/iletisim.html")
        speak("İletişim sayfası tarayıcınızda açılıyor.")
    
    def start_new_game(self):
        saves = list_saves()
        if saves:
            existing = saves[0]
            wx.MessageBox(
                f"Bu bilgisayarda zaten '{existing}' adlı bir hesap kayıtlı.\n"
                f"Aynı bilgisayarda birden fazla hesap açılamaz.\n\n"
                f"Devam etmek için ana menüden 'Devam Et' seçeneğini kullanın.\n"
                f"Farklı bir hesapla başlamak isterseniz önce 'Devam Et' ekranından\n"
                f"mevcut kaydı silmeniz gerekir.",
                "Tek Hesap Kuralı", wx.OK | wx.ICON_WARNING
            )
            speak(f"Bu bilgisayarda zaten {existing} adlı bir hesap kayıtlı. Yeni hesap açılamaz.")
            return

        dlg = wx.TextEntryDialog(self, "Kullanıcı adınız:", "Kullanıcı Adı")
        if dlg.ShowModal() == wx.ID_OK:
            username = dlg.GetValue().strip()
            dlg.Destroy()
            if not username:
                speak("Kullanıcı adı boş olamaz")
                return
            self.username = username
            self.EndModal(ID_NEW)
        else:
            dlg.Destroy()
    
    def continue_game(self):
        saves = list_saves()
        if not saves:
            speak("Kayıtlı oyun yok")
            return
        dlg = LoadGameDialog(self, saves)
        result = dlg.ShowModal()
        if result == wx.ID_OK and dlg.selected_user:
            self.username = dlg.selected_user
            dlg.Destroy()
            self.EndModal(ID_LOAD)
        else:
            dlg.Destroy()
    
    def show_leaderboard(self):
        """Skor tablosunu gösteren dialog."""
        dlg = wx.Dialog(self, title="Skor Tablosu Yükleniyor...", size=(300, 150))
        dlg.CenterOnScreen()
        
        panel = wx.Panel(dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)
        loading_label = wx.StaticText(panel, label="Skorlar yükleniyor, lütfen bekleyin...")
        sizer.Add(loading_label, 0, wx.ALL | wx.CENTER, 20)
        panel.SetSizer(sizer)
        dlg.Show()
        
        def load_scores():
            try:
                scores = get_leaderboard()
                wx.CallAfter(self._show_leaderboard_dialog, scores, dlg)
            except Exception as e:
                wx.CallAfter(self._show_leaderboard_dialog, None, dlg, str(e))
        
        thread = threading.Thread(target=load_scores)
        thread.daemon = True
        thread.start()
    
    def _show_leaderboard_dialog(self, scores, loading_dlg, error=None):
        """Skor tablosu dialog'u gösterir."""
        loading_dlg.Destroy()
        
        if error:
            wx.MessageBox(f"Skorlar yüklenirken hata oluştu:\n{error}", "Hata", wx.OK | wx.ICON_ERROR)
            return
        
        if scores is None:
            wx.MessageBox(
                "Skor tablosu yüklenemedi.\n\n"
                "İnternet bağlantınızı kontrol edip tekrar deneyin.",
                "Bağlantı Hatası", wx.OK | wx.ICON_ERROR
            )
            speak("Skor tablosu yüklenemedi. İnternet bağlantınızı kontrol edin.")
            return
        
        if not scores:
            wx.MessageBox("Henüz hiç skor kaydedilmemiş.", "Skor Tablosu", wx.OK | wx.ICON_INFORMATION)
            return
        
        dlg = wx.Dialog(self, title="SKOR TABLOSU", size=(500, 450))
        
        panel = wx.Panel(dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title = wx.StaticText(panel, label="EN İYİ SKORLAR")
        title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        list_box.SetMinSize((460, 300))
        
        for i, entry in enumerate(scores, 1):
            username = entry.get("username", "Bilinmeyen")
            cash = entry.get("cash", 0)

            label = f"{i}. {username} Nakit: {format_tl(cash)} TL"
            list_box.Append(label)
        
        sizer.Add(list_box, 1, wx.EXPAND | wx.ALL, 10)
        
        close_btn = wx.Button(panel, label="Kapat")
        sizer.Add(close_btn, 0, wx.ALL | wx.CENTER, 10)
        
        panel.SetSizer(sizer)

        def _close_leaderboard(e):
            self.play_sound(self.sound_select)
            dlg.EndModal(wx.ID_OK)

        close_btn.Bind(wx.EVT_BUTTON, _close_leaderboard)
        dlg.CenterOnScreen()
        dlg.ShowModal()
        dlg.Destroy()
    
    def toggle_score_submission(self):
        """Skor gönderimi toggle işlemi."""
        yeni_durum = not leaderboard.is_score_submission_enabled()
        leaderboard.set_score_submission_enabled(yeni_durum)

        status = "Etkin" if yeni_durum else "Devre Dışı"
        current_items = self.menu_list.GetItems()
        if len(current_items) > 3:
            current_items[3] = f"Skor Gönderimi: {status}"
            self.menu_list.SetItems(current_items)
            self.menu_list.SetSelection(3)
            self.menu_list.SetFocus()
        
        msg = f"Skor gönderimi {status.lower()}"
        speak(msg)
        wx.MessageBox(msg, "Bilgi", wx.OK | wx.ICON_INFORMATION)
    
    def play_sound(self, sound_path):
        if os.path.exists(sound_path):
            self.audio.play_sound(sound_path)


class LoadGameDialog(wx.Dialog):
    def __init__(self, parent, saves):
        super().__init__(parent, title="Kayıtlı Oyunlar", size=(350, 400))
        self.parent = parent
        self.saves = saves
        self.selected_user = None
        self.audio = AudioManager()
        self.sound_navigate = resource_path("sounds/button.wav")
        self.sound_select = resource_path("sounds/DROPDOWNBUTTONGRID.mp3")
        self._last_spoken_index = -1
        self._is_loading = False
        
        self._build_ui()
        self._bind_events()
        
        wx.CallAfter(self.save_list.SetFocus)
        if self.saves:
            wx.CallAfter(self.save_list.SetSelection, 0)
    
    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title = wx.StaticText(panel, label="KAYITLI OYUNLAR")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 15)
        
        self.save_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.save_list.SetItems(self.saves)
        if self.saves:
            self.save_list.SetSelection(0)
        sizer.Add(self.save_list, 1, wx.EXPAND | wx.ALL, 10)
        
        info = wx.StaticText(panel, label="Yukarı/Aşağı seç, Enter veya Çift Tık yükle, Delete sil")
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 5)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.load_btn = wx.Button(panel, label="Yükle (Enter)")
        self.delete_btn = wx.Button(panel, label="Sil (Delete)")
        self.cancel_btn = wx.Button(panel, label="İptal (Esc)")
        btn_sizer.Add(self.load_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.delete_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 10)
        
        panel.SetSizer(sizer)
    
    def _bind_events(self):
        self.save_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_activate)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        self.load_btn.Bind(wx.EVT_BUTTON, self.on_load_button)
        self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete_button)
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel_button)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_dialog_key)
    
    def on_close(self, event):
        self.EndModal(wx.ID_CANCEL)
    
    def on_dialog_key(self, event: wx.KeyEvent):
        keycode = event.GetKeyCode()
        item_count = self.save_list.GetCount()
        idx = self.save_list.GetSelection()
        if idx == wx.NOT_FOUND:
            if item_count > 0:
                self.save_list.SetSelection(0)
                idx = 0
            else:
                event.Skip()
                return
        
        if keycode == wx.WXK_DOWN:
            if idx < item_count - 1:
                idx += 1
                self.save_list.SetSelection(idx)
                self.play_sound(self.sound_navigate)
            return
        elif keycode == wx.WXK_UP:
            if idx > 0:
                idx -= 1
                self.save_list.SetSelection(idx)
                self.play_sound(self.sound_navigate)
            return
        elif keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.play_sound(self.sound_select)
            self._load_selected()
            return
        elif keycode == wx.WXK_DELETE or keycode == wx.WXK_NUMPAD_DELETE:
            self.delete_selected()
            return
        elif keycode == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        else:
            event.Skip()
    
    def on_activate(self, event):
        self.play_sound(self.sound_select)
        self._load_selected()

    def on_load_button(self, event):
        self.play_sound(self.sound_select)
        self._load_selected()

    def _load_selected(self):
        if self._is_loading:
            return
        idx = self.save_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.saves):
            self._is_loading = True
            self.selected_user = self.save_list.GetString(idx)
            speak(f"{self.selected_user} yükleniyor...")
            self.EndModal(wx.ID_OK)
        else:
            speak("Kayıt seçilmedi")

    def on_delete_button(self, event):
        self.delete_selected()
    
    def on_cancel_button(self, event):
        self.play_sound(self.sound_navigate)
        self.EndModal(wx.ID_CANCEL)
    
    def delete_selected(self):
        idx = self.save_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Silinecek kayıt seçilmedi")
            return
        if not self.saves or idx >= len(self.saves):
            return
        username = self.save_list.GetString(idx)
        if wx.MessageBox(f"'{username}' kaydını sil?", "Kayıt Sil", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            delete_save(username)
            self.saves.remove(username)
            self.save_list.SetItems(self.saves)
            speak(f"{username} kaydı silindi")
            self._last_spoken_index = -1
            if not self.saves:
                speak("Kayıtlı oyun kalmadı")
                self.EndModal(wx.ID_CANCEL)
            elif self.saves:
                self.save_list.SetSelection(0)
    
    def play_sound(self, sound_path):
        if os.path.exists(sound_path):
            self.audio.play_sound(sound_path)


class HistoryDialog(wx.Dialog):
    """
    Oyun boyunca ekran okuyucuya söylenmiş tüm mesajların listesini gösterir.
    Hızlı gün atlarken kaçırılan anonsları tekrar okumak için kullanılır.
    Salt-okunur çok satırlı bir metin kutusu olduğu için ekran okuyucunuzun
    normal metin okuma / inceleme (review) tuşlarıyla satır satır
    gezinebilirsiniz; ayrıca Ctrl+A ile tümünü seçip kopyalayabilirsiniz.
    """

    def __init__(self, parent):
        super().__init__(
            parent, title="Geçmiş",
            size=(600, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.parent = parent
        self._build_ui()
        self._bind_events()
        self._load_entries()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="GEÇMİŞ - SÖYLENEN MESAJLAR")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        info = wx.StaticText(panel, label="En yeni mesaj en altta. Ctrl+A: tümünü seç, Esc: kapat")
        sizer.Add(info, 0, wx.LEFT | wx.BOTTOM, 10)

        self.text_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_DONTWRAP
        )
        self.text_ctrl.SetMinSize((560, 380))
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(panel, label="Yenile")
        self.close_btn = wx.Button(panel, label="Kapat")
        btn_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self._load_entries())
        self.close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

    def on_key_down(self, event: wx.KeyEvent):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
            return
        event.Skip()

    def _load_entries(self):
        # Döngüsel import'tan kaçınmak için burada import ediyoruz.
        from history_log import get_history
        entries = get_history()

        if not entries:
            self.text_ctrl.SetValue("Henüz kayıtlı bir mesaj yok.")
            return

        lines = []
        for entry in entries:
            day = entry.get("day")
            gun_str = f"[Gün {day}] " if day is not None else ""
            lines.append(f"{entry['time']}  {gun_str}{entry['text']}")

        self.text_ctrl.SetValue("\n".join(lines))
        # İmleci en sona (en yeni mesaja) götür.
        self.text_ctrl.SetInsertionPointEnd()


class DailyMessageDialog(wx.Dialog):
    """
    GÜNÜN MESAJI
    Geliştiricinin GitHub üzerinden yayınladığı, oyunculara yönelik
    duyuru/mesajı gösterir. Sadece daha önce gösterilmemiş (yeni tarihli)
    bir mesaj varsa açılır - bkz. daily_message.py.
    """

    def __init__(self, parent, date_str: str, message_text: str):
        super().__init__(
            parent, title="Günün Mesajı",
            size=(520, 380),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.parent = parent
        self._build_ui(date_str, message_text)
        self._bind_events()
        self.CenterOnScreen()

    def _build_ui(self, date_str, message_text):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=f"GÜNÜN MESAJI ({date_str})")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.text_ctrl = wx.TextCtrl(
            panel, value=message_text,
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_WORDWRAP
        )
        self.text_ctrl.SetMinSize((470, 260))
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        self.close_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.close_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

    def on_key_down(self, event: wx.KeyEvent):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
            return
        event.Skip()

class CompanyDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title="Şirket Yönetimi", size=(650, 560))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="ŞİRKET YÖNETİMİ")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        sizer.Add(wx.StaticText(panel, label="Şirketleriniz (farklı şehirlerde birden fazla olabilir):"),
                   0, wx.LEFT | wx.TOP, 10)
        self.company_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.company_list.SetMinSize((550, 100))
        sizer.Add(self.company_list, 0, wx.EXPAND | wx.ALL, 10)

        self.close_btn = wx.Button(panel, label="Seçili Şirketi Kapat")
        sizer.Add(self.close_btn, 0, wx.ALL | wx.CENTER, 5)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label="Yeni Şirket Kur:"), 0, wx.LEFT | wx.TOP, 5)

        guide = wx.StaticText(
            panel,
            label=(
                "Rehber: Düşük sermayeyle başlamak için Tekstil Atölyesi veya "
                "Restoran uygundur. Daha yüksek günlük kâr isterseniz Kripto "
                "Madenciliği veya Gece Kulübü daha uygundur, ancak günlük "
                "giderleri de yüksektir. Oto Galeri dengeli bir orta "
                "seçenektir. Her şirket her gün otomatik olarak kendi kârını "
                "üretir ve kendi kredi notunu yükseltir. Her şehirde en fazla "
                "bir şirketiniz olabilir, ama farklı şehirlerde istediğiniz "
                "kadar şirket açabilirsiniz. Listeden bir tip seçtiğinizde "
                "altta o şirketin maliyet, gider ve kâr aralığı mevcut "
                "bakiyenize göre gösterilir."
            ),
        )
        guide.Wrap(560)
        sizer.Add(guide, 0, wx.EXPAND | wx.ALL, 10)

        company_choices = [
            self._format_company_choice(key, data) for key, data in COMPANY_TYPES.items()
        ]

        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_sizer.Add(wx.StaticText(panel, label="Şirket Tipi:"), 0, wx.ALL | wx.CENTER, 5)
        self.type_combo = wx.ComboBox(panel, choices=company_choices, style=wx.CB_READONLY)
        for i, key in enumerate(COMPANY_TYPES.keys()):
            self.type_combo.SetClientData(i, key)
        type_sizer.Add(self.type_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(type_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.detail_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.detail_text.SetMinSize((550, 90))
        sizer.Add(self.detail_text, 0, wx.EXPAND | wx.ALL, 5)

        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_sizer.Add(wx.StaticText(panel, label="Şirket Adı:"), 0, wx.ALL | wx.CENTER, 5)
        self.name_input = wx.TextCtrl(panel)
        name_sizer.Add(self.name_input, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 5)

        city_sizer = wx.BoxSizer(wx.HORIZONTAL)
        city_sizer.Add(wx.StaticText(panel, label="Şehir:"), 0, wx.ALL | wx.CENTER, 5)
        self.city_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        city_sizer.Add(self.city_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(city_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.setup_btn = wx.Button(panel, label="Bu Şehirde Şirket Kur")
        sizer.Add(self.setup_btn, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _format_company_choice(self, key, data):
        cost = data["setup_cost"]
        upkeep = data["daily_upkeep"]
        profit_min = data["daily_profit_min"]
        profit_max = data["daily_profit_max"]
        afford = "Kurulabilir" if self.state.cash >= cost else "Nakit yetersiz"
        return (
            f"{key} — Kuruluş: {cost:,.0f} TL, Günlük Gider: {upkeep:,.0f} TL, "
            f"Günlük Kâr: {profit_min:,.0f}-{profit_max:,.0f} TL, {afford} "
            f"({data.get('description', '')})"
        )

    def _bind_events(self):
        self.setup_btn.Bind(wx.EVT_BUTTON, self.on_setup)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_company)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.type_combo.Bind(wx.EVT_COMBOBOX, self.on_type_selected)
        self.company_list.Bind(wx.EVT_LISTBOX, self.on_company_select)

    def _update_ui(self):
        self.company_list.Clear()
        for c in self.state.companies:
            self.company_list.Append(
                f"{c['name']} ({c['city']}) - {c['type']} - Kredi Notu: {c['credit_score']} - "
                f"Aktif Gün: {c['days_active']} - Toplam Kâr: {format_tl(c['total_profit'])} TL - "
                f"Aylık Ciro: {format_tl(c['monthly_revenue'])} TL",
                c["id"],
            )
        self.close_btn.Enable(len(self.state.companies) > 0)

        available_cities = self.state.get_available_company_cities()
        self.city_combo.Clear()
        self.city_combo.AppendItems(available_cities)
        if available_cities:
            self.city_combo.SetSelection(0)
            self.type_combo.Enable(True)
            self.name_input.Enable(True)
            self.city_combo.Enable(True)
            self.setup_btn.Enable(True)
            self.detail_text.SetValue(
                "Bir şirket tipi seçtiğinizde ayrıntılar burada görünecek."
            )
        else:
            self.type_combo.Enable(False)
            self.name_input.Enable(False)
            self.city_combo.Enable(False)
            self.setup_btn.Enable(False)
            self.detail_text.SetValue("Şirket açabileceğiniz boş şehir kalmadı.")

    def _get_selected_company_type(self):
        idx = self.type_combo.GetSelection()
        if idx == wx.NOT_FOUND:
            return ""
        return self.type_combo.GetClientData(idx)

    def on_company_select(self, event):
        idx = self.company_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.state.companies):
            c = self.state.companies[idx]
            speak(f"{c['name']} ({c['city']}) seçildi")

    def on_type_selected(self, event):
        company_type = self._get_selected_company_type()
        data = COMPANY_TYPES.get(company_type)
        if not data:
            return

        cost = data["setup_cost"]
        upkeep = data["daily_upkeep"]
        profit_min = data["daily_profit_min"]
        profit_max = data["daily_profit_max"]

        affordable = self.state.cash >= cost
        afford_text = "Şu an nakitiniz yeterli." if affordable else (
            f"Şu an nakitiniz yetersiz (eksik: {format_tl(cost - self.state.cash)} TL)."
        )

        detail = (
            f"{company_type}\n"
            f"Kuruluş maliyeti: {format_tl(cost)} TL | Günlük gider: {format_tl(upkeep)} TL | "
            f"Günlük kâr: {format_tl(profit_min)}-{format_tl(profit_max)} TL\n"
            f"{data.get('description', '')}\n"
            f"{afford_text}"
        )
        self.detail_text.SetValue(detail)

    def on_setup(self, event):
        company_type = self._get_selected_company_type()
        company_name = self.name_input.GetValue().strip()

        if not company_type:
            speak("Şirket tipi seçin")
            return

        if not company_name:
            speak("Şirket adı girin")
            return

        c_idx = self.city_combo.GetSelection()
        if c_idx == wx.NOT_FOUND:
            speak("Şehir seçin")
            return
        city = self.city_combo.GetString(c_idx)

        success, msg = self.state.setup_company(company_type, company_name, city)
        speak(msg)
        if success:
            self.name_input.SetValue("")
            self._update_ui()

    def on_close_company(self, event):
        idx = self.company_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Kapatmak istediğiniz şirketi seçin")
            return

        company_id = self.company_list.GetClientData(idx)
        company = self.state.get_company(company_id)
        name = f"{company['name']} ({company['city']})" if company else "şirket"

        if wx.MessageBox(f"{name} kapatılsın mı?", "Onay", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            success, msg = self.state.close_company(company_id)
            speak(msg)
            if success:
                self._update_ui()


class EmployeeManagementDialog(wx.Dialog):
    """Adam tutma / şehirlere dağıtma yönetim penceresi.

    Adamlar artık ŞİRKETTEN TAMAMEN BAĞIMSIZ çalışır: tutulan adam
    gönderildiği şehirde kendi başına karaborsa işi çevirir, hiçbir
    şirket kurmaz. Oyuncu sadece adam tutar/kovar; üretilen para
    otomatik olarak cüzdana yansır, 30 günde bir de maaş otomatik
    olarak kesilir.
    """

    def __init__(self, parent, state):
        super().__init__(parent, title="Adam Yönetimi", size=(700, 560))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="ADAM YÖNETİMİ")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((640, 60))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Adamlarınız:"), 0, wx.LEFT | wx.TOP, 10)
        self.employee_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.employee_list.SetMinSize((640, 130))
        sizer.Add(self.employee_list, 0, wx.EXPAND | wx.ALL, 10)

        self.fire_btn = wx.Button(panel, label="Kov")
        sizer.Add(self.fire_btn, 0, wx.ALL | wx.CENTER, 5)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label="Yeni Adam Tut ve Şehre Gönder:"), 0, wx.LEFT | wx.TOP, 5)

        person_sizer = wx.BoxSizer(wx.HORIZONTAL)
        person_sizer.Add(wx.StaticText(panel, label="Adam:"), 0, wx.ALL | wx.CENTER, 5)
        self.person_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        person_sizer.Add(self.person_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(person_sizer, 0, wx.EXPAND | wx.ALL, 5)

        city_sizer = wx.BoxSizer(wx.HORIZONTAL)
        city_sizer.Add(wx.StaticText(panel, label="Şehir:"), 0, wx.ALL | wx.CENTER, 5)
        self.city_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        city_sizer.Add(self.city_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(city_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.detail_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.detail_text.SetMinSize((640, 60))
        sizer.Add(self.detail_text, 0, wx.EXPAND | wx.ALL, 5)

        self.hire_btn = wx.Button(panel, label="Adam Tut")
        sizer.Add(self.hire_btn, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.fire_btn.Bind(wx.EVT_BUTTON, self.on_fire)
        self.hire_btn.Bind(wx.EVT_BUTTON, self.on_hire)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.employee_list.Bind(wx.EVT_LISTBOX, self.on_employee_select)
        self.person_combo.Bind(wx.EVT_COMBOBOX, self.on_person_selected)
        self.city_combo.Bind(wx.EVT_COMBOBOX, self.on_city_selected)

    def _update_ui(self):
        # Adam listesi
        self.employee_list.Clear()
        for e in self.state.employees:
            self.employee_list.Append(
                f"{e['name']} - {e['city']} - "
                f"Toplam Ürettiği: {format_tl(e.get('total_generated', 0.0))} TL - "
                f"Maaşa {e['days_until_salary']} gün kaldı",
                e["id"],
            )
        self.fire_btn.Enable(len(self.state.employees) > 0)

        hire_cost = self.state.get_employee_hire_cost()
        salary = self.state.get_employee_salary()
        self.status_text.SetValue(
            f"Toplam Adam: {len(self.state.employees)} | "
            f"Tutma Masrafı: {format_tl(hire_cost)} TL | "
            f"Maaş: {format_tl(salary)} TL / 30 gün | "
            f"Nakit: {format_tl(self.state.cash)} TL"
        )

        # Tutulabilecek kişiler
        self.person_combo.Clear()
        available_people = self.state.get_available_people()
        self.person_combo.AppendItems(available_people)
        if available_people:
            self.person_combo.SetSelection(0)

        # Boş şehirler (düz liste, bölge yok)
        self.city_combo.Clear()
        self.available_cities = self.state.get_available_cities()
        self.city_combo.AppendItems(self.available_cities)
        if self.available_cities:
            self.city_combo.SetSelection(0)

        can_hire = bool(available_people) and bool(self.available_cities)
        self.person_combo.Enable(can_hire)
        self.city_combo.Enable(can_hire)
        self.hire_btn.Enable(can_hire)

        if not available_people:
            self.detail_text.SetValue("Tutabileceğiniz kimse kalmadı.")
        elif not self.available_cities:
            self.detail_text.SetValue("Boş şehir kalmadı, her ile zaten bir adam gönderilmiş.")
        else:
            self.detail_text.SetValue(
                f"Tutma masrafı: {format_tl(hire_cost)} TL. Bu adam seçtiğiniz şehirde kendi "
                f"başına karaborsa işi çevirir, şirket kurmaz. 30 günde bir {format_tl(salary)} TL maaş öder."
            )

    def on_employee_select(self, event):
        idx = self.employee_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        employee_id = self.employee_list.GetClientData(idx)
        e = self.state.get_employee(employee_id)
        if e:
            speak(
                f"{e['name']} - {e['city']} - "
                f"Toplam ürettiği {format_tl(e.get('total_generated', 0.0))} TL"
            )

    def on_person_selected(self, event):
        idx = self.person_combo.GetSelection()
        if idx != wx.NOT_FOUND:
            speak(self.person_combo.GetString(idx))

    def on_city_selected(self, event):
        idx = self.city_combo.GetSelection()
        if idx != wx.NOT_FOUND:
            speak(self.city_combo.GetString(idx))

    def on_hire(self, event):
        p_idx = self.person_combo.GetSelection()
        c_idx = self.city_combo.GetSelection()

        if p_idx == wx.NOT_FOUND:
            speak("Bir adam seçin")
            return
        if c_idx == wx.NOT_FOUND:
            speak("Bir şehir seçin")
            return

        name = self.person_combo.GetString(p_idx)
        city = self.available_cities[c_idx]

        success, msg = self.state.hire_employee(name, city)
        speak(msg)
        if success:
            self._update_ui()
            if self.parent:
                self.parent.auto_save()

    def on_fire(self, event):
        idx = self.employee_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Kovmak istediğiniz adamı seçin")
            return

        employee_id = self.employee_list.GetClientData(idx)
        e = self.state.get_employee(employee_id)
        name = e["name"] if e else "Bu adam"

        if wx.MessageBox(f"{name} kovulsun mu?", "Onay", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            success, msg = self.state.fire_employee(employee_id)
            speak(msg)
            if success:
                self._update_ui()
                if self.parent:
                    self.parent.auto_save()


class InformantDialog(wx.Dialog):
    """Muhbir tutma / kovma yönetim penceresi. Muhbir tutulduğunda, gün
    sonunda belirli bir ihtimalle bir sonraki gün için yaklaşan bir polis
    operasyonunu ÖNCEDEN (bir gün önceden) haber verir; oyuncu ertesi gün
    mallarını hızlıca elden çıkarıp polis kontrolünü atlatabilir (bkz.
    main.py on_next_day)."""

    def __init__(self, parent, state):
        super().__init__(parent, title="Muhbir Yönetimi", size=(440, 320))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="MUHBİR YÖNETİMİ")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        info = wx.StaticText(
            panel,
            label=(
                "Bir muhbir tuttuğunuzda, doğrudan polisle bağlantılı "
                "olduğu için gerçekleşecek HER baskını bir gün "
                "öncesinden haber verir. Ertesi gün bu uyarıyla "
                "karşılaştığınızda mallarınızı hızlıca gerçek fiyatına "
                "elden çıkarıp o günkü polis baskınını tamamen "
                "atlatabilirsiniz. Uyarıyı görmezden gelirseniz o gün "
                "polis KESİN olarak gelir."
            ),
        )
        info.Wrap(380)
        sizer.Add(info, 0, wx.EXPAND | wx.ALL, 10)

        self.status_text = wx.StaticText(panel, label="")
        sizer.Add(self.status_text, 0, wx.ALL | wx.CENTER, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hire_btn = wx.Button(panel, label="Muhbir Tut")
        self.fire_btn = wx.Button(panel, label="Muhbiri Kov")
        btn_sizer.Add(self.hire_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.fire_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.hire_btn.Bind(wx.EVT_BUTTON, self.on_hire)
        self.fire_btn.Bind(wx.EVT_BUTTON, self.on_fire)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        hire_cost = INFORMANT_CONFIG["hire_cost"]
        daily_upkeep = INFORMANT_CONFIG["daily_upkeep"]

        if self.state.has_informant:
            self.status_text.SetLabel(
                f"Aktif bir muhbiriniz var.\n"
                f"Günlük ücret: {format_tl(daily_upkeep)} TL\n"
                f"Doğrudan polisle bağlantılı: gerçekleşecek her baskını\n"
                f"bir gün öncesinden haber verir."
            )
            self.hire_btn.Enable(False)
            self.fire_btn.Enable(True)
        else:
            self.status_text.SetLabel(
                f"Muhbiriniz yok.\n"
                f"Tutma masrafı: {format_tl(hire_cost)} TL\n"
                f"Günlük ücret: {format_tl(daily_upkeep)} TL\n"
                f"Doğrudan polisle bağlantılı: gerçekleşecek her baskını\n"
                f"bir gün öncesinden haber verir."
            )
            self.hire_btn.Enable(True)
            self.fire_btn.Enable(False)

    def on_hire(self, event):
        success, msg = self.state.hire_informant()
        speak(msg)
        if success:
            self._update_ui()

    def on_fire(self, event):
        if wx.MessageBox("Muhbiri kovmak istediğinize emin misiniz?", "Onay",
                          wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            success, msg = self.state.fire_informant()
            speak(msg)
            if success:
                self._update_ui()


class BankLoanDialog(wx.Dialog):
    """Şirket üzerinden çekilen banka (ticari) kredisi. Kredi hazır paketler
    halinde seçilir; taksitler her 30 günde bir otomatik olarak çekilir."""

    def __init__(self, parent, state):
        super().__init__(parent, title="Banka Kredisi", size=(540, 480))
        self.parent = parent
        self.state = state
        self.options = []
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="BANKA KREDİSİ (Şirket)")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((480, 130))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Kredi Paketleri:"), 0, wx.LEFT | wx.TOP, 10)
        self.option_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.option_list.SetMinSize((480, 100))
        sizer.Add(self.option_list, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.take_btn = wx.Button(panel, label="Kredi Çek")
        self.payoff_btn = wx.Button(panel, label="Erken Kapat")
        btn_sizer.Add(self.take_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.payoff_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.take_btn.Bind(wx.EVT_BUTTON, self.on_take_loan)
        self.payoff_btn.Bind(wx.EVT_BUTTON, self.on_payoff)
        self.option_list.Bind(wx.EVT_LISTBOX, self.on_option_select)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        tier = self.state.get_credit_tier()

        if self.state.loan_amount > 0:
            remaining_installments = self.state.loan_total_installments - self.state.loan_installments_paid
            self.status_text.SetValue(
                f"Aktif Kredi: {format_tl(self.state.loan_amount)} TL\n"
                f"Kalan Borç: {format_tl(self.state.loan_total_debt)} TL\n"
                f"Taksit: {format_tl(self.state.loan_installment_amount)} TL / 30 gün\n"
                f"Sonraki Taksite: {self.state.loan_days_until_installment} gün\n"
                f"Kalan Taksit Sayısı: {remaining_installments}\n"
                f"Faiz Oranı: %{self.state.loan_interest_rate*100:.1f}\n\n"
                f"Kredi Notu (ortalama): {self.state.get_average_credit_score()}\n\n"
                f"Not: Taksitler her 30 günde bir hesabınızdan otomatik çekilir."
            )
            self.options = []
            self.option_list.Clear()
            self.option_list.Enable(False)
            self.take_btn.Enable(False)
            self.payoff_btn.Enable(self.state.cash >= self.state.loan_total_debt)
        else:
            self.payoff_btn.Enable(False)
            self.options = self.state.get_loan_options()
            self.option_list.Clear()

            if not self.options:
                self.status_text.SetValue(
                    f"Kredi Notu (ortalama): {self.state.get_average_credit_score()}\n"
                    f"Durum: Kredi notu yetersiz veya şirket yok"
                )
                self.option_list.Enable(False)
            else:
                limit = self.state.get_loan_limit()
                self.status_text.SetValue(
                    f"Kredi Notu (ortalama): {self.state.get_average_credit_score()}\n"
                    f"Kredi Limiti: {format_tl(limit)} TL\n"
                    f"Faiz Oranı: %{tier['interest_rate']*100:.1f}\n\n"
                    f"Bir paket seçip 'Kredi Çek' butonuna basın.\n"
                    f"Taksitler her 30 günde bir otomatik çekilir."
                )
                for opt in self.options:
                    self.option_list.Append(
                        f"{opt['label']}: {opt['amount']:,.0f} TL | "
                        f"{opt['installments']} taksit x {opt['installment_amount']:,.0f} TL "
                        f"(30 günde bir) | Toplam borç: {opt['total_debt']:,.0f} TL"
                    )
                self.option_list.Enable(True)
            self.take_btn.Enable(bool(self.options))

    def on_option_select(self, event):
        idx = self.option_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.options):
            opt = self.options[idx]
            speak(f"{opt['label']} seçildi. {opt['amount']:,.0f} TL, {opt['installments']} taksit")

    def on_take_loan(self, event):
        idx = self.option_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.options):
            speak("Lütfen bir kredi paketi seçin")
            return

        opt = self.options[idx]
        success, msg = self.state.take_loan(opt["amount"], opt["installments"])
        speak(msg)
        if success:
            self._update_ui()

    def on_payoff(self, event):
        if wx.MessageBox("Krediyi erken kapatmak istediğinize emin misiniz?", "Onay",
                          wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        success, msg = self.state.pay_loan_full()
        speak(msg)
        if success:
            self._update_ui()


class LandLoanDialog(wx.Dialog):
    """Belirli bir arsa üzerinden çekilen teminatlı kredi. Kredi hazır paketler
    halinde seçilir; taksitler her 30 günde bir otomatik olarak çekilir."""

    def __init__(self, parent, state, land_index):
        super().__init__(parent, title="Arsa Kredisi", size=(540, 480))
        self.parent = parent
        self.state = state
        self.land_index = land_index
        self.options = []
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        land = self.state.lands[self.land_index]
        title = wx.StaticText(panel, label=f"ARSA KREDİSİ - {land['type']}")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((480, 130))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label="Kredi Paketleri:"), 0, wx.LEFT | wx.TOP, 10)
        self.option_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.option_list.SetMinSize((480, 100))
        sizer.Add(self.option_list, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.take_btn = wx.Button(panel, label="Kredi Çek")
        self.payoff_btn = wx.Button(panel, label="Erken Kapat")
        btn_sizer.Add(self.take_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.payoff_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.take_btn.Bind(wx.EVT_BUTTON, self.on_take_loan)
        self.payoff_btn.Bind(wx.EVT_BUTTON, self.on_payoff)
        self.option_list.Bind(wx.EVT_LISTBOX, self.on_option_select)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        land = self.state.lands[self.land_index]

        if land.get("has_loan", False):
            debt = land.get("loan_debt", 0.0)
            total_installments = land.get("loan_total_installments", 1)
            paid_installments = land.get("loan_installments_paid", 0)
            self.status_text.SetValue(
                f"Aktif Kredi: {format_tl(land.get('loan_amount', 0.0))} TL\n"
                f"Kalan Borç: {format_tl(debt)} TL\n"
                f"Taksit: {format_tl(land.get('loan_installment_amount', 0.0))} TL / 30 gün\n"
                f"Sonraki Taksite: {land.get('loan_days_until_installment', 30)} gün\n"
                f"Kalan Taksit Sayısı: {total_installments - paid_installments}\n"
                f"Faiz Oranı: %{land.get('loan_interest_rate', 0.15)*100:.1f}\n\n"
                f"Not: Taksitler her 30 günde bir hesabınızdan otomatik çekilir.\n"
                f"Taksit ödenemezse arsa bankaya devredilir (haciz)."
            )
            self.options = []
            self.option_list.Clear()
            self.option_list.Enable(False)
            self.take_btn.Enable(False)
            self.payoff_btn.Enable(self.state.cash >= debt)
        else:
            self.payoff_btn.Enable(False)
            self.options = self.state.get_land_loan_options(self.land_index)
            self.option_list.Clear()

            if not self.options:
                self.status_text.SetValue("Bu arsa için kredi limiti yok")
                self.option_list.Enable(False)
            else:
                limit = self.state.get_land_loan_limit(self.land_index)
                self.status_text.SetValue(
                    f"Arsa teminatlı kredi limiti: {format_tl(limit)} TL\n"
                    f"Faiz Oranı: %15.0\n\n"
                    f"Bir paket seçip 'Kredi Çek' butonuna basın.\n"
                    f"Taksitler her 30 günde bir otomatik çekilir."
                )
                for opt in self.options:
                    self.option_list.Append(
                        f"{opt['label']}: {opt['amount']:,.0f} TL | "
                        f"{opt['installments']} taksit x {opt['installment_amount']:,.0f} TL "
                        f"(30 günde bir) | Toplam borç: {opt['total_debt']:,.0f} TL"
                    )
                self.option_list.Enable(True)
            self.take_btn.Enable(bool(self.options))

    def on_option_select(self, event):
        idx = self.option_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.options):
            opt = self.options[idx]
            speak(f"{opt['label']} seçildi. {opt['amount']:,.0f} TL, {opt['installments']} taksit")

    def on_take_loan(self, event):
        idx = self.option_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.options):
            speak("Lütfen bir kredi paketi seçin")
            return

        opt = self.options[idx]
        success, msg = self.state.take_land_loan(self.land_index, opt["amount"], opt["installments"])
        speak(msg)
        if success:
            self._update_ui()

    def on_payoff(self, event):
        if wx.MessageBox("Arsa kredisini erken kapatmak istediğinize emin misiniz?", "Onay",
                          wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        success, msg = self.state.pay_land_loan_full(self.land_index)
        speak(msg)
        if success:
            self._update_ui()


class BankingDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title="Bankacılık", size=(400, 250))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="BANKACILIK")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.StaticText(panel, label="")
        sizer.Add(self.status_text, 0, wx.ALL | wx.CENTER, 10)

        self.interest_text = wx.StaticText(
            panel,
            label="Faiz yok: kazandığınız her şey doğrudan nakde geçer.\n"
                  "Faiz sadece aldığınız kredi borcuna uygulanır."
        )
        sizer.Add(self.interest_text, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        self.status_text.SetLabel(
            f"Nakit: {format_tl(self.state.cash)} TL"
        )


class GamblingDialog(wx.Dialog):
    """
    RULET (KUMAR) EKRANI
    Kullanıcı bir veya daha fazla bahsi listeye ekler, ardından
    "Bahisleri Bitir / Çarkı Çevir" ile hepsi birden oynanır:
    çark.mp3 çalmaya başlar, ses BİTENE KADAR beklenir, ardından sonuç
    (kazanan sayı/renk ve her bahsin durumu) ekran okuyucuya bildirilir.
    """

    BET_CHOICES = [
        ("kirmizi", "Kırmızı (2x)"),
        ("siyah", "Siyah (2x)"),
        ("cift", "Çift (2x)"),
        ("tek", "Tek (2x)"),
        ("1-18", "1-18 (2x)"),
        ("19-36", "19-36 (2x)"),
        ("1.duzine", "1. Düzine 1-12 (3x)"),
        ("2.duzine", "2. Düzine 13-24 (3x)"),
        ("3.duzine", "3. Düzine 25-36 (3x)"),
        ("sayi", "Tek Sayı 0-36 (36x)"),
    ]

    # NOT: dosya adı ASCII tutuldu (diğer ses dosyalarıyla aynı kural:
    # para.mp3, buy.ogg, button.wav...). "sounds/cark.mp3" dosyasını
    # kendiniz eklemelisiniz (rulet çarkı dönüş sesi).
    SOUND_CARK = resource_path("sounds/cark.mp3")

    def __init__(self, parent, state):
        super().__init__(parent, title="Rulet - Kumar Oyna", size=(480, 560))
        self.parent = parent
        self.state = state
        self.pending_bets = []
        self.spin_timer = None
        self.is_spinning = False

        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="RULET")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.cash_text = wx.StaticText(panel, label="")
        sizer.Add(self.cash_text, 0, wx.ALL | wx.CENTER, 5)

        bet_labels = [label for _, label in self.BET_CHOICES]
        self.bet_type_radio = wx.RadioBox(panel, label="Bahis Türü", choices=bet_labels,
                                           majorDimension=1, style=wx.RA_SPECIFY_COLS)
        sizer.Add(self.bet_type_radio, 0, wx.EXPAND | wx.ALL, 10)

        number_sizer = wx.BoxSizer(wx.HORIZONTAL)
        number_sizer.Add(wx.StaticText(panel, label="Sayı (yalnızca 'Tek Sayı' için, 0-36):"),
                          0, wx.ALL | wx.CENTER, 5)
        self.number_spinner = wx.SpinCtrl(panel, value="0", min=0, max=36)
        self.number_spinner.Disable()
        number_sizer.Add(self.number_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(number_sizer, 0, wx.EXPAND | wx.ALL, 5)

        amount_sizer = wx.BoxSizer(wx.HORIZONTAL)
        amount_sizer.Add(wx.StaticText(panel, label="Bahis Tutarı (TL):"), 0, wx.ALL | wx.CENTER, 5)
        self.amount_spinner = wx.SpinCtrl(panel, value="100", min=1, max=100000000)
        amount_sizer.Add(self.amount_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(amount_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.add_bet_btn = wx.Button(panel, label="Bahis Ekle")
        sizer.Add(self.add_bet_btn, 0, wx.ALL | wx.CENTER, 5)

        sizer.Add(wx.StaticText(panel, label="Eklenen Bahisler:"), 0, wx.LEFT | wx.TOP, 10)
        self.bets_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.bets_list.SetMinSize((420, 90))
        sizer.Add(self.bets_list, 0, wx.EXPAND | wx.ALL, 10)

        self.remove_bet_btn = wx.Button(panel, label="Seçili Bahsi Sil")
        sizer.Add(self.remove_bet_btn, 0, wx.ALL | wx.CENTER, 5)

        self.status_text = wx.StaticText(panel, label="Bahislerinizi ekleyip çarkı çevirin.")
        self.status_text.Wrap(440)
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.spin_btn = wx.Button(panel, label="Bahisleri Bitir / Çarkı Çevir")
        self.close_btn = wx.Button(panel, label="Kapat")
        btn_sizer.Add(self.spin_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.bet_type_radio.Bind(wx.EVT_RADIOBOX, self.on_bet_type_changed)
        self.add_bet_btn.Bind(wx.EVT_BUTTON, self.on_add_bet)
        self.remove_bet_btn.Bind(wx.EVT_BUTTON, self.on_remove_bet)
        self.spin_btn.Bind(wx.EVT_BUTTON, self.on_spin)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_dialog)
        self.Bind(wx.EVT_CLOSE, self.on_close_dialog)

    def _update_ui(self):
        self.cash_text.SetLabel(f"Nakit: {format_tl(self.state.cash)} TL")

    def on_bet_type_changed(self, event):
        idx = self.bet_type_radio.GetSelection()
        bet_type = self.BET_CHOICES[idx][0]
        self.number_spinner.Enable(bet_type == "sayi")

    def _total_pending(self) -> float:
        return sum(b["amount"] for b in self.pending_bets)

    def on_add_bet(self, event):
        idx = self.bet_type_radio.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Bahis türü seçin")
            return
        bet_type, label = self.BET_CHOICES[idx]
        amount = float(self.amount_spinner.GetValue())
        if amount <= 0:
            speak("Geçerli bir tutar girin")
            return

        if self._total_pending() + amount > self.state.cash:
            speak("Yetersiz bakiye, bu bahsi ekleyemezsiniz")
            return

        number = None
        display = label
        if bet_type == "sayi":
            number = self.number_spinner.GetValue()
            display = f"Tek Sayı: {number} (36x)"

        self.pending_bets.append({"type": bet_type, "number": number, "amount": amount})
        self.bets_list.Append(f"{display} - {format_tl(amount)} TL")
        speak(f"{display} için {format_tl(amount)} TL bahis eklendi")

    def on_remove_bet(self, event):
        idx = self.bets_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Silmek istediğiniz bahsi seçin")
            return
        self.pending_bets.pop(idx)
        self.bets_list.Delete(idx)
        speak("Bahis silindi")

    def on_spin(self, event):
        if self.is_spinning:
            return
        if not self.pending_bets:
            speak("Önce en az bir bahis ekleyin")
            return

        total_bet = self._total_pending()
        if self.state.cash < total_bet:
            speak("Yetersiz bakiye")
            return

        self.is_spinning = True
        self._set_controls_enabled(False)
        self.status_text.SetLabel("Çark dönüyor, lütfen bekleyin...")
        speak("Çark dönüyor, lütfen bekleyin")

        if self.parent:
            self.parent.play_sound(self.SOUND_CARK)

        duration = _get_spin_sound_duration(self.SOUND_CARK)
        self.spin_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_spin_finished, self.spin_timer)
        self.spin_timer.StartOnce(int(duration * 1000))

    def on_spin_finished(self, event):
        if self.spin_timer:
            self.spin_timer.Stop()
            self.spin_timer = None

        result = self.state.play_roulette(self.pending_bets)
        self.is_spinning = False

        if not result.get("success"):
            speak(result.get("message", "Kumar işlemi başarısız"))
            self.status_text.SetLabel("Bahisler işlenemedi, tekrar deneyin.")
            self._set_controls_enabled(True)
            return

        winning_number = result["winning_number"]
        winning_color = result["winning_color"]
        net = result["net"]

        lines = [f"Çark {winning_number} ({winning_color}) geldi."]
        for br in result["bet_results"]:
            label = ROULETTE_BET_LABELS.get(br["type"], br["type"])
            if br["type"] == "sayi":
                label = f"{label} {br['number']}"
            if br["won"]:
                lines.append(f"{label} bahsi KAZANDI: {format_tl(br['payout'])} TL")
            else:
                lines.append(f"{label} bahsi kaybetti: {format_tl(br['amount'])} TL")

        if net >= 0:
            lines.append(f"Toplam net kazanç: {format_tl(net)} TL")
        else:
            lines.append(f"Toplam net kayıp: {format_tl(abs(net))} TL")

        summary = " ".join(lines)
        self.status_text.SetLabel(summary)
        speak(summary)

        self._update_ui()
        if self.parent:
            self.parent.update_wallet_display()
            self.parent.auto_save()

        self.pending_bets = []
        self.bets_list.Clear()

        self.spin_btn.SetLabel("Bahisleri Bitir / Çarkı Çevir")
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool):
        self.bet_type_radio.Enable(enabled)
        is_sayi = self.BET_CHOICES[self.bet_type_radio.GetSelection()][0] == "sayi"
        self.number_spinner.Enable(enabled and is_sayi)
        self.amount_spinner.Enable(enabled)
        self.add_bet_btn.Enable(enabled)
        self.remove_bet_btn.Enable(enabled)
        self.spin_btn.Enable(enabled)

    def on_close_dialog(self, event):
        if self.is_spinning:
            speak("Çark dönerken kapatamazsınız")
            if hasattr(event, "Veto"):
                event.Veto()
            return
        self.EndModal(wx.ID_OK)


class JailDialog(wx.Dialog):
    def __init__(self, parent, state, on_complete=None):
        super().__init__(parent, title="Hapis", size=(400, 300),
                        style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP)
        self.parent = parent
        self.state = state
        self.on_complete = on_complete
        self.timer = None
        self.remaining_seconds = 0
        self.total_seconds = 0
        self.total_days = 0
        self.days_processed = 0
        self.jail_events = []
        self.is_running = False
        self.last_speak_time = 0

        self.sound_prison = resource_path("sounds/prison.mp3")
        if not os.path.exists(self.sound_prison):
            self.sound_prison = resource_path("sounds/game_music.mp3")

        self._build_ui()
        self._bind_events()
        self.CenterOnScreen()

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="TUTUKLANDINIZ")
        title.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(wx.RED)
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        info = wx.StaticText(panel, label="Hapiste geçen her gün işleriniz durur")
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 5)

        self.day_label = wx.StaticText(panel, label="Kalan Gün: 0")
        self.day_label.SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(self.day_label, 0, wx.ALL | wx.CENTER, 10)

        self.time_label = wx.StaticText(panel, label="Kalan Süre: 0 saniye")
        sizer.Add(self.time_label, 0, wx.ALL | wx.CENTER, 5)

        self.exit_btn = wx.Button(panel, label="Hapis devam ediyor...")
        self.exit_btn.Disable()
        sizer.Add(self.exit_btn, 0, wx.ALL | wx.CENTER, 15)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.exit_btn.Bind(wx.EVT_BUTTON, self.on_exit)
        self.Bind(wx.EVT_CLOSE, self.on_exit)

    def start(self):
        if self.is_running:
            return

        days = self.state.jail_days
        if days <= 0:
            self.state.in_jail = False
            if self.on_complete:
                self.on_complete()
            self.Destroy()
            return

        if self.timer and self.timer.IsRunning():
            self.timer.Stop()

        self.is_running = True
        self.total_days = days
        self.total_seconds = days * 15
        self.remaining_seconds = self.total_seconds
        self.days_processed = 0
        self.jail_events = []
        self.last_speak_time = 0

        if self.parent:
            self.parent.audio.stop_music()
            self.parent.audio.play_music(self.sound_prison, loop=True)

        self.day_label.SetLabel(f"Kalan Gün: {days}")
        self.time_label.SetLabel(f"Kalan Süre: {self.total_seconds} saniye")
        self.exit_btn.SetLabel("Hapis devam ediyor...")
        self.exit_btn.Disable()

        speak(f"{days} gün hapis cezası")

        self.timer.Start(1000)
        self.Show()
        self.Raise()

    def on_timer(self, event):
        if not self.is_running:
            return
        if not self.timer or not self.timer.IsRunning():
            return
        wx.CallAfter(self._update_ui)

    def _update_ui(self):
        if not self.is_running:
            return

        self.remaining_seconds -= 1

        elapsed = self.total_seconds - self.remaining_seconds
        days_passed = min(self.total_days, int(elapsed / 15))
        remaining_days = max(0, self.total_days - days_passed)

        self.state.jail_days = remaining_days

        while self.days_processed < days_passed:
            self.days_processed += 1
            self.state.day += 1
            self.jail_events.extend(self.state.process_jail_day())

        self.day_label.SetLabel(f"Kalan Gün: {remaining_days}")
        self.time_label.SetLabel(f"Kalan Süre: {self.remaining_seconds} saniye")
        self.SetTitle(f"Hapis - {remaining_days} gün kaldı")

        if self.parent:
            self.parent.SetStatusText(f"HAPİSTE - {remaining_days} gün kaldı")
            self.parent.update_wallet_display()

        current_time = time.time()
        if current_time - self.last_speak_time >= 10:
            self.last_speak_time = current_time
            speak(f"Hapiste {self.state.jail_days} gün kaldı")

        if self.remaining_seconds <= 0 or remaining_days <= 0:
            self.complete_jail()

    def complete_jail(self):
        if self.timer:
            self.timer.Stop()
            self.timer = None

        self.is_running = False

        if self.parent:
            self.parent.audio.stop_music()
            self.parent.audio.play_music(self.parent.get_current_music_track(), loop=True)

        while self.days_processed < self.total_days:
            self.days_processed += 1
            self.state.day += 1
            self.jail_events.extend(self.state.process_jail_day())

        days_served = self.total_days if self.total_days > 0 else 1
        self.state.in_jail = False
        self.state.jail_days = 0

        self.day_label.SetLabel("HAPİS BİTTİ")
        self.time_label.SetLabel("Serbestsiniz")
        self.SetTitle("Hapis bitti")
        self.exit_btn.SetLabel("Çıkış")
        self.exit_btn.Enable()

        speak(f"Hapis cezanız bitti. {days_served} gün yattınız")

        if self.jail_events:
            summary = " ".join(self.jail_events)
            speak(summary)

        if self.parent:
            self.parent.refresh_product_list()
            self.parent.update_wallet_display()
            self.parent.set_jail_mode(False)

        if self.on_complete:
            self.on_complete()

    def on_exit(self, event):
        if self.exit_btn.IsEnabled():
            if self.timer:
                self.timer.Stop()
                self.timer = None

            self.is_running = False
            self.state.in_jail = False
            self.state.jail_days = 0

            if self.parent:
                self.parent.audio.stop_music()
                self.parent.audio.play_music(self.parent.get_current_music_track(), loop=True)
                self.parent.refresh_product_list()
                self.parent.update_wallet_display()
                self.parent.set_jail_mode(False)

            self.Destroy()
            if self.on_complete:
                self.on_complete()


# ============================================================
# ANA OYUN PENCERESI
# ============================================================