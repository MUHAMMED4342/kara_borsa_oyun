
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
from game_data import PRODUCT_CATEGORIES, get_flat_product_order, product_display_name, category_display_name, land_type_display_name, company_type_display_name
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl
from audio_manager import AudioManager
from save_manager import save_game, load_game, apply_one_time_heat_reset, import_cloud_save, build_save_data

import auth_manager
import ticket_manager
import settings_manager
from i18n import t, get_language
import i18n
from game_state import GameState, resource_path, get_music_tracks, open_help, ID_LOAD, ID_NEW
from dialogs import (
    LandManagementDialog, MainMenu, LoadGameDialog, CompanyDialog,
    InformantDialog, BankLoanDialog, LandLoanDialog, BankingDialog, JailDialog,
    HistoryDialog, EmployeeManagementDialog, GamblingDialog, DailyMessageDialog,
    TermsDialog, TERMS_VERSION,
    ProductActionDialog, AuthDialog, TicketsDialog,
    CountrySelectDialog, AuctionDialog,
    open_localized_help,
)

import leaderboard
from leaderboard import send_score


_last_spoken_text = None
_last_spoken_time = 0.0
_DUPLICATE_SPEAK_WINDOW = 2.0  # saniye


def speak(text: str):
    """Ekran okuyucuya seslendirir VE aynı mesajı geçmiş kaydına ekler.
    Böylece hızlı gün atlarken kaçırdığınız anonsları F3 ile açılan
    'Geçmiş' ekranından tekrar okuyabilirsiniz.

    Gün atlarken (özellikle uzun olay/kâr özetlerinde) aynı metnin arka
    arkaya iki kez okunduğu bildirilmişti. Kök neden hangi katmanda olursa
    olsun (ör. bir arayüz/erişilebilirlik bileşeninin aynı anonsu ikinci
    kez tetiklemesi), BURADA tek bir merkezi noktadan geçen HER anons
    aynı metni kısa bir süre (2 sn) içinde ikinci kez görürse sessizce
    yok sayılır. Böylece kullanıcı hiçbir zaman aynı cümleyi/özeti art
    arda iki kez duymaz; gerçekten farklı iki anons (metni farklı olan)
    her zaman normal şekilde okunur."""
    global _last_spoken_text, _last_spoken_time
    now = time.time()
    if text and text == _last_spoken_text and (now - _last_spoken_time) < _DUPLICATE_SPEAK_WINDOW:
        return
    _last_spoken_text = text
    _last_spoken_time = now
    _tts_speak(text)
    log_history(text)


