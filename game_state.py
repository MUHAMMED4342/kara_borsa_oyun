# game_state.py - Oyun durumu (GameState) ve yardımcı fonksiyonlar
# -*- coding: utf-8 -*-

import os
import random
import sys
import time
import wx
import webbrowser

import updater
from game_data import (
    PRODUCT_CATEGORIES, PRODUCTS, EVENTS, RARE_EVENTS, get_flat_product_order,
    COMPANY_TYPES, CREDIT_TIERS, calculate_dirty_money_risk,
    LAND_TYPES
)
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl


def speak(text: str):
    """Ekran okuyucuya seslendirir VE aynı mesajı geçmiş kaydına ekler."""
    _tts_speak(text)
    log_history(text)


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


def get_music_tracks() -> list:
    sounds_dir = resource_path("sounds")
    tracks = []
    try:
        for fname in os.listdir(sounds_dir):
            name, ext = os.path.splitext(fname)
            if ext.lower() == ".mp3" and name.isdigit():
                tracks.append((int(name), os.path.join(sounds_dir, fname)))
    except OSError:
        pass
    tracks.sort(key=lambda t: t[0])
    return [path for _, path in tracks]


ID_LOAD = wx.NewIdRef()
ID_NEW = wx.NewIdRef()


class GameState:
    STARTING_CASH = 15000.0
    STARTING_CLEAN_MONEY = 0.0
    STARTING_DIRTY_CASH = 0.0
    BANK_INTEREST_RATE = 0.015

    def __init__(self, load_data=None):
        self.lands = []
        self.land_prices = {}
        
        if load_data:
            self.cash = load_data.get("cash", self.STARTING_CASH)
            self.dirty_cash = load_data.get("dirty_cash", self.STARTING_DIRTY_CASH)
            self.clean_money = load_data.get("clean_money", self.STARTING_CLEAN_MONEY)
            self.day = load_data.get("day", 1)
            self.inventory = load_data.get("inventory", {name: 0 for name in PRODUCTS})
            self.prices = load_data.get("prices", {name: float(data["base_price"]) for name, data in PRODUCTS.items()})
            self.in_jail = load_data.get("in_jail", False)
            self.jail_days = load_data.get("jail_days", 0)
            self.has_company = load_data.get("has_company", False)
            self.company_type = load_data.get("company_type", "")
            self.company_name = load_data.get("company_name", "")
            self.company_credit_score = load_data.get("company_credit_score", 0)
            self.company_total_laundered = load_data.get("company_total_laundered", 0.0)
            self.company_monthly_revenue = load_data.get("company_monthly_revenue", 0.0)
            self.company_days_active = load_data.get("company_days_active", 0)
            self.company_upkeep_paid = load_data.get("company_upkeep_paid", 0)
            self.loan_amount = load_data.get("loan_amount", 0.0)
            self.loan_interest_rate = load_data.get("loan_interest_rate", 0.0)
            self.loan_days_remaining = load_data.get("loan_days_remaining", 0)
            self.loan_total_debt = load_data.get("loan_total_debt", 0.0)
            self.loan_total_installments = load_data.get("loan_total_installments", 0)
            self.loan_installments_paid = load_data.get("loan_installments_paid", 0)
            self.loan_installment_amount = load_data.get("loan_installment_amount", 0.0)
            self.loan_days_until_installment = load_data.get("loan_days_until_installment", 0)
            self.laundering_in_progress = load_data.get("laundering_in_progress", False)
            self.laundering_days_left = load_data.get("laundering_days_left", 0)
            self.laundering_amount = load_data.get("laundering_amount", 0.0)
            self.laundering_method = load_data.get("laundering_method", "")
            self.police_heat = load_data.get("police_heat", 0)
            self.total_crime = load_data.get("total_crime", 0.0)
            self.deaths_caused = load_data.get("deaths_caused", 0)
            self.highest_cash = load_data.get("highest_cash", self.cash)
            
            self.lands = load_data.get("lands", [])
            self.land_prices = load_data.get("land_prices", {})

            for name in PRODUCTS:
                if name not in self.inventory:
                    self.inventory[name] = 0
                if name not in self.prices:
                    self.prices[name] = float(PRODUCTS[name]["base_price"])
            
            if not self.land_prices:
                self._init_land_prices()
        else:
            self.cash = self.STARTING_CASH
            self.dirty_cash = self.STARTING_DIRTY_CASH
            self.clean_money = self.STARTING_CLEAN_MONEY
            self.day = 1
            self.inventory = {name: 0 for name in PRODUCTS}
            self.prices = {name: float(data["base_price"]) for name, data in PRODUCTS.items()}
            self.in_jail = False
            self.jail_days = 0
            self.has_company = False
            self.company_type = ""
            self.company_name = ""
            self.company_credit_score = 0
            self.company_days_active = 0
            self.company_total_laundered = 0.0
            self.company_monthly_revenue = 0.0
            self.company_upkeep_paid = 0
            self.loan_amount = 0.0
            self.loan_interest_rate = 0.0
            self.loan_days_remaining = 0
            self.loan_total_debt = 0.0
            self.loan_total_installments = 0
            self.loan_installments_paid = 0
            self.loan_installment_amount = 0.0
            self.loan_days_until_installment = 0
            self.laundering_in_progress = False
            self.laundering_days_left = 0
            self.laundering_amount = 0.0
            self.laundering_method = ""
            self.police_heat = 0
            self.total_crime = 0.0
            self.deaths_caused = 0
            self.highest_cash = self.cash
            
            self.lands = []
            self.land_prices = {}
            self._init_land_prices()

    def _init_land_prices(self):
        for land_type, data in LAND_TYPES.items():
            self.land_prices[land_type] = float(data["base_price"])

    # ----- ARSA METOTLARI -----
    
    def get_land_price(self, land_type: str) -> float:
        if land_type in self.land_prices:
            return self.land_prices[land_type]
        return float(LAND_TYPES[land_type]["base_price"])

    def get_land_list(self) -> list:
        return self.lands

    def get_land_count(self, land_type: str) -> int:
        count = 0
        for land in self.lands:
            if land["type"] == land_type:
                count += 1
        return count

    def buy_land(self, land_type: str) -> tuple:
        if land_type not in LAND_TYPES:
            return False, "Geçersiz arsa tipi"
        
        price = self.get_land_price(land_type)
        
        if self.cash < price:
            return False, f"Yetersiz nakit. Fiyat: {format_tl(price)} TL"
        
        self.cash -= price
        self.lands.append({
            "type": land_type,
            "purchase_price": price,
            "purchase_day": self.day
        })
        
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        
        return True, f"{land_type} satın alındı. Fiyat: {format_tl(price)} TL"

    def sell_land(self, land_index: int) -> tuple:
        if land_index < 0 or land_index >= len(self.lands):
            return False, "Geçersiz arsa indeksi"
        
        land = self.lands[land_index]
        land_type = land["type"]
        current_price = self.get_land_price(land_type)
        
        commission = current_price * 0.05
        sale_price = current_price - commission
        
        self.cash += sale_price
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        
        removed = self.lands.pop(land_index)
        
        return True, f"{land_type} satıldı. Kazanç: {format_tl(sale_price)} TL (Komisyon: {format_tl(commission)} TL)"

    def get_land_loan_limit(self, land_index: int) -> float:
        if land_index < 0 or land_index >= len(self.lands):
            return 0.0
        
        land = self.lands[land_index]
        land_type = land["type"]
        current_price = self.get_land_price(land_type)
        multiplier = LAND_TYPES[land_type]["credit_multiplier"]
        
        return current_price * multiplier

    LAND_LOAN_PRESETS = [
        ("Küçük Kredi", 0.25, 1),
        ("Orta Kredi", 0.50, 2),
        ("Büyük Kredi", 1.00, 3),
    ]

    def get_land_loan_options(self, land_index: int) -> list:
        """Seçilen arsa için alınabilecek hazır kredi paketlerini döner."""
        if land_index < 0 or land_index >= len(self.lands):
            return []
        if self.lands[land_index].get("has_loan", False):
            return []

        limit = self.get_land_loan_limit(land_index)
        if limit <= 0:
            return []

        interest_rate = 0.15
        options = []
        for label, pct, installments in self.LAND_LOAN_PRESETS:
            amount = round(limit * pct, 2)
            if amount <= 0:
                continue
            total_debt = round(amount * (1 + interest_rate), 2)
            installment_amount = round(total_debt / installments, 2)
            options.append({
                "label": label,
                "amount": amount,
                "installments": installments,
                "term_days": installments * 30,
                "interest_rate": interest_rate,
                "total_debt": total_debt,
                "installment_amount": installment_amount,
            })
        return options

    def take_land_loan(self, land_index: int, amount: float, installments: int = 1) -> tuple:
        if land_index < 0 or land_index >= len(self.lands):
            return False, "Geçersiz arsa indeksi"
        
        if amount <= 0:
            return False, "Geçerli miktar girin"

        if self.lands[land_index].get("has_loan", False):
            return False, "Bu arsa üzerinde zaten kredi var"
        
        limit = self.get_land_loan_limit(land_index)
        if amount > limit:
            return False, f"Maksimum kredi: {format_tl(limit)} TL"
        
        installments = max(1, int(installments))
        interest_rate = 0.15
        total_debt = round(amount * (1 + interest_rate), 2)
        installment_amount = round(total_debt / installments, 2)
        
        self.clean_money += amount
        
        land = self.lands[land_index]
        land["has_loan"] = True
        land["loan_amount"] = amount
        land["loan_debt"] = total_debt
        land["loan_interest_rate"] = interest_rate
        land["loan_total_installments"] = installments
        land["loan_installments_paid"] = 0
        land["loan_installment_amount"] = installment_amount
        land["loan_days_until_installment"] = 30
        
        return True, (f"{format_tl(amount)} TL arsa teminatlı kredi onaylandı. Toplam borç: {format_tl(total_debt)} TL "
                       f"(Faiz: %15). {installments} taksit, her 30 günde bir {format_tl(installment_amount)} TL "
                       f"otomatik olarak çekilecek")

    def pay_land_loan_full(self, land_index: int) -> tuple:
        """Arsa kredisini erken kapatma - kalan tüm borç tek seferde ödenir."""
        if land_index < 0 or land_index >= len(self.lands):
            return False, "Geçersiz arsa indeksi"

        land = self.lands[land_index]
        if not land.get("has_loan", False):
            return False, "Bu arsada aktif kredi yok"

        debt = land.get("loan_debt", 0.0)
        if self.clean_money < debt:
            return False, f"Erken kapatma için yetersiz temiz para. Gereken: {format_tl(debt)} TL"

        self.clean_money -= debt
        land["has_loan"] = False
        land.pop("loan_amount", None)
        land.pop("loan_debt", None)
        land.pop("loan_interest_rate", None)
        land.pop("loan_total_installments", None)
        land.pop("loan_installments_paid", None)
        land.pop("loan_installment_amount", None)
        land.pop("loan_days_until_installment", None)

        return True, f"{format_tl(debt)} TL ödendi. Arsa kredisi erken kapatıldı, arsa artık satılabilir"

    def process_land_loans_daily(self) -> list:
        """Her arsa kredisi için 30 günde bir otomatik taksit tahsilatı yapar.
        Taksit ödenemezse arsa bankaya devredilir (haciz)."""
        messages = []
        to_remove = []

        for i, land in enumerate(self.lands):
            if not land.get("has_loan", False):
                continue

            land["loan_days_until_installment"] = land.get("loan_days_until_installment", 30) - 1
            if land["loan_days_until_installment"] > 0:
                continue

            debt = land.get("loan_debt", 0.0)
            installment = land.get("loan_installment_amount", debt)
            due = round(min(installment, debt), 2)
            paid = self._auto_deduct(due)
            debt = round(debt - paid, 2)
            land["loan_debt"] = debt

            if paid < due - 0.01:
                messages.append(
                    f"{land['type']} arsa kredisi taksidi ödenemedi (Gereken: {format_tl(due)} TL, "
                    f"ödenebilen: {format_tl(paid)} TL). Arsa bankaya devredildi (haciz)!"
                )
                to_remove.append(i)
                continue

            land["loan_installments_paid"] = land.get("loan_installments_paid", 0) + 1

            if debt <= 0.01:
                messages.append(f"{land['type']} arsa kredisi taksidi ödendi: {format_tl(paid)} TL. Kredi tamamen kapandı!")
                land["has_loan"] = False
                land.pop("loan_amount", None)
                land.pop("loan_debt", None)
                land.pop("loan_interest_rate", None)
                land.pop("loan_total_installments", None)
                land.pop("loan_installments_paid", None)
                land.pop("loan_installment_amount", None)
                land.pop("loan_days_until_installment", None)
            else:
                land["loan_days_until_installment"] = 30
                messages.append(
                    f"{land['type']} arsa kredisi taksidi ödendi: {format_tl(paid)} TL. Kalan borç: {format_tl(debt)} TL"
                )

        for i in sorted(to_remove, reverse=True):
            self.lands.pop(i)

        return messages

    def fluctuate_land_prices(self):
        for land_type in LAND_TYPES:
            data = LAND_TYPES[land_type]
            change = random.uniform(-0.05, 0.05)
            new_price = self.land_prices.get(land_type, data["base_price"]) * (1 + change)
            new_price = max(data["min_price"], min(data["max_price"], new_price))
            self.land_prices[land_type] = round(new_price, 2)

    def wallet_text(self) -> str:
        base = f"Gün {self.day} | Nakit: {format_tl(self.cash)} TL"
        if self.dirty_cash > 0:
            base += f" | Kirli: {format_tl(self.dirty_cash)} TL"
        if self.clean_money > 0:
            base += f" | Temiz: {format_tl(self.clean_money)} TL"
        if self.has_company:
            base += f" | Şirket: {self.company_name}"
            if self.loan_amount > 0:
                base += f" | Kredi: {format_tl(self.loan_amount)} TL"
        if self.lands:
            base += f" | Arsa: {len(self.lands)} adet"
        if self.in_jail:
            base += f" | HAPİSTE {self.jail_days} gün"
        if self.police_heat > 0:
            base += f" | Polis riski: %{self.police_heat:.0f}"
        return base

    def get_credit_tier(self):
        if not self.has_company:
            return None
        tier = CREDIT_TIERS[0]
        for t in CREDIT_TIERS:
            if self.company_credit_score >= t["min_score"]:
                tier = t
        return tier

    def get_loan_limit(self) -> float:
        tier = self.get_credit_tier()
        if not tier or not tier["can_loan"]:
            return 0.0
        if self.company_days_active > 0:
            days_this_month = (self.company_days_active - 1) % 30 + 1
        else:
            days_this_month = 1
        monthly_income = (self.company_monthly_revenue / days_this_month) * 30
        base_limit = monthly_income * 2
        return base_limit * tier["loan_limit_multiplier"]

    def inventory_summary_text(self) -> str:
        parts = [self.wallet_text(), "Envanter özeti:"]
        has_item = False
        for category, names in PRODUCT_CATEGORIES.items():
            owned = [f"{name}: {self.inventory.get(name, 0)} adet" for name in names if self.inventory.get(name, 0) > 0]
            if owned:
                has_item = True
                parts.append(f"{category}: " + ", ".join(owned))
        if not has_item:
            parts.append("Envanterinizde ürün yok.")
        
        if self.lands:
            parts.append("\nArsalarınız:")
            for i, land in enumerate(self.lands):
                land_type = land["type"]
                price = self.get_land_price(land_type)
                parts.append(f"{i+1}. {land_type} - Değer: {format_tl(price)} TL")
        
        return " ".join(parts)

    def fluctuate_prices(self, min_pct: float = -0.10, max_pct: float = 0.10) -> None:
        for name, data in PRODUCTS.items():
            change = random.uniform(min_pct, max_pct)
            for category, names in PRODUCT_CATEGORIES.items():
                if name in names:
                    change += random.uniform(-0.03, 0.03)
                    break
            new_price = self.prices[name] * (1 + change)
            new_price = max(data["min_price"], min(data["max_price"], new_price))
            self.prices[name] = round(new_price, 2)
        
        self.fluctuate_land_prices()

    def buy_bulk(self, name: str, quantity: int) -> tuple:
        total_price = self.prices[name] * quantity
        if self.cash < total_price:
            return False, 0, "Yetersiz bakiye"
        self.cash -= total_price
        self.inventory[name] += quantity

        from_dirty = min(self.dirty_cash, total_price)
        self.dirty_cash -= from_dirty
        remaining = total_price - from_dirty
        if remaining > 0:
            from_clean = min(self.clean_money, remaining)
            self.clean_money -= from_clean

        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        return True, total_price, f"{quantity} adet {name} alındı"

    def sell_bulk(self, name: str, quantity: int) -> tuple:
        if self.inventory.get(name, 0) < quantity:
            return False, 0, "Yeterli stok yok"
        total_price = self.prices[name] * quantity
        self.inventory[name] -= quantity
        self.dirty_cash += total_price
        self.cash += total_price
        self.total_crime += total_price
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        speak(f"{quantity} adet {name} satıldı, {format_tl(total_price)} TL kazanıldı")
        return True, total_price, f"{quantity} adet {name} satıldı"

    def go_to_jail(self, days: int) -> str:
        self.in_jail = True
        self.jail_days = days
        return f"{days} gün hapis cezası"

    def setup_company(self, company_type: str, company_name: str) -> tuple:
        if self.has_company:
            return False, "Zaten şirketiniz var"

        if company_type not in COMPANY_TYPES:
            return False, "Geçersiz şirket tipi"

        company_data = COMPANY_TYPES[company_type]
        cost = company_data["setup_cost"]

        if self.cash < cost:
            return False, f"Yetersiz nakit. Kurulum maliyeti: {format_tl(cost)} TL"

        self.cash -= cost
        self.has_company = True
        self.company_type = company_type
        self.company_name = company_name
        self.company_credit_score = 50
        self.company_days_active = 0
        self.company_total_laundered = 0.0
        self.company_monthly_revenue = 0.0
        self.company_upkeep_paid = 0

        return True, f"{company_name} kuruldu. Başlangıç kredi notu: 50"

    def close_company(self) -> tuple:
        if not self.has_company:
            return False, "Aktif şirket yok"

        if self.loan_amount > 0:
            return False, "Önce kredi borcunu kapatın"

        self.has_company = False
        self.company_type = ""
        self.company_name = ""
        self.company_credit_score = 0
        self.company_total_laundered = 0.0
        self.company_monthly_revenue = 0.0
        self.company_days_active = 0

        return True, "Şirket kapatıldı"

    def launder_money(self, amount: float) -> tuple:
        if not self.has_company:
            return False, "Önce şirket kurun"

        if amount <= 0:
            return False, "Geçerli miktar girin"

        if amount > self.dirty_cash:
            return False, f"Yetersiz kirli para. Mevcut: {format_tl(self.dirty_cash)} TL"

        company_data = COMPANY_TYPES[self.company_type]
        max_launder = self.dirty_cash * company_data["laundering_capacity"]

        if amount > max_launder:
            return False, f"Maksimum aklama: {format_tl(max_launder)} TL"

        self.dirty_cash -= amount
        self.clean_money += amount
        self.company_total_laundered += amount
        self.company_monthly_revenue += amount

        credit_boost = int(amount / 1000)
        self.company_credit_score += max(1, credit_boost)

        return True, f"{format_tl(amount)} TL aklandı. Kredi notu: {self.company_credit_score}"

    def pay_company_upkeep(self) -> bool:
        if not self.has_company:
            return True

        company_data = COMPANY_TYPES[self.company_type]
        upkeep = company_data["daily_upkeep"]

        if self.clean_money >= upkeep:
            self.clean_money -= upkeep
            self.cash -= upkeep
            self.company_upkeep_paid += upkeep
            return True
        elif self.dirty_cash >= upkeep:
            self.dirty_cash -= upkeep
            self.cash -= upkeep
            self.company_upkeep_paid += upkeep
            return True
        elif self.cash >= upkeep:
            self.cash -= upkeep
            self.company_upkeep_paid += upkeep
            return True
        else:
            self.has_company = False
            self.company_type = ""
            self.company_name = ""
            self.company_credit_score = 0
            return False

    LOAN_PRESETS = [
        ("Küçük Kredi", 0.25, 1),
        ("Orta Kredi", 0.50, 2),
        ("Büyük Kredi", 1.00, 3),
    ]

    def get_loan_options(self) -> list:
        """Kredi notuna göre alınabilecek hazır kredi paketlerini döner."""
        if self.loan_amount > 0:
            return []

        tier = self.get_credit_tier()
        if not tier or not tier["can_loan"]:
            return []

        limit = self.get_loan_limit()
        if limit <= 0:
            return []

        rate = tier["interest_rate"]
        options = []
        for label, pct, installments in self.LOAN_PRESETS:
            amount = round(limit * pct, 2)
            if amount <= 0:
                continue
            total_debt = round(amount * (1 + rate), 2)
            installment_amount = round(total_debt / installments, 2)
            options.append({
                "label": label,
                "amount": amount,
                "installments": installments,
                "term_days": installments * 30,
                "interest_rate": rate,
                "total_debt": total_debt,
                "installment_amount": installment_amount,
            })
        return options

    def take_loan(self, amount: float, installments: int = 1) -> tuple:
        if not self.has_company:
            return False, "Önce şirket kurun"

        if self.loan_amount > 0:
            return False, "Aktif kredi var"

        if amount <= 0:
            return False, "Geçerli miktar girin"

        limit = self.get_loan_limit()
        if amount > limit:
            return False, f"Maksimum kredi: {format_tl(limit)} TL"

        tier = self.get_credit_tier()
        if not tier or not tier["can_loan"]:
            return False, "Kredi notu yetersiz"

        installments = max(1, int(installments))
        self.loan_amount = amount
        self.loan_interest_rate = tier["interest_rate"]
        self.loan_total_debt = round(amount * (1 + tier["interest_rate"]), 2)
        self.loan_total_installments = installments
        self.loan_installments_paid = 0
        self.loan_installment_amount = round(self.loan_total_debt / installments, 2)
        self.loan_days_remaining = installments * 30
        self.loan_days_until_installment = 30
        self.clean_money += amount

        return True, (f"{format_tl(amount)} TL kredi onaylandı. Faiz: %{tier['interest_rate']*100:.1f}. "
                       f"{installments} taksit, her 30 günde bir {format_tl(self.loan_installment_amount)} TL "
                       f"otomatik olarak çekilecek")

    def pay_loan_full(self) -> tuple:
        """Krediyi erken kapatma - kalan tüm borç tek seferde ödenir."""
        if self.loan_amount <= 0:
            return False, "Aktif kredi yok"

        debt = self.loan_total_debt
        if self.clean_money < debt:
            return False, f"Erken kapatma için yetersiz temiz para. Gereken: {format_tl(debt)} TL"

        self.clean_money -= debt
        self._clear_loan()
        return True, f"{format_tl(debt)} TL ödendi. Kredi erken kapatıldı"

    def _clear_loan(self):
        self.loan_amount = 0
        self.loan_total_debt = 0
        self.loan_interest_rate = 0.0
        self.loan_days_remaining = 0
        self.loan_total_installments = 0
        self.loan_installments_paid = 0
        self.loan_installment_amount = 0.0
        self.loan_days_until_installment = 0

    def _auto_deduct(self, amount: float) -> float:
        """Bir ödemeyi sırasıyla temiz paradan, kirli paradan ve son olarak nakitten
        otomatik olarak çeker. Gerçekte ödenebilen miktarı döner."""
        remaining = round(amount, 2)
        if remaining <= 0:
            return 0.0

        if self.clean_money > 0:
            pay = min(self.clean_money, remaining)
            self.clean_money -= pay
            self.cash -= pay
            remaining -= pay

        if remaining > 0 and self.dirty_cash > 0:
            pay = min(self.dirty_cash, remaining)
            self.dirty_cash -= pay
            self.cash -= pay
            remaining -= pay

        if remaining > 0 and self.cash > 0:
            pay = min(self.cash, remaining)
            self.cash -= pay
            remaining -= pay

        return round(amount - remaining, 2)

    def process_loan_daily(self) -> tuple:
        """Kredi her 30 günde bir otomatik olarak taksit öder. Taksit ödenemezse
        kredi temerrüde düşer (main.py bunu default_loan() ile ele alır)."""
        if self.loan_amount <= 0:
            return True, None

        self.loan_days_until_installment -= 1
        if self.loan_days_until_installment > 0:
            return True, None

        due = round(min(self.loan_installment_amount, self.loan_total_debt), 2)
        paid = self._auto_deduct(due)
        self.loan_total_debt = round(self.loan_total_debt - paid, 2)

        if paid < due - 0.01:
            return False, (f"Taksit ödenemedi (Gereken: {format_tl(due)} TL, "
                            f"ödenebilen: {format_tl(paid)} TL)")

        self.loan_installments_paid += 1

        if self.loan_total_debt <= 0.01:
            msg = f"Son taksit ödendi: {format_tl(paid)} TL. Kredi tamamen kapandı!"
            self._clear_loan()
            return True, msg

        self.loan_days_until_installment = 30
        return True, f"Kredi taksidi ödendi: {format_tl(paid)} TL. Kalan borç: {format_tl(self.loan_total_debt)} TL"

    def default_loan(self) -> tuple:
        if not self.has_company:
            return False, "Aktif şirket yok"

        self.has_company = False
        self.company_type = ""
        self.company_name = ""
        self.company_credit_score = 0

        seized = self.clean_money
        self.clean_money = 0
        self.cash -= seized
        seized_dirty = self.dirty_cash * 0.5
        self.dirty_cash -= seized_dirty
        self.cash -= seized_dirty

        self._clear_loan()

        return True, f"Şirket kapatıldı. {format_tl(seized)} TL temiz para musadere edildi"

    def police_check(self) -> dict:
        self.police_heat = min(100, self.police_heat + (self.dirty_cash / 50000) * 10)
        risk = calculate_dirty_money_risk(self.dirty_cash) * (1 + self.police_heat / 100)

        if random.random() < risk:
            bribe_amount = self.cash * random.uniform(0.10, 0.30)
            bribe_amount = round(bribe_amount, 2)
            return {
                "caught": True,
                "bribe_amount": bribe_amount,
                "can_bribe": self.cash > 0,
                "risk": risk
            }
        return {"caught": False, "risk": risk}

    def bribe_police(self, amount: float) -> bool:
        if amount <= self.cash:
            self.cash -= amount
            self.police_heat = max(0, self.police_heat - 20)
            return True
        return False

    def apply_event(self, event: dict) -> str:
        etype = event["type"]
        if etype == "price":
            pct = random.uniform(event["min_pct"], event["max_pct"])
            category = event["category"]
            for name in PRODUCT_CATEGORIES[category]:
                data = PRODUCTS[name]
                new_price = self.prices[name] * (1 + pct)
                new_price = max(data["min_price"], min(data["max_price"], new_price))
                self.prices[name] = round(new_price, 2)
            return event["message_template"].format(category=category, pct=f"{abs(pct) * 100:.1f}")
        elif etype == "cash_gain":
            pct = random.uniform(event["min_pct"], event["max_pct"])
            amount = round(self.cash * pct, 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event["message_template"].format(amount=f"{format_tl(amount)}")
        elif etype == "cash_loss":
            if self.cash <= 0:
                return event.get("zero_message", f"{event['name']}: kayıp yok")
            pct = random.uniform(event["min_pct"], event["max_pct"])
            amount = round(min(self.cash * pct, self.cash), 2)
            self.cash -= amount
            return event["message_template"].format(amount=f"{format_tl(amount)}")
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
                return event.get("zero_message", f"{event['name']}: kayıp yok")
            return event["message_template"].format(category=category, count=total_lost)
        elif etype == "raid_combo":
            cash_pct = random.uniform(event["cash_min_pct"], event["cash_max_pct"])
            cash_loss = round(min(self.cash * cash_pct, self.cash), 2)
            self.cash -= cash_loss
            category = event["category"]
            inv_pct = random.uniform(event["inventory_min_pct"], event["inventory_max_pct"])
            total_lost = 0
            for name in PRODUCT_CATEGORIES[category]:
                qty = self.inventory.get(name, 0)
                lost = min(qty, int(round(qty * inv_pct)))
                self.inventory[name] -= lost
                total_lost += lost
            if cash_loss == 0 and total_lost == 0:
                return event.get("zero_message", f"{event['name']}: kayıp yok")
            return event["message_template"].format(amount=f"{format_tl(cash_loss)}", category=category, count=total_lost)
        elif etype == "company_audit":
            if self.has_company and self.clean_money > 0:
                risk_amount = self.clean_money * 0.10
                if random.random() < 0.3:
                    self.clean_money -= risk_amount
                    return f"Maliye cezası. {format_tl(risk_amount)} TL bloke edildi"
                else:
                    return "Maliye denetimi geçti"
            return "Maliye denetimi geçti"
        elif etype == "company_reputation":
            if self.has_company:
                boost = event.get("credit_boost", 0)
                penalty = event.get("credit_penalty", 0)
                if boost:
                    self.company_credit_score += boost
                    return event["message_template"].format(credit_boost=boost)
                elif penalty:
                    self.company_credit_score = max(0, self.company_credit_score + penalty)
                    return event["message_template"].format(credit_penalty=abs(penalty))
                return event["message_template"]
            return f"{event['name']}: Şirketiniz olmadığı için etkilenmediniz"
        elif etype == "land_price":
            pct = random.uniform(event["min_pct"], event["max_pct"])
            for land_type in LAND_TYPES:
                data = LAND_TYPES[land_type]
                new_price = self.land_prices.get(land_type, data["base_price"]) * (1 + pct)
                new_price = max(data["min_price"], min(data["max_price"], new_price))
                self.land_prices[land_type] = round(new_price, 2)
            return event["message_template"].format(pct=f"{abs(pct) * 100:.1f}")
        elif etype == "inheritance":
            amount = random.uniform(event["min_amount"], event["max_amount"])
            amount = round(amount, 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event["message_template"].format(amount=f"{format_tl(amount)}")
        elif etype == "death":
            self.deaths_caused += 1
            return f"{event['name']}. Toplam ölüm: {self.deaths_caused}"
        return f"{event.get('name', 'Bilinmeyen olay')} gerçekleşti"

    def trigger_random_events(self, probability: float = 0.60, min_events: int = 1, max_events: int = 3):
        if random.random() >= probability:
            return []
        
        # Normal olaylar
        count = random.randint(min_events, min(max_events, len(EVENTS)))
        chosen = random.sample(EVENTS, count)
        results = [self.apply_event(event) for event in chosen]
        
        # Nadir olaylar (bağımsız kontrol)
        for rare in RARE_EVENTS:
            if random.random() < rare.get("chance", 0.001):
                results.append(self.apply_event(rare))
        
        return results

    def apply_bank_interest(self) -> float:
        if self.clean_money > 0:
            interest = self.clean_money * self.BANK_INTEREST_RATE
            self.clean_money += interest
            return interest
        return 0.0

    def process_jail_day(self) -> list:
        messages = []
        self.fluctuate_prices()
        if self.has_company:
            if not self.pay_company_upkeep():
                messages.append("Şirketiniz iflas etti, işletme giderleri karşılanamadı")
        if self.loan_amount > 0:
            success, msg = self.process_loan_daily()
            if not success:
                self.default_loan()
                messages.append(f"Kredi temerrüdüne düştünüz: {msg}")
            elif msg:
                messages.append(msg)
        messages.extend(self.process_land_loans_daily())
        return messages


def open_help():
    help_path = resource_path("help.html")
    if os.path.exists(help_path):
        webbrowser.open(help_path)
    else:
        create_help_file(help_path)
        webbrowser.open(help_path)


def create_help_file(path):
    help_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Karaborsa Ticaret Simülasyonu - Yardım</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 25px; }
        .shortcut { background: #2c3e50; color: white; padding: 2px 8px; border-radius: 4px; font-family: monospace; }
        ul { padding-left: 20px; }
        li { margin: 8px 0; }
    </style>
</head>
<body>
    <h1>Karaborsa Ticaret Simülasyonu - Yardım</h1>
    <h2>Kısayollar</h2>
    <ul>
        <li><span class="shortcut">F1</span> - Yardım</li>
        <li><span class="shortcut">F2</span> - Durum raporu</li>
        <li><span class="shortcut">F5</span> - Gün atla</li>
        <li><span class="shortcut">F6</span> - Arsa Yönetimi</li>
        <li><span class="shortcut">C</span> - Nakit durumu</li>
        <li><span class="shortcut">D</span> - Seçili ürünün kategorisi</li>
        <li><span class="shortcut">E</span> - Envanter özeti</li>
        <li><span class="shortcut">PgUp</span> - Ses artır</li>
        <li><span class="shortcut">PgDn</span> - Ses azalt</li>
    </ul>
    <h2>Arsa Sistemi</h2>
    <ul>
        <li><strong>Arsa Satın Al:</strong> 5 farklı arsa tipi mevcut</li>
        <li><strong>Arsa Sat:</strong> Piyasa değerinden satabilirsiniz (%5 komisyon)</li>
        <li><strong>Arsa Teminatlı Kredi:</strong> Arsa değerinin %70'ine kadar kredi</li>
        <li><strong>Fiyat Dalgalanmaları:</strong> Arsa fiyatları her gün değişir</li>
    </ul>
    <h2>Oyun Hakkında</h2>
    <p>Karaborsa'da ticaret yaparak para kazanın, şirket kurun, para aklayın ve zengin olun!</p>
</body>
</html>"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(help_content)


# ============================================================
# ARSA YÖNETİM DİALOGU (Mevduat KALDIRILDI)
# ============================================================