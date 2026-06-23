# -*- coding: utf-8 -*-
"""
main.py
-------
Karaborsa Ticaret Simülasyonu - Erişilebilir wxPython Uygulaması

Çalıştırmak için:
    pip install -r requirements.txt
    python main.py

Gereksinimler: wxPython, accessible_output2, pygame
(bkz. requirements.txt ve README.md)
"""

import os
import random
import sys

import wx

from game_data import PRODUCT_CATEGORIES, PRODUCTS, EVENTS, get_flat_product_order
from accessibility_helper import speak
from audio_manager import AudioManager


def resource_path(relative_path: str) -> str:
    """
    Hem normal `python main.py` ile çalışırken hem de PyInstaller ile
    .exe'ye paketlendikten sonra dosya yollarının (özellikle sounds/
    klasörü) doğru bulunmasını sağlar.

    PyInstaller --onefile ile derlendiğinde, programla birlikte paketlenen
    dosyalar çalışma anında geçici bir klasöre (`sys._MEIPASS`) açılır.
    Bu fonksiyon olmadan "sounds/game_music.mp3" gibi göreli yollar
    .exe içinde bulunamaz.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


# ---------------------------------------------------------------------------
# Oyun Durumu (Model katmanı - UI'dan bağımsız, test edilebilir)
# ---------------------------------------------------------------------------
class GameState:
    """
    Oyunun tüm verisini (nakit, envanter, fiyatlar, gün sayacı) tutar.
    UI kodundan tamamen ayrıdır; bu sayede ileride birim testi yazmak
    veya farklı bir arayüz (örn. konsol) eklemek kolaylaşır.
    """

    STARTING_CASH = 5000.0

    def __init__(self):
        self.cash = self.STARTING_CASH
        self.day = 1
        self.inventory = {name: 0 for name in PRODUCTS}
        self.prices = {name: float(data["base_price"]) for name, data in PRODUCTS.items()}

    # -- Cüzdan bilgisi -------------------------------------------------
    def wallet_text(self) -> str:
        """
        Üstteki sabit cüzdan göstergesi için metni üretir.

        NOT: Dolar / Euro / Altın gibi ürünler artık diğer ürünlerden
        (uyuşturucu, silah vb.) hiçbir mekanik farkı olmadığı için burada
        ÖZEL OLARAK gösterilmez; sadece normal envanterdeki bir ürün gibi
        ürün listesinde yer alır. Cüzdan göstergesi yalnızca elinizdeki
        nakit (TL) ve gün bilgisini gösterir.
        """
        return f"Gün {self.day} | Nakit: {self.cash:,.2f} TL"

    def inventory_summary_text(self) -> str:
        """'C' tuşu ile seslendirilecek detaylı envanter özetini üretir."""
        parts = [self.wallet_text(), "Envanter özeti:"]
        has_item = False
        for category, names in PRODUCT_CATEGORIES.items():
            owned = [f"{name}: {self.inventory.get(name, 0)} adet" for name in names if self.inventory.get(name, 0) > 0]
            if owned:
                has_item = True
                parts.append(f"{category}: " + ", ".join(owned))
        if not has_item:
            parts.append("Envanterinizde hiç ürün bulunmuyor.")
        return " ".join(parts)

    # -- Fiyat mekaniği ----------------------------------------------------------
    def fluctuate_prices(self, min_pct: float = -0.08, max_pct: float = 0.08) -> None:
        """
        Her gün geçişinde tüm ürün fiyatlarını rastgele hafifçe dalgalandırır.

        NOT: Bu "doğal piyasa gürültüsü" kasıtlı olarak küçük tutulur (±%8).
        Böylece bir gün sonra tetiklenen bir OLAY'ın (örn. %15-%80 arası
        etki) fiyat üzerindeki etkisi her zaman net biçimde görülebilir;
        günlük rastgele gürültü olayın etkisini bastırmaz.
        """
        for name, data in PRODUCTS.items():
            change = random.uniform(min_pct, max_pct)
            new_price = self.prices[name] * (1 + change)
            new_price = max(data["min_price"], min(data["max_price"], new_price))
            self.prices[name] = round(new_price, 2)

    def apply_event(self, event: dict) -> str:
        """
        Tek bir olayı uygular ve gerçekleşen etkiyi anlatan, ekran okuyucu ile
        seslendirilecek hazır bir metin döndürür. Mesaj olayın GERÇEKTE ne
        kadar etki ettiğini (yüzde, TL tutarı, adet) içerir; böylece olayın
        fiyatları/cüzdanı etkilediği her zaman açıkça anlaşılır.
        """
        etype = event["type"]

        if etype == "price":
            pct = random.uniform(event["min_pct"], event["max_pct"])
            category = event["category"]
            for name in PRODUCT_CATEGORIES[category]:
                data = PRODUCTS[name]
                new_price = self.prices[name] * (1 + pct)
                new_price = max(data["min_price"], min(data["max_price"], new_price))
                self.prices[name] = round(new_price, 2)
            return event["message_template"].format(
                category=category, pct=f"{abs(pct) * 100:.1f}"
            )

        elif etype == "cash_gain":
            pct = random.uniform(event["min_pct"], event["max_pct"])
            amount = round(self.cash * pct, 2)
            self.cash += amount
            return event["message_template"].format(amount=f"{amount:,.2f}")

        elif etype == "cash_loss":
            if self.cash <= 0:
                return event.get("zero_message", f"{event['name']}: kayıp yaşanmadı.")
            pct = random.uniform(event["min_pct"], event["max_pct"])
            amount = round(min(self.cash * pct, self.cash), 2)
            self.cash -= amount
            return event["message_template"].format(amount=f"{amount:,.2f}")

        elif etype == "inventory_loss":
            category = event["category"]
            pct = random.uniform(event["min_pct"], event["max_pct"])
            total_lost = 0
            for name in PRODUCT_CATEGORIES[category]:
                qty = self.inventory.get(name, 0)
                lost = min(qty, int(round(qty * pct)))
                self.inventory[name] -= lost
                total_lost += lost
            if total_lost == 0:
                return event.get("zero_message", f"{event['name']}: kayıp yaşanmadı.")
            return event["message_template"].format(category=category, count=total_lost)

        elif etype == "raid_combo":
            category = event["category"]
            cash_lost = 0.0
            if self.cash > 0:
                cash_pct = random.uniform(event["cash_min_pct"], event["cash_max_pct"])
                cash_lost = round(min(self.cash * cash_pct, self.cash), 2)
                self.cash -= cash_lost

            inv_pct = random.uniform(event["inventory_min_pct"], event["inventory_max_pct"])
            total_lost = 0
            for name in PRODUCT_CATEGORIES[category]:
                qty = self.inventory.get(name, 0)
                lost = min(qty, int(round(qty * inv_pct)))
                self.inventory[name] -= lost
                total_lost += lost

            if cash_lost == 0 and total_lost == 0:
                return event.get("zero_message", f"{event['name']}: kayıp yaşanmadı.")
            return event["message_template"].format(
                category=category, amount=f"{cash_lost:,.2f}", count=total_lost
            )

        # Bilinmeyen bir olay tipi gelirse sessizce yok say (ileride yeni tip
        # eklenirken kodun çökmesini önler).
        return f"{event.get('name', 'Bilinmeyen olay')} gerçekleşti."

    def trigger_random_events(self, probability: float = 0.30, min_events: int = 1, max_events: int = 3):
        """
        %probability ihtimalle min_events..max_events arası rastgele olay seçer,
        her birini uygular (apply_event) ve gerçekleşen etkiyi anlatan hazır
        mesajları döndürür. Hiçbir olay tetiklenmezse boş liste döner.
        """
        if random.random() >= probability:
            return []

        count = random.randint(min_events, min(max_events, len(EVENTS)))
        chosen = random.sample(EVENTS, count)
        return [self.apply_event(event) for event in chosen]

    # -- Alım / satım ----------------------------------------------------------
    def can_buy(self, name: str) -> bool:
        return self.cash >= self.prices[name]

    def buy(self, name: str) -> float:
        """1 adet ürün satın alır, ödenen fiyatı döndürür. can_buy() önce kontrol edilmeli."""
        price = self.prices[name]
        self.cash -= price
        self.inventory[name] += 1
        return price

    def can_sell(self, name: str) -> bool:
        return self.inventory.get(name, 0) > 0

    def sell(self, name: str) -> float:
        """1 adet ürün satar, alınan fiyatı döndürür. can_sell() önce kontrol edilmeli."""
        price = self.prices[name]
        self.inventory[name] -= 1
        self.cash += price
        return price


# ---------------------------------------------------------------------------
# Arayüz (View/Controller katmanı)
# ---------------------------------------------------------------------------
class MainFrame(wx.Frame):
    SOUND_MUSIC = resource_path("sounds/game_music.mp3")
    SOUND_BUY = resource_path("sounds/para.mp3")     # "Bir adet X ürünü Y fiyatına satın alındı."
    SOUND_SELL = resource_path("sounds/buy.ogg")     # "Bir adet X ürünü Y fiyatına satıldı."

    def __init__(self):
        super().__init__(None, title="Karaborsa Ticaret Simülasyonu", size=(680, 540))

        self.state = GameState()
        self.audio = AudioManager()
        self.flat_products = get_flat_product_order()

        self._build_ui()
        self._bind_events()

        self.audio.play_music(self.SOUND_MUSIC, loop=True)
        self.refresh_product_list()

        # Pencere açılır açılmaz oyuncuya hoş geldin + durum bilgisi seslendirilir.
        speak(
            "Karaborsa Ticaret Simülasyonuna hoş geldiniz. "
            "Ürün listesinde gezinmek için yön tuşlarını, "
            "alım satım için Tab tuşunu kullanabilirsiniz. "
            + self.state.wallet_text()
        )

    # -- UI kurulumu -------------------------------------------------------
    def _build_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 1) Cüzdan göstergesi - pencerenin en üstünde sabit metin alanı.
        #    wx.TE_READONLY bir TextCtrl kullanıyoruz; StaticText'e göre
        #    ekran okuyucular tarafından "salt okunur metin alanı" olarak
        #    daha tutarlı duyurulur ve programatik SetValue çağrısı odak
        #    değişmeden de erişilebilir kalır.
        self.wallet_display = wx.TextCtrl(
            panel,
            value=self.state.wallet_text(),
            style=wx.TE_READONLY | wx.TE_LEFT,
        )
        self.wallet_display.SetName("Cüzdan Bilgisi")
        main_sizer.Add(self.wallet_display, 0, wx.EXPAND | wx.ALL, 10)

        # 2) Ürün listesi
        list_label = wx.StaticText(panel, label="Ürünler:")
        main_sizer.Add(list_label, 0, wx.LEFT | wx.TOP, 10)

        self.product_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.product_list.SetName("Ürün Listesi")
        main_sizer.Add(self.product_list, 1, wx.EXPAND | wx.ALL, 10)

        # 3) Butonlar: Satın Al, Sat, Gün Atla
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.buy_button = wx.Button(panel, label="&Satın Al")
        self.sell_button = wx.Button(panel, label="&Sat")
        self.next_day_button = wx.Button(panel, label="&Gün Atla")

        btn_sizer.Add(self.buy_button, 0, wx.ALL, 5)
        btn_sizer.Add(self.sell_button, 0, wx.ALL, 5)
        btn_sizer.Add(self.next_day_button, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        # 4) Durum çubuğu - kısayol tuşları hatırlatması (görsel kullanıcılar için)
        self.CreateStatusBar()
        self.SetStatusText(
            "C: Cüzdan/Envanter özeti seslendir | Page Up/Down: Müzik sesi | Tab: Gezinme"
        )

        panel.SetSizer(main_sizer)

        # Tab navigasyon sırası: Ürün Listesi -> Satın Al -> Sat -> Gün Atla
        self.buy_button.MoveAfterInTabOrder(self.product_list)
        self.sell_button.MoveAfterInTabOrder(self.buy_button)
        self.next_day_button.MoveAfterInTabOrder(self.sell_button)

        self.product_list.SetFocus()

    def _bind_events(self):
        self.buy_button.Bind(wx.EVT_BUTTON, self.on_buy)
        self.sell_button.Bind(wx.EVT_BUTTON, self.on_sell)
        self.next_day_button.Bind(wx.EVT_BUTTON, self.on_next_day)
        self.product_list.Bind(wx.EVT_LISTBOX, self.on_select_product)

        # Genel klavye dinleyicisi: 'C', Page Up, Page Down.
        # EVT_CHAR_HOOK pencere içindeki hangi kontrol odaklanmış olursa olsun yakalar.
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)

    # -- Yardımcı UI fonksiyonları -------------------------------------------
    def refresh_product_list(self, keep_selection: bool = True):
        """Ürün listesini güncel fiyat/envanter bilgisiyle yeniden çizer."""
        previous_index = self.product_list.GetSelection() if keep_selection else wx.NOT_FOUND

        items = []
        for category, names in PRODUCT_CATEGORIES.items():
            for name in names:
                price = self.state.prices[name]
                qty = self.state.inventory.get(name, 0)
                items.append(f"{name} - Fiyat: {price:,.2f} TL (Envanter: {qty} adet)")

        self.product_list.Set(items)

        if previous_index != wx.NOT_FOUND and previous_index < len(items):
            self.product_list.SetSelection(previous_index)
        elif items:
            self.product_list.SetSelection(0)

    def get_selected_product_name(self):
        idx = self.product_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return None
        return self.flat_products[idx]

    def update_wallet_display(self):
        self.wallet_display.SetValue(self.state.wallet_text())

    # -- Olay yöneticileri (event handlers) -----------------------------------
    def on_select_product(self, event):
        idx = self.product_list.GetSelection()
        if idx != wx.NOT_FOUND:
            speak(self.product_list.GetString(idx))

    def on_buy(self, event):
        name = self.get_selected_product_name()
        if not name:
            speak("Lütfen önce listeden bir ürün seçin.")
            return

        if not self.state.can_buy(name):
            speak(f"Yetersiz bakiye. {name} satın alamazsınız.")
            return

        price = self.state.buy(name)
        self.audio.play_sound(self.SOUND_BUY)

        self.refresh_product_list()
        self.update_wallet_display()
        speak(f"Bir adet {name} ürünü {price:,.2f} TL fiyatına satın alındı.")

    def on_sell(self, event):
        name = self.get_selected_product_name()
        if not name:
            speak("Lütfen önce listeden bir ürün seçin.")
            return

        if not self.state.can_sell(name):
            speak(f"Envanterinizde {name} bulunmuyor.")
            return

        price = self.state.sell(name)
        self.audio.play_sound(self.SOUND_SELL)

        self.refresh_product_list()
        self.update_wallet_display()
        speak(f"Bir adet {name} ürünü {price:,.2f} TL fiyatına satıldı.")

    def on_next_day(self, event):
        self.state.day += 1
        self.state.fluctuate_prices()
        event_messages = self.state.trigger_random_events()

        self.refresh_product_list()
        self.update_wallet_display()

        announcement = f"Gün {self.state.day} başladı. Fiyatlar güncellendi."
        if event_messages:
            announcement += " " + " ".join(event_messages)
        else:
            announcement += " Bugün özel bir küresel olay yaşanmadı."
        speak(announcement)

    def on_key_down(self, event: wx.KeyEvent):
        keycode = event.GetKeyCode()

        if keycode == ord('C'):
            speak(self.state.inventory_summary_text())
        elif keycode == wx.WXK_PAGEUP:
            new_volume = self.audio.volume_up()
            speak(f"Müzik sesi yüzde {int(new_volume * 100)}.")
        elif keycode == wx.WXK_PAGEDOWN:
            new_volume = self.audio.volume_down()
            speak(f"Müzik sesi yüzde {int(new_volume * 100)}.")
        else:
            # Diğer tüm tuşlar (Tab, ok tuşları, Enter vb.) normal şekilde
            # ilgili kontrole iletilsin; aksi halde standart wx navigasyonu bozulur.
            event.Skip()


# ---------------------------------------------------------------------------
# Uygulama girişi
# ---------------------------------------------------------------------------
class KaraborsaApp(wx.App):
    def OnInit(self):
        frame = MainFrame()
        frame.Show()
        return True


def main():
    app = KaraborsaApp(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