def _ask_update_confirmation(remote_version: str) -> bool:
    try:
        dlg = wx.MessageDialog(
            None,
            t("update.found_prompt", version=remote_version),
            t("update.title"),
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

    def __init__(self, username=None, load_data=None, country=None):
        super().__init__(None, title=t("app.title_with_user", username=username), size=(800, 650))
        self.username = username
        self.state = GameState(load_data, country=country)
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
            speak(t("welcome.jail", username=username, days=self.state.jail_days))
            self.set_jail_mode(True)
            wx.CallAfter(self.start_jail_dialog)
        else:
            speak(t("welcome.normal", username=username))

        if settings_manager.is_daily_message_enabled():
            daily_message.check_for_new_message(self._on_daily_message_ready)

        if self.username:
            ticket_manager.check_for_new_replies_async(
                self.username, self._on_ticket_replies_ready
            )

    def _on_daily_message_ready(self, date_str: str, messages):
        """daily_message arka plan thread'inden çağrılır; UI güncellemesi
        ana thread'de yapılmalı, bu yüzden wx.CallAfter kullanıyoruz.
        `messages`, dile göre çözülecek bir {dil_kodu: metin} sözlüğüdür -
        bkz. daily_message.resolve_message()."""
        wx.CallAfter(self._show_daily_message, date_str, messages)

    def _show_daily_message(self, date_str: str, messages):
        if self.state.in_jail:
            wx.CallLater(2000, self._show_daily_message, date_str, messages)
            return

        # Dil, tam gösterim anında (hapiste bekleme sonrası dahil) o anki
        # arayüz diline göre çözülür - böylece oyuncu bekleme sırasında
        # dil değiştirse bile doğru dilde görür.
        message_text = daily_message.resolve_message(messages, i18n.get_language())
        if not message_text:
            daily_message.mark_seen(date_str)
            return

        speak(t("daily_message.announce", date=date_str, message=message_text))
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

        label = wx.StaticText(panel, label=t("ui.products_label"))
        sizer.Add(label, 0, wx.LEFT | wx.TOP, 10)

        self.product_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        sizer.Add(self.product_list, 1, wx.EXPAND | wx.ALL, 10)

        qty_sizer = wx.BoxSizer(wx.HORIZONTAL)
        qty_sizer.Add(wx.StaticText(panel, label=t("ui.quantity_label")), 0, wx.ALL | wx.CENTER, 5)
        self.qty_spinner = wx.SpinCtrl(panel, value="1", min=1, max=1000000)
        self.bind_typing_sound(self.qty_spinner)
        qty_sizer.Add(self.qty_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(qty_sizer, 0, wx.LEFT | wx.TOP, 5)

        btn_sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.buy_btn = wx.Button(panel, label=t("ui.buy"))
        self.sell_btn = wx.Button(panel, label=t("ui.sell"))
        self.next_btn = wx.Button(panel, label=t("ui.next_day"))
        btn_sizer1.Add(self.buy_btn, 0, wx.ALL, 3)
        btn_sizer1.Add(self.sell_btn, 0, wx.ALL, 3)
        btn_sizer1.Add(self.next_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer1, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        self.company_btn = wx.Button(panel, label=t("ui.company_management"))
        self.employees_btn = wx.Button(panel, label=t("ui.employees"))
        self.informant_btn = wx.Button(panel, label=t("ui.informant_management"))
        self.loan_btn = wx.Button(panel, label=t("ui.take_loan"))
        btn_sizer2.Add(self.company_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.employees_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.informant_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.loan_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer2, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer3 = wx.BoxSizer(wx.HORIZONTAL)
        self.bank_btn = wx.Button(panel, label=t("ui.banking"))
        self.land_btn = wx.Button(panel, label=t("ui.land_management"))
        self.status_btn = wx.Button(panel, label=t("ui.status_report"))
        self.gamble_btn = wx.Button(panel, label=t("ui.gamble"))
        btn_sizer3.Add(self.bank_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.land_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.status_btn, 0, wx.ALL, 3)
        btn_sizer3.Add(self.gamble_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer3, 0, wx.ALIGN_CENTER | wx.TOP, 5)

        btn_sizer4 = wx.BoxSizer(wx.HORIZONTAL)
        self.support_btn = wx.Button(panel, label=t("ui.support_ticket"))
        self.auction_btn = wx.Button(panel, label=t("ui.auction"))
        btn_sizer4.Add(self.support_btn, 0, wx.ALL, 3)
        btn_sizer4.Add(self.auction_btn, 0, wx.ALL, 3)
        sizer.Add(btn_sizer4, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.CreateStatusBar()
        self.SetStatusText(t("ui.status_bar_full"))

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
        self.auction_btn.Bind(wx.EVT_BUTTON, self.on_auction)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def set_jail_mode(self, in_jail: bool):
        for btn in [self.buy_btn, self.sell_btn, self.next_btn,
                    self.company_btn, self.informant_btn, self.loan_btn,
                    self.bank_btn, self.land_btn, self.status_btn,
                    self.employees_btn, self.gamble_btn, self.auction_btn]:
            btn.Enable(not in_jail)
        self.product_list.Enable(not in_jail)
        self.qty_spinner.Enable(not in_jail)
        if in_jail:
            self.SetStatusText(t("ui.status_bar_jail", days=self.state.jail_days))
        else:
            self.SetStatusText(t("ui.status_bar_default"))

    def refresh_product_list(self, keep_selection: bool = True):
        prev_name = self.get_selected_product() if keep_selection else None
        self.set_jail_mode(self.state.in_jail)

        rows = []
        for name in self.flat_products:
            price = self.state.prices[name]
            qty = self.state.inventory.get(name, 0)
            label = t("product.list_label", name=product_display_name(name), price=format_tl(price), qty=qty)
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
        return t("product.unknown_category")

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
        dlg = wx.TextEntryDialog(self, t("cheat.prompt"), t("cheat.title"))
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
            speak(t("cheat.money_added", amount=format_tl(bonus)))
        elif command == "/admin123":
            bonus = 5_000_000_000_000.0
            self.state.cash += bonus
            if self.state.cash > self.state.highest_cash:
                self.state.highest_cash = self.state.cash
            self.update_wallet_display()
            speak(t("cheat.money_added", amount=format_tl(bonus)))
        elif command == "/admin":
            webbrowser.open("https://github.com/MUHAMMED4342/kara_borsa_oyun")
            speak(t("cheat.github_opened"))
        elif command == "/kayitlar":
            save_dir = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "Karaborsa", "KaraborsaSimulasyonu",
            )
            os.makedirs(save_dir, exist_ok=True)
            try:
                os.startfile(save_dir)
                speak(t("cheat.save_folder_opened"))
            except OSError:
                speak(t("cheat.save_folder_failed"))
        elif command == "/dil" or command.startswith("/lang"):
            self.open_translation_editor()
        else:
            speak(t("cheat.unknown_command"))

    def open_translation_editor(self):
        """Opens the Translation Editor panel (Ctrl+Alt+L, or the
        hidden /dil command in the cheat console). Lets you see the
        English source text for every in-game string and type in its
        Turkish translation; Save writes straight to locales/tr.json."""
        from translation_editor import TranslationEditorDialog
        dlg = TranslationEditorDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

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
            speak(t("common.in_jail"))
            return

        name = self.get_selected_product()
        if not name:
            speak(t("common.select_product"))
            return

        price = self.state.prices[name]
        qty = self.qty_spinner.GetValue()

        self.play_sound(self.SOUND_BUTTON)
        dlg = ProductActionDialog(self, product_display_name(name), price, qty)
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
            speak(t("common.in_jail"))
            return
        self.play_sound(self.SOUND_BUTTON)
        name = self.get_selected_product()
        if not name:
            speak(t("common.select_product"))
            return
        qty = self.qty_spinner.GetValue()
        if qty <= 0:
            speak(t("common.enter_valid_quantity"))
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
            speak(t("common.in_jail"))
            return
        self.play_sound(self.SOUND_BUTTON)
        name = self.get_selected_product()
        if not name:
            speak(t("common.select_product"))
            return
        qty = self.qty_spinner.GetValue()
        if qty <= 0:
            speak(t("common.enter_valid_quantity"))
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
            speak(t("common.in_jail"))
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
            speak(t("common.in_jail"))
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
            speak(t("common.in_jail"))
            return

        self.play_sound(self.SOUND_BUTTON)

        choices = [t("loan.bank_option"), t("loan.land_option")]
        type_dlg = wx.SingleChoiceDialog(self, t("loan.choose_prompt"), t("ui.take_loan"), choices)
        if type_dlg.ShowModal() != wx.ID_OK:
            type_dlg.Destroy()
            return
        selection = type_dlg.GetSelection()
        type_dlg.Destroy()

        if selection == 0:
            if not self.state.has_company:
                speak(t("loan.need_company"))
                return
            dlg = BankLoanDialog(self, self.state)
            if dlg.ShowModal() == wx.ID_OK:
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
            dlg.Destroy()
        else:
            if not self.state.lands:
                speak(t("loan.need_land"))
                return

            land_choices = []
            for i, land in enumerate(self.state.lands):
                status = t("land.has_loan_suffix") if land.get("has_loan", False) else ""
                land_choices.append(f"{i+1}. {land_type_display_name(land['type'])}{status}")

            land_dlg = wx.SingleChoiceDialog(self, t("loan.choose_land_prompt"),
                                              t("land.select_title"), land_choices)
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
            speak(t("common.in_jail"))
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = BankingDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.update_wallet_display()

    def on_land_management(self, event):
        if self.state.in_jail:
            speak(t("common.in_jail"))
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
            speak(t("common.in_jail"))
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
            speak(t("common.in_jail"))
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = GamblingDialog(self, self.state)
        dlg.ShowModal()
        self.update_wallet_display()
        self.auto_save()
        dlg.Destroy()

    def on_auction(self, event):
        if self.state.in_jail:
            speak(t("common.in_jail"))
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = AuctionDialog(self, self.state)
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
            t("ticket.info_day"): self.state.day,
            t("ticket.info_cash"): t("money.amount_tl", amount=format_tl(self.state.cash)),
            t("ticket.info_in_jail"): t("common.yes") if self.state.in_jail else t("common.no"),
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
            msg = t("ticket.reply_single", number=r['number'], title=r['title'])
        else:
            msg = t("ticket.reply_multi", count=len(results))
        self.play_sound(self.SOUND_TICKET_REPLY)
        speak(msg + t("ticket.reply_suffix"))

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
            speak(t("common.in_jail"))
            return

        lines = [
            t("status.title"),
            t("status.day", day=self.state.day),
            t("status.cash", cash=format_tl(self.state.cash)),
            t("status.police_risk", risk=f"{self.state.police_heat:.1f}"),
            t("status.total_crime_income", amount=format_tl(self.state.total_crime)),
            t("status.highest_cash", amount=format_tl(self.state.highest_cash)),
        ]

        if self.state.lands:
            lines.append("")
            lines.append(t("status.land_info_title"))
            total_value = 0
            for i, land in enumerate(self.state.lands):
                land_type = land["type"]
                price = self.state.get_land_price(land_type)
                total_value += price
                purchase_price = land["purchase_price"]
                profit = price - purchase_price
                days_held = self.state.day - land["purchase_day"]
                lines.append(t("status.land_line", index=i + 1, type=land_type_display_name(land_type),
                                price=f"{price:,.0f}", purchase=f"{purchase_price:,.0f}",
                                days=days_held))
            lines.append(t("status.total_land_value", amount=f"{total_value:,.0f}"))

        if self.state.has_company:
            lines.append("")
            lines.append(t("status.company_info_title"))
            for c in self.state.companies:
                lines.extend([
                    t("status.company_name", name=c['name']),
                    t("status.company_city", city=c['city'] or '-'),
                    t("status.company_type", type=company_type_display_name(c['type'])),
                    t("status.company_credit_score", score=c['credit_score']),
                    t("status.company_active_days", days=c['days_active']),
                    t("status.company_total_profit", amount=format_tl(c['total_profit'])),
                    t("status.company_monthly_revenue", amount=format_tl(c['monthly_revenue'])),
                    "",
                ])

            if self.state.loan_amount > 0:
                remaining_installments = self.state.loan_total_installments - self.state.loan_installments_paid
                lines.extend([
                    "",
                    t("status.loan_info_title"),
                    "-" * 30,
                    t("status.loan_amount", amount=format_tl(self.state.loan_amount)),
                    t("status.loan_total_debt", amount=format_tl(self.state.loan_total_debt)),
                    t("status.loan_installment", amount=format_tl(self.state.loan_installment_amount)),
                    t("status.loan_next_installment", days=self.state.loan_days_until_installment),
                    t("status.loan_remaining_installments", n=remaining_installments),
                    t("status.loan_interest_rate", rate=f"{self.state.loan_interest_rate*100:.1f}"),
                ])
        else:
            lines.append(t("status.no_company"))

        loaned_lands = [land for land in self.state.lands if land.get("has_loan", False)]
        if loaned_lands:
            lines.append("")
            lines.append(t("status.land_loans_title"))
            lines.append("-" * 30)
            for land in loaned_lands:
                lines.append(t(
                    "status.land_loan_line",
                    type=land_type_display_name(land['type']),
                    debt=format_tl(land.get('loan_debt', 0.0)),
                    installment=format_tl(land.get('loan_installment_amount', 0.0)),
                    days=land.get('loan_days_until_installment', 30),
                ))

        if self.state.employees:
            lines.append("")
            lines.append(t("status.employees_title"))
            lines.append("-" * 30)
            total_generated = 0.0
            for e in self.state.employees:
                total_generated += e.get("total_generated", 0.0)
                lines.append(t(
                    "status.employee_line",
                    name=e['name'], city=e['city'],
                    amount=format_tl(e.get('total_generated', 0.0)),
                    days=e['days_until_salary'],
                ))
            lines.append(t("status.total_employee_generated", amount=format_tl(total_generated)))

        if self.state.deaths_caused > 0:
            lines.append(t("status.deaths", n=self.state.deaths_caused))

        text = "\n".join(lines)
        speak(text)

    def on_history(self, event):
        """F3: Şimdiye kadar söylenmiş tüm mesajları gösteren geçmiş ekranını açar."""
        if self.state.in_jail:
            speak(t("common.in_jail"))
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
        speak(t("jail.complete"))
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
                    log_history(t("log.score_sent", amount=format_tl(total)))
                else:
                    log_history(t("log.score_send_failed", message=msg))
            except Exception as e:
                log_history(t("log.score_send_unexpected_error", error=e))
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
            log_history(t("log.day_advance_error", error=e))
            speak(t("day.advance_error_speak"))
        finally:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
            self._advancing_day = False

    def _advance_day(self):
        self.play_sound(self.SOUND_TRANSITION)

        narration = []

        self.state.day += 1
        log_history(t("log.day_started", day=self.state.day))

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
                narration.append(t("day.informant_left"))

        if self.state.loan_amount > 0:
            success, msg = self.state.process_loan_daily()
            if not success:
                _, default_msg = self.state.default_loan()
                narration.append(t("day.loan_default", message=default_msg))
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
            narration.append(t("day.bank_interest", amount=format_tl(bank_interest)))
            narrated_gain += bank_interest

        informant_evaded = False
        if was_warned:
            self.state.informant_warning_active = False
            warn_msg = t("day.informant_warning_body")
            if narration:
                _speak_narration(narration)
                narration = []
            dlg = wx.MessageDialog(self, warn_msg, t("day.informant_warning_title"),
                                  wx.YES_NO | wx.ICON_WARNING)
            dlg.SetYesNoLabels(t("day.dump_yes"), t("day.dump_no"))
            if dlg.ShowModal() == wx.ID_YES:
                count, earned = self.state.dump_inventory_for_evasion()
                narration.append(t("day.dumped_evaded", count=count, earned=format_tl(earned)))
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
                narration.append(t("day.informant_wrong"))
        elif self.state.has_informant:
            self.state.update_police_heat()
            police = {"caught": False}
        else:
            police = self.state.police_check()

        if police["caught"]:
            self.audio.play_sound(self.SOUND_POLICE)
            jail_msg = self.state.go_to_jail(random.randint(1, 3))
            narration.append(t("day.caught", message=jail_msg))
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
            narration.append(t("day.informant_warns_tomorrow"))

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

        if key in (ord('L'), ord('l')) and event.ControlDown() and event.AltDown():
            self.open_translation_editor()
            return

        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if wx.Window.FindFocus() is self.product_list:
                self.show_product_action_popup()
                return

        if key == wx.WXK_F1:
            open_localized_help()
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
        if key == wx.WXK_F8:
            self.on_auction(event)
            return
        
        if key == ord('C') or key == ord('c'):
            speak(t("status.cash", cash=format_tl(self.state.cash)))
            return
        if key == ord('D') or key == ord('d'):
            name = self.get_selected_product()
            if name:
                category = self.get_product_category(name)
                speak(t("product.category_announce", name=product_display_name(name), category=category_display_name(category)))
            else:
                speak(t("common.select_product"))
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
                speak(t("audio.volume_announce", vol=int(vol * 100)))
                self._last_volume_speak_time = current_time
            return
        if key == wx.WXK_PAGEDOWN:
            vol = self.audio.volume_down()
            current_time = time.time()
            if current_time - self._last_volume_speak_time > 0.5:
                speak(t("audio.volume_announce", vol=int(vol * 100)))
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
                t("close.score_in_progress_body"),
                t("close.score_in_progress_title"),
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
            self, title=t("app.name"),
            style=wx.CAPTION | wx.STAY_ON_TOP,
        )
        panel = wx.Panel(wait_dlg)
        msg = wx.StaticText(panel, label=t("close.please_wait_body"))
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(msg, 0, wx.ALL, 20)
        panel.SetSizer(sizer)
        wait_dlg.Fit()
        wait_dlg.CenterOnScreen()
        wait_dlg.Show()
        speak(t("close.please_wait_speak"))

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
        self._play_startup_logo_sound()

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
                speak(t("app.username_required"))
                return False
            country_dlg = CountrySelectDialog()
            country_dlg.ShowModal()
            country = country_dlg.selected_country
            country_dlg.Destroy()
            frame = MainFrame(username, country=country)
            frame.Show()
            return True
        elif result == ID_LOAD:
            if not username:
                speak(t("app.no_save_selected"))
                return False
            data = load_game(username)
            if data:
                frame = MainFrame(username, data)
                frame.Show()
                return True
            else:
                speak(t("app.save_load_failed"))
                return False
        return False


    def _play_startup_logo_sound(self):
        """Oyun açılır açılmaz, ana menü (hatta gizlilik/kullanım şartları
        onay ekranı) görünmeden HEMEN ÖNCE çalınan kısa logo/açılış sesi.
        Diğer tüm tek seferlik efektler gibi (ör. düğme tıklama sesleri)
        ARKA PLANDA/ASENKRON çalar - hiçbir ekranı BEKLETMEZ, terms/auth
        akışı hemen ardından normal şekilde devam eder. sounds/logo.mp3
        yoksa veya çalınamazsa sessizce atlanır (oyunun açılışını asla
        engellemez/geciktirmez)."""
        try:
            audio = AudioManager()
            logo_path = resource_path("sounds/logo.mp3")
            if os.path.exists(logo_path):
                audio.play_sound(logo_path)
        except Exception:
            pass

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
            speak(t("auth.offline_continue"))

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