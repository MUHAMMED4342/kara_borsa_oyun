import math
import os
import random
import time
import wx
import threading
import webbrowser

from game_data import (
    COMPANY_TYPES, LAND_TYPES, EMPLOYEE_HIRE_FEE, EMPLOYEE_BASE_SALARY, INFORMANT_CONFIG,
    land_type_display_name, land_type_description, company_type_display_name, company_type_description,
    AUCTION_ITEMS, auction_item_display_name,
)
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl
from audio_manager import AudioManager
from save_manager import list_saves, delete_save, rename_save
from game_state import resource_path, open_help, open_release_notes, ID_LOAD, ID_NEW, ROULETTE_BET_LABELS, get_roulette_color_label, COUNTRIES, DEFAULT_COUNTRY
from i18n import t
import i18n
import daily_message

import leaderboard
from leaderboard import get_leaderboard, get_gist_content

import ticket_manager
import settings_manager
import app_log
import updater


_last_spoken_text = None
_last_spoken_time = 0.0
_DUPLICATE_SPEAK_WINDOW = 2.0  # saniye


def speak(text: str):
    """Ekran okuyucuya seslendirir VE aynı mesajı geçmiş kaydına ekler.
    main.py'deki speak() ile aynı çift-okuma önleme mantığı: aynı metin
    kısa bir süre (2 sn) içinde ikinci kez gelirse (ör. gün atlama veya
    hapis özetinde) yok sayılır, böylece kullanıcı aynı uzun özeti art
    arda iki kez duymaz."""
    global _last_spoken_text, _last_spoken_time
    now = time.time()
    if text and text == _last_spoken_text and (now - _last_spoken_time) < _DUPLICATE_SPEAK_WINDOW:
        return
    _last_spoken_text = text
    _last_spoken_time = now
    _tts_speak(text)
    log_history(text)


SOUND_TYPING = resource_path("sounds/typing.wav")
SOUND_TICKET_SENT = resource_path("sounds/gonderim.mp3")
SOUND_TICKET_REPLY = resource_path("sounds/yanit.mp3")


def bind_typing_sound(ctrl, audio_manager):
    """Verilen metin giriş kontrolüne (TextCtrl, SpinCtrl vb.) her
    karakter yazıldığında typing.wav çalacak şekilde bağlar. Ayarlar
    ekranından kapatılmışsa (settings_manager.is_typing_sound_enabled)
    hiçbir şey çalmaz."""
    def _on_type(event):
        if settings_manager.is_typing_sound_enabled() and os.path.exists(SOUND_TYPING):
            audio_manager.play_sound(SOUND_TYPING)
        event.Skip()
    ctrl.Bind(wx.EVT_TEXT, _on_type)


def bind_typing_sound_to_dialog(dialog, audio_manager):
    """wx.TextEntryDialog gibi içindeki TextCtrl'e doğrudan erişilemeyen
    hazır pencerelerde, alt kontrolleri tarayıp bulunan TextCtrl'e ses
    bağlar."""
    for child in dialog.GetChildren():
        if isinstance(child, wx.TextCtrl):
            bind_typing_sound(child, audio_manager)
            break


def _ask_update_confirmation(remote_version: str) -> bool:
    """main.py'deki aynı isimli fonksiyonun birebir eşi. dialogs.py,
    main.py'yi import EDEMEZ (main.py zaten dialogs.py'yi import
    ediyor - döngüsel import olurdu), bu yüzden Ayarlar ekranındaki
    'Güncellemeleri Kontrol Et' butonu için burada ayrıca tutuluyor."""
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


def _open_localized_html(base_filename: str, fallback_func):
    """Tries to open a language-specific version of an HTML asset
    (e.g. base_filename='help.html' becomes 'en_help.html',
    'de_help.html', 'ja_help.html', ... - the file name prefix always
    matches the active i18n language code) if one has been placed
    next to the game. Falls back to the game's normal (fallback_func)
    behavior when no such file exists yet, so languages without their
    own page don't break - they just keep showing whatever
    fallback_func already opened before this existed.

    To add a localized help/release-notes page for a language, drop a
    file following this naming pattern into the same folder the
    existing help file lives in - no code change needed.
    """
    lang = i18n.get_language()
    localized_name = f"{lang}_{base_filename}"
    try:
        path = resource_path(localized_name)
        if os.path.exists(path):
            if path.startswith(("http://", "https://")):
                url = path
            else:
                url = "file:///" + os.path.abspath(path).replace(os.sep, "/")
            webbrowser.open(url)
            return
    except Exception as e:
        print(f"[i18n] Could not open localized asset '{localized_name}': {e}")
    fallback_func()


def open_localized_help():
    _open_localized_html("help.html", open_help)


def open_localized_release_notes():
    _open_localized_html("release_notes.html", open_release_notes)


class ProductActionDialog(wx.Dialog):
    """Ürün listesinde Enter'a basıldığında açılan hızlı işlem penceresi.
    Sadece 'Satın Al' ve 'Sat' düğmelerini gösterir; hangisine basılırsa
    (veya hangisi Enter ile seçilirse) sonucu self.result üzerinden
    ('buy' / 'sell' / None) çağırana bildirir."""

    def __init__(self, parent, product_name, price, qty):
        super().__init__(parent, title=t("product_action.title"),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.result = None

        self._build_ui(product_name, price, qty)
        self._bind_events()
        self.Fit()
        self.CenterOnParent()

    def _build_ui(self, product_name, price, qty):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        info = wx.StaticText(
            panel,
            label=t("product.list_label", name=product_name, price=format_tl(price), qty=qty)
        )
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buy_btn = wx.Button(panel, label=t("ui.buy"))
        self.sell_btn = wx.Button(panel, label=t("ui.sell"))
        self.cancel_btn = wx.Button(panel, label=t("product_action.cancel"))
        btn_sizer.Add(self.buy_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.sell_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)
        wx.CallAfter(self.buy_btn.SetFocus)

    def _bind_events(self):
        self.buy_btn.Bind(wx.EVT_BUTTON, self.on_buy)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell)
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.Bind(wx.EVT_CLOSE, self.on_cancel)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_ESCAPE:
            self.on_cancel(event)
            return
        event.Skip()

    def on_buy(self, event):
        self.result = "buy"
        self.EndModal(wx.ID_OK)

    def on_sell(self, event):
        self.result = "sell"
        self.EndModal(wx.ID_OK)

    def on_cancel(self, event):
        self.result = None
        self.EndModal(wx.ID_CANCEL)


class LandManagementDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title=t("land.title"), size=(650, 550))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("land.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        sizer.Add(wx.StaticText(panel, label=t("land.your_lands")), 0, wx.LEFT | wx.TOP, 10)
        self.land_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.land_list.SetMinSize((500, 150))
        sizer.Add(self.land_list, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label=t("land.market_lands")), 0, wx.LEFT | wx.TOP, 10)
        self.market_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.market_list.SetMinSize((500, 100))
        sizer.Add(self.market_list, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        self.buy_btn = wx.Button(panel, label=t("ui.buy"))
        self.sell_btn = wx.Button(panel, label=t("ui.sell"))
        btn_sizer1.Add(self.buy_btn, 0, wx.ALL, 5)
        btn_sizer1.Add(self.sell_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer1, 0, wx.ALIGN_CENTER, 5)

        info_note = wx.StaticText(panel, label=t("land.loan_note"))
        sizer.Add(info_note, 0, wx.LEFT | wx.BOTTOM, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((500, 80))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        self.done_btn = wx.Button(panel, label=t("land.done"))
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
            profit_str = t("land.profit_positive", amount=f"{profit:,.0f}") if profit >= 0 else t("land.profit_negative", amount=f"{profit:,.0f}")
            has_loan = land.get("has_loan", False)
            if has_loan:
                debt = land.get("loan_debt", land.get("loan_amount", 0.0) * 1.15)
                days_left = land.get("loan_days_until_installment", 30)
                loan_str = t("land.loan_suffix", debt=f"{debt:,.0f}", days=days_left)
            else:
                loan_str = ""
            self.land_list.Append(t("land.owned_line", index=i+1, type=land_type_display_name(land_type),
                                     price=f"{price:,.0f}", profit=profit_str, loan=loan_str))

        self.market_list.Clear()
        for land_type, data in LAND_TYPES.items():
            price = self.state.get_land_price(land_type)
            count = self.state.get_land_count(land_type)
            label = t("land.market_line", type=land_type_display_name(land_type), price=f"{price:,.0f}",
                       count=count, description=land_type_description(land_type))
            self.market_list.Append(label, land_type)

        total_land_value = sum(self.state.get_land_price(land["type"]) for land in self.state.lands)
        status = t("land.status_summary", count=len(self.state.lands),
                    value=f"{total_land_value:,.0f}", cash=f"{self.state.cash:,.0f}")
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
            speak(t("land.select_announce", type=land_type_display_name(land_type), price=f"{price:,.0f}",
                    purchase=f"{purchase_price:,.0f}", days=days_held))

    def on_market_select(self, event):
        idx = self.market_list.GetSelection()
        if idx != wx.NOT_FOUND:
            land_type = self.market_list.GetClientData(idx)
            price = self.state.get_land_price(land_type)
            speak(t("land.market_select_announce", type=land_type_display_name(land_type), price=f"{price:,.0f}",
                    description=land_type_description(land_type)))

    def on_buy_land(self, event):
        idx = self.market_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak(t("land.select_type_first"))
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
            speak(t("land.select_to_sell"))
            return
        
        land = self.state.lands[idx]
        if land.get("has_loan", False):
            speak(t("land.has_loan_block_sell"))
            return
        
        if wx.MessageBox(t("land.confirm_sell"), t("common.confirm_title"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            success, msg = self.state.sell_land(idx)
            speak(msg)
            if success:
                self._update_ui()
                self.parent.auto_save()


TERMS_VERSION = "1.0"
TERMS_FILES = [
    ("terms.tab_privacy", "gizlilik politikası.txt"),
    ("terms.tab_terms", "kullanimsartlari.txt"),
]


def _load_localized_document(filename: str) -> str:
    """gizlilik politikası.txt / kullanimsartlari.txt gibi çok-dilli
    (günün mesajıyla AYNI "<dil_kodu>:" blok biçimi) düz metin
    belgelerini okur ve o anki arayüz diline uygun bölümü döner. Hem
    ZORUNLU ilk-açılış onay ekranı (TermsDialog) hem de ana menüden
    salt-okunur görüntüleme (DocumentViewerDialog) bu tek fonksiyonu
    paylaşır."""
    path = resource_path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    except Exception:
        return t("terms.file_missing", filename=filename)

    messages = daily_message.parse_language_blocks(raw)
    resolved = daily_message.resolve_message(messages, i18n.get_language())
    return resolved if resolved else raw


class DocumentViewerDialog(wx.Dialog):
    """Ana menüden 'Gizlilik Politikası' / 'Kullanım Şartları' seçilince
    açılan SALT OKUNUR görüntüleyici. Uygulamanın ilk açılışındaki
    ZORUNLU onay ekranından (TermsDialog - kabul/reddet, reddedilirse
    uygulama kapanır) FARKLI bir sınıftır: burada sadece metni okuyup
    'Kapat' ile çıkabilirsiniz, hesabı veya oyunu hiçbir şekilde
    etkilemez."""

    def __init__(self, parent, title_key: str, filename: str):
        super().__init__(parent, title=t(title_key), size=(600, 560))
        self.title_key = title_key
        self.filename = filename
        self._build_ui()
        self._bind_events()
        self.CenterOnScreen()
        speak(t(self.title_key))

    def _build_ui(self):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t(self.title_key))
        title.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        outer.Add(title, 0, wx.ALL | wx.CENTER, 12)

        text_ctrl = wx.TextCtrl(
            panel, value=_load_localized_document(self.filename),
            style=wx.TE_MULTILINE | wx.TE_READONLY
        )
        outer.Add(text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 15)

        self.close_btn = wx.Button(panel, label=t("common.close"))
        outer.Add(self.close_btn, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(outer)
        self.close_btn.SetFocus()

    def _bind_events(self):
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_close(self, event):
        self.EndModal(wx.ID_OK)


class TermsDialog(wx.Dialog):
    """Oyunun İLK açılışında, hesaptan tamamen bağımsız olarak (giriş
    ekranından bile ÖNCE, bkz. main.py App._ensure_terms_accepted),
    gizlilik politikası ve kullanım şartlarının gösterilip kabul
    edilmesini sağlar. X ile kapatmak da 'reddet' sayılır - kabul
    edilmeden uygulama hiçbir ekrana geçmez, sadece kapanır.

    Kabul edildiğinde settings_manager'a TERMS_VERSION yazılır; bu
    sayede sadece BİR KEZ (cihaz başına) gösterilir. Metinler ileride
    değişirse TERMS_VERSION artırılır, kullanıcı otomatik olarak
    yeniden onay ekranını görür."""

    def __init__(self, parent=None):
        super().__init__(
            parent, title=t("terms.title"),
            size=(600, 560),
        )
        self._build_ui()
        self._bind_events()
        self.CenterOnScreen()
        speak(t("terms.speak_intro"))

    def _load_text(self, filename: str) -> str:
        """gizlilik politikası.txt / kullanimsartlari.txt dosyalarını okur.
        bkz. _load_localized_document (bu iki sınıf arasında paylaşılan
        çok-dilli ayrıştırma mantığı orada toplanmıştır)."""
        return _load_localized_document(filename)

    def _build_ui(self):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("terms.header"))
        title.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        outer.Add(title, 0, wx.ALL | wx.CENTER, 12)

        self.notebook = wx.Notebook(panel)
        for label_key, filename in TERMS_FILES:
            page = wx.Panel(self.notebook)
            page_sizer = wx.BoxSizer(wx.VERTICAL)
            text_ctrl = wx.TextCtrl(
                page, value=self._load_text(filename),
                style=wx.TE_MULTILINE | wx.TE_READONLY
            )
            page_sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 8)
            page.SetSizer(page_sizer)
            self.notebook.AddPage(page, t(label_key))
        outer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_accept = wx.Button(panel, label=t("terms.accept_btn"))
        self.btn_decline = wx.Button(panel, label=t("terms.decline_btn"))
        btn_sizer.Add(self.btn_accept, 1, wx.EXPAND | wx.RIGHT, 6)
        btn_sizer.Add(self.btn_decline, 1, wx.EXPAND)
        outer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(outer)
        self.btn_accept.SetFocus()

    def _bind_events(self):
        self.btn_accept.Bind(wx.EVT_BUTTON, self.on_accept)
        self.btn_decline.Bind(wx.EVT_BUTTON, self.on_decline)
        self.Bind(wx.EVT_CLOSE, self.on_decline)

    def on_accept(self, event):
        self.EndModal(wx.ID_OK)

    def on_decline(self, event):
        self.EndModal(wx.ID_CANCEL)


class SettingsDialog(wx.Dialog):
    """Ana menüden açılan 'Ayarlar' ekranı. Bu cihaza özel ayarları
    (skor gönderimi, günün mesajı, ses seviyesi) tek bir yerden açıp
    kapatmayı sağlar. wx.CheckBox kullanıyoruz çünkü ekran okuyucular
    "işaretli / işaretsiz" durumunu kendisi anons ediyor."""

    def __init__(self, parent=None):
        super().__init__(parent, title=t("settings.title"), size=(420, 560))
        self.audio = AudioManager()
        self._last_vol_speak_time = 0.0
        self._build_ui()
        self._bind_events()
        self.Bind(wx.EVT_CLOSE, self.on_close_dialog)
        self.CenterOnScreen()
        speak(t("settings.speak_intro"))

    def _build_ui(self):
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("settings.header"))
        title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        outer.Add(title, 0, wx.ALL | wx.CENTER, 12)

        self.btn_change_language = wx.Button(panel, label=t("settings.change_language_btn"))
        outer.Add(self.btn_change_language, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        outer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        self.cb_score_submission = wx.CheckBox(panel, label=t("settings.score_submission"))
        self.cb_score_submission.SetValue(leaderboard.is_score_submission_enabled())
        outer.Add(self.cb_score_submission, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 15)

        self.cb_daily_message = wx.CheckBox(panel, label=t("settings.daily_message"))
        self.cb_daily_message.SetValue(settings_manager.is_daily_message_enabled())
        outer.Add(self.cb_daily_message, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.cb_typing_sound = wx.CheckBox(panel, label=t("settings.typing_sound"))
        self.cb_typing_sound.SetValue(settings_manager.is_typing_sound_enabled())
        outer.Add(self.cb_typing_sound, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.cb_auto_update = wx.CheckBox(panel, label=t("settings.auto_update"))
        self.cb_auto_update.SetValue(settings_manager.is_auto_update_check_enabled())
        outer.Add(self.cb_auto_update, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.btn_check_update = wx.Button(panel, label=t("settings.check_update_btn"))
        outer.Add(self.btn_check_update, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        outer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        self.music_volume_label = wx.StaticText(
            panel, label=t("settings.music_volume", vol=int(self.audio.music_volume * 100))
        )
        outer.Add(self.music_volume_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)
        self.music_slider = wx.Slider(
            panel, value=int(self.audio.music_volume * 100),
            minValue=0, maxValue=100, style=wx.SL_HORIZONTAL
        )
        self.music_slider.SetLineSize(10)
        outer.Add(self.music_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.sfx_volume_label = wx.StaticText(
            panel, label=t("settings.sfx_volume", vol=int(self.audio.sfx_volume * 100))
        )
        outer.Add(self.sfx_volume_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 15)
        self.sfx_slider = wx.Slider(
            panel, value=int(self.audio.sfx_volume * 100),
            minValue=0, maxValue=100, style=wx.SL_HORIZONTAL
        )
        self.sfx_slider.SetLineSize(10)
        outer.Add(self.sfx_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)

        self.btn_close = wx.Button(panel, label=t("settings.close_btn"))
        outer.Add(self.btn_close, 0, wx.EXPAND | wx.ALL, 15)

        panel.SetSizer(outer)
        self.btn_change_language.SetFocus()

    def _bind_events(self):
        self.btn_change_language.Bind(wx.EVT_BUTTON, self.on_change_language)
        self.cb_score_submission.Bind(wx.EVT_CHECKBOX, self.on_toggle_score_submission)
        self.cb_daily_message.Bind(wx.EVT_CHECKBOX, self.on_toggle_daily_message)
        self.cb_typing_sound.Bind(wx.EVT_CHECKBOX, self.on_toggle_typing_sound)
        self.cb_auto_update.Bind(wx.EVT_CHECKBOX, self.on_toggle_auto_update)
        self.btn_check_update.Bind(wx.EVT_BUTTON, self.on_check_update_now)
        self.music_slider.Bind(wx.EVT_SLIDER, self.on_music_slider)
        self.sfx_slider.Bind(wx.EVT_SLIDER, self.on_sfx_slider)
        self.btn_close.Bind(wx.EVT_BUTTON, self.on_close_dialog)

    def on_change_language(self, event):
        dlg = LanguageDialog(self)
        dlg.ShowModal()
        changed = dlg.changed
        dlg.Destroy()
        if changed:
            self._rebuild_ui()
            parent = self.GetParent()
            if parent is not None and hasattr(parent, "_rebuild_ui"):
                parent._rebuild_ui()

    def _rebuild_ui(self):
        """Panel ve tüm çocuklarını yok edip _build_ui() + _bind_events()'i
        tekrar çağırır. EVT_CLOSE __init__'te ayrı bağlandığı için
        burada tekrar bağlanmıyor, çift tetiklenme olmuyor."""
        for child in list(self.GetChildren()):
            child.Destroy()
        self._build_ui()
        self._bind_events()
        self.Layout()
        speak(t("settings.speak_intro"))

    def on_toggle_score_submission(self, event):
        enabled = self.cb_score_submission.GetValue()
        leaderboard.set_score_submission_enabled(enabled)
        speak(t("settings.score_submission_toggled",
                state=t("settings.state_enabled") if enabled else t("settings.state_disabled")))

    def on_toggle_daily_message(self, event):
        enabled = self.cb_daily_message.GetValue()
        settings_manager.set_daily_message_enabled(enabled)
        speak(t("settings.daily_message_toggled",
                state=t("settings.state_enabled") if enabled else t("settings.state_disabled")))

    def on_toggle_typing_sound(self, event):
        enabled = self.cb_typing_sound.GetValue()
        settings_manager.set_typing_sound_enabled(enabled)
        speak(t("settings.typing_sound_toggled",
                state=t("settings.state_enabled") if enabled else t("settings.state_disabled")))

    def on_toggle_auto_update(self, event):
        enabled = self.cb_auto_update.GetValue()
        settings_manager.set_auto_update_check_enabled(enabled)
        speak(t("settings.auto_update_toggled",
                state=t("settings.state_enabled") if enabled else t("settings.state_disabled")))

    def on_check_update_now(self, event):
        speak(t("settings.checking_updates_speak"))

        def _on_no_update(message):
            wx.MessageBox(message, t("update.title"), wx.OK | wx.ICON_INFORMATION)
            speak(message)

        updater.check_for_update_async(
            ask_user_callback=_ask_update_confirmation,
            on_no_update_callback=_on_no_update,
        )

    def _throttled_speak(self, text):
        now = time.time()
        if now - self._last_vol_speak_time >= 0.15:
            speak(text)
            self._last_vol_speak_time = now

    def on_music_slider(self, event):
        vol = self.music_slider.GetValue() / 100.0
        self.audio.set_music_volume(vol)
        self.music_volume_label.SetLabel(t("settings.music_volume", vol=self.music_slider.GetValue()))
        self._throttled_speak(t("settings.music_volume", vol=self.music_slider.GetValue()))

    def on_sfx_slider(self, event):
        vol = self.sfx_slider.GetValue() / 100.0
        self.audio.set_sfx_volume(vol)
        self.sfx_volume_label.SetLabel(t("settings.sfx_volume", vol=self.sfx_slider.GetValue()))
        self._throttled_speak(t("settings.sfx_volume", vol=self.sfx_slider.GetValue()))

    def on_close_dialog(self, event):
        self.EndModal(wx.ID_CLOSE)


class CountrySelectDialog(wx.Dialog):
    """YENİ bir oyuna başlarken gösterilen ülke seçim penceresi. Oyuncunun
    seçtiği ülkeye göre (bkz. game_state.COUNTRIES) şirket/arsa şehir ve
    ilçe havuzu belirlenir - Türkiye'nin yanı sıra ABD, İngiltere ve
    Avustralya desteklenir. Kayıtlı bir oyun YÜKLENİRKEN bu pencere
    gösterilmez; ülke, o kaydın kendi 'country' alanından okunur (bkz.
    game_state.GameState.__init__)."""

    def __init__(self, parent=None):
        super().__init__(parent, title=t("country.title"), size=(360, 380))
        self.selected_country = DEFAULT_COUNTRY
        self._build_ui()
        self._bind_events()
        self.CenterOnScreen()
        speak(t("country.speak_intro"))

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("country.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.codes = list(COUNTRIES.keys())
        self.country_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.country_list.SetItems([t(COUNTRIES[code]["name_key"]) for code in self.codes])
        default_index = self.codes.index(DEFAULT_COUNTRY) if DEFAULT_COUNTRY in self.codes else 0
        self.country_list.SetSelection(default_index)
        sizer.Add(self.country_list, 1, wx.EXPAND | wx.ALL, 10)

        self.select_btn = wx.Button(panel, label=t("country.select_btn"))
        sizer.Add(self.select_btn, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(sizer)
        self.country_list.SetFocus()

    def _bind_events(self):
        self.select_btn.Bind(wx.EVT_BUTTON, self.on_select)
        self.country_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_select)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_select(self, event):
        idx = self.country_list.GetSelection()
        if idx == wx.NOT_FOUND:
            idx = 0
        self.selected_country = self.codes[idx]
        self.EndModal(wx.ID_OK)

    def on_close(self, event):
        # Kapatmak = varsayılan (Türkiye) ile devam etmek anlamına gelir;
        # ülke seçimi ZORUNLU bir engel değildir, sadece bir tercihtir.
        self.selected_country = DEFAULT_COUNTRY
        self.EndModal(wx.ID_OK)


class LanguageDialog(wx.Dialog):
    """Basit bir dil seçim penceresi: MainMenu ve SettingsDialog'dan
    açılır. Yalnızca mevcut dilleri (built-in İngilizce/Türkçe artı
    Çeviri Editörü'nden herhangi birinin eklediği diller) listeler;
    yeni dil OLUŞTURMA işlemi kasıtlı olarak burada değil, Çeviri
    Editöründe (Ctrl+Alt+L) - çünkü yeni bir dil oluşturmak "boş"
    bir dosyayla başlar ve asıl işi çeviri ekranı yapar."""

    def __init__(self, parent):
        super().__init__(parent, title=t("language.title"), size=(340, 360))
        self.changed = False
        self._build_ui()
        self._bind_events()
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("language.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.langs = i18n.available_languages()
        self.lang_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.lang_list.SetItems([name for _code, name in self.langs])

        current = i18n.get_language()
        codes = [code for code, _name in self.langs]
        if current in codes:
            self.lang_list.SetSelection(codes.index(current))
        elif self.langs:
            self.lang_list.SetSelection(0)

        sizer.Add(self.lang_list, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.select_btn = wx.Button(panel, label=t("language.select_btn"))
        self.cancel_btn = wx.Button(panel, label=t("language.cancel_btn"))
        btn_sizer.Add(self.select_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)
        self.lang_list.SetFocus()

    def _bind_events(self):
        self.select_btn.Bind(wx.EVT_BUTTON, self.on_select)
        self.cancel_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CANCEL))
        self.lang_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_select)
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CANCEL))

    def on_select(self, event):
        idx = self.lang_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.langs):
            self.EndModal(wx.ID_CANCEL)
            return

        code = self.langs[idx][0]
        if code != i18n.get_language():
            i18n.set_language(code)
            self.changed = True
            speak(t("language.changed_speak"))

        self.EndModal(wx.ID_OK)


class MainMenu(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title=t("app.name"), size=(350, 480))
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
        
        title = wx.StaticText(panel, label=t("menu.header"))
        title.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 15)

        # (etiket, işleyici) çiftleri - liste, menünün TEK doğruluk
        # kaynağıdır. Her öğe kendi işleyicisiyle birlikte taşınıyor,
        # index kayması mümkün değil.
        self._menu_actions = [
            (t("menu.item_new_game"), self.start_new_game),
            (t("menu.item_continue"), self.continue_game),
            (t("menu.item_leaderboard"), self.show_leaderboard),
            (t("menu.item_settings"), self.open_settings),
            (t("menu.item_language"), self.open_language),
            (t("menu.item_help"), open_localized_help),
            (t("menu.item_daily_message"), self.show_daily_message_now),
            (t("menu.item_tickets"), self.open_tickets_from_menu),
            (t("menu.item_privacy_policy"), self.open_privacy_policy),
            (t("menu.item_terms_of_service"), self.open_terms_of_service),
            (t("menu.item_exit"), self._exit_menu),
        ]

        self.menu_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.menu_list.SetItems([label for label, _handler in self._menu_actions])
        self.menu_list.SetSelection(0)
        sizer.Add(self.menu_list, 1, wx.EXPAND | wx.ALL, 20)
        
        info = wx.StaticText(panel, label=t("menu.nav_hint"))
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 10)
        
        panel.SetSizer(sizer)
        self.menu_list.SetFocus()
    
    def _bind_events(self):
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def on_close(self, event):
        self.EndModal(wx.ID_CANCEL)

    def _exit_menu(self):
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

        if 0 <= idx < len(self._menu_actions):
            _label, handler = self._menu_actions[idx]
            handler()

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def open_language(self):
        dlg = LanguageDialog(self)
        dlg.ShowModal()
        changed = dlg.changed
        dlg.Destroy()
        if changed:
            self._rebuild_ui()

    def _rebuild_ui(self):
        """Panel ve tüm çocuklarını yok edip _build_ui()'yi tekrar
        çağırır - dil değiştiğinde menüyü anında yeni dilde yeniden
        çizmek için kullanılır."""
        for child in list(self.GetChildren()):
            child.Destroy()
        self._build_ui()
        self.Layout()

    def open_tickets_from_menu(self):
        """Ana menüden 'Biletlerim' seçilince açılır. Tek hesap kuralı
        gereği bu makinede en fazla bir kayıt olabileceğinden,
        kullanıcı adını mevcut kayıttan alır. Henüz hiç hesap
        oluşturulmamışsa (ilk açılış), önce oyuna başlamasını ister."""
        saves = list_saves()
        if not saves:
            wx.MessageBox(
                t("menu.no_account_for_tickets_body"),
                t("menu.no_account_for_tickets_title"), wx.OK | wx.ICON_INFORMATION
            )
            speak(t("menu.no_account_for_tickets_speak"))
            return

        username = saves[0]
        dlg = TicketsDialog(self, username, self.audio)
        dlg.ShowModal()
        dlg.Destroy()

    def open_privacy_policy(self):
        """Ana menüden 'Gizlilik Politikası' seçilince açılır. Salt
        okunur - ilk açılıştaki zorunlu onay ekranından farklı olarak
        burada kabul/reddet YOKTUR, sadece okuyup kapatırsınız."""
        for label_key, filename in TERMS_FILES:
            if label_key == "terms.tab_privacy":
                dlg = DocumentViewerDialog(self, "menu.item_privacy_policy", filename)
                dlg.ShowModal()
                dlg.Destroy()
                return

    def open_terms_of_service(self):
        """Ana menüden 'Kullanım Şartları' seçilince açılır. Salt
        okunur - ilk açılıştaki zorunlu onay ekranından farklı olarak
        burada kabul/reddet YOKTUR, sadece okuyup kapatırsınız."""
        for label_key, filename in TERMS_FILES:
            if label_key == "terms.tab_terms":
                dlg = DocumentViewerDialog(self, "menu.item_terms_of_service", filename)
                dlg.ShowModal()
                dlg.Destroy()
                return

    def show_daily_message_now(self):
        """Ana menüden 'Günün Mesajını Görüntüle' seçilince açılır.
        main.py'deki OTOMATİK kontrolün (check_for_new_message) aksine,
        burada mesaj daha önce görülmüş olsa bile HER ZAMAN gösterilir.
        Ağ isteği ARKA PLANDA yapılır ki ana menü kilitlenmesin."""
        speak(t("menu.daily_message_fetching"))

        def worker():
            result = daily_message.fetch_daily_message()
            wx.CallAfter(self._on_daily_message_fetched, result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_daily_message_fetched(self, result):
        if result is None:
            wx.MessageBox(
                t("menu.daily_message_unavailable_body"),
                t("menu.daily_message_unavailable_title"), wx.OK | wx.ICON_INFORMATION
            )
            speak(t("menu.daily_message_unavailable_body"))
            return

        date_str, date_obj, messages = result
        message_text = daily_message.resolve_message(messages, i18n.get_language())
        if not message_text:
            wx.MessageBox(
                t("menu.daily_message_unavailable_body"),
                t("menu.daily_message_unavailable_title"), wx.OK | wx.ICON_INFORMATION
            )
            speak(t("menu.daily_message_unavailable_body"))
            return

        dlg = DailyMessageDialog(self, date_str, message_text)
        dlg.ShowModal()
        dlg.Destroy()

    def start_new_game(self):
        saves = list_saves()
        if saves:
            existing = saves[0]
            wx.MessageBox(
                t("menu.single_account_body", existing=existing),
                t("menu.single_account_title"), wx.OK | wx.ICON_WARNING
            )
            speak(t("menu.single_account_speak", existing=existing))
            return

        dlg = wx.TextEntryDialog(self, t("menu.username_prompt"), t("menu.username_prompt_title"))
        bind_typing_sound_to_dialog(dlg, self.audio)
        if dlg.ShowModal() == wx.ID_OK:
            username = dlg.GetValue().strip()
            dlg.Destroy()
            if not username:
                speak(t("menu.username_empty"))
                return
            self.username = username
            self.EndModal(ID_NEW)
        else:
            dlg.Destroy()
    
    def continue_game(self):
        saves = list_saves()
        if not saves:
            speak(t("menu.no_saved_game_speak"))
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
        dlg = wx.Dialog(self, title=t("leaderboard.loading_title"), size=(300, 150))
        dlg.CenterOnScreen()
        
        panel = wx.Panel(dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)
        loading_label = wx.StaticText(panel, label=t("leaderboard.loading_body"))
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
            wx.MessageBox(t("leaderboard.load_error", error=error), t("menu.unexpected_error_title"), wx.OK | wx.ICON_ERROR)
            return
        
        if scores is None:
            wx.MessageBox(
                t("leaderboard.load_failed_body"),
                t("leaderboard.load_failed_title"), wx.OK | wx.ICON_ERROR
            )
            speak(t("leaderboard.load_failed_speak"))
            return
        
        if not scores:
            wx.MessageBox(t("leaderboard.empty_body"), t("leaderboard.title"), wx.OK | wx.ICON_INFORMATION)
            return
        
        dlg = wx.Dialog(self, title=t("leaderboard.title"), size=(500, 450))
        
        panel = wx.Panel(dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        title = wx.StaticText(panel, label=t("leaderboard.header"))
        title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        list_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        list_box.SetMinSize((460, 300))
        
        for i, entry in enumerate(scores, 1):
            username = entry.get("username", t("leaderboard.unknown_user"))
            cash = entry.get("cash", 0)

            label = t("leaderboard.entry_line", rank=i, username=username, cash=format_tl(cash))
            list_box.Append(label)
        
        sizer.Add(list_box, 1, wx.EXPAND | wx.ALL, 10)
        
        close_btn = wx.Button(panel, label=t("leaderboard.close_btn"))
        sizer.Add(close_btn, 0, wx.ALL | wx.CENTER, 10)
        
        panel.SetSizer(sizer)

        def _close_leaderboard(e):
            self.play_sound(self.sound_select)
            dlg.EndModal(wx.ID_OK)

        close_btn.Bind(wx.EVT_BUTTON, _close_leaderboard)
        dlg.CenterOnScreen()
        dlg.ShowModal()
        dlg.Destroy()

    def play_sound(self, sound_path):
        if os.path.exists(sound_path):
            self.audio.play_sound(sound_path)


class LoadGameDialog(wx.Dialog):
    def __init__(self, parent, saves):
        super().__init__(parent, title=t("loadgame.title"), size=(350, 400))
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
        
        title = wx.StaticText(panel, label=t("loadgame.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 15)
        
        self.save_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.save_list.SetItems(self.saves)
        if self.saves:
            self.save_list.SetSelection(0)
        sizer.Add(self.save_list, 1, wx.EXPAND | wx.ALL, 10)
        
        info = wx.StaticText(panel, label=t("loadgame.nav_hint"))
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 5)
        
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.load_btn = wx.Button(panel, label=t("loadgame.load_btn"))
        self.delete_btn = wx.Button(panel, label=t("loadgame.delete_btn"))
        self.cancel_btn = wx.Button(panel, label=t("loadgame.cancel_btn"))
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
            speak(t("loadgame.loading_speak", username=self.selected_user))
            self.EndModal(wx.ID_OK)
        else:
            speak(t("loadgame.no_save_selected"))

    def on_delete_button(self, event):
        self.delete_selected()
    
    def on_cancel_button(self, event):
        self.play_sound(self.sound_navigate)
        self.EndModal(wx.ID_CANCEL)
    
    def delete_selected(self):
        idx = self.save_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak(t("loadgame.no_save_to_delete"))
            return
        if not self.saves or idx >= len(self.saves):
            return
        username = self.save_list.GetString(idx)
        if wx.MessageBox(t("loadgame.confirm_delete", username=username), t("loadgame.confirm_delete_title"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            delete_save(username)
            self.saves.remove(username)
            self.save_list.SetItems(self.saves)
            speak(t("loadgame.deleted_speak", username=username))
            self._last_spoken_index = -1
            if not self.saves:
                speak(t("loadgame.no_saves_left_speak"))
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
            parent, title=t("history.title"),
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

        title = wx.StaticText(panel, label=t("history.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        info = wx.StaticText(panel, label=t("history.hint"))
        sizer.Add(info, 0, wx.LEFT | wx.BOTTOM, 10)

        self.text_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_DONTWRAP
        )
        self.text_ctrl.SetMinSize((560, 380))
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(panel, label=t("history.refresh_btn"))
        self.close_btn = wx.Button(panel, label=t("history.close_btn"))
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
        from history_log import get_history
        entries = get_history()

        if not entries:
            self.text_ctrl.SetValue(t("history.empty"))
            return

        lines = []
        for entry in entries:
            day = entry.get("day")
            gun_str = t("history.day_prefix", day=day) if day is not None else ""
            lines.append(f"{entry['time']}  {gun_str}{entry['text']}")

        self.text_ctrl.SetValue("\n".join(lines))
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
            parent, title=t("daily_message.title"),
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

        title = wx.StaticText(panel, label=t("daily_message.header", date=date_str))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.text_ctrl = wx.TextCtrl(
            panel, value=message_text,
            style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.TE_AUTO_URL
        )
        self.text_ctrl.SetMinSize((470, 260))
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        self.close_btn = wx.Button(panel, label=t("daily_message.ok_btn"))
        sizer.Add(self.close_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.text_ctrl.Bind(wx.EVT_TEXT_URL, self.on_url_click)

    def on_url_click(self, event: wx.TextUrlEvent):
        
        mouse_event = event.GetMouseEvent()
        if mouse_event.LeftUp():
            url = self.text_ctrl.GetRange(event.GetURLStart(), event.GetURLEnd())
            try:
                webbrowser.open(url)
            except Exception:
                pass
        event.Skip()

    def on_key_down(self, event: wx.KeyEvent):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_OK)
            return
        event.Skip()


class CompanyDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title=t("company.title"), size=(650, 560))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("company.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        sizer.Add(wx.StaticText(panel, label=t("company.your_companies_label")),
                   0, wx.LEFT | wx.TOP, 10)
        self.company_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.company_list.SetMinSize((550, 100))
        sizer.Add(self.company_list, 0, wx.EXPAND | wx.ALL, 10)

        self.close_btn = wx.Button(panel, label=t("company.close_selected_btn"))
        sizer.Add(self.close_btn, 0, wx.ALL | wx.CENTER, 5)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label=t("company.new_company_label")), 0, wx.LEFT | wx.TOP, 5)

        guide = wx.StaticText(
            panel,
            label=t("company.guide"),
        )
        guide.Wrap(560)
        sizer.Add(guide, 0, wx.EXPAND | wx.ALL, 10)

        company_choices = [
            self._format_company_choice(key, data) for key, data in COMPANY_TYPES.items()
        ]

        type_sizer = wx.BoxSizer(wx.HORIZONTAL)
        type_sizer.Add(wx.StaticText(panel, label=t("company.type_label")), 0, wx.ALL | wx.CENTER, 5)
        self.type_combo = wx.ComboBox(panel, choices=company_choices, style=wx.CB_READONLY)
        for i, key in enumerate(COMPANY_TYPES.keys()):
            self.type_combo.SetClientData(i, key)
        type_sizer.Add(self.type_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(type_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.detail_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.detail_text.SetMinSize((550, 90))
        sizer.Add(self.detail_text, 0, wx.EXPAND | wx.ALL, 5)

        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_sizer.Add(wx.StaticText(panel, label=t("company.name_label")), 0, wx.ALL | wx.CENTER, 5)
        self.name_input = wx.TextCtrl(panel)
        bind_typing_sound(self.name_input, self.parent.audio)
        name_sizer.Add(self.name_input, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 5)

        city_sizer = wx.BoxSizer(wx.HORIZONTAL)
        city_sizer.Add(wx.StaticText(panel, label=t("company.city_label")), 0, wx.ALL | wx.CENTER, 5)
        self.city_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        city_sizer.Add(self.city_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(city_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.setup_btn = wx.Button(panel, label=t("company.setup_btn"))
        sizer.Add(self.setup_btn, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label=t("company.done_btn"))
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _format_company_choice(self, key, data):
        cost = data["setup_cost"]
        upkeep = data["daily_upkeep"]
        profit_min = data["daily_profit_min"]
        profit_max = data["daily_profit_max"]
        afford = t("company.can_setup") if self.state.cash >= cost else t("company.insufficient_cash")
        return t("company.type_choice_line", key=company_type_display_name(key), cost=f"{cost:,.0f}", upkeep=f"{upkeep:,.0f}",
                  profit_min=f"{profit_min:,.0f}", profit_max=f"{profit_max:,.0f}",
                  afford=afford, description=company_type_description(key))

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
                t("company.list_line", name=c['name'], city=c['city'], type=company_type_display_name(c['type']),
                  score=c['credit_score'], days=c['days_active'],
                  profit=format_tl(c['total_profit']), revenue=format_tl(c['monthly_revenue'])),
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
            self.detail_text.SetValue(t("company.select_type_hint"))
        else:
            self.type_combo.Enable(False)
            self.name_input.Enable(False)
            self.city_combo.Enable(False)
            self.setup_btn.Enable(False)
            self.detail_text.SetValue(t("company.no_free_city_hint"))

    def _get_selected_company_type(self):
        idx = self.type_combo.GetSelection()
        if idx == wx.NOT_FOUND:
            return ""
        return self.type_combo.GetClientData(idx)

    def on_company_select(self, event):
        idx = self.company_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.state.companies):
            c = self.state.companies[idx]
            speak(t("company.select_announce", name=c['name'], city=c['city']))

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
        afford_text = t("company.afford_yes") if affordable else t(
            "company.afford_no", amount=format_tl(cost - self.state.cash))

        detail = t("company.type_detail", type=company_type_display_name(company_type), cost=format_tl(cost),
                    upkeep=format_tl(upkeep), profit_min=format_tl(profit_min),
                    profit_max=format_tl(profit_max), description=company_type_description(company_type),
                    afford=afford_text)
        self.detail_text.SetValue(detail)

    def on_setup(self, event):
        company_type = self._get_selected_company_type()
        company_name = self.name_input.GetValue().strip()

        if not company_type:
            speak(t("company.select_type_first"))
            return

        if not company_name:
            speak(t("company.enter_name"))
            return

        c_idx = self.city_combo.GetSelection()
        if c_idx == wx.NOT_FOUND:
            speak(t("company.select_city"))
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
            speak(t("company.select_to_close"))
            return

        company_id = self.company_list.GetClientData(idx)
        company = self.state.get_company(company_id)
        name = f"{company['name']} ({company['city']})" if company else t("company.default_name")

        if wx.MessageBox(t("company.confirm_close", name=name), t("common.confirm_title"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
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
        super().__init__(parent, title=t("employees.title"), size=(700, 560))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("employees.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((640, 60))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label=t("employees.your_employees_label")), 0, wx.LEFT | wx.TOP, 10)
        self.employee_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.employee_list.SetMinSize((640, 130))
        sizer.Add(self.employee_list, 0, wx.EXPAND | wx.ALL, 10)

        self.fire_btn = wx.Button(panel, label=t("employees.fire_btn"))
        sizer.Add(self.fire_btn, 0, wx.ALL | wx.CENTER, 5)

        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 5)
        sizer.Add(wx.StaticText(panel, label=t("employees.new_hire_label")), 0, wx.LEFT | wx.TOP, 5)

        person_sizer = wx.BoxSizer(wx.HORIZONTAL)
        person_sizer.Add(wx.StaticText(panel, label=t("employees.person_label")), 0, wx.ALL | wx.CENTER, 5)
        self.person_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        person_sizer.Add(self.person_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(person_sizer, 0, wx.EXPAND | wx.ALL, 5)

        city_sizer = wx.BoxSizer(wx.HORIZONTAL)
        city_sizer.Add(wx.StaticText(panel, label=t("employees.city_label")), 0, wx.ALL | wx.CENTER, 5)
        self.city_combo = wx.ComboBox(panel, style=wx.CB_READONLY)
        city_sizer.Add(self.city_combo, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(city_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.detail_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.detail_text.SetMinSize((640, 60))
        sizer.Add(self.detail_text, 0, wx.EXPAND | wx.ALL, 5)

        self.hire_btn = wx.Button(panel, label=t("employees.hire_btn"))
        sizer.Add(self.hire_btn, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label=t("employees.done_btn"))
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
        self.employee_list.Clear()
        for e in self.state.employees:
            self.employee_list.Append(
                t("employees.list_line", name=e['name'], city=e['city'],
                  amount=format_tl(e.get('total_generated', 0.0)), days=e['days_until_salary']),
                e["id"],
            )
        self.fire_btn.Enable(len(self.state.employees) > 0)

        hire_cost = self.state.get_employee_hire_cost()
        salary = self.state.get_employee_salary()
        self.status_text.SetValue(
            t("employees.status_summary", count=len(self.state.employees),
              cost=format_tl(hire_cost), salary=format_tl(salary), cash=format_tl(self.state.cash))
        )

        self.person_combo.Clear()
        available_people = self.state.get_available_people()
        self.person_combo.AppendItems(available_people)
        if available_people:
            self.person_combo.SetSelection(0)

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
            self.detail_text.SetValue(t("employees.none_available"))
        elif not self.available_cities:
            self.detail_text.SetValue(t("employees.no_free_city"))
        else:
            self.detail_text.SetValue(
                t("employees.hire_detail", cost=format_tl(hire_cost), salary=format_tl(salary))
            )

    def on_employee_select(self, event):
        idx = self.employee_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        employee_id = self.employee_list.GetClientData(idx)
        e = self.state.get_employee(employee_id)
        if e:
            speak(t("employees.select_announce", name=e['name'], city=e['city'],
                    amount=format_tl(e.get('total_generated', 0.0))))

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
            speak(t("employees.select_person"))
            return
        if c_idx == wx.NOT_FOUND:
            speak(t("employees.select_city"))
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
            speak(t("employees.select_to_fire"))
            return

        employee_id = self.employee_list.GetClientData(idx)
        e = self.state.get_employee(employee_id)
        name = e["name"] if e else t("employees.default_name")

        if wx.MessageBox(t("employees.confirm_fire", name=name), t("common.confirm_title"), wx.YES_NO | wx.ICON_WARNING) == wx.YES:
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
        super().__init__(parent, title=t("informant.title"), size=(440, 320))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("informant.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        info = wx.StaticText(
            panel,
            label=t("informant.info"),
        )
        info.Wrap(380)
        sizer.Add(info, 0, wx.EXPAND | wx.ALL, 10)

        self.status_text = wx.StaticText(panel, label="")
        sizer.Add(self.status_text, 0, wx.ALL | wx.CENTER, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.hire_btn = wx.Button(panel, label=t("informant.hire_btn"))
        self.fire_btn = wx.Button(panel, label=t("informant.fire_btn"))
        btn_sizer.Add(self.hire_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.fire_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label=t("informant.done_btn"))
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
                t("informant.has_status", upkeep=format_tl(daily_upkeep))
            )
            self.hire_btn.Enable(False)
            self.fire_btn.Enable(True)
        else:
            self.status_text.SetLabel(
                t("informant.no_status", cost=format_tl(hire_cost), upkeep=format_tl(daily_upkeep))
            )
            self.hire_btn.Enable(True)
            self.fire_btn.Enable(False)

    def on_hire(self, event):
        success, msg = self.state.hire_informant()
        speak(msg)
        if success:
            self._update_ui()

    def on_fire(self, event):
        if wx.MessageBox(t("informant.confirm_fire"), t("common.confirm_title"),
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

        title = wx.StaticText(panel, label=t("bankloan.title"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((480, 130))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label=t("bankloan.packages_label")), 0, wx.LEFT | wx.TOP, 10)
        self.option_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.option_list.SetMinSize((480, 100))
        sizer.Add(self.option_list, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.take_btn = wx.Button(panel, label=t("bankloan.take_btn"))
        self.payoff_btn = wx.Button(panel, label=t("bankloan.payoff_btn"))
        btn_sizer.Add(self.take_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.payoff_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label=t("bankloan.done_btn"))
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
                t("bankloan.active_status",
                  amount=format_tl(self.state.loan_amount),
                  debt=format_tl(self.state.loan_total_debt),
                  installment=format_tl(self.state.loan_installment_amount),
                  days=self.state.loan_days_until_installment,
                  remaining=remaining_installments,
                  rate=f"{self.state.loan_interest_rate*100:.1f}",
                  score=self.state.get_average_credit_score())
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
                    t("bankloan.no_options_status", score=self.state.get_average_credit_score())
                )
                self.option_list.Enable(False)
            else:
                limit = self.state.get_loan_limit()
                self.status_text.SetValue(
                    t("bankloan.options_status", score=self.state.get_average_credit_score(),
                      limit=format_tl(limit), rate=f"{tier['interest_rate']*100:.1f}")
                )
                for opt in self.options:
                    self.option_list.Append(
                        t("bankloan.option_line", label=opt['label'], amount=f"{opt['amount']:,.0f}",
                          installments=opt['installments'], installment_amount=f"{opt['installment_amount']:,.0f}",
                          total_debt=f"{opt['total_debt']:,.0f}")
                    )
                self.option_list.Enable(True)
            self.take_btn.Enable(bool(self.options))

    def on_option_select(self, event):
        idx = self.option_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.options):
            opt = self.options[idx]
            speak(t("bankloan.option_select_announce", label=opt['label'],
                    amount=f"{opt['amount']:,.0f}", installments=opt['installments']))

    def on_take_loan(self, event):
        idx = self.option_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.options):
            speak(t("bankloan.select_package"))
            return

        opt = self.options[idx]
        success, msg = self.state.take_loan(opt["amount"], opt["installments"])
        speak(msg)
        if success:
            self._update_ui()

    def on_payoff(self, event):
        if wx.MessageBox(t("bankloan.confirm_payoff"), t("common.confirm_title"),
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
        super().__init__(parent, title=t("landloan.title"), size=(540, 480))
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
        title = wx.StaticText(panel, label=t("landloan.header", type=land_type_display_name(land['type'])))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((480, 130))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label=t("bankloan.packages_label")), 0, wx.LEFT | wx.TOP, 10)
        self.option_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.option_list.SetMinSize((480, 100))
        sizer.Add(self.option_list, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.take_btn = wx.Button(panel, label=t("bankloan.take_btn"))
        self.payoff_btn = wx.Button(panel, label=t("bankloan.payoff_btn"))
        btn_sizer.Add(self.take_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.payoff_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label=t("bankloan.done_btn"))
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
                t("landloan.active_status",
                  amount=format_tl(land.get('loan_amount', 0.0)), debt=format_tl(debt),
                  installment=format_tl(land.get('loan_installment_amount', 0.0)),
                  days=land.get('loan_days_until_installment', 30),
                  remaining=total_installments - paid_installments,
                  rate=f"{land.get('loan_interest_rate', 0.15)*100:.1f}")
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
                self.status_text.SetValue(t("landloan.no_limit_status"))
                self.option_list.Enable(False)
            else:
                limit = self.state.get_land_loan_limit(self.land_index)
                self.status_text.SetValue(
                    t("landloan.options_status", limit=format_tl(limit))
                )
                for opt in self.options:
                    self.option_list.Append(
                        t("bankloan.option_line", label=opt['label'], amount=f"{opt['amount']:,.0f}",
                          installments=opt['installments'], installment_amount=f"{opt['installment_amount']:,.0f}",
                          total_debt=f"{opt['total_debt']:,.0f}")
                    )
                self.option_list.Enable(True)
            self.take_btn.Enable(bool(self.options))

    def on_option_select(self, event):
        idx = self.option_list.GetSelection()
        if idx != wx.NOT_FOUND and idx < len(self.options):
            opt = self.options[idx]
            speak(t("bankloan.option_select_announce", label=opt['label'],
                    amount=f"{opt['amount']:,.0f}", installments=opt['installments']))

    def on_take_loan(self, event):
        idx = self.option_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.options):
            speak(t("bankloan.select_package"))
            return

        opt = self.options[idx]
        success, msg = self.state.take_land_loan(self.land_index, opt["amount"], opt["installments"])
        speak(msg)
        if success:
            self._update_ui()

    def on_payoff(self, event):
        if wx.MessageBox(t("landloan.confirm_payoff"), t("common.confirm_title"),
                          wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        success, msg = self.state.pay_land_loan_full(self.land_index)
        speak(msg)
        if success:
            self._update_ui()


class BankingDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title=t("banking.title"), size=(400, 250))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("banking.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.StaticText(panel, label="")
        sizer.Add(self.status_text, 0, wx.ALL | wx.CENTER, 10)

        self.interest_text = wx.StaticText(
            panel,
            label=t("banking.interest_note")
        )
        sizer.Add(self.interest_text, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label=t("banking.done_btn"))
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        self.status_text.SetLabel(
            t("banking.cash_status", cash=format_tl(self.state.cash))
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
        ("kirmizi", "gambling.bet_red"),
        ("siyah", "gambling.bet_black"),
        ("cift", "gambling.bet_even"),
        ("tek", "gambling.bet_odd"),
        ("1-18", "gambling.bet_1_18"),
        ("19-36", "gambling.bet_19_36"),
        ("1.duzine", "gambling.bet_dozen1"),
        ("2.duzine", "gambling.bet_dozen2"),
        ("3.duzine", "gambling.bet_dozen3"),
        ("sayi", "gambling.bet_single_number"),
    ]

    SOUND_CARK = resource_path("sounds/cark.mp3")

    # Pan (stereo döndürme) güncelleme sıklığı. ~33 Hz - kulakla fark
    # edilecek kadar sık ama gereksiz CPU harcamayacak kadar seyrek.
    PAN_UPDATE_MS = 30
    # Dönüşün BAŞLANGIÇTAKİ hızı (saniyede tam tur), bu aralıktan
    # rastgele seçilir. ÖNEMLİ: bunu bilerek DÜŞÜK tutuyoruz - insan
    # kulağı saniyede ~1-1.5 turu geçen bir dönüşü YÖN olarak değil,
    # bir titreşim/tremolo gibi algılar. Çark, gerçek bir rulet gibi
    # sabit bir yavaşlamayla (friksiyon) bu hızdan başlayıp, sesin tam
    # bitişinde hıza sıfıra inecek şekilde YAVAŞLAYARAK durur.
    SPIN_INITIAL_SPEED_MIN = 0.9   # tur/saniye
    SPIN_INITIAL_SPEED_MAX = 1.4   # tur/saniye

    def __init__(self, parent, state):
        super().__init__(parent, title=t("gambling.title"), size=(480, 560))
        self.parent = parent
        self.state = state
        self.pending_bets = []
        self.spin_timer = None
        self.is_spinning = False
        # 3D/binaural döndürme efekti için:
        self.pan_timer = None
        self.spin_channel = None
        self.spin_start_time = 0.0
        self.spin_duration = 0.0
        self.spin_initial_speed = 0.0

        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("gambling.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.cash_text = wx.StaticText(panel, label="")
        sizer.Add(self.cash_text, 0, wx.ALL | wx.CENTER, 5)

        bet_labels = [t(label_key) for _, label_key in self.BET_CHOICES]
        self.bet_type_radio = wx.RadioBox(panel, label=t("gambling.bet_type_label"), choices=bet_labels,
                                           majorDimension=1, style=wx.RA_SPECIFY_COLS)
        sizer.Add(self.bet_type_radio, 0, wx.EXPAND | wx.ALL, 10)

        number_sizer = wx.BoxSizer(wx.HORIZONTAL)
        number_sizer.Add(wx.StaticText(panel, label=t("gambling.number_label")),
                          0, wx.ALL | wx.CENTER, 5)
        self.number_spinner = wx.SpinCtrl(panel, value="0", min=0, max=36)
        bind_typing_sound(self.number_spinner, self.parent.audio)
        self.number_spinner.Disable()
        number_sizer.Add(self.number_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(number_sizer, 0, wx.EXPAND | wx.ALL, 5)

        amount_sizer = wx.BoxSizer(wx.HORIZONTAL)
        amount_sizer.Add(wx.StaticText(panel, label=t("gambling.amount_label")), 0, wx.ALL | wx.CENTER, 5)
        self.amount_spinner = wx.SpinCtrl(panel, value="100", min=1, max=100000000)
        bind_typing_sound(self.amount_spinner, self.parent.audio)
        amount_sizer.Add(self.amount_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(amount_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.add_bet_btn = wx.Button(panel, label=t("gambling.add_bet_btn"))
        sizer.Add(self.add_bet_btn, 0, wx.ALL | wx.CENTER, 5)

        sizer.Add(wx.StaticText(panel, label=t("gambling.added_bets_label")), 0, wx.LEFT | wx.TOP, 10)
        self.bets_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.bets_list.SetMinSize((420, 90))
        sizer.Add(self.bets_list, 0, wx.EXPAND | wx.ALL, 10)

        self.remove_bet_btn = wx.Button(panel, label=t("gambling.remove_bet_btn"))
        sizer.Add(self.remove_bet_btn, 0, wx.ALL | wx.CENTER, 5)

        self.status_text = wx.StaticText(panel, label=t("gambling.initial_status"))
        self.status_text.Wrap(440)
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.spin_btn = wx.Button(panel, label=t("gambling.spin_btn"))
        self.close_btn = wx.Button(panel, label=t("gambling.close_btn"))
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
        self.cash_text.SetLabel(t("gambling.cash_label", cash=format_tl(self.state.cash)))

    def on_bet_type_changed(self, event):
        idx = self.bet_type_radio.GetSelection()
        bet_type = self.BET_CHOICES[idx][0]
        self.number_spinner.Enable(bet_type == "sayi")

    def _total_pending(self) -> float:
        return sum(b["amount"] for b in self.pending_bets)

    def on_add_bet(self, event):
        idx = self.bet_type_radio.GetSelection()
        if idx == wx.NOT_FOUND:
            speak(t("gambling.select_bet_type"))
            return
        bet_type, label_key = self.BET_CHOICES[idx]
        label = t(label_key)
        amount = float(self.amount_spinner.GetValue())
        if amount <= 0:
            speak(t("gambling.enter_valid_amount"))
            return

        if self._total_pending() + amount > self.state.cash:
            speak(t("gambling.insufficient_balance"))
            return

        number = None
        display = label
        if bet_type == "sayi":
            number = self.number_spinner.GetValue()
            display = t("gambling.single_number_display", number=number)

        self.pending_bets.append({"type": bet_type, "number": number, "amount": amount})
        self.bets_list.Append(t("gambling.bet_added_line", display=display, amount=format_tl(amount)))
        speak(t("gambling.bet_added_speak", display=display, amount=format_tl(amount)))

    def on_remove_bet(self, event):
        idx = self.bets_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak(t("gambling.select_bet_to_remove"))
            return
        self.pending_bets.pop(idx)
        self.bets_list.Delete(idx)
        speak(t("gambling.bet_removed_speak"))

    def on_spin(self, event):
        if self.is_spinning:
            return
        if not self.pending_bets:
            speak(t("gambling.add_bet_first"))
            return

        total_bet = self._total_pending()
        if self.state.cash < total_bet:
            speak(t("gambling.insufficient_balance_generic"))
            return

        self.is_spinning = True
        self._set_controls_enabled(False)
        self.status_text.SetLabel(t("gambling.spinning_status"))
        speak(t("gambling.spinning_speak"))

        duration = _get_spin_sound_duration(self.SOUND_CARK)
        initial_speed = random.uniform(
            self.SPIN_INITIAL_SPEED_MIN, self.SPIN_INITIAL_SPEED_MAX
        )

        channel = None
        live_pan = False
        if self.parent:
            # ÖNCELİK: sesi baştan, kafanın etrafında (ön->sağ->arka->sol->ön)
            # gerçekten dönecek şekilde (ITD + ILD + ön/arka boğukluk
            # ile) işleyip öyle çalıyoruz. Bu, sadece sol<->sağ giden
            # basit bir pan'dan farklı olarak GERÇEK bir 3D/binaural
            # döngü hissi verir.
            channel, real_length = self.parent.audio.play_rotating_spin_sound(
                self.SOUND_CARK, duration, initial_speed
            )
            if channel is not None and real_length > 0:
                duration = real_length
            else:
                # numpy yoksa ya da işlem başarısız olursa: canlı
                # (yalnızca sol/sağ) pan güncellemesine düşüyoruz.
                channel, real_length = self.parent.audio.play_panned_sound(self.SOUND_CARK)
                if real_length > 0:
                    duration = real_length
                live_pan = channel is not None

        self.spin_channel = channel
        self.spin_start_time = time.time()
        self.spin_duration = duration
        self.spin_initial_speed = initial_speed

        if live_pan:
            self.pan_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_spin_pan_tick, self.pan_timer)
            self.pan_timer.Start(self.PAN_UPDATE_MS)
        else:
            # Döndürme efekti sesin içine zaten baştan işlendi (ya da
            # ses hiç çalınamadı) - burada sadece süre kadar bekleyip
            # sonucu açıklıyoruz.
            self.spin_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_spin_finished, self.spin_timer)
            self.spin_timer.StartOnce(int(duration * 1000))

    def on_spin_pan_tick(self, event):
        """Yalnızca 3D/binaural üretim başarısız olduğunda (numpy yok
        vb.) devreye giren YEDEK yol: çark sesi çalarken periyodik
        olarak çağrılır, sesin sol<->sağ arasında (basit stereo pan
        ile) gidip gelmesini sağlar. Ses (channel) durduğunda veya
        süresi dolduğunda sonucu açıklamaya geçer."""
        elapsed = time.time() - self.spin_start_time
        channel_finished = (
            self.spin_channel is not None and not self.spin_channel.get_busy()
        )

        if elapsed >= self.spin_duration or channel_finished:
            self.pan_timer.Stop()
            self.pan_timer = None
            if self.parent and self.spin_channel is not None:
                self.parent.audio.set_channel_pan(self.spin_channel, 0.0)
            self.on_spin_finished(None)
            return

        # Ana (binaural) yoldakiyle AYNI kinematik model: sabit
        # yavaşlama (friksiyon) - v(t) = v0*(1 - t/T). Bilerek düşük
        # bir başlangıç hızı (SPIN_INITIAL_SPEED_MIN/MAX) kullanıyoruz
        # çünkü kulak saniyede ~1-1.5 turu aşan dönüşleri yön olarak
        # değil, titreşim gibi algılar.
        t = min(elapsed, self.spin_duration)
        v0 = self.spin_initial_speed
        T = self.spin_duration if self.spin_duration > 0 else 1.0
        rotations = v0 * t - (v0 * t * t) / (2.0 * T)
        angle = rotations * 2 * math.pi

        # Dönmekte olan bir ses kaynağının azimut açısının stereo
        # izdüşümü: sin(angle), sesin sürekli sol<->sağ arasında
        # kayması ile 'etrafımızda dönüyor' hissini verir.
        pan = math.sin(angle)
        if self.parent and self.spin_channel is not None:
            self.parent.audio.set_channel_pan(self.spin_channel, pan)

    def on_spin_finished(self, event):
        if self.spin_timer:
            self.spin_timer.Stop()
            self.spin_timer = None
        if self.pan_timer:
            self.pan_timer.Stop()
            self.pan_timer = None
        self.spin_channel = None

        result = self.state.play_roulette(self.pending_bets)
        self.is_spinning = False

        if not result.get("success"):
            speak(result.get("message", t("gambling.spin_failed_default")))
            self.status_text.SetLabel(t("gambling.spin_failed_status"))
            self._set_controls_enabled(True)
            return

        winning_number = result["winning_number"]
        winning_color = get_roulette_color_label(result["winning_color"])
        net = result["net"]

        lines = [t("gambling.result_landed", number=winning_number, color=winning_color)]
        for br in result["bet_results"]:
            label = ROULETTE_BET_LABELS.get(br["type"], br["type"])
            if br["type"] == "sayi":
                label = f"{label} {br['number']}"
            if br["won"]:
                lines.append(t("gambling.result_won", label=label, amount=format_tl(br['payout'])))
            else:
                lines.append(t("gambling.result_lost", label=label, amount=format_tl(br['amount'])))

        total_won = sum(br["payout"] for br in result["bet_results"] if br["won"])
        if total_won > 0:
            lines.append(t("gambling.result_total_won", amount=format_tl(total_won)))
        if net >= 0:
            lines.append(t("gambling.result_total_profit", amount=format_tl(net)))
        else:
            lines.append(t("gambling.result_total_loss", amount=format_tl(abs(net))))

        summary = " ".join(lines)
        self.status_text.SetLabel(summary)

        # Sesli anons: çok sayıda bahiste her bir bahsin tek tek
        # "kazandı / kaybetti" diye okunması uzun sürüyordu. Artık
        # yalnızca hangi sayının geldiği ile toplam kazanç/kâr (ya da
        # zarar) özet olarak seslendiriliyor; bahis bahis dökümü
        # yukarıdaki status_text üzerinde (yazılı olarak) duruyor.
        speech_parts = [t("gambling.result_landed", number=winning_number, color=winning_color)]
        if total_won > 0:
            speech_parts.append(t("gambling.result_total_won", amount=format_tl(total_won)))
        if net >= 0:
            speech_parts.append(t("gambling.result_total_profit", amount=format_tl(net)))
        else:
            speech_parts.append(t("gambling.result_total_loss", amount=format_tl(abs(net))))
        speak(" ".join(speech_parts))

        self._update_ui()
        if self.parent:
            self.parent.update_wallet_display()
            self.parent.auto_save()

        self.pending_bets = []
        self.bets_list.Clear()

        self.spin_btn.SetLabel(t("gambling.spin_btn"))
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
            speak(t("gambling.spinning_block_close"))
            if hasattr(event, "Veto"):
                event.Veto()
            return
        self.EndModal(wx.ID_OK)


class AuctionDialog(wx.Dialog):
    """
    AÇIK ARTIRMA EKRANI - GERÇEK ZAMANLI, CANLI AÇIK ARTIRMA
    ---------------------------------------------------------
    Ekran açıldığında rastgele bir eşya seçilir ve "X ürünü X fiyatından
    satılıyor, teklifler nedir?" tarzı bir açılış anonsu yapılır (bkz.
    GameState.start_new_auction). Oyuncu hiçbir şey yapmak zorunda
    değildir - sadece izleyebilir: geri sayım süresi boyunca (varsayılan
    60 saniye, ayarlanabilir) 2-4 gerçek rakip KENDİLİĞİNDEN teklif
    verebilir (bkz. GameState.tick_auction), ve belirli aralıklarla
    "X ürünü X fiyatına satılıyor" hatırlatma anonsları yapılır. Süre
    boyunca kimse daha yüksek teklif vermezse, o anki en yüksek teklifi
    veren kazanır. Süre dolduğunda kısa bir aradan sonra YENİ bir eşya
    için otomatik olarak yeni bir açık artırma başlar - ekran açık
    kaldığı sürece canlı akış devam eder.

    Bir wx.Timer ile saniyede bir güncellenir (bkz. on_timer); pencere
    kapanırken zamanlayıcı DURDURULUR (bkz. _stop_timer) ki arka planda
    çalışmaya devam edip artık var olmayan kontrollere erişmeye çalışıp
    çökmesin.
    """

    TICK_MS = 1000
    RESTART_DELAY_SECONDS = 3.0

    def __init__(self, parent, state):
        super().__init__(parent, title=t("auction.title"), size=(560, 700),
                          style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.parent = parent
        self.state = state
        self.awaiting_restart = False
        self.restart_at = 0.0

        self._build_ui()
        self._bind_events()
        self.CenterOnScreen()

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)

        self._begin_new_auction_round(initial=True)
        self.timer.Start(self.TICK_MS)

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("auction.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.cash_text = wx.StaticText(panel, label="")
        sizer.Add(self.cash_text, 0, wx.ALL | wx.CENTER, 5)

        self.item_text = wx.StaticText(panel, label="")
        self.item_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(self.item_text, 0, wx.ALL | wx.CENTER, 5)

        self.price_text = wx.StaticText(panel, label="")
        sizer.Add(self.price_text, 0, wx.ALL | wx.CENTER, 3)

        self.countdown_text = wx.StaticText(panel, label="")
        sizer.Add(self.countdown_text, 0, wx.ALL | wx.CENTER, 3)

        self.bidders_text = wx.StaticText(panel, label="")
        sizer.Add(self.bidders_text, 0, wx.LEFT | wx.RIGHT, 10)

        sizer.Add(wx.StaticText(panel, label=t("auction.history_label")), 0, wx.LEFT | wx.TOP, 10)
        self.history_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.history_box.SetMinSize((520, 120))
        sizer.Add(self.history_box, 0, wx.EXPAND | wx.ALL, 10)

        bid_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bid_sizer.Add(wx.StaticText(panel, label=t("auction.bid_amount_label")), 0, wx.ALL | wx.CENTER, 5)
        self.bid_spinner = wx.SpinCtrlDouble(panel, value="0", min=0, max=999999999, inc=1000)
        self.bid_spinner.SetDigits(0)
        bind_typing_sound(self.bid_spinner, self.parent.audio)
        bid_sizer.Add(self.bid_spinner, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(bid_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.bid_btn = wx.Button(panel, label=t("auction.bid_btn"))
        sizer.Add(self.bid_btn, 0, wx.ALL | wx.CENTER, 5)

        self.status_text = wx.StaticText(panel, label="")
        self.status_text.Wrap(520)
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        duration_sizer = wx.BoxSizer(wx.HORIZONTAL)
        duration_sizer.Add(wx.StaticText(panel, label=t("auction.duration_setting_label")), 0, wx.ALL | wx.CENTER, 5)
        self.duration_spinner = wx.SpinCtrl(
            panel, min=self.state.AUCTION_MIN_DURATION_SECONDS,
            max=self.state.AUCTION_MAX_DURATION_SECONDS,
            initial=self.state.get_auction_duration_seconds(),
        )
        bind_typing_sound(self.duration_spinner, self.parent.audio)
        duration_sizer.Add(self.duration_spinner, 0, wx.ALL | wx.CENTER, 5)
        self.duration_apply_btn = wx.Button(panel, label=t("auction.duration_apply_btn"))
        duration_sizer.Add(self.duration_apply_btn, 0, wx.ALL | wx.CENTER, 5)
        sizer.Add(duration_sizer, 0, wx.EXPAND | wx.ALL, 5)
        duration_hint = wx.StaticText(panel, label=t("auction.duration_hint"))
        duration_hint.Wrap(520)
        sizer.Add(duration_hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        sizer.Add(wx.StaticText(panel, label=t("auction.owned_label")), 0, wx.LEFT | wx.TOP, 5)
        self.owned_box = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.owned_box.SetMinSize((520, 70))
        sizer.Add(self.owned_box, 0, wx.EXPAND | wx.ALL, 10)

        self.sell_btn = wx.Button(panel, label=t("auction.sell_btn"))
        sizer.Add(self.sell_btn, 0, wx.ALL | wx.CENTER, 5)

        self.close_btn = wx.Button(panel, label=t("common.close"))
        sizer.Add(self.close_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)
        self.bid_btn.SetFocus()

    def _bind_events(self):
        self.bid_btn.Bind(wx.EVT_BUTTON, self.on_bid)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell)
        self.duration_apply_btn.Bind(wx.EVT_BUTTON, self.on_apply_duration)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def _stop_timer(self):
        if getattr(self, "timer", None) and self.timer.IsRunning():
            self.timer.Stop()

    def on_close(self, event):
        self._stop_timer()
        self.EndModal(wx.ID_OK)

    # ------------------------------------------------------------
    # Açık artırma turu akışı
    # ------------------------------------------------------------

    def _begin_new_auction_round(self, initial=False):
        self.awaiting_restart = False
        opening = self.state.start_new_auction()

        self._refresh_owned()
        self._refresh_history()
        self._update_item_and_price()
        self._update_bidders_label()
        self._sync_bid_spinner_min()
        self.bid_btn.Enable()

        self.status_text.SetLabel(opening["message"])
        self.status_text.Wrap(520)
        speak(opening["message"])

        if not initial and self.parent:
            self.parent.update_wallet_display()

    def on_timer(self, event):
        if self.awaiting_restart:
            if time.time() >= self.restart_at:
                self._begin_new_auction_round()
            else:
                self._update_countdown_label(0, waiting=True)
            return

        result = self.state.tick_auction()
        if result["resolved"]:
            return

        if result["bid_event"]:
            self._on_bid_event(result["bid_event"])

        if result["announcement"]:
            self.status_text.SetLabel(result["announcement"])
            self.status_text.Wrap(520)
            speak(result["announcement"])

        self._update_item_and_price()
        self._update_countdown_label(result["time_remaining"])
        self._update_bidders_label()

        if result["time_remaining"] <= 0:
            self._resolve_and_schedule_restart()

    def _on_bid_event(self, bid_event):
        self._refresh_history()
        message = t(
            "auction.npc_bid_event",
            npc=bid_event["label"], amount=format_tl(bid_event["amount"]),
        )
        speak(message)

    def _resolve_and_schedule_restart(self):
        result = self.state.resolve_current_auction()

        self.status_text.SetLabel(result["message"])
        self.status_text.Wrap(520)
        speak(result["message"])

        self._refresh_history()
        self._refresh_owned()
        self.cash_text.SetLabel(t("auction.cash_label", amount=format_tl(self.state.cash)))
        self.bid_btn.Disable()

        if self.parent:
            self.parent.update_wallet_display()
            self.parent.auto_save()

        self.awaiting_restart = True
        self.restart_at = time.time() + self.RESTART_DELAY_SECONDS
        self.countdown_text.SetLabel(t("auction.next_auction_starting"))

    # ------------------------------------------------------------
    # Görüntü güncellemeleri
    # ------------------------------------------------------------

    def _update_item_and_price(self):
        entry = self.state.auction_current
        if not entry:
            return
        self.item_text.SetLabel(auction_item_display_name(entry["item_id"]))
        self.price_text.SetLabel(t("auction.current_price_label", amount=format_tl(entry["current_price"])))
        self.cash_text.SetLabel(t("auction.cash_label", amount=format_tl(self.state.cash)))

    def _update_countdown_label(self, remaining, waiting=False):
        if waiting:
            self.countdown_text.SetLabel(t("auction.next_auction_starting"))
            return
        self.countdown_text.SetLabel(t("auction.time_remaining_label", seconds=max(0, int(remaining) + (1 if remaining > 0 else 0))))

    def _update_bidders_label(self):
        active_count = self.state.get_auction_active_bidder_count()
        self.bidders_text.SetLabel(t("auction.active_bidders_label", count=active_count))

    def _refresh_history(self):
        self.history_box.Clear()
        for row in self.state.get_auction_bid_history():
            self.history_box.Append(t("auction.history_row", who=row["label"], amount=format_tl(row["amount"])))
        if self.history_box.GetCount() > 0:
            self.history_box.SetSelection(self.history_box.GetCount() - 1)

    def _refresh_owned(self):
        self.owned_box.Clear()
        for item_id, qty, name in self.state.get_auction_inventory_summary():
            self.owned_box.Append(t("auction.owned_row", item=name, qty=qty))

    def _sync_bid_spinner_min(self):
        entry = self.state.auction_current
        if entry:
            min_bid = entry["current_price"] + 1
            self.bid_spinner.SetRange(min_bid, 999999999)
            self.bid_spinner.SetValue(min_bid)

    # ------------------------------------------------------------
    # Kullanıcı eylemleri
    # ------------------------------------------------------------

    def on_bid(self, event):
        if self.awaiting_restart:
            speak(t("auction.no_active_auction"))
            return

        bid_amount = round(self.bid_spinner.GetValue(), 2)
        result = self.state.place_live_auction_bid(bid_amount)

        self.status_text.SetLabel(result["message"])
        self.status_text.Wrap(520)
        speak(result["message"])

        if result["success"]:
            self._refresh_history()
            self._update_item_and_price()
            self._update_bidders_label()
            self._sync_bid_spinner_min()
            if self.parent:
                self.parent.update_wallet_display()

    def on_apply_duration(self, event):
        applied = self.state.set_auction_duration_seconds(self.duration_spinner.GetValue())
        self.duration_spinner.SetValue(applied)
        message = t("auction.duration_applied_message", seconds=applied)
        self.status_text.SetLabel(message)
        self.status_text.Wrap(520)
        speak(message)

    def on_sell(self, event):
        idx = self.owned_box.GetSelection()
        owned = self.state.get_auction_inventory_summary()
        if idx == wx.NOT_FOUND or idx >= len(owned):
            speak(t("auction.select_owned_first"))
            return
        item_id = owned[idx][0]

        success, msg = self.state.sell_auction_item(item_id)
        self.status_text.SetLabel(msg)
        self.status_text.Wrap(520)
        speak(msg)

        if success:
            self._refresh_owned()
            self.cash_text.SetLabel(t("auction.cash_label", amount=format_tl(self.state.cash)))
            if self.parent:
                self.parent.update_wallet_display()
                self.parent.auto_save()


class NewTicketDialog(wx.Dialog):
    """Yeni bir destek bileti (GitHub Issue) açmak için kullanılan pencere.
    Konu ve mesaj girilir; gönderim arka planda yapılır, pencere bu
    sırada kilitlenir ki oyuncu aynı bileti iki kez göndermesin."""

    def __init__(self, parent, username, audio_manager, extra_info=None):
        super().__init__(parent, title=t("newticket.title"), size=(520, 420),
                          style=wx.DEFAULT_DIALOG_STYLE)
        self.username = username
        self.audio = audio_manager
        self.extra_info = extra_info or {}
        self.created_ticket = None
        self._sending = False

        self._build_ui()
        self._bind_events()
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("newticket.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        sizer.Add(wx.StaticText(panel, label=t("newticket.subject_label")), 0, wx.LEFT | wx.TOP, 10)
        self.subject_ctrl = wx.TextCtrl(panel)
        bind_typing_sound(self.subject_ctrl, self.audio)
        sizer.Add(self.subject_ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        sizer.Add(wx.StaticText(panel, label=t("newticket.message_label")), 0, wx.LEFT | wx.TOP, 10)
        self.message_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.message_ctrl.SetMinSize((440, 200))
        bind_typing_sound(self.message_ctrl, self.audio)
        sizer.Add(self.message_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        self.status_label = wx.StaticText(panel, label="")
        sizer.Add(self.status_label, 0, wx.LEFT | wx.BOTTOM, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.send_btn = wx.Button(panel, label=t("newticket.send_btn"))
        self.load_log_btn = wx.Button(panel, label=t("newticket.load_log_btn"))
        self.cancel_btn = wx.Button(panel, label=t("newticket.cancel_btn"))
        btn_sizer.Add(self.send_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.load_log_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)
        wx.CallAfter(self.subject_ctrl.SetFocus)

    def _bind_events(self):
        self.send_btn.Bind(wx.EVT_BUTTON, self.on_send)
        self.load_log_btn.Bind(wx.EVT_BUTTON, self.on_load_log)
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.Bind(wx.EVT_CLOSE, self.on_cancel)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

    def on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE and not self._sending:
            self.on_cancel(event)
            return
        event.Skip()

    def on_load_log(self, event):
        """Oyun geçmişini (history_log) ve konsol çıktılarının
        toplandığı dosyayı (app_log) mesaj kutusuna ekler - destek
        ekibinin sorunu teşhis etmesine yardımcı olur."""
        if self._sending:
            return

        parts = []
        try:
            from history_log import get_history
            entries = get_history()
            if entries:
                lines = []
                for entry in entries:
                    day = entry.get("day")
                    gun_str = t("history.day_prefix", day=day) if day is not None else ""
                    lines.append(f"{entry['time']}  {gun_str}{entry['text']}")
                parts.append(t("newticket.history_section", lines="\n".join(lines)))
        except Exception as e:
            print(f"[Bilet] Oyun geçmişi okunamadı: {e}")

        debug_tail = app_log.get_log_tail(max_chars=6000)
        if debug_tail:
            parts.append(t("newticket.app_log_section", tail=debug_tail))

        if not parts:
            wx.MessageBox(t("newticket.no_log_body"),
                           t("newticket.info_title"), wx.OK | wx.ICON_INFORMATION)
            speak(t("newticket.no_log_speak"))
            return

        log_text = "\n\n".join(parts)
        current = self.message_ctrl.GetValue()
        separator = "\n\n" if current.strip() else ""
        self.message_ctrl.SetValue(current + separator + t("newticket.log_added_prefix", text=log_text))
        self.message_ctrl.SetInsertionPointEnd()
        speak(t("newticket.log_added_speak"))

    def on_send(self, event):
        if self._sending:
            return

        subject = self.subject_ctrl.GetValue().strip()
        message = self.message_ctrl.GetValue().strip()

        if not subject or not message:
            wx.MessageBox(t("newticket.empty_fields_body"),
                           t("newticket.missing_info_title"), wx.OK | wx.ICON_WARNING)
            speak(t("newticket.empty_fields_speak"))
            return

        self._sending = True
        self.send_btn.Disable()
        self.cancel_btn.Disable()
        self.status_label.SetLabel(t("newticket.sending_status"))
        speak(t("newticket.sending_speak"))

        def worker():
            try:
                ticket = ticket_manager.create_ticket(
                    self.username, subject, message, extra_info=self.extra_info
                )
                wx.CallAfter(self._on_success, ticket)
            except Exception as e:
                wx.CallAfter(self._on_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, ticket):
        self._sending = False
        self.created_ticket = ticket
        self.audio.play_sound(SOUND_TICKET_SENT)
        speak(t("newticket.created_speak", number=ticket['number']))
        wx.MessageBox(
            t("newticket.created_body", number=ticket['number']),
            t("newticket.created_title"), wx.OK | wx.ICON_INFORMATION
        )
        self.EndModal(wx.ID_OK)

    def _on_error(self, error_message):
        self._sending = False
        self.send_btn.Enable()
        self.cancel_btn.Enable()
        self.status_label.SetLabel("")
        wx.MessageBox(t("newticket.send_failed_body", error=error_message),
                       t("menu.unexpected_error_title"), wx.OK | wx.ICON_ERROR)
        speak(t("newticket.send_failed_speak"))

    def on_cancel(self, event):
        if self._sending:
            speak(t("newticket.cannot_close_while_sending"))
            if hasattr(event, "Veto"):
                event.Veto()
            return
        self.EndModal(wx.ID_CANCEL)


class TicketsDialog(wx.Dialog):
    """'Biletlerim' ekranı: oyuncunun açtığı biletlerin listesi, seçili
    biletin tüm yanıt geçmişi ve (bilet kapanmadığı sürece) tekrar
    yanıt yazabilme. Açıldığında ve her 'Yenile'de GitHub'dan güncel
    durum çekilir."""

    def __init__(self, parent, username, audio_manager, extra_info=None):
        super().__init__(parent, title=t("tickets.title"), size=(650, 560),
                          style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.username = username
        self.audio = audio_manager
        self.extra_info = extra_info or {}
        self.tickets = []
        self.selected_ticket = None
        self._busy = False

        self._build_ui()
        self._bind_events()
        self.CenterOnParent()
        self._reload_ticket_list()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("tickets.header"))
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        top_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.new_ticket_btn = wx.Button(panel, label=t("tickets.new_ticket_btn"))
        self.refresh_btn = wx.Button(panel, label=t("tickets.refresh_btn"))
        top_btn_sizer.Add(self.new_ticket_btn, 0, wx.ALL, 5)
        top_btn_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        sizer.Add(top_btn_sizer, 0, wx.ALIGN_CENTER, 5)

        sizer.Add(wx.StaticText(panel, label=t("tickets.your_tickets_label")), 0, wx.LEFT | wx.TOP, 10)
        self.ticket_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.ticket_list.SetMinSize((600, 110))
        sizer.Add(self.ticket_list, 0, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label=t("tickets.reply_history_label")), 0, wx.LEFT | wx.TOP, 5)
        self.thread_text = wx.TextCtrl(
            panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_WORDWRAP
        )
        self.thread_text.SetMinSize((600, 170))
        sizer.Add(self.thread_text, 1, wx.EXPAND | wx.ALL, 10)

        sizer.Add(wx.StaticText(panel, label=t("tickets.your_reply_label")), 0, wx.LEFT | wx.TOP, 5)
        self.reply_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        self.reply_ctrl.SetMinSize((600, 70))
        bind_typing_sound(self.reply_ctrl, self.audio)
        sizer.Add(self.reply_ctrl, 0, wx.EXPAND | wx.ALL, 10)

        bottom_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.reply_btn = wx.Button(panel, label=t("tickets.reply_btn"))
        self.close_btn = wx.Button(panel, label=t("tickets.close_btn"))
        bottom_btn_sizer.Add(self.reply_btn, 0, wx.ALL, 5)
        bottom_btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)
        sizer.Add(bottom_btn_sizer, 0, wx.ALIGN_CENTER, 10)

        panel.SetSizer(sizer)
        self._set_detail_controls_enabled(False)

    def _bind_events(self):
        self.new_ticket_btn.Bind(wx.EVT_BUTTON, self.on_new_ticket)
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.ticket_list.Bind(wx.EVT_LISTBOX, self.on_select_ticket)
        self.reply_btn.Bind(wx.EVT_BUTTON, self.on_reply)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_dialog)
        self.Bind(wx.EVT_CLOSE, self.on_close_dialog)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

    def on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE and not self.reply_ctrl.HasFocus():
            self.on_close_dialog(event)
            return
        event.Skip()

    def _set_detail_controls_enabled(self, enabled: bool):
        self.reply_ctrl.Enable(enabled)
        self.reply_btn.Enable(enabled)

    # -- Bilet listesi -----------------------------------------------

    def _reload_ticket_list(self):
        self.tickets = ticket_manager.list_local_tickets(self.username)
        self.ticket_list.Clear()

        if not self.tickets:
            self.ticket_list.Append(t("tickets.none_yet"))
            self.thread_text.SetValue("")
            self._set_detail_controls_enabled(False)
            return

        for tk in self.tickets:
            state_label = t("tickets.state_closed") if tk.get("state") == "closed" else t("tickets.state_open")
            self.ticket_list.Append(t("tickets.list_line", number=tk['number'], title=tk.get('title', ''), state=state_label))

        wx.CallAfter(self.ticket_list.SetSelection, 0)
        wx.CallAfter(self.on_select_ticket, None)

    def on_new_ticket(self, event):
        dlg = NewTicketDialog(self, self.username, self.audio, self.extra_info)
        result = dlg.ShowModal()
        dlg.Destroy()
        if result == wx.ID_OK:
            self._reload_ticket_list()

    def on_refresh(self, event):
        self._reload_ticket_list()

    # -- Seçili biletin detayı ----------------------------------------

    def on_select_ticket(self, event):
        idx = self.ticket_list.GetSelection()
        if idx == wx.NOT_FOUND or idx >= len(self.tickets):
            self.selected_ticket = None
            self._set_detail_controls_enabled(False)
            return

        self.selected_ticket = self.tickets[idx]
        self.thread_text.SetValue(t("tickets.loading"))
        self._set_detail_controls_enabled(False)

        ticket_number = self.selected_ticket["number"]

        def worker():
            try:
                thread = ticket_manager.fetch_ticket_thread(ticket_number)
                wx.CallAfter(self._show_thread, ticket_number, thread)
            except Exception as e:
                wx.CallAfter(self._show_thread_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _show_thread(self, ticket_number, thread):
        # GitHub tarafında tüm mesajlar AYNI hesaptan (token sahibi)
        # gönderildiği için "author" alanı oyuncu ile yönetimi ayırt
        # etmez. Onun yerine, oyuncunun kendi gönderdiği yorumların
        # id'lerini yerel kayıttan (own_comment_ids) okuyup GitHub
        # kullanıcı adı yerine "SİZ" / "YÖNETİM CEVABI" başlıkları
        # gösteriyoruz; kullanıcı kimin ne yazdığını unutmasın diye.
        local_ticket = ticket_manager.get_local_ticket(self.username, ticket_number)
        own_ids = set((local_ticket or {}).get("own_comment_ids") or [])

        lines = [t("tickets.you_header"), thread.get("body", "").strip(), ""]
        for c in thread.get("comments", []):
            when = (c.get("created_at") or "")[:16].replace("T", " ")
            header = t("tickets.you_header_short") if c.get("id") in own_ids else t("tickets.admin_header")
            lines.append(f"--- {header} [{when}] ---")
            lines.append(c.get("body", "").strip())
            lines.append("")

        self.thread_text.SetValue("\n".join(lines).strip())

        is_closed = thread.get("state") == "closed"
        self._set_detail_controls_enabled(not is_closed)
        if is_closed:
            self.thread_text.AppendText(t("tickets.closed_notice"))

        comment_count = len(thread.get("comments", []))
        ticket_manager.mark_ticket_seen(self.username, ticket_number, comment_count)

    def _show_thread_error(self, error_message):
        self.thread_text.SetValue(t("tickets.thread_load_failed", error=error_message))
        self._set_detail_controls_enabled(False)

    def on_reply(self, event):
        if self._busy or not self.selected_ticket:
            return

        message = self.reply_ctrl.GetValue().strip()
        if not message:
            speak(t("tickets.reply_empty"))
            return

        self._busy = True
        self.reply_btn.Disable()
        ticket_number = self.selected_ticket["number"]

        def worker():
            try:
                ticket_manager.add_reply(self.username, ticket_number, message)
                thread = ticket_manager.fetch_ticket_thread(ticket_number)
                wx.CallAfter(self._on_reply_success, ticket_number, thread)
            except Exception as e:
                wx.CallAfter(self._on_reply_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_reply_success(self, ticket_number, thread):
        self._busy = False
        self.reply_btn.Enable()
        self.reply_ctrl.SetValue("")
        self._show_thread(ticket_number, thread)
        self.audio.play_sound(SOUND_TICKET_SENT)
        speak(t("tickets.reply_sent_speak"))

    def _on_reply_error(self, error_message):
        self._busy = False
        self.reply_btn.Enable()
        wx.MessageBox(t("tickets.reply_failed_body", error=error_message),
                       t("menu.unexpected_error_title"), wx.OK | wx.ICON_ERROR)
        speak(t("tickets.reply_failed_speak"))

    def on_close_dialog(self, event):
        self.EndModal(wx.ID_OK)


class JailDialog(wx.Dialog):
    def __init__(self, parent, state, on_complete=None):
        super().__init__(parent, title=t("jail.dialog_title"), size=(400, 300),
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

        self.SetEscapeId(wx.ID_NONE)
        self.SetAffirmativeId(wx.ID_NONE)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=t("jail.header"))
        title.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(wx.RED)
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        info = wx.StaticText(panel, label=t("jail.info"))
        sizer.Add(info, 0, wx.ALL | wx.CENTER, 5)

        self.day_label = wx.StaticText(panel, label=t("jail.days_remaining_label", days=0))
        self.day_label.SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(self.day_label, 0, wx.ALL | wx.CENTER, 10)

        self.time_label = wx.StaticText(panel, label=t("jail.time_remaining_label", seconds=0))
        sizer.Add(self.time_label, 0, wx.ALL | wx.CENTER, 5)

        self.exit_btn = wx.Button(panel, label=t("jail.in_progress_btn"))
        self.exit_btn.Disable()
        sizer.Add(self.exit_btn, 0, wx.ALL | wx.CENTER, 15)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.exit_btn.Bind(wx.EVT_BUTTON, self.on_exit)
        self.Bind(wx.EVT_CLOSE, self.on_exit)

    def on_char_hook(self, event):
        keycode = event.GetKeyCode()

        if self.is_running:
            return

        if keycode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            return
        if keycode == wx.WXK_ESCAPE:
            self.on_exit(event)
            return
        event.Skip()

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
            self.parent.Disable()

        self.day_label.SetLabel(t("jail.days_remaining_label", days=days))
        self.time_label.SetLabel(t("jail.time_remaining_label", seconds=self.total_seconds))
        self.exit_btn.SetLabel(t("jail.in_progress_btn"))
        self.exit_btn.Disable()

        speak(t("jail.sentence_announce", days=days))

        self.timer.Start(1000)
        self.Show()
        self.Raise()
        self.SetFocus()

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

        self.day_label.SetLabel(t("jail.days_remaining_label", days=remaining_days))
        self.time_label.SetLabel(t("jail.time_remaining_label", seconds=self.remaining_seconds))
        self.SetTitle(t("jail.window_title_countdown", days=remaining_days))

        if self.parent:
            self.parent.SetStatusText(t("jail.status_bar_countdown", days=remaining_days))
            self.parent.update_wallet_display()

        current_time = time.time()
        if current_time - self.last_speak_time >= 10:
            self.last_speak_time = current_time
            speak(t("jail.days_left_speak", days=self.state.jail_days))

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

        self.day_label.SetLabel(t("jail.done_header"))
        self.time_label.SetLabel(t("jail.done_sub"))
        self.SetTitle(t("jail.done_window_title"))
        self.exit_btn.SetLabel(t("jail.exit_btn"))
        self.exit_btn.Enable()

        speak(t("jail.completed_speak", days=days_served))

        if self.jail_events:
            summary = " ".join(self.jail_events)
            speak(summary)

        if self.parent:
            self.parent.Enable()
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
                self.parent.Enable()
                self.parent.refresh_product_list()
                self.parent.update_wallet_display()
                self.parent.set_jail_mode(False)

            self.Destroy()
            if self.on_complete:
                self.on_complete()
        else:
            speak(t("jail.exit_blocked_speak"))
            if hasattr(event, "Veto"):
                event.Veto()