# main.py - Karaborsa Ticaret Simülasyonu (Görme Engelli Dostu)
# Giriş noktası: MainFrame (ana pencere) ve App
# -*- coding: utf-8 -*-

import os
import random
import sys
import time
import wx
import threading

import updater
from game_data import PRODUCT_CATEGORIES, get_flat_product_order
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl
from audio_manager import AudioManager
from save_manager import save_game, load_game

from game_state import GameState, resource_path, get_music_tracks, open_help, ID_LOAD, ID_NEW
from dialogs import (
    LandManagementDialog, MainMenu, LoadGameDialog, CompanyDialog,
    InformantDialog, BankLoanDialog, LandLoanDialog, BankingDialog, JailDialog,
    HistoryDialog, EmployeeManagementDialog
)

# Skor tablosu için import
# ÖNEMLİ: skor_gonderimi_aktif'i "from leaderboard import skor_gonderimi_aktif"
# ile almıyoruz; bu şekilde alınan isim sadece bu modülün kendi kopyası olur
# ve leaderboard.py'deki gerçek değer değiştiğinde güncellenmez. Bunun yerine
# modülün kendisini import edip leaderboard.is_score_submission_enabled()
# üzerinden her seferinde güncel değeri okuyoruz.
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
        
        # SKOR GÜNCELLEME: Her 3 günde bir skor gönderimi için sayaç
        self.days_since_last_score_update = 0
        self.score_update_interval = 3  # Her 3 günde bir
        # Arka planda hâlâ devam eden bir skor gönderimi var mı?
        # Kapatma sırasında kullanıcıyı uyarmak için kullanılır.
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
        self.qty_spinner = wx.SpinCtrl(panel, value="1", min=1, max=100)
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
        btn_sizer3.Add(self.bank_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.land_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.status_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer3, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.CreateStatusBar()
        self.SetStatusText("F1: Yardım | F3: Geçmiş | F6: Arsa | F7: Adamlar | C: Nakit | D: Kategori | E: Envanter | PgUp/PgDn: Ses | Otomatik kayıt aktif")

        panel.SetSizer(sizer)
        self.product_list.SetFocus()

    def _bind_events(self):
        self.buy_btn.Bind(wx.EVT_BUTTON, self.on_buy)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell)
        self.next_btn.Bind(wx.EVT_BUTTON, self.on_next_day)
        self.company_btn.Bind(wx.EVT_BUTTON, self.on_company)
        self.informant_btn.Bind(wx.EVT_BUTTON, self.on_informant)
        self.loan_btn.Bind(wx.EVT_BUTTON, self.on_loan)
        self.bank_btn.Bind(wx.EVT_BUTTON, self.on_banking)
        self.land_btn.Bind(wx.EVT_BUTTON, self.on_land_management)
        self.status_btn.Bind(wx.EVT_BUTTON, self.on_status)
        self.employees_btn.Bind(wx.EVT_BUTTON, self.on_employees)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def set_jail_mode(self, in_jail: bool):
        for btn in [self.buy_btn, self.sell_btn, self.next_btn,
                    self.company_btn, self.informant_btn, self.loan_btn,
                    self.bank_btn, self.land_btn, self.status_btn,
                    self.employees_btn]:
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
        duyurulmaz. Şu an desteklenen tek komut:

            /para   -> hesaba anında 20.000.000 TL ekler.

        Bilinmeyen bir komut girilirse ya da alan boş bırakılıp iptal
        edilirse hiçbir şey değişmez.
        """
        dlg = wx.TextEntryDialog(self, "Hile komutu girin:", "Geliştirici Konsolu")
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
        else:
            speak("[Hile] Bilinmeyen komut.")

    def play_sound(self, sound_path):
        if os.path.exists(sound_path):
            self.audio.play_sound(sound_path)

    def auto_save(self):
        if self.username and not self.state.in_jail:
            save_game(self.username, self.state)

    def on_autosave(self, event):
        self.auto_save()

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
            f"Temiz Para: {format_tl(self.state.clean_money)} TL",
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
            lines.extend([
                "",
                "ŞİRKET BİLGİLERİ",
                f"İsim: {self.state.company_name}",
                f"Şehir: {self.state.company_city or '-'}",
                f"Tip: {self.state.company_type}",
                f"Kredi Notu: {self.state.company_credit_score}",
                f"Aktif Gün: {self.state.company_days_active}",
                f"Toplam Kâr: {format_tl(self.state.company_total_profit)} TL",
                f"Aylık Ciro: {format_tl(self.state.company_monthly_revenue)} TL",
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
        # Skor gönderimi kapalıysa işlem yapma
        if not leaderboard.is_score_submission_enabled():
            return
        
        # Kullanıcı adı yoksa işlem yapma
        if not self.username:
            return
        
        # Hapisteyken skor gönderme
        if self.state.in_jail:
            return
        
        # Toplam varlık sıfırsa skor gönderme
        total_wealth = self.state.cash + self.state.clean_money
        if total_wealth <= 0:
            return
        
        # Skor gönderimini arka planda yap (UI donmasın)
        def send_score_async():
            self._score_submission_in_progress = True
            try:
                success, msg = send_score(
                    self.username, 
                    self.state.cash, 
                    self.state.day, 
                    self.state.clean_money
                )
                # Sesle rahatsız etmemek için gönderim sonucu sadece
                # geçmişe (F3) yazılıyor, sesli anons yapılmıyor.
                if success:
                    total = self.state.cash + self.state.clean_money
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

    def on_next_day(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz. Bekleyin")
            return

        self.play_sound(self.SOUND_TRANSITION)

        # Ekran okuyucu, art arda hızlıca gelen speak() çağrılarında her
        # yenisini bir öncekinin sözünü keserek başlatıyordu; bu yüzden
        # gün başlangıcındaki tüm anonsları tek bir listede topluyoruz ve
        # en sonda TEK bir speak() çağrısıyla birleştirip okutuyoruz. Böylece
        # hiçbir mesaj bir sonraki mesaj tarafından yarıda kesilmiyor ve
        # geçmiş (F3) ekranına bakmaya gerek kalmadan hepsi duyuluyor.
        narration = []

        self.state.day += 1
        narration.append(f"Gün {self.state.day} başladı.")

        if self.state.has_company:
            self.state.company_days_active += 1
            if self.state.company_days_active % 30 == 0:
                self.state.company_monthly_revenue = 0.0

        self.state.fluctuate_prices()

        if self.state.has_company:
            if not self.state.pay_company_upkeep():
                narration.append("Şirketiniz kapandı. İşletme giderleri karşılanamadı.")
                speak(" ".join(narration))
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
                return
            profit_msg = self.state.process_company_daily()
            if profit_msg:
                narration.append(profit_msg)

        # DÜN verilmiş bir muhbir uyarısı varsa, bugünkü ücret ödemesi
        # başarısız olup muhbir kovulsa bile bu uyarı YOK SAYILMAMALI.
        # Bu yüzden bayrağı, muhbiri kovabilecek ödeme işleminden ÖNCE
        # okuyup saklıyoruz.
        was_warned = getattr(self.state, "informant_warning_active", False)

        if self.state.has_informant:
            if not self.state.pay_informant_upkeep():
                narration.append("Muhbiriniz ücretini alamadı ve sizi terk etti.")

        if self.state.loan_amount > 0:
            success, msg = self.state.process_loan_daily()
            if not success:
                self.state.default_loan()
                narration.append(f"Kredi temerrüdü. Şirket kapatıldı. {msg}")
                speak(" ".join(narration))
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
                return
            elif msg:
                narration.append(msg)

        for land_msg in self.state.process_land_loans_daily():
            narration.append(land_msg)

        for employee_msg in self.state.process_employees_daily():
            narration.append(employee_msg)

        bank_interest = self.state.apply_bank_interest()

        informant_evaded = False
        if was_warned:
            # Bu uyarı DÜN muhbir tarafından verildi (bkz. altta): bugün
            # için geçerli, yani muhbir sizi bir gün önceden uyarmış oldu.
            self.state.informant_warning_active = False
            warn_msg = (
                "MUHBİRİNİZ DÜN BİR POLİS OPERASYONU İÇİN SİZİ UYARMIŞTI!\n\n"
                "Muhbirinize göre bugün polis gelebilir (ama muhbirler "
                "bazen yanılır). Elinizdeki malları hemen gerçek fiyatına "
                "elden çıkarıp riski azaltmak ister misiniz?"
            )
            # O ana kadarki günlük anonsları, diyalog açılmadan hemen önce
            # tek seferde okutuyoruz ki oyuncu hiçbirini kaçırmasın; diyalog
            # kutusunun kendi metnini ekran okuyucu zaten ayrıca duyurur.
            if narration:
                speak(" ".join(narration))
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
                informant_evaded = True
            dlg.Destroy()

        if informant_evaded:
            self.state.update_police_heat()
            police = {"caught": False}
        elif was_warned:
            # Uyarıyı görmezden geldiniz. Muhbiriniz çoğunlukla haklı çıkar
            # (yüzde 80 ihtimalle polis gerçekten gelir), ama bazen yanılır
            # (yüzde 20 ihtimalle baskın hiç gerçekleşmez).
            self.state.update_police_heat()
            if random.random() < 0.8:
                police = {"caught": True}
            else:
                police = {"caught": False}
                narration.append(
                    "Neyse ki bu sefer muhbiriniz yanılmış: polis gelmedi."
                )
        elif self.state.has_informant:
            # Muhbiriniz doğrudan polisle bağlantılı: uyarı gelmediyse
            # (dünkü tahmin "güvenli" demekti, ya da muhbir daha yeni
            # tutuldu) bugün kesinlikle güvendesiniz - sürpriz baskın yok.
            self.state.update_police_heat()
            police = {"caught": False}
        else:
            # Muhbiriniz yok: normal, rastgele polis kontrolü işler.
            police = self.state.police_check()

        if police["caught"]:
            self.audio.play_sound(self.SOUND_POLICE)
            jail_msg = self.state.go_to_jail(random.randint(1, 3))
            narration.append(f"POLİS SİZİ YAKALADI VE TUTUKLADI! {jail_msg}")
            speak(" ".join(narration))
            self.update_wallet_display()
            self.refresh_product_list()
            self.auto_save()
            self.audio.play_sound(self.SOUND_JAIL_DOOR)
            wx.CallAfter(self.start_jail_dialog)
            return

        # Bugünü atlattıysanız, muhbir (varsa) doğrudan polisle bağlantılı
        # olduğu için YARIN gerçekleşecek her baskını önceden haber verir -
        # bu uyarı bir sonraki gün başında (yukarıdaki blok) işleme alınır.
        if self.state.has_informant and self.state.check_informant_warning():
            self.state.informant_warning_active = True
            narration.append(
                "Muhbiriniz yarın polis gelebilir dedi. Mallarınızı "
                "elden çıkarmak isteyebilirsiniz."
            )

        events = self.state.trigger_random_events()

        self.refresh_product_list()
        self.update_wallet_display()

        if bank_interest > 0:
            narration.append(f"Banka faizi: {format_tl(bank_interest)} TL")
        if events:
            narration.extend(events)
        if narration:
            speak(" ".join(narration))

        # SKOR GÜNCELLEME: Her 3 günde bir (buraya geldiğinde gün atlanmış oldu)
        self.days_since_last_score_update += 1
        if self.days_since_last_score_update >= self.score_update_interval:
            self.days_since_last_score_update = 0
            self.update_score()

        # OTOMATİK KAYIT: Her gün sonunda kaydet
        self.auto_save()

    def check_game_over(self):
        """
        OYUN SONU KONTROLÜ - ARTIK KULLANILMIYOR!
        Oyun sınırsız (endless) modda çalışır.
        Skor her 3 günde bir otomatik güncellenir.
        """
        pass  # Hiçbir şey yapma - oyun asla bitmez!

    def on_key_down(self, event: wx.KeyEvent):
        key = event.GetKeyCode()

        # --- GELİŞTİRİCİ HİLE KONSOLU (Ctrl+Alt+F) ---
        # SADECE geliştirme/test kolaylığı içindir; menüde veya
        # yardım dosyasında belgelenmez, oyunun normal akışının bir
        # parçası değildir.
        if key in (ord('F'), ord('f')) and event.ControlDown() and event.AltDown():
            self.open_cheat_console()
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
            self.on_next_day(event)
            return
        if key == wx.WXK_F6:
            self.on_land_management(event)
            return
        if key == wx.WXK_F7:
            self.on_employees(event)
            return
        
        if key == ord('C') or key == ord('c'):
            cash_text = f"Nakit: {format_tl(self.state.cash)} TL"
            if self.state.clean_money > 0:
                cash_text += f", Temiz para: {format_tl(self.state.clean_money)} TL"
            speak(cash_text)
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
        # Arka planda hâlâ devam eden bir skor gönderimi varsa
        # (ör. az önce otomatik tetiklenen 3 günlük gönderim henüz
        # bitmediyse), kapatmadan önce kullanıcıya sor.
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
        
        # Oyun kapanırken son skoru gönder
        if self.username and not self.state.in_jail:
            self.update_score()
            self.auto_save()
        
        event.Skip()


# ============================================================
# UYGULAMA
# ============================================================

class App(wx.App):
    def OnInit(self):
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


if __name__ == "__main__":
    updater.check_for_update_async(ask_user_callback=_ask_update_confirmation)

    app = App()
    app.MainLoop()

    updater.apply_pending_update_if_ready()