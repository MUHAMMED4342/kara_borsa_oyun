# main.py - Karaborsa Ticaret Simülasyonu (Görme Engelli Dostu)
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
from accessibility_helper import speak
from audio_manager import AudioManager
from save_manager import save_game, load_game, list_saves, delete_save


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
            return False, f"Yetersiz nakit. Fiyat: {price:,.2f} TL"
        
        self.cash -= price
        self.lands.append({
            "type": land_type,
            "purchase_price": price,
            "purchase_day": self.day
        })
        
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        
        return True, f"{land_type} satın alındı. Fiyat: {price:,.2f} TL"

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
        
        return True, f"{land_type} satıldı. Kazanç: {sale_price:,.2f} TL (Komisyon: {commission:,.2f} TL)"

    def get_land_loan_limit(self, land_index: int) -> float:
        if land_index < 0 or land_index >= len(self.lands):
            return 0.0
        
        land = self.lands[land_index]
        land_type = land["type"]
        current_price = self.get_land_price(land_type)
        multiplier = LAND_TYPES[land_type]["credit_multiplier"]
        
        return current_price * multiplier

    def take_land_loan(self, land_index: int, amount: float) -> tuple:
        if land_index < 0 or land_index >= len(self.lands):
            return False, "Geçersiz arsa indeksi"
        
        if amount <= 0:
            return False, "Geçerli miktar girin"

        if self.lands[land_index].get("has_loan", False):
            return False, "Bu arsa üzerinde zaten kredi var"
        
        limit = self.get_land_loan_limit(land_index)
        if amount > limit:
            return False, f"Maksimum kredi: {limit:,.2f} TL"
        
        interest_rate = 0.15
        total_debt = amount * (1 + interest_rate)
        
        self.clean_money += amount
        
        self.lands[land_index]["has_loan"] = True
        self.lands[land_index]["loan_amount"] = amount
        self.lands[land_index]["loan_debt"] = total_debt
        self.lands[land_index]["loan_interest_rate"] = interest_rate
        
        return True, f"{amount:,.2f} TL arsa teminatlı kredi onaylandı. Toplam borç: {total_debt:,.2f} TL (Faiz: %15)"

    def pay_land_loan(self, land_index: int, amount: float) -> tuple:
        if land_index < 0 or land_index >= len(self.lands):
            return False, "Geçersiz arsa indeksi"

        land = self.lands[land_index]
        if not land.get("has_loan", False):
            return False, "Bu arsada aktif kredi yok"

        if amount <= 0:
            return False, "Geçerli miktar girin"

        if amount > self.clean_money:
            return False, f"Yetersiz temiz para. Mevcut: {self.clean_money:,.2f} TL"

        debt = land.get("loan_debt", land.get("loan_amount", 0.0) * 1.15)
        payment = min(amount, debt)
        self.clean_money -= payment
        debt -= payment
        land["loan_debt"] = debt

        if debt <= 0:
            land["has_loan"] = False
            land.pop("loan_amount", None)
            land.pop("loan_debt", None)
            land.pop("loan_interest_rate", None)
            return True, f"{payment:,.2f} TL ödendi. Arsa kredisi tamamen kapandı, arsa artık satılabilir"

        return True, f"{payment:,.2f} TL ödendi. Kalan borç: {debt:,.2f} TL"

    def fluctuate_land_prices(self):
        for land_type in LAND_TYPES:
            data = LAND_TYPES[land_type]
            change = random.uniform(-0.05, 0.05)
            new_price = self.land_prices.get(land_type, data["base_price"]) * (1 + change)
            new_price = max(data["min_price"], min(data["max_price"], new_price))
            self.land_prices[land_type] = round(new_price, 2)

    def wallet_text(self) -> str:
        base = f"Gün {self.day} | Nakit: {self.cash:,.2f} TL"
        if self.dirty_cash > 0:
            base += f" | Kirli: {self.dirty_cash:,.2f} TL"
        if self.clean_money > 0:
            base += f" | Temiz: {self.clean_money:,.2f} TL"
        if self.has_company:
            base += f" | Şirket: {self.company_name}"
            if self.loan_amount > 0:
                base += f" | Kredi: {self.loan_amount:,.2f} TL"
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
                parts.append(f"{i+1}. {land_type} - Değer: {price:,.2f} TL")
        
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
        speak(f"{quantity} adet {name} satıldı, {total_price:,.2f} TL kazanıldı")
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
            return False, f"Yetersiz nakit. Kurulum maliyeti: {cost:,.2f} TL"

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
            return False, f"Yetersiz kirli para. Mevcut: {self.dirty_cash:,.2f} TL"

        company_data = COMPANY_TYPES[self.company_type]
        max_launder = self.dirty_cash * company_data["laundering_capacity"]

        if amount > max_launder:
            return False, f"Maksimum aklama: {max_launder:,.2f} TL"

        self.dirty_cash -= amount
        self.clean_money += amount
        self.company_total_laundered += amount
        self.company_monthly_revenue += amount

        credit_boost = int(amount / 1000)
        self.company_credit_score += max(1, credit_boost)

        return True, f"{amount:,.2f} TL aklandı. Kredi notu: {self.company_credit_score}"

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

    def take_loan(self, amount: float) -> tuple:
        if not self.has_company:
            return False, "Önce şirket kurun"

        if self.loan_amount > 0:
            return False, "Aktif kredi var"

        if amount <= 0:
            return False, "Geçerli miktar girin"

        limit = self.get_loan_limit()
        if amount > limit:
            return False, f"Maksimum kredi: {limit:,.2f} TL"

        tier = self.get_credit_tier()
        if not tier or not tier["can_loan"]:
            return False, "Kredi notu yetersiz"

        self.loan_amount = amount
        self.loan_interest_rate = tier["interest_rate"]
        self.loan_days_remaining = 30
        self.loan_total_debt = amount * (1 + tier["interest_rate"])
        self.clean_money += amount

        return True, f"{amount:,.2f} TL kredi onaylandı. Faiz: %{tier['interest_rate']*100:.1f}"

    def pay_loan_installment(self, amount: float) -> tuple:
        if self.loan_amount <= 0:
            return False, "Aktif kredi yok"

        if amount <= 0:
            return False, "Geçerli miktar girin"

        if amount > self.clean_money:
            return False, f"Yetersiz temiz para. Mevcut: {self.clean_money:,.2f} TL"

        payment = min(amount, self.loan_total_debt)
        self.clean_money -= payment
        self.loan_total_debt -= payment
        self.loan_amount = max(0, self.loan_amount - payment)

        if self.loan_total_debt <= 0:
            self.loan_amount = 0
            self.loan_days_remaining = 0
            return True, "Kredi kapandı"

        return True, f"{payment:,.2f} TL ödendi. Kalan: {self.loan_total_debt:,.2f} TL"

    def process_loan_daily(self) -> tuple:
        if self.loan_amount <= 0:
            return True, None

        self.loan_days_remaining -= 1

        if self.loan_days_remaining <= 0:
            return False, f"Kredi vadesi doldu. Borç: {self.loan_total_debt:,.2f} TL"

        return True, None

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

        self.loan_amount = 0
        self.loan_total_debt = 0
        self.loan_days_remaining = 0

        return True, f"Şirket kapatıldı. {seized:,.2f} TL temiz para musadere edildi"

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
            return event["message_template"].format(amount=f"{amount:,.2f}")
        elif etype == "cash_loss":
            if self.cash <= 0:
                return event.get("zero_message", f"{event['name']}: kayıp yok")
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
            return event["message_template"].format(amount=f"{cash_loss:,.2f}", category=category, count=total_lost)
        elif etype == "company_audit":
            if self.has_company and self.clean_money > 0:
                risk_amount = self.clean_money * 0.10
                if random.random() < 0.3:
                    self.clean_money -= risk_amount
                    return f"Maliye cezası. {risk_amount:,.2f} TL bloke edildi"
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
        elif etype == "death":
            self.deaths_caused += 1
            return f"{event['name']}. Toplam ölüm: {self.deaths_caused}"
        elif etype == "inheritance":
            amount = round(random.uniform(event["min_amount"], event["max_amount"]), 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event["message_template"].format(amount=f"{amount:,.2f}")
        return f"{event.get('name', 'Bilinmeyen olay')} gerçekleşti"

    def trigger_random_events(self, probability: float = 0.60, min_events: int = 1, max_events: int = 3):
        messages = []

        # Çok nadir, hayat değiştiren büyük olaylar (örn. miras). Bunlar
        # normal olay havuzunun dışında, kendi düşük ihtimalleriyle
        # ayrıca kontrol edilir; böylece diğer olaylarla eşit sıklıkta
        # tetiklenmezler.
        for rare_event in RARE_EVENTS:
            if random.random() < rare_event.get("chance", 0.005):
                messages.append(self.apply_event(rare_event))

        if random.random() < probability:
            count = random.randint(min_events, min(max_events, len(EVENTS)))
            chosen = random.sample(EVENTS, count)
            messages.extend(self.apply_event(event) for event in chosen)

        return messages

    def apply_daily_hustle_income(self) -> float:
        """
        Her gün, elimizdeki nakitten bağımsız olarak küçük, garanti bir
        gelir sağlar (ufak iş, bahşiş, küçük alışverişler vb.). Amaç,
        oyuncunun sadece rastgele olay şansına bağlı kalmadan, gün
        geçirdikçe azıcık da olsa para kazanmasını sağlamaktır.
        Kayıptan çok kazanç hissettirmesi için sabit bir taban ve
        düşük bir tavanla sınırlandırılmıştır.
        """
        base = random.uniform(150.0, 450.0)
        pct_bonus = self.cash * random.uniform(0.002, 0.01)
        income = round(min(base + pct_bonus, 5000.0), 2)
        self.cash += income
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        return income

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
        self.land_loan_btn = wx.Button(panel, label="Arsa Kredisi")
        self.pay_loan_btn = wx.Button(panel, label="Kredi Öde")
        btn_sizer1.Add(self.buy_btn, 0, wx.ALL, 5)
        btn_sizer1.Add(self.sell_btn, 0, wx.ALL, 5)
        btn_sizer1.Add(self.land_loan_btn, 0, wx.ALL, 5)
        btn_sizer1.Add(self.pay_loan_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer1, 0, wx.ALIGN_CENTER, 5)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((500, 80))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.buy_btn.Bind(wx.EVT_BUTTON, self.on_buy_land)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell_land)
        self.land_loan_btn.Bind(wx.EVT_BUTTON, self.on_land_loan)
        self.pay_loan_btn.Bind(wx.EVT_BUTTON, self.on_pay_land_loan)
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
                loan_str = f" [Kredili, borç: {debt:,.0f} TL]"
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
            f"Nakit: {self.state.cash:,.0f} TL | "
            f"Temiz Para: {self.state.clean_money:,.0f} TL"
        )
        self.status_text.SetValue(status)

        has_land = len(self.state.lands) > 0
        has_loaned_land = any(land.get("has_loan", False) for land in self.state.lands)
        self.sell_btn.Enable(has_land)
        self.land_loan_btn.Enable(has_land)
        self.pay_loan_btn.Enable(has_loaned_land and self.state.clean_money > 0)

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

    def on_land_loan(self, event):
        idx = self.land_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Lütfen kredi çekmek istediğiniz arsayı seçin")
            return
        
        land = self.state.lands[idx]
        if land.get("has_loan", False):
            speak("Bu arsa üzerinde zaten kredi var")
            return
        
        limit = self.state.get_land_loan_limit(idx)
        if limit <= 0:
            speak("Bu arsa için kredi limiti yok")
            return
        
        dlg = wx.TextEntryDialog(
            self, 
            f"Arsa teminatlı kredi limiti: {limit:,.0f} TL\nMiktar girin:",
            "Arsa Kredisi"
        )
        if dlg.ShowModal() == wx.ID_OK:
            try:
                amount = float(dlg.GetValue().replace(",", "."))
                success, msg = self.state.take_land_loan(idx, amount)
                speak(msg)
                if success:
                    self._update_ui()
                    self.parent.auto_save()
            except ValueError:
                speak("Geçersiz miktar")
        dlg.Destroy()

    def on_pay_land_loan(self, event):
        idx = self.land_list.GetSelection()
        if idx == wx.NOT_FOUND:
            speak("Lütfen kredi ödemek istediğiniz arsayı seçin")
            return

        land = self.state.lands[idx]
        if not land.get("has_loan", False):
            speak("Bu arsada aktif kredi yok")
            return

        debt = land.get("loan_debt", land.get("loan_amount", 0.0) * 1.15)
        dlg = wx.TextEntryDialog(
            self,
            f"Kalan borç: {debt:,.0f} TL\nÖdeme miktarı girin:",
            "Arsa Kredisi Öde"
        )
        if dlg.ShowModal() == wx.ID_OK:
            try:
                amount = float(dlg.GetValue().replace(",", "."))
                success, msg = self.state.pay_land_loan(idx, amount)
                speak(msg)
                if success:
                    self._update_ui()
                    self.parent.auto_save()
            except ValueError:
                speak("Geçersiz miktar")
        dlg.Destroy()


# ============================================================
# MENU SINIFLARI
# ============================================================

class MainMenu(wx.Dialog):
    def __init__(self, parent=None):
        super().__init__(parent, title="Karaborsa", size=(350, 400))
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
        
        self.menu_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        self.menu_list.SetItems([
            "Yeni Oyun",
            "Devam Et",
            "Yardım",
            "Çıkış"
        ])
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
        if idx == 0:
            self.start_new_game()
        elif idx == 1:
            self.continue_game()
        elif idx == 2:
            open_help()
        elif idx == 3:
            self.EndModal(wx.ID_CANCEL)
    
    def start_new_game(self):
        dlg = wx.TextEntryDialog(self, "Kullanıcı adınız:", "Kullanıcı Adı")
        if dlg.ShowModal() == wx.ID_OK:
            username = dlg.GetValue().strip()
            dlg.Destroy()
            if not username:
                speak("Kullanıcı adı boş olamaz")
                return
            saves = list_saves()
            if username in saves:
                if wx.MessageBox(f"'{username}' kayıtlı. Üzerine yaz?", "Uyarı", wx.YES_NO) != wx.YES:
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


# ============================================================
# OYUN DIALOGLARI
# ============================================================

class CompanyDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title="Şirket Yönetimi", size=(600, 450))
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

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((500, 120))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        guide = wx.StaticText(
            panel,
            label=(
                "Rehber: Düşük sermayeyle başlamak için Tekstil Atölyesi veya "
                "Restoran uygundur. Yüksek kirli para hacmini hızlı aklamak "
                "isterseniz Kripto Madenciliği veya Gece Kulübü daha uygundur, "
                "ancak günlük giderleri de yüksektir. Oto Galeri dengeli bir "
                "orta seçenektir. Listeden bir tip seçtiğinizde altta o "
                "şirketin maliyet, gider ve aklama kapasitesi ile mevcut "
                "bakiyenize göre uygun olup olmadığı gösterilir."
            ),
        )
        guide.Wrap(520)
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
        self.detail_text.SetMinSize((500, 90))
        sizer.Add(self.detail_text, 0, wx.EXPAND | wx.ALL, 5)

        name_sizer = wx.BoxSizer(wx.HORIZONTAL)
        name_sizer.Add(wx.StaticText(panel, label="Şirket Adı:"), 0, wx.ALL | wx.CENTER, 5)
        self.name_input = wx.TextCtrl(panel)
        name_sizer.Add(self.name_input, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(name_sizer, 0, wx.EXPAND | wx.ALL, 5)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.setup_btn = wx.Button(panel, label="Kur")
        self.close_btn = wx.Button(panel, label="Kapat")
        btn_sizer.Add(self.setup_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.close_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _format_company_choice(self, key, data):
        cost = data["setup_cost"]
        upkeep = data["daily_upkeep"]
        capacity = data["laundering_capacity"] * 100
        afford = "Kurulabilir" if self.state.cash >= cost else "Nakit yetersiz"
        return (
            f"{key} — Kuruluş: {cost:,.0f} TL, Günlük Gider: {upkeep:,.0f} TL, "
            f"Aklama Kapasitesi: %{capacity:.0f}, {afford} "
            f"({data.get('description', '')})"
        )

    def _bind_events(self):
        self.setup_btn.Bind(wx.EVT_BUTTON, self.on_setup)
        self.close_btn.Bind(wx.EVT_BUTTON, self.on_close_company)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))
        self.type_combo.Bind(wx.EVT_COMBOBOX, self.on_type_selected)

    def _update_ui(self):
        if self.state.has_company:
            self.status_text.SetValue(
                f"Şirket: {self.state.company_name}\n"
                f"Tip: {self.state.company_type}\n"
                f"Kredi Notu: {self.state.company_credit_score}\n"
                f"Aktif Gün: {self.state.company_days_active}\n"
                f"Toplam Aklanan: {self.state.company_total_laundered:,.2f} TL\n"
                f"Aylık Ciro: {self.state.company_monthly_revenue:,.2f} TL\n"
                f"Temiz Para: {self.state.clean_money:,.2f} TL"
            )
            self.detail_text.SetValue("")
            self.type_combo.Enable(False)
            self.name_input.Enable(False)
            self.setup_btn.Enable(False)
            self.close_btn.Enable(True)
        else:
            self.status_text.SetValue("Aktif şirket yok")
            self.detail_text.SetValue(
                "Bir şirket tipi seçtiğinizde ayrıntılar burada görünecek."
            )
            self.type_combo.Enable(True)
            self.name_input.Enable(True)
            self.setup_btn.Enable(True)
            self.close_btn.Enable(False)

    def _get_selected_company_type(self):
        idx = self.type_combo.GetSelection()
        if idx == wx.NOT_FOUND:
            return ""
        return self.type_combo.GetClientData(idx)

    def on_type_selected(self, event):
        company_type = self._get_selected_company_type()
        data = COMPANY_TYPES.get(company_type)
        if not data:
            return

        cost = data["setup_cost"]
        upkeep = data["daily_upkeep"]
        capacity = data["laundering_capacity"] * 100

        affordable = self.state.cash >= cost
        afford_text = "Şu an nakitiniz yeterli." if affordable else (
            f"Şu an nakitiniz yetersiz (eksik: {cost - self.state.cash:,.2f} TL)."
        )

        detail = (
            f"{company_type}\n"
            f"Kuruluş maliyeti: {cost:,.2f} TL | Günlük gider: {upkeep:,.2f} TL | "
            f"Aklama kapasitesi: %{capacity:.0f}\n"
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

        success, msg = self.state.setup_company(company_type, company_name)
        speak(msg)
        if success:
            self._update_ui()

    def on_close_company(self, event):
        if not self.state.has_company:
            return

        if wx.MessageBox("Şirketi kapatmak istediğinize emin misiniz?", "Onay", wx.YES_NO | wx.ICON_WARNING) == wx.YES:
            success, msg = self.state.close_company()
            speak(msg)
            if success:
                self._update_ui()


class LaunderDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title="Para Aklama", size=(400, 300))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="PARA AKLAMA")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.StaticText(panel, label="")
        sizer.Add(self.status_text, 0, wx.ALL | wx.CENTER, 5)

        amount_sizer = wx.BoxSizer(wx.HORIZONTAL)
        amount_sizer.Add(wx.StaticText(panel, label="Aklanacak Miktar:"), 0, wx.ALL | wx.CENTER, 5)
        self.amount_input = wx.TextCtrl(panel)
        amount_sizer.Add(self.amount_input, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(amount_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.launder_btn = wx.Button(panel, label="Aklama Yap")
        sizer.Add(self.launder_btn, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.launder_btn.Bind(wx.EVT_BUTTON, self.on_launder)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        company_data = COMPANY_TYPES.get(self.state.company_type, {})
        max_launder = self.state.dirty_cash * company_data.get("laundering_capacity", 0.3)

        self.status_text.SetLabel(
            f"Kirli Para: {self.state.dirty_cash:,.2f} TL\n"
            f"Maksimum Aklama: {max_launder:,.2f} TL\n"
            f"Kredi Notu: {self.state.company_credit_score}"
        )

    def on_launder(self, event):
        try:
            amount = float(self.amount_input.GetValue().replace(",", "."))
        except ValueError:
            speak("Geçerli miktar girin")
            return

        success, msg = self.state.launder_money(amount)
        speak(msg)
        if success:
            self._update_ui()
            self.amount_input.SetValue("")


class LoanDialog(wx.Dialog):
    def __init__(self, parent, state):
        super().__init__(parent, title="Ticari Kredi", size=(500, 400))
        self.parent = parent
        self.state = state
        self._build_ui()
        self._bind_events()
        self._update_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label="TİCARİ KREDİ")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)

        self.status_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE)
        self.status_text.SetMinSize((400, 100))
        sizer.Add(self.status_text, 0, wx.EXPAND | wx.ALL, 10)

        amount_sizer = wx.BoxSizer(wx.HORIZONTAL)
        amount_sizer.Add(wx.StaticText(panel, label="Kredi Miktarı:"), 0, wx.ALL | wx.CENTER, 5)
        self.amount_input = wx.TextCtrl(panel)
        amount_sizer.Add(self.amount_input, 1, wx.ALL | wx.CENTER, 5)
        sizer.Add(amount_sizer, 0, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.take_btn = wx.Button(panel, label="Kredi Çek")
        self.pay_btn = wx.Button(panel, label="Taksit Öde")
        btn_sizer.Add(self.take_btn, 0, wx.ALL, 5)
        btn_sizer.Add(self.pay_btn, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.take_btn.Bind(wx.EVT_BUTTON, self.on_take_loan)
        self.pay_btn.Bind(wx.EVT_BUTTON, self.on_pay_loan)
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        limit = self.state.get_loan_limit()
        tier = self.state.get_credit_tier()

        if self.state.loan_amount > 0:
            self.status_text.SetValue(
                f"Aktif Kredi: {self.state.loan_amount:,.2f} TL\n"
                f"Toplam Borç: {self.state.loan_total_debt:,.2f} TL\n"
                f"Kalan Gün: {self.state.loan_days_remaining}\n"
                f"Faiz Oranı: %{self.state.loan_interest_rate*100:.1f}\n\n"
                f"Kredi Notu: {self.state.company_credit_score}\n"
                f"Kredi Limiti: {limit:,.2f} TL"
            )
            self.take_btn.Enable(False)
            self.pay_btn.Enable(True)
        else:
            if tier and tier["can_loan"]:
                status_text = (
                    f"Kredi Notu: {self.state.company_credit_score}\n"
                    f"Kredi Limiti: {limit:,.2f} TL\n"
                    f"Faiz Oranı: %{tier['interest_rate']*100:.1f}\n"
                    f"Durum: Kredi çekilebilir"
                )
            else:
                status_text = (
                    f"Kredi Notu: {self.state.company_credit_score}\n"
                    f"Durum: Kredi notu yetersiz veya şirket yok"
                )
            self.status_text.SetValue(status_text)
            self.take_btn.Enable(True if tier and tier["can_loan"] else False)
            self.pay_btn.Enable(False)

    def on_take_loan(self, event):
        try:
            amount = float(self.amount_input.GetValue().replace(",", "."))
        except ValueError:
            speak("Geçerli miktar girin")
            return

        success, msg = self.state.take_loan(amount)
        speak(msg)
        if success:
            self._update_ui()
            self.amount_input.SetValue("")

    def on_pay_loan(self, event):
        try:
            amount = float(self.amount_input.GetValue().replace(",", "."))
        except ValueError:
            speak("Geçerli miktar girin")
            return

        success, msg = self.state.pay_loan_installment(amount)
        speak(msg)
        if success:
            self._update_ui()
            self.amount_input.SetValue("")


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

        self.interest_text = wx.StaticText(panel, label=f"Günlük Faiz: %{self.state.BANK_INTEREST_RATE*100:.1f}")
        sizer.Add(self.interest_text, 0, wx.ALL | wx.CENTER, 5)

        self.done_btn = wx.Button(panel, label="Tamam")
        sizer.Add(self.done_btn, 0, wx.ALL | wx.CENTER, 10)

        panel.SetSizer(sizer)

    def _bind_events(self):
        self.done_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK))

    def _update_ui(self):
        self.status_text.SetLabel(
            f"Temiz Para: {self.state.clean_money:,.2f} TL\n"
            f"Nakit: {self.state.cash:,.2f} TL"
        )


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

class MainFrame(wx.Frame):
    SOUND_MUSIC = resource_path("sounds/game_music.mp3")
    SOUND_PRISON = resource_path("sounds/prison.mp3")
    SOUND_BUY = resource_path("sounds/para.mp3")
    SOUND_SELL = resource_path("sounds/buy.ogg")
    SOUND_BUTTON = resource_path("sounds/DROPDOWNBUTTONGRID.mp3")
    SOUND_NAVIGATE = resource_path("sounds/button.wav")
    SOUND_TRANSITION = resource_path("sounds/transition.mp3")
    SOUND_POLICE = resource_path("sounds/polis_siren.mp3")

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
        self.launder_btn = wx.Button(panel, label="Para Aklama")
        self.loan_btn = wx.Button(panel, label="Ticari Kredi")
        btn_sizer2.Add(self.company_btn, 0, wx.ALL, 3)
        btn_sizer2.Add(self.launder_btn, 0, wx.ALL, 3)
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
        self.SetStatusText("F1: Yardım | F6: Arsa | C: Nakit | D: Kategori | E: Envanter | PgUp/PgDn: Ses | Otomatik kayıt aktif")

        panel.SetSizer(sizer)
        self.product_list.SetFocus()

    def _bind_events(self):
        self.buy_btn.Bind(wx.EVT_BUTTON, self.on_buy)
        self.sell_btn.Bind(wx.EVT_BUTTON, self.on_sell)
        self.next_btn.Bind(wx.EVT_BUTTON, self.on_next_day)
        self.company_btn.Bind(wx.EVT_BUTTON, self.on_company)
        self.launder_btn.Bind(wx.EVT_BUTTON, self.on_launder)
        self.loan_btn.Bind(wx.EVT_BUTTON, self.on_loan)
        self.bank_btn.Bind(wx.EVT_BUTTON, self.on_banking)
        self.land_btn.Bind(wx.EVT_BUTTON, self.on_land_management)
        self.status_btn.Bind(wx.EVT_BUTTON, self.on_status)
        
        self.Bind(wx.EVT_CHAR_HOOK, self.on_key_down)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def set_jail_mode(self, in_jail: bool):
        for btn in [self.buy_btn, self.sell_btn, self.next_btn,
                    self.company_btn, self.launder_btn, self.loan_btn,
                    self.bank_btn, self.land_btn, self.status_btn]:
            btn.Enable(not in_jail)
        self.product_list.Enable(not in_jail)
        self.qty_spinner.Enable(not in_jail)
        if in_jail:
            self.SetStatusText(f"HAPİSTE - {self.state.jail_days} gün kaldı")
        else:
            self.SetStatusText("F1: Yardım | F6: Arsa | C: Nakit | D: Kategori | E: Envanter | PgUp/PgDn: Ses | Otomatik kayıt aktif")

    def refresh_product_list(self, keep_selection: bool = True):
        prev_name = self.get_selected_product() if keep_selection else None
        self.set_jail_mode(self.state.in_jail)

        rows = []
        for name in self.flat_products:
            price = self.state.prices[name]
            qty = self.state.inventory.get(name, 0)
            label = f"{name} - {price:,.2f} TL ({qty} adet)"
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

    def on_launder(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        if not self.state.has_company:
            speak("Önce şirket kurun")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = LaunderDialog(self, self.state)
        if dlg.ShowModal() == wx.ID_OK:
            self.refresh_product_list()
            self.update_wallet_display()
            self.auto_save()
        dlg.Destroy()

    def on_loan(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz")
            return

        if not self.state.has_company:
            speak("Önce şirket kurun")
            return

        self.play_sound(self.SOUND_BUTTON)
        dlg = LoanDialog(self, self.state)
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
            f"Nakit: {self.state.cash:,.2f} TL",
            f"Kirli Para: {self.state.dirty_cash:,.2f} TL",
            f"Temiz Para: {self.state.clean_money:,.2f} TL",
            f"Polis Riski: %{self.state.police_heat:.1f}",
            f"Toplam Suçlu Gelir: {self.state.total_crime:,.2f} TL",
            f"En Yüksek Nakit: {self.state.highest_cash:,.2f} TL",
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
                f"Tip: {self.state.company_type}",
                f"Kredi Notu: {self.state.company_credit_score}",
                f"Aktif Gün: {self.state.company_days_active}",
                f"Toplam Aklanan: {self.state.company_total_laundered:,.2f} TL",
                f"Aylık Ciro: {self.state.company_monthly_revenue:,.2f} TL",
            ])

            if self.state.loan_amount > 0:
                lines.extend([
                    "",
                    "KREDİ BİLGİLERİ",
                    "-" * 30,
                    f"Kredi Miktarı: {self.state.loan_amount:,.2f} TL",
                    f"Toplam Borç: {self.state.loan_total_debt:,.2f} TL",
                    f"Kalan Gün: {self.state.loan_days_remaining}",
                    f"Faiz Oranı: %{self.state.loan_interest_rate*100:.1f}",
                ])
        else:
            lines.append("Şirket: Yok")

        if self.state.deaths_caused > 0:
            lines.append(f"Ölümler: {self.state.deaths_caused}")

        text = "\n".join(lines)
        speak(text)

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

    def on_next_day(self, event):
        if self.state.in_jail:
            speak("Hapistesiniz. Bekleyin")
            return

        self.play_sound(self.SOUND_TRANSITION)
        
        self.state.day += 1
        
        speak(f"Gün {self.state.day} başladı")

        if self.state.has_company:
            self.state.company_days_active += 1
            if self.state.company_days_active % 30 == 0:
                self.state.company_monthly_revenue = 0.0

        self.state.fluctuate_prices()

        if self.state.has_company:
            if not self.state.pay_company_upkeep():
                speak("Şirketiniz kapandı. İşletme giderleri karşılanamadı")
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
                return

        if self.state.loan_amount > 0:
            success, msg = self.state.process_loan_daily()
            if not success:
                self.state.default_loan()
                speak("Kredi temerrüdü. Şirket kapatıldı")
                self.refresh_product_list()
                self.update_wallet_display()
                self.auto_save()
                return

        bank_interest = self.state.apply_bank_interest()
        hustle_income = self.state.apply_daily_hustle_income()

        police = self.state.police_check()

        if police["caught"]:
            self.audio.play_sound(self.SOUND_POLICE)
            bribe_amount = police["bribe_amount"]

            if police["can_bribe"] and self.state.cash > 0:
                msg = (f"POLİS YAKALADI!\n\n"
                       f"Kirli para: {self.state.dirty_cash:,.2f} TL\n"
                       f"Rüşvet miktarı: {bribe_amount:,.2f} TL\n"
                       f"Rüşvet ver?")

                dlg = wx.MessageDialog(self, msg, "POLİS TARAFINDAN YAKALANDINIZ",
                                      wx.YES_NO | wx.ICON_WARNING)
                dlg.SetYesNoLabels("Evet, rüşvet ver", "Hayır, hapse gir")

                if dlg.ShowModal() == wx.ID_YES:
                    if self.state.bribe_police(bribe_amount):
                        speak(f"Rüşvet verdiniz. {bribe_amount:,.2f} TL ödendi")
                        self.update_wallet_display()
                        self.refresh_product_list()
                        self.auto_save()
                        dlg.Destroy()
                        events = self.state.trigger_random_events()
                        self.refresh_product_list()
                        self.update_wallet_display()
                        msgs = []
                        if bank_interest > 0:
                            msgs.append(f"Banka faizi: {bank_interest:,.2f} TL")
                        if hustle_income > 0:
                            msgs.append(f"Günlük kazanç: {hustle_income:,.2f} TL")
                        if events:
                            msgs.extend(events)
                        if msgs:
                            speak(" ".join(msgs))
                            self.auto_save()
                        return
                    else:
                        speak("Rüşvet veremediniz. Polis tutukluyor")
                        days = random.randint(1, 3)
                        self.state.go_to_jail(days)
                        dlg.Destroy()
                        self.update_wallet_display()
                        self.refresh_product_list()
                        self.auto_save()
                        wx.CallAfter(self.start_jail_dialog)
                        return
                else:
                    speak("Rüşvet vermeyi reddettiniz. Polis tutukluyor")
                    days = random.randint(1, 3)
                    self.state.go_to_jail(days)
                    dlg.Destroy()
                    self.update_wallet_display()
                    self.refresh_product_list()
                    self.auto_save()
                    wx.CallAfter(self.start_jail_dialog)
                    return
            else:
                speak("Polis yakaladı. Rüşvet verecek para yok. Tutuklanıyorsunuz")
                days = random.randint(1, 3)
                self.state.go_to_jail(days)
                self.update_wallet_display()
                self.refresh_product_list()
                self.auto_save()
                wx.CallAfter(self.start_jail_dialog)
                return

        events = self.state.trigger_random_events()

        self.refresh_product_list()
        self.update_wallet_display()

        msgs = []
        if bank_interest > 0:
            msgs.append(f"Banka faizi: {bank_interest:,.2f} TL")
        if hustle_income > 0:
            msgs.append(f"Günlük kazanç: {hustle_income:,.2f} TL")
        if events:
            msgs.extend(events)
        if msgs:
            speak(" ".join(msgs))

    def on_key_down(self, event: wx.KeyEvent):
        key = event.GetKeyCode()
        
        if key == wx.WXK_F1:
            open_help()
            return
        if key == wx.WXK_F2:
            self.on_status(event)
            return
        if key == wx.WXK_F5:
            self.on_next_day(event)
            return
        if key == wx.WXK_F6:
            self.on_land_management(event)
            return
        
        if key == ord('C') or key == ord('c'):
            cash_text = f"Nakit: {self.state.cash:,.2f} TL"
            if self.state.dirty_cash > 0:
                cash_text += f", Kirli para: {self.state.dirty_cash:,.2f} TL"
            if self.state.clean_money > 0:
                cash_text += f", Temiz para: {self.state.clean_money:,.2f} TL"
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
        if self.jail_dialog:
            self.jail_dialog.Destroy()
            self.jail_dialog = None
        if self.autosave_timer:
            self.autosave_timer.Stop()
        if self.username:
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