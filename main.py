
import os
import random
import sys
import time
import wx
import threading
import webbrowser

import updater
import daily_message
import app_log
from game_data import PRODUCT_CATEGORIES, get_flat_product_order
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl
from audio_manager import AudioManager
from save_manager import save_game, load_game, apply_one_time_heat_reset, import_cloud_save, build_save_data

import auth_manager
import ticket_manager
import settings_manager
from game_state import GameState, resource_path, get_music_tracks, open_help, ID_LOAD, ID_NEW
from dialogs import (
    LandManagementDialog, MainMenu, LoadGameDialog, CompanyDialog,
    InformantDialog, BankLoanDialog, LandLoanDialog, BankingDialog, JailDialog,
    HistoryDialog, EmployeeManagementDialog, GamblingDialog, DailyMessageDialog,
    TermsDialog, TERMS_VERSION,
    ProductActionDialog, AuthDialog, TicketsDialog
)

import leaderboard
from leaderboard import send_score


def speak(text: str):
    """Ekran okuyucuya seslendirir VE aynı mesajı geçmiş kaydına ekler.
    Böylece hızlı gün atlarken kaçırdığınız anonsları F3 ile açılan
    'Geçmiş' ekranından tekrar okuyabilirsiniz."""
    _tts_speak(text)
    log_history(text)


def _ask_update_confirmation(remote_version: str) -> bool:
    try:
        dlg = wx.MessageDialog(
            None,
            f"Yeni sürüm bulundu ({remote_version}). İndirilsin mi?",
            "Güncelleme",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        result = dlg.ShowModal()
        dlg.Destroy()
        return result == wx.ID_YES
    except Exception:
        return False


class MainFrame(wx.Frame):
    SOUND_MUSIC = resource_path("sounds/game_music.mp3")
    SOUND_PRISON = resource_path("sounds/prison.mp3")
    SOUND_BUY = resource_path("sounds/para.mp3")
    SOUND_SELL = resource_path("sounds/buy.ogg")
    SOUND_BUTTON = resource_path("sounds/DROPDOWNBUTTONGRID.mp3")
    SOUND_NAVIGATE = resource_path("sounds/button.wav")
    SOUND_TRANSITION = resource_path("sounds/transition.mp3")
    SOUND_POLICE = resource_path("sounds/polis_siren.mp3")
    SOUND_JAIL_DOOR = resource_path("sounds/Prison Door Opening Sound.mp3")
    SOUND_CARK = resource_path("sounds/cark.mp3")
    SOUND_MANI = resource_path("sounds/mani.mp3")
    SOUND_TYPING = resource_path("sounds/typing.wav")
    SOUND_TICKET_REPLY = resource_path("sounds/yanit.mp3")

    def __init__(self, username=None, load_data=None):
        super().__init__(None, title=f"Karaborsa - {username}", size=(800, 650))
        self.username = username
        self.state = GameState(load_data)
        self.audio = AudioManager()
        self.flat_products = get_flat_product_order()
        self.jail_dialog = None
        self.autosave_timer = None
        self._last_volume_speak_time = 0
        self._last_spoken_index = -1
        self._advancing_day = False
        self._last_day_advance_time = 0.0
        
        self.days_since_last_score_update = 0
        self.score_update_interval = 3
        self._score_submission_in_progress = False

        self.music_tracks = get_music_tracks()
        self.current_track_index = 0
        if self.music_tracks and self.SOUND_MUSIC in self.music_tracks:
            self.current_track_index = self.music_tracks.index(self.SOUND_MUSIC)

        self._build_ui()
        self._bind_events()

        self.audio.play_music(self.get_current_music_track(), loop=True)
        self.refresh_product_list()

        self.autosave_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_autosave, self.autosave_timer)
        self.autosave_timer.Start(30000)

        if self.state.in_jail:
            speak(f"Hoş geldiniz {username}. Hapistesiniz. {self.state.jail_days} gün kaldı")
            self.set_jail_mode(True)
            wx.CallAfter(self.start_jail_dialog)
        else:
            speak(f"Hoş geldiniz {username}")

        if settings_manager.is_daily_message_enabled():
            daily_message.check_for_new_message(self._on_daily_message_ready)

        if self.username:
            ticket_manager.check_for_new_replies_async(
                self.username, self._on_ticket_replies_ready
            )

    def _on_daily_message_ready(self, date_str: str, message_text: str):
        """daily_message arka plan thread'inden çağrılır; UI güncellemesi
        ana thread'de yapılmalı, bu yüzden wx.CallAfter kullanıyoruz."""
        wx.CallAfter(self._show_daily_message, date_str, message_text)

    def _show_daily_message(self, date_str: str, message_text: str):
        if self.state.in_jail:
            wx.CallLater(2000, self._show_daily_message, date_str, message_text)
            return

        speak(f"Günün mesajı ({date_str}): {message_text}")
        dlg = DailyMessageDialog(self, date_str, message_text)
        dlg.ShowModal()
        dlg.Destroy()
        daily_message.mark_seen(date_str)

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.wallet_display = wx.TextCtrl(panel, value=self.state.wallet_text(),
                                          style=wx.TE_READONLY | wx.TE_LEFT)
        self.wallet_display.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(self.wallet_display, 0, wx.EXPAND | wx.ALL, 10)

        label = wx.StaticText(panel, label="Ürünler:")
        sizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

        self.product_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        sizer.Add(self.product_list, 1, wx.EXPAND | wx.ALL, 10)

        qty_sizer = wx.BoxSizer(wx.HORIZONTAL)
        qty_sizer.Add(wx.StaticText(panel, label="Adet:"), 0, wx.ALL | wx.CENTER, 5)
        self.qty_spinner = wx.SpinCtrl(panel, value="1", min=1, max=1000000)
        self.bind_typing_sound(self.qty_spinner)
        qty_sizer.Add(self.qty_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(qty_sizer, 0, wx.LEFT | wx.TOP, 5)

        btn_sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.buy_btn = wx.Button(panel, label="Satın Al")
        self.sell_btn = wx.Button(panel, label="Sat")
        self.next_btn = wx.Button(panel, label="Gün Atla")
        btn_sizer1.Add(self.buy_btn, 0, wx.ALL, 3)
        btn_sizer1.Add(self.sell_btn, 0, wx.ALL, 3)
        btn_sizer1.Add(self.next_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer1, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.company_btn = wx.Button(panel, label="Şirket Yönetimi")
        self.employees_btn = wx.Button(panel, label="Adamlarım")
        self.informant_btn = wx.Button(panel, label="Muhbir Yönetimi")
        self.loan_btn = wx.Button(panel, label="Kredi Çek")
        btn_sizer2.Add(self.company_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.employees_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.informant_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.loan_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer2, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        self.bank_btn = wx.Button(panel, label="Bankacılık")
        self.land_btn = wx.Button(panel, label="Arsa Yönetimi")
        self.status_btn = wx.Button(panel, label="Durum Raporu")
        self.gamble_btn = wx.Button(panel, label="Kumar Oyna")
        btn_sizer3.Add(self.bank_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.land_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.status_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.gamble_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer3, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer4 = wx.BoxSizer(wx.HORIZONTAL)
        self.support_btn = wx.Button(panel, label="Destek / Bilet")
        btn_sizer4.Add(self.support_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer4, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.CreateStatusBar()
        self.SetStatusText("F1: Yardım | F3: Geçmiş | F6: Arsa | F7: Adamlar | C: Nakit | D: Kategori | E: Envanter | PgUp/PgDn: Ses | Otomatik kayıt aktif")

        panel.SetSizer(sizer)
        self.product_list.SetFocus()

    def _bind_events(self):
        self.buy_btn.Bind(wx.EVT_BUTTON, self.on_buy)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell)
        self.next_btn.Bind(wx.EVT_BUTTON, self.request_next_day)
        self.company_btn.Bind(wx.EVT_BUTTON, self.on_company)
        self.informant_btn.Bind(wx.EVT_BUTTON, self.on_informant)
        self.loan_btn.Bind(wx.EVT_BUTTON, self.on_loan)
        self.bank_btn.Bind(wx.EVT_BUTTON, self.on_banking)
        self.land_btn.Bind(wx.EVT_BUTTON, self.on_land_management)
        self.status_btn.Bind(wx.EVT_BUTTON, self.on_status)
        self.employees_btn.Bind(wx.EVT_BUTTON, self.on_employees)
        self.gamble_btn.Bind(wx.EVT_BUTTON, self.on_gamble)
        self.support_btn.Bind(wx.EVT_BUTTON, self.on_support)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def set_jail_mode(self, in_jail: bool):
        for btn in [self.buy_btn, self.sell_btn, self.next_btn,
                    self.company_btn, self.informant_btn, self.loan_btn,
                    self.bank_btn, self.land_btn, self.status_btn,
                    self.employees_btn, self.gamble_btn]:
            btn.Enable(not in_jail)
        self.product_list.Enable(not in_jail)
        self.qty_spinner.Enable(not in_jail)
        if in_jail:
            self.SetStatusText(f"HAPİSTE - {self.state.jail_days} gün kaldı")
        else:
            self.SetStatusText("F1: Yardım | F3: Geçmiş | F6: Arsa | C: Nakit | D: Kategori | E: Envanter | PgUp/PgDn: Ses | Otomatik kayıt aktif")

    def refresh_product_list(self, keep_selection: bool = True):
        prev_name = self.get_selected_product() if keep_selection else None
        self.set_jail_mode(self.state.in_jail)

        rows = []
        for name in self.flat_products:
            price = self.state.prices[name]
            qty = self.state.inventory.get(name, 0)
            label = f"{name} - {format_tl(price)} TL ({qty} adet)"
            rows.append((price, label, name))

        rows.sort(key=lambda r: r[0])

        self.product_list.Clear()
        new_index = wx.NOT_FOUND
        for i, (price, label, name) in enumerate(rows):
            self.product_list.Append(label, name)
            if prev_name is not None and name == prev_name:
                new_index = i

        if new_index != wx.NOT_FOUND:
            self.product_list.SetSelection(new_index)
        elif rows:
            self.product_list.SetSelection(0)
        
        self._last_spoken_index = -1

    def get_selected_product(self):
        idx = self.product_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return None
        return self.product_list.GetClientData(idx)

    def get_product_category(self, product_name: str) -> str:
        for category, names in PRODUCT_CATEGORIES.items():
            if product_name in names:
                return category
        return "Bilinmeyen Kategori"

    def update_wallet_display(self):
        self.wallet_display.SetValue(self.state.wallet_text())

    def open_cheat_console(self):
        """
        GELİŞTİRİCİ HİLE KONSOLU - Ctrl+Alt+F ile açılır.

        SADECE geliştirme/test amaçlıdır: menüde görünmez, yardım
        dosyasında (help.html) belgelenmez, oyuncuya hiçbir şekilde
        duyurulmaz. Şu an desteklenen komutlar:

            /para      -> hesaba anında 20.000.000 TL ekler.
            /admin123  -> hesaba anında 5.000.000.000.000 TL ekler.
            /admin     -> oyunun GitHub deposunu tarayıcıda açar.
            /kayitlar  -> kayıt dosyalarının bulunduğu local appdata
                          klasörünü dosya gezgininde açar.

        Bilinmeyen bir komut girilirse ya da alan boş bırakılıp iptal
        edilirse hiçbir şey değişmez.
        """
        dlg = wx.TextEntryDialog(self, "Hile komutu girin:", "Geliştirici Konsolu")
        for child in dlg.GetChildren():
            if isinstance(child, wx.TextCtrl):
                self.bind_typing_sound(child)
                break
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            command = dlg.GetValue().strip().lower()
        finally:
            dlg.Destroy()

        if not command:
            return

        if command == "/para":
            bonus = 20_000_000.0
            self.state.cash += bonus
            if self.state.cash > self.state.highest_cash:
                self.state.highest_cash = self.state.cash
            self.update_wallet_display()
            speak(f"[Hile] Hesabınıza {format_tl(bonus)} TL eklendi.")
        elif command == "/admin123":
            bonus = 5_000_000_000_000.0
            self.state.cash += bonus
            if self.state.cash > self.state.highest_cash:
                self.state.highest_cash = self.state.cash
            self.update_wallet_display()
            speak(f"[Hile] Hesabınıza {format_tl(bonus)} TL eklendi.")
        elif command == "/admin":
            webbrowser.open("https://github.com/MUHAMMED4342/kara_borsa_oyun")
            speak("[Hile] GitHub deposu tarayıcıda açıldı.")
        elif command == "/kayitlar":
            save_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "Karaborsa", "KaraborsaSimulasyonu",
            )
            os.makedirs(save_dir, exist_ok=True)
            try:
                os.startfile(save_dir)
                speak("[Hile] Kayıt klasörü açıldı.")
            except OSError:
                speak("[Hile] Kayıt klasörü açılamadı.")
        else:
            speak("[Hile] Bilinmeyen komut.")

    def play_sound(self, sound_path):
        if os.path.exists(sound_path):
            self.audio.play_sound(sound_path)

    def bind_typing_sound(self, ctrl):
        """Verilen metin giriş kontrolüne (TextCtrl, SpinCtrl vb.) her
        karakter yazıldığında typing.wav çalacak şekilde bağlanır."""
        ctrl.Bind(wx.EVT_TEXT, self._on_typing_sound)

    def _on_typing_sound(self, event):
        if settings_manager.is_typing_sound_enabled():
            self.play_sound(self.SOUND_TYPING)
        event.Skip()

    def auto_save(self):
        if self.username and not self.state.in_jail:
            save_game(self.username, self.state)

    def on_autosave(self, event):
        self.auto_save()

    def show_product_action_popup(self):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        name = self.get_selected_product()
        if not name:
            speak("Ürün seçin")
            return

        price = self.state.prices[name]
        qty = self.qty_spinner.GetValue()

        self.play_sound(self.SOUND_BUTTON)
        dlg = ProductActionDialog(self, name, price, qty)
        result = dlg.ShowModal()
        action = dlg.result
        dlg.Destroy()

        if result == wx.ID_OK:
            if action == "buy":
                self.on_buy(None)
            elif action == "sell":
                self.on_sell(None)

        self.product_list.SetFocus()

    def on_buy(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return
        self.play_sound(self.SOUND_BUTTON)
        name = self.get_selected_product()
        if not name:
            speak("Ürün seçin")
            return
        qty = self.qty_spinner.GetValue()
        if qty <= 0:
            speak("Geçerli miktar girin")
            return
        success, total, msg = self.state.buy_bulk(name, qty)
        if success:
            self.audio.play_sound(self.SOUND_BUY)
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        speak(msg)

    def on_sell(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return
        self.play_sound(self.SOUND_BUTTON)
        name = self.get_selected_product()
        if not name:
            speak("Ürün seçin")
            return
        qty = self.qty_spinner.GetValue()
        if qty <= 0:
            speak("Geçerli miktar girin")
            return
        success, total, msg = self.state.sell_bulk(name, qty)
        if success:
            self.audio.play_sound(self.SOUND_SELL)
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        if not success:
            speak(msg)

    def on_company(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = CompanyDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        dlg.Destroy()

    def on_informant(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = InformantDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        dlg.Destroy()

    def on_loan(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)

        choices = ["Banka Kredisi (Şirket)", "Arsa Kredisi (Teminatlı)"]
        type_dlg = wx.SingleChoiceDialog(self, "Hangi krediyi çekmek istiyorsunuz?", "Kredi Çek", choices)
        if type_dlg.ShowModal() != wx.ID_OK:
            type_dlg.Destroy()
            return
        selection = type_dlg.GetSelection()
        type_dlg.Destroy()

        if selection == 0:
            if not self.state.has_company:
                speak("Banka kredisi için önce şirket kurmalısınız")
                return
            dlg = BankLoanDialog(self, self.state)
            if dlg.ShowModal() == wx.ID_OK:
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
            dlg.Destroy()
        else:
            if not self.state.lands:
                speak("Arsa kredisi için önce arsa satın almalısınız")
                return

            land_choices = []
            for i, land in enumerate(self.state.lands):
                status = " [Kredili]" if land.get("has_loan", False) else ""
                land_choices.append(f"{i+1}. {land['type']}{status}")

            land_dlg = wx.SingleChoiceDialog(self, "Hangi arsa için kredi işlemi yapmak istiyorsunuz?",
                                              "Arsa Seç", land_choices)
            if land_dlg.ShowModal() != wx.ID_OK:
                land_dlg.Destroy()
                return
            idx = land_dlg.GetSelection()
            land_dlg.Destroy()

            dlg = LandLoanDialog(self, self.state, idx)
            if dlg.ShowModal() == wx.ID_OK:
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
            dlg.Destroy()

    def on_banking(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = BankingDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.update_wallet_display()

    def on_land_management(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = LandManagementDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        dlg.Destroy()

    def on_employees(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = EmployeeManagementDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        dlg.Destroy()

    def on_gamble(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = GamblingDialog(self, self.state)
        dlg.ShowModal()
        self.update_wallet_display()
        self.auto_save()
        dlg.Destroy()

    def on_support(self, event):
        """Destek/Bilet ekranını açar. Hapisteyken de kullanılabilir
        tutuluyor (set_jail_mode kilit listesine dahil edilmedi) -
        oyuncu hapisteyken de bir sorun bildirebilmeli."""
        self.play_sound(self.SOUND_BUTTON)
        dlg = TicketsDialog(self, self.username, self.audio, self._ticket_extra_info())
        dlg.ShowModal()
        dlg.Destroy()

    def _ticket_extra_info(self) -> dict:
        """Yeni bilet açarken (ve destek ekibinin ilk bakışta göreceği
        gövdede) otomatik eklenecek oyun bilgileri."""
        return {
            "Oyun günü": self.state.day,
            "Nakit": f"{format_tl(self.state.cash)} TL",
            "Hapiste mi": "Evet" if self.state.in_jail else "Hayır",
        }

    def _on_ticket_replies_ready(self, results: list):
        """ticket_manager arka plan thread'inden çağrılır; UI
        güncellemesi ana thread'de yapılmalı."""
        wx.CallAfter(self._notify_ticket_replies, results)

    def _notify_ticket_replies(self, results: list):
        if not results:
            return
        if len(results) == 1:
            r = results[0]
            msg = f"Bilet #{r['number']} ({r['title']}) için yeni yanıt var."
        else:
            msg = f"{len(results)} biletinize yeni yanıt geldi."
        self.play_sound(self.SOUND_TICKET_REPLY)
        speak(msg + " Görmek için 'Destek / Bilet' butonunu kullanın.")

    def get_current_music_track(self) -> str:
        if self.music_tracks:
            return self.music_tracks[self.current_track_index]
        return self.SOUND_MUSIC

    def next_music_track(self):
        if not self.music_tracks or self.state.in_jail:
            return
        self.current_track_index = (self.current_track_index + 1) % len(self.music_tracks)
        self.audio.stop_music()
        self.audio.play_music(self.get_current_music_track(), loop=True)

    def prev_music_track(self):
        if not self.music_tracks or self.state.in_jail:
            return
        self.current_track_index = (self.current_track_index - 1) % len(self.music_tracks)
        self.audio.stop_music()
        self.audio.play_music(self.get_current_music_track(), loop=True)

    def on_status(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        lines = [
            "DURUM RAPORU",
            f"Gün: {self.state.day}",
            f"Nakit: {format_tl(self.state.cash)} TL",
            f"Polis Riski: %{self.state.police_heat:.1f}",
            f"Toplam Suçlu Gelir: {format_tl(self.state.total_crime)} TL",
            f"En Yüksek Nakit: {format_tl(self.state.highest_cash)} TL",
        ]

        if self.state.lands:
            lines.append("")
            lines.append("ARSA BİLGİLERİ")
            total_value = 0
            for i, land in enumerate(self.state.lands):
                land_type = land["type"]
                price = self.state.get_land_price(land_type)
                total_value += price
                purchase_price = land["purchase_price"]
                profit = price - purchase_price
                days_held = self.state.day - land["purchase_day"]
                lines.append(f"{i+1}. {land_type} - {price:,.0f} TL (Alış: {purchase_price:,.0f} TL, {days_held} gün)")
            lines.append(f"Toplam Arsa Değeri: {total_value:,.0f} TL")

        if self.state.has_company:
            lines.append("")
            lines.append("ŞİRKET BİLGİLERİ")
            for c in self.state.companies:
                lines.extend([
                    f"İsim: {c['name']}",
                    f"Şehir: {c['city'] or '-'}",
                    f"Tip: {c['type']}",
                    f"Kredi Notu: {c['credit_score']}",
                    f"Aktif Gün: {c['days_active']}",
                    f"Toplam Kâr: {format_tl(c['total_profit'])} TL",
                    f"Aylık Ciro: {format_tl(c['monthly_revenue'])} TL",
                    "",
                ])

            if self.state.loan_amount > 0:
                remaining_installments = self.state.loan_total_installments - self.state.loan_installments_paid
                lines.extend([
                    "",
                    "KREDİ BİLGİLERİ",
                    "-" * 30,
                    f"Kredi Miktarı: {format_tl(self.state.loan_amount)} TL",
                    f"Toplam Borç: {format_tl(self.state.loan_total_debt)} TL",
                    f"Taksit: {format_tl(self.state.loan_installment_amount)} TL / 30 gün",
                    f"Sonraki Taksite: {self.state.loan_days_until_installment} gün",
                    f"Kalan Taksit Sayısı: {remaining_installments}",
                    f"Faiz Oranı: %{self.state.loan_interest_rate*100:.1f}",
                ])
        else:
            lines.append("Şirket: Yok")

        loaned_lands = [land for land in self.state.lands if land.get("has_loan", False)]
        if loaned_lands:
            lines.append("")
            lines.append("ARSA KREDİLERİ")
            lines.append("-" * 30)
            for land in loaned_lands:
                lines.append(
                    f"{land['type']}: Borç {format_tl(land.get('loan_debt', 0.0))} TL | "
                    f"Taksit {format_tl(land.get('loan_installment_amount', 0.0))} TL | "
                    f"Sonraki taksite {land.get('loan_days_until_installment', 30)} gün"
                )

        if self.state.employees:
            lines.append("")
            lines.append("ADAMLARINIZ")
            lines.append("-" * 30)
            total_generated = 0.0
            for e in self.state.employees:
                total_generated += e.get("total_generated", 0.0)
                lines.append(
                    f"{e['name']} - {e['city']} - "
                    f"Toplam Ürettiği: {format_tl(e.get('total_generated', 0.0))} TL - "
                    f"Maaşa {e['days_until_salary']} gün kaldı"
                )
            lines.append(f"Toplam Üretim (Adamlar): {format_tl(total_generated)} TL")

        if self.state.deaths_caused > 0:
            lines.append(f"Ölümler: {self.state.deaths_caused}")

        text = "\n".join(lines)
        speak(text)

    def on_history(self, event):
        """F3: Şimdiye kadar söylenmiş tüm mesajları gösteren geçmiş ekranını açar."""
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        dlg = HistoryDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def start_jail_dialog(self):
        if self.jail_dialog is not None:
            return
        if not self.state.in_jail:
            return
        if self.state.jail_days <= 0:
            self.state.in_jail = False
            self.set_jail_mode(False)
            self.refresh_product_list()
            self.update_wallet_display()
            return

        self.audio.stop_music()
        self.audio.play_music(self.SOUND_PRISON, loop=True)

        self.set_jail_mode(True)
        self.update_wallet_display()
        self.jail_dialog = JailDialog(self, self.state, self.on_jail_complete)
        self.jail_dialog.start()

    def on_jail_complete(self):
        self.jail_dialog = None

        self.audio.stop_music()
        self.audio.play_music(self.get_current_music_track(), loop=True)

        self.set_jail_mode(False)
        self.refresh_product_list()
        self.update_wallet_display()
        speak("Hapis bitti. Serbestsiniz")
        self.auto_save()

    def update_score(self):
        """
        Skoru hesaplar ve GitHub Gist'e gönderir.
        Her 3 günde bir otomatik olarak çağrılır.
        """
        if not leaderboard.is_score_submission_enabled():
            return
        
        if not self.username:
            return
        
        if self.state.in_jail:
            return
        
        total_wealth = self.state.cash
        if total_wealth <= 0:
            return
        
        def send_score_async():
            self._score_submission_in_progress = True
            try:
                success, msg = send_score(
                    self.username, 
                    self.state.cash, 
                    self.state.day, 
                    0.0
                )
                if success:
                    total = self.state.cash
                    log_history(f"Skor tablosuna gönderildi: {format_tl(total)} TL")
                else:
                    log_history(f"Skor gönderilemedi: {msg}")
            except Exception as e:
                log_history(f"Skor gönderiminde beklenmeyen hata: {e}")
            finally:
                self._score_submission_in_progress = False
        
        thread = threading.Thread(target=send_score_async)
        thread.daemon = True
        thread.start()

    def request_next_day(self, event):
        """F5 tuşuna basılı tutulduğunda (tuş tekrarı) veya 'Gün Atla'
        düğmesine art arda tıklandığında art arda birçok günün bir anda
        işlenmesini engeller. Böylece tuşu basılı tutarak günleri hızlıca
        atlayıp para kasmak mümkün olmaz; en fazla belirli bir aralıkla
        (ve bir önceki gün işlemi bitmeden) yeni bir gün işlenir."""
        now = time.time()
        if self._advancing_day:
            return
        if now - self._last_day_advance_time < 0.6:
            return
        self._last_day_advance_time = now
        self.on_next_day(event)

    def on_next_day(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz. Bekleyin")
            return

        if self._advancing_day:
            return
        self._advancing_day = True

        try:
            self._advance_day()
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            log_history(f"[HATA] Gün ilerletilirken beklenmeyen bir sorun oluştu: {e}")
            speak(
                "Gün ilerletilirken beklenmeyen bir hata oluştu. Oyun "
                "kaydedildi, geçmiş ekranında (F3) hata kaydı var."
            )
        finally:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
            self._advancing_day = False

    def _advance_day(self):
        self.play_sound(self.SOUND_TRANSITION)

        narration = []

        self.state.day += 1
        log_history(f"Gün {self.state.day} başladı.")

        if self.state.has_company:
            monthly_company_msgs = self.state.advance_companies_day()
            narration.extend(monthly_company_msgs)

        self.state.fluctuate_prices()

        if self.state.has_company:
            closed_messages = self.state.pay_company_upkeep()
            for msg in closed_messages:
                narration.append(msg)
            profit_msg = self.state.process_company_daily()
            if profit_msg:
                log_history(profit_msg)

        narrated_gain = 0.0

        def _speak_narration(text_list):
            """narration listesini tek seferde okutur; narrated_gain
            (yalnızca banka faizi + muhbirden kaçış + rastgele olay
            kazançlarının toplamı) sıfırdan büyükse mani.mp3 çalar."""
            nonlocal narrated_gain
            if not text_list:
                narrated_gain = 0.0
                return
            if narrated_gain > 0:
                self.play_sound(self.SOUND_MANI)
            narrated_gain = 0.0
            speak(" ".join(text_list))

        was_warned = getattr(self.state, "informant_warning_active", False)

        if self.state.has_informant:
            if not self.state.pay_informant_upkeep():
                narration.append("Muhbiriniz ücretini alamadı ve sizi terk etti.")

        if self.state.loan_amount > 0:
            success, msg = self.state.process_loan_daily()
            if not success:
                _, default_msg = self.state.default_loan()
                narration.append(f"Kredi temerrüdü. {default_msg}")
                _speak_narration(narration)
                self.refresh_product_list()
                self.update_wallet_display()
                # auto_save() burada ÇAĞRILMIYOR: bu fonksiyonu çağıran
                # on_next_day()'in finally bloğu, buradan dönüldükten hemen
                # sonra zaten kaydı yapıyor. Burada da çağrılırsa her gün
                # ilerlemesinde kayıt iki kez (ve buluta iki kez) gönderilir.
                return
            elif msg:
                narration.append(msg)

        for land_msg in self.state.process_land_loans_daily():
            narration.append(land_msg)

        for employee_msg in self.state.process_employees_daily():
            narration.append(employee_msg)

        bank_interest = self.state.apply_bank_interest()
        if bank_interest > 0:
            narration.append(f"Banka faizi: {format_tl(bank_interest)} TL")
            narrated_gain += bank_interest

        informant_evaded = False
        if was_warned:
            self.state.informant_warning_active = False
            warn_msg = (
                "MUHBİRİNİZ DÜN BİR POLİS OPERASYONU İÇİN SİZİ UYARMIŞTI!\n\n"
                "Muhbirinize göre bugün polis gelebilir (ama muhbirler "
                "bazen yanılır). Elinizdeki malları hemen gerçek fiyatına "
                "elden çıkarıp riski azaltmak ister misiniz?"
            )
            if narration:
                _speak_narration(narration)
                narration = []
            dlg = wx.MessageDialog(self, warn_msg, "MUHBİR UYARISI",
                                  wx.YES_NO | wx.ICON_WARNING)
            dlg.SetYesNoLabels("Evet, malları elden çıkar", "Hayır, riske gir")
            if dlg.ShowModal() == wx.ID_YES:
                count, earned = self.state.dump_inventory_for_evasion()
                narration.append(
                    f"Mallarınızı hızlıca elden çıkardınız ({count} adet, "
                    f"{format_tl(earned)} TL kazandınız) ve polisi atlattınız!"
                )
                narrated_gain += earned
                informant_evaded = True
            dlg.Destroy()

        if informant_evaded:
            self.state.update_police_heat()
            police = {"caught": False}
        elif was_warned:
            self.state.update_police_heat()
            if self.state.roll_police_catch():
                police = {"caught": True}
            else:
                police = {"caught": False}
                narration.append(
                    "Neyse ki bu sefer muhbiriniz yanılmış: polis gelmedi."
                )
        elif self.state.has_informant:
            self.state.update_police_heat()
            police = {"caught": False}
        else:
            police = self.state.police_check()

        if police["caught"]:
            self.audio.play_sound(self.SOUND_POLICE)
            jail_msg = self.state.go_to_jail(random.randint(1, 3))
            narration.append(f"POLİS SİZİ YAKALADI VE TUTUKLADI! {jail_msg}")
            _speak_narration(narration)
            self.update_wallet_display()
            self.refresh_product_list()
            # auto_save() burada ÇAĞRILMIYOR (bkz. yukarıdaki not) - on_next_day()
            # finally bloğu kaydı zaten yapacak.
            self.audio.play_sound(self.SOUND_JAIL_DOOR)
            wx.CallAfter(self.start_jail_dialog)
            return

        if self.state.has_informant and self.state.check_informant_warning():
            self.state.informant_warning_active = True
            narration.append(
                "Muhbiriniz yarın polis gelebilir dedi. Mallarınızı "
                "elden çıkarmak isteyebilirsiniz."
            )

        cash_before_events = self.state.cash
        events = self.state.trigger_random_events()
        event_cash_delta = self.state.cash - cash_before_events
        if event_cash_delta > 0:
            narrated_gain += event_cash_delta

        self.refresh_product_list()
        self.update_wallet_display()

        if events:
            narration.extend(events)
        if narration:
            _speak_narration(narration)

        self.days_since_last_score_update += 1
        if self.days_since_last_score_update >= self.score_update_interval:
            self.days_since_last_score_update = 0
            self.update_score()

        # auto_save() burada ÇAĞRILMIYOR (bkz. yukarıdaki not) - on_next_day()
        # finally bloğu kaydı zaten yapacak.

    def check_game_over(self):
        """
        OYUN SONU KONTROLÜ - ARTIK KULLANILMIYOR!
        Oyun sınırsız (endless) modda çalışır.
        Skor her 3 günde bir otomatik güncellenir.
        """
        pass

    def on_key_down(self, event: wx.KeyEvent):
        key = event.GetKeyCode()

        if self.state.in_jail:
            event.Skip(False)
            return

        if key in (ord('F'), ord('f')) and event.ControlDown() and event.AltDown():
            self.open_cheat_console()
            return

        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if wx.Window.FindFocus() is self.product_list:
                self.show_product_action_popup()
                return

        if key == wx.WXK_F1:
            open_help()
            return
        if key == wx.WXK_F2:
            self.on_status(event)
            return
        if key == wx.WXK_F3:
            self.on_history(event)
            return
        if key == wx.WXK_F5:
            self.request_next_day(event)
            return
        if key == wx.WXK_F6:
            self.on_land_management(event)
            return
        if key == wx.WXK_F7:
            self.on_employees(event)
            return
        
        if key == ord('C') or key == ord('c'):
            speak(f"Nakit: {format_tl(self.state.cash)} TL")
            return
        if key == ord('D') or key == ord('d'):
            name = self.get_selected_product()
            if name:
                category = self.get_product_category(name)
                speak(f"{name} ürünü {category} kategorisinde")
            else:
                speak("Ürün seçin")
            return
        if key == ord('E') or key == ord('e'):
            speak(self.state.inventory_summary_text())
            return
        if key == ord('I') or key == ord('i'):
            speak(self.state.inventory_items_text())
            return
        
        if key == wx.WXK_PAGEUP:
            vol = self.audio.volume_up()
            current_time = time.time()
            if current_time - self._last_volume_speak_time > 0.5:
                speak(f"Ses {int(vol * 100)}%")
                self._last_volume_speak_time = current_time
            return
        if key == wx.WXK_PAGEDOWN:
            vol = self.audio.volume_down()
            current_time = time.time()
            if current_time - self._last_volume_speak_time > 0.5:
                speak(f"Ses {int(vol * 100)}%")
                self._last_volume_speak_time = current_time
            return

        if key == wx.WXK_HOME:
            self.prev_music_track()
            return
        if key == wx.WXK_END:
            self.next_music_track()
            return
        
        if key == wx.WXK_DOWN or key == wx.WXK_UP:
            self.play_sound(self.SOUND_NAVIGATE)
            event.Skip()
            return
        
        event.Skip()

    def on_close(self, event):
        if self._score_submission_in_progress:
            if wx.MessageBox(
                "Skor gönderimi yapılıyor. Çıkmak istediğinize emin misiniz?",
                "Skor Gönderimi Devam Ediyor",
                wx.YES_NO | wx.ICON_WARNING
            ) != wx.YES:
                if event.CanVeto():
                    event.Veto()
                return

        if self.jail_dialog:
            self.jail_dialog.Destroy()
            self.jail_dialog = None
        if self.autosave_timer:
            self.autosave_timer.Stop()

        if self.username and not self.state.in_jail:
            self.update_score()
            # Yerel kayıt her zaman anında yapılır (ağ gerekmez, veri
            # kaybı riski yok, ayarlardan kapatılamaz).
            save_game(self.username, self.state)

            if not settings_manager.is_cloud_backup_enabled():
                # Ayarlardan buluta yedekleme kapatılmışsa, kapanışta
                # ağ isteği hiç atılmaz - "lütfen bekleyin" penceresi
                # de gösterilmez, oyun anında kapanır.
                event.Skip()
                return

            if event.CanVeto():
                # Kapanmayı bir an için engelleyip buluta SON HALİ tek
                # seferlik göndermeyi deniyoruz; kullanıcı beklerken
                # bunu görsün diye küçük bir bilgi penceresi gösteriyoruz.
                event.Veto()
                self._exit_with_final_cloud_push()
                return
            else:
                # Sistem tarafında kapanma engellenemiyorsa (ör. Windows
                # kapanıyor), en azından arka planda göndermeyi dene ama
                # kapanmayı bekletme.
                try:
                    save_data = build_save_data(self.username, self.state)
                    auth_manager.push_active_save_async(save_data, force=True)
                except Exception as e:
                    print(f"[Bulut Kayıt] Kapanışta (zorunlu) gönderim denemesi hata verdi: {e}")

        event.Skip()

    def _exit_with_final_cloud_push(self):
        """Pencere kapatılırken buluta SON kez ve TEK SEFERLİK gönderim
        yapar. 'Lütfen bekleyin' yazan küçük bir pencere gösterir; bu
        gönderim 10 saniyeden uzun sürerse ya da hiç bitmezse (internet
        yok, sunucu yanıt vermiyor vb.) süre dolduğunda oyunu yine de
        kapatır - kullanıcı asla ekranda takılı kalmaz."""
        try:
            save_data = build_save_data(self.username, self.state)
        except Exception as e:
            print(f"[Bulut Kayıt] Kapanışta save_data oluşturulamadı: {e}")
            self.Destroy()
            return

        wait_dlg = wx.Dialog(
            self, title="Karaborsa",
            style=wx.CAPTION | wx.STAY_ON_TOP,
        )
        panel = wx.Panel(wait_dlg)
        msg = wx.StaticText(panel, label="Lütfen bekleyin, skorunuz gönderiliyor...")
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(msg, 0, wx.ALL, 20)
        panel.SetSizer(sizer)
        wait_dlg.Fit()
        wait_dlg.CenterOnScreen()
        wait_dlg.Show()
        speak("Lütfen bekleyin, skorunuz gönderiliyor")

        finished = threading.Event()

        def worker():
            try:
                sess = auth_manager.get_current_session()
                if sess.get("access_token") and sess.get("user_id"):
                    auth_manager.push_cloud_save(sess["access_token"], sess["user_id"], save_data)
            except Exception as e:
                print(f"[Bulut Kayıt] Kapanışta gönderim hatası: {e}")
            finally:
                finished.set()

        threading.Thread(target=worker, daemon=True).start()

        state = {"done": False}

        def finalize():
            if state["done"]:
                return
            state["done"] = True
            try:
                wait_dlg.Destroy()
            except Exception:
                pass
            self.Destroy()

        def poll():
            if state["done"]:
                return
            if finished.is_set():
                finalize()
            else:
                wx.CallLater(200, poll)

        # 10 saniyelik SERT sınır: gönderim bitmese bile burada kapanır.
        wx.CallLater(10000, finalize)
        wx.CallLater(200, poll)


class App(wx.App):
    def OnInit(self):
        if not self._ensure_terms_accepted():
            return False

        if not self._ensure_authenticated():
            return False

        dlg = MainMenu()
        result = dlg.ShowModal()
        username = dlg.username
        dlg.Destroy()

        if result == ID_NEW:
            if not username:
                speak("Kullanıcı adı gerekli")
                return False
            frame = MainFrame(username)
            frame.Show()
            return True
        elif result == ID_LOAD:
            if not username:
                speak("Kayıt seçilmedi")
                return False
            data = load_game(username)
            if data:
                frame = MainFrame(username, data)
                frame.Show()
                return True
            else:
                speak("Kayıt yüklenemedi")
                return False
        return False

    def _ensure_terms_accepted(self) -> bool:
        """Gizlilik politikası ve kullanım şartlarının bu CİHAZDA en az
        bir kez kabul edilmesini zorunlu kılar. Hesaptan tamamen
        bağımsızdır - giriş ekranından (_ensure_authenticated) bile
        ÖNCE çağrılır, böylece hangi hesapla oynanacağından bağımsız
        olarak sadece cihaz başına bir kez gösterilir. Daha önce
        (aynı TERMS_VERSION ile) kabul edilmişse hiçbir şey
        göstermeden True döner."""
        if settings_manager.is_terms_accepted(TERMS_VERSION):
            return True

        dlg = TermsDialog()
        result = dlg.ShowModal()
        dlg.Destroy()

        if result != wx.ID_OK:
            return False

        settings_manager.set_terms_accepted(TERMS_VERSION)
        return True

    def _ensure_authenticated(self) -> bool:
        """PocketBase üzerinden ZORUNLU giriş akışı. Kullanıcı geçerli bir
        kullanıcı adı/şifre hesabıyla giriş yapmadan/hesap oluşturmadan
        bu fonksiyon False döner ve uygulama hiçbir içeriğe (ana menü,
        oyun ekranı) geçmeden kapanır.

        Önceden kaydedilmiş bir oturum varsa (aynı hesapla daha önce
        giriş yapılmışsa) sessizce yenilenir; bu SADECE oturum hâlâ
        PocketBase tarafında geçerliyse çalışır - geçersizse (örn.
        token süresi dolmuşsa) giriş ekranı yine de zorunlu olarak
        gösterilir.

        Giriş başarılı olduktan sonra, bu hesaba ait PocketBase'deki
        bulut kaydı varsa bu cihaza indirilir; böylece oyuncunun
        ilerlemesi hiçbir zaman kaybolmaz."""
        session = auth_manager.try_restore_session()

        if not session:
            auth_dlg = AuthDialog()
            result = auth_dlg.ShowModal()
            session = auth_dlg.session
            auth_dlg.Destroy()

            if result != wx.ID_OK or not session:
                return False

            auth_manager.save_session(session)
        elif session.get("_offline"):
            speak("İnternete ulaşılamadı, çevrimdışı devam ediliyor. "
                  "İlerlemeniz bu bilgisayara kaydedilecek, internete "
                  "bağlanınca buluta senkronize edilecek.")

        auth_manager.set_current_session(session)

        sess = auth_manager.get_current_session()
        try:
            cloud_save = auth_manager.fetch_cloud_save(sess["access_token"], sess["user_id"])
            if cloud_save:
                import_cloud_save(cloud_save)
        except Exception as e:
            print(f"[Bilgi] Bulut kaydı kontrol edilemedi (internet yok olabilir): {e}")

        return True


if __name__ == "__main__":
    app_log.init_logging()

    if settings_manager.is_auto_update_check_enabled():
        updater.check_for_update_async(ask_user_callback=_ask_update_confirmation)

    apply_one_time_heat_reset()

    app = App()
    app.MainLoop()

    updater.apply_pending_update_if_ready()