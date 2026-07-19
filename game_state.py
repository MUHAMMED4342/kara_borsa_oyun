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
    COMPANY_TYPES, CREDIT_TIERS, calculate_police_risk, INFORMANT_CONFIG,
    LAND_TYPES, EMPLOYEE_HIRE_FEE,
    EMPLOYEE_BASE_SALARY, EMPLOYEE_DAILY_MIN, EMPLOYEE_DAILY_MAX,
    load_names_from_file, load_cities_from_file,
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


# ---------------------------------------------------------------------------
# ADAM TUTMA - isim/şehir havuzları
# ---------------------------------------------------------------------------
# insanlar.txt ve iller.txt TEK KAYNAKTIR (oyunun ana klasöründe,
# resource_path ile bulunan yerde aranır). Dosya yoksa/bozuksa/boşsa
# ilgili havuz boş liste olur; "Adam Yönetimi" ekranı bunu zaten
# "Tutabileceğiniz kimse kalmadı" / "Boş şehir kalmadı" mesajlarıyla
# gösteriyor, oyun çökmez.
def _load_people_pool() -> list:
    return load_names_from_file(resource_path("insanlar.txt"))


def _load_city_list() -> list:
    """Düz şehir listesini döner (bölge kavramı YOK)."""
    return load_cities_from_file(resource_path("iller.txt"))


ACTIVE_PEOPLE_POOL = _load_people_pool()
ACTIVE_CITIES = _load_city_list()


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
    BANK_INTEREST_RATE = 0.015  # AYLIK oran - her 30 günde bir uygulanır (apply_bank_interest)

    def __init__(self, load_data=None):
        self.lands = []
        self.land_prices = {}
        
        if load_data:
            self.cash = load_data.get("cash", self.STARTING_CASH)
            self.clean_money = load_data.get("clean_money", self.STARTING_CLEAN_MONEY)
            self.day = load_data.get("day", 1)
            self.inventory = load_data.get("inventory", {name: 0 for name in PRODUCTS})
            self.prices = load_data.get("prices", {name: float(data["base_price"]) for name, data in PRODUCTS.items()})
            self.in_jail = load_data.get("in_jail", False)
            self.jail_days = load_data.get("jail_days", 0)
            self.has_company = load_data.get("has_company", False)
            self.company_type = load_data.get("company_type", "")
            self.company_name = load_data.get("company_name", "")
            self.company_city = load_data.get("company_city", "")
            self.company_credit_score = load_data.get("company_credit_score", 0)
            self.company_total_profit = load_data.get("company_total_profit", 0.0)
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
            self.has_informant = load_data.get("has_informant", False)
            self.informant_warning_active = load_data.get("informant_warning_active", False)
            self.police_heat = load_data.get("police_heat", 0)
            self.total_crime = load_data.get("total_crime", 0.0)
            self.deaths_caused = load_data.get("deaths_caused", 0)
            self.highest_cash = load_data.get("highest_cash", self.cash)
            self.days_until_bank_interest = load_data.get("days_until_bank_interest", 30)
            
            self.lands = load_data.get("lands", [])
            self.land_prices = load_data.get("land_prices", {})

            self.employees = load_data.get("employees", [])
            self._backfill_employee_defaults()

            for name in PRODUCTS:
                if name not in self.inventory:
                    self.inventory[name] = 0
                if name not in self.prices:
                    self.prices[name] = float(PRODUCTS[name]["base_price"])
            
            if not self.land_prices:
                self._init_land_prices()
        else:
            self.cash = self.STARTING_CASH
            self.clean_money = self.STARTING_CLEAN_MONEY
            self.day = 1
            self.inventory = {name: 0 for name in PRODUCTS}
            self.prices = {name: float(data["base_price"]) for name, data in PRODUCTS.items()}
            self.in_jail = False
            self.jail_days = 0
            self.has_company = False
            self.company_type = ""
            self.company_name = ""
            self.company_city = ""
            self.company_credit_score = 0
            self.company_days_active = 0
            self.company_total_profit = 0.0
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
            self.has_informant = False
            self.informant_warning_active = False
            self.police_heat = 0
            self.total_crime = 0.0
            self.deaths_caused = 0
            self.highest_cash = self.cash
            self.days_until_bank_interest = 30
            
            self.lands = []
            self.land_prices = {}
            self._init_land_prices()

            self.employees = []

    def _backfill_employee_defaults(self):
        """Eski kayıtlardan gelen adam kayıtlarında eksik alan varsa doldurur.
        NOT: Adamlar artık şirket kurmuyor; eski kayıtlarda kalmış olabilecek
        company_type/company_name/region/credit_score/monthly_revenue/
        total_laundered/upkeep_unpaid_days gibi alanlar varsa dokunulmadan
        kalır ama artık hiçbir yerde kullanılmaz."""
        defaults = {
            "total_generated": 0.0,
            "days_active": 0,
            "hired_day": self.day,
            "salary": EMPLOYEE_BASE_SALARY,
            "days_until_salary": 30,
        }
        for e in self.employees:
            for key, value in defaults.items():
                e.setdefault(key, value)

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
        
        self._spend_cash(price)
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
        
        # Kredi tutarı gerçek, harcanabilir paradır: hem "temiz para"
        # etiketine HEM de toplam nakde (cash) eklenmeli. clean_money,
        # cash'in bir alt kümesi olduğu için (bkz. buy_bulk), sadece
        # clean_money'i artırmak parayı gerçekte oyuncuya vermez.
        self.clean_money += amount
        self.cash += amount
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        
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

        self._reduce_clean_money(debt)
        self.cash -= debt
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
        if self.clean_money > 0:
            base += f" | Temiz: {format_tl(self.clean_money)} TL"
        if self.has_company:
            base += f" | Şirket: {self.company_name} ({self.company_city})"
            if self.loan_amount > 0:
                base += f" | Kredi: {format_tl(self.loan_amount)} TL"
        if self.lands:
            base += f" | Arsa: {len(self.lands)} adet"
        if self.employees:
            base += f" | Adamlar: {len(self.employees)}"
        if self.has_informant:
            base += " | Muhbir: aktif"
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

        if self.employees:
            parts.append("\nAdamlarınız:")
            for e in self.employees:
                parts.append(
                    f"{e['name']} ({e['city']}) - "
                    f"maaşa {e['days_until_salary']} gün kaldı"
                )

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

        if self.clean_money > 0:
            from_clean = min(self.clean_money, total_price)
            self._reduce_clean_money(from_clean)

        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        return True, total_price, f"{quantity} adet {name} alındı"

    def sell_bulk(self, name: str, quantity: int) -> tuple:
        if self.inventory.get(name, 0) < quantity:
            return False, 0, "Yeterli stok yok"
        total_price = self.prices[name] * quantity
        self.inventory[name] -= quantity
        self.cash += total_price
        self.total_crime += total_price
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        speak(f"{quantity} adet {name} satıldı, {format_tl(total_price)} TL kazanıldı")
        return True, total_price, f"{quantity} adet {name} satıldı"

    # ----- ADAM TUTMA METOTLARI (Şirketten TAMAMEN bağımsız) -----

    def get_available_people(self) -> list:
        """Henüz kimse tarafından tutulmamış isimlerin listesi."""
        hired = {e["name"] for e in self.employees}
        return [n for n in ACTIVE_PEOPLE_POOL if n not in hired]

    def get_occupied_cities(self) -> set:
        return {e["city"] for e in self.employees}

    def get_available_cities(self) -> list:
        """Henüz adam gönderilmemiş şehirlerin düz listesi (bölge yok)."""
        occupied = self.get_occupied_cities()
        return [city for city in ACTIVE_CITIES if city not in occupied]

    def get_city_list(self) -> list:
        """Tüm şehirlerin düz listesi (şirket kurarken de kullanılır)."""
        return list(ACTIVE_CITIES)

    def get_employee_hire_cost(self) -> float:
        return float(EMPLOYEE_HIRE_FEE)

    def get_employee_salary(self) -> float:
        return float(EMPLOYEE_BASE_SALARY)

    def _next_employee_id(self) -> int:
        used = [e.get("id", 0) for e in self.employees]
        return (max(used) + 1) if used else 1

    def get_employee(self, employee_id: int) -> dict:
        for e in self.employees:
            if e["id"] == employee_id:
                return e
        return None

    def hire_employee(self, name: str, city: str) -> tuple:
        """Bir adamı tutup bir şehre gönderir. Adam kendi başına o şehirde
        karaborsa işi çevirir; hiçbir şirket kurmaz. Oyuncu sadece kiralama
        masrafını öder ve 30 günde bir maaş verir."""
        if name not in self.get_available_people():
            return False, "Bu kişi zaten tutulmuş ya da geçersiz"

        if city not in ACTIVE_CITIES:
            return False, "Geçersiz şehir"

        if city in self.get_occupied_cities():
            return False, f"{city} ilinde zaten bir adamınız var"

        cost = self.get_employee_hire_cost()
        if self.cash < cost:
            return False, f"Yetersiz nakit. Gereken: {format_tl(cost)} TL"

        self._spend_cash(cost)
        salary = self.get_employee_salary()

        employee = {
            "id": self._next_employee_id(),
            "name": name,
            "city": city,
            "total_generated": 0.0,
            "days_active": 0,
            "hired_day": self.day,
            "salary": salary,
            "days_until_salary": 30,
        }
        self.employees.append(employee)

        return True, (
            f"{name}, {city} iline gönderildi. Kiralama masrafı: {format_tl(cost)} TL. "
            f"30 günde bir maaş: {format_tl(salary)} TL"
        )

    def fire_employee(self, employee_id: int) -> tuple:
        for i, e in enumerate(self.employees):
            if e["id"] == employee_id:
                name, city = e["name"], e["city"]
                self.employees.pop(i)
                return True, f"{name} kovuldu. {city} artık boş, başka bir adam gönderebilirsiniz."
        return False, "Adam bulunamadı"

    def employee_summary_text(self) -> str:
        if not self.employees:
            return "Hiç adamınız yok."
        parts = [f"Toplam {len(self.employees)} adamınız var.", "Adamlarınız:"]
        for e in self.employees:
            parts.append(
                f"{e['name']} - {e['city']} - Aktif Gün: {e['days_active']} - "
                f"Toplam Ürettiği: {format_tl(e['total_generated'])} TL - "
                f"Maaş: {format_tl(e['salary'])} TL, maaşa {e['days_until_salary']} gün kaldı"
            )
        return " ".join(parts)

    def process_employees_daily(self) -> list:
        """Her gün: her adam kendi şehrinde karaborsa işi çevirip nakit
        üretir. 30 günde bir oyuncudan maaşını alır. Maaş ödenemezse adam
        sizi terk eder."""
        messages = []
        to_remove = []

        for e in self.employees:
            e["days_active"] += 1

            # Deneyim arttıkça (maks +%50) biraz daha fazla üretir.
            experience_bonus = min(0.5, e["days_active"] / 200)
            gross = round(random.uniform(EMPLOYEE_DAILY_MIN, EMPLOYEE_DAILY_MAX) * (1 + experience_bonus), 2)

            self.cash += gross
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash

            e["total_generated"] += gross

            e["days_until_salary"] -= 1
            if e["days_until_salary"] <= 0:
                salary = e["salary"]
                paid = self._auto_deduct(salary)
                if paid < salary - 0.01:
                    messages.append(
                        f"{e['name']} ({e['city']}) maaşını alamadı ve sizi terk etti!"
                    )
                    to_remove.append(e["id"])
                    continue
                e["days_until_salary"] = 30
                messages.append(
                    f"{e['name']} ({e['city']}): maaş ödendi ({format_tl(salary)} TL). "
                    f"Bu dönem ürettiği: {format_tl(gross)} TL"
                )

        if to_remove:
            self.employees = [e for e in self.employees if e["id"] not in to_remove]

        return messages

    def go_to_jail(self, days: int) -> str:
        seized = round(self.cash * 0.25, 2)
        if seized > 0:
            if self.clean_money > 0:
                self._reduce_clean_money(min(self.clean_money, seized))
            self.cash -= seized
            if self.cash < 0:
                self.cash = 0.0
        self.in_jail = True
        self.jail_days = days
        if seized > 0:
            return f"{days} gün hapis cezası. Ayrıca paranızın çeyreğine ({format_tl(seized)} TL) el konuldu"
        return f"{days} gün hapis cezası"

    def setup_company(self, company_type: str, company_name: str, city: str = "") -> tuple:
        """Oyuncunun kendi şirketini kurar. Adamlar sisteminden TAMAMEN
        bağımsızdır; şehir seçimi burada sadece hangi ilde faaliyet
        gösterdiğinizi belirtir, bir adamınızın olduğu şehirle çakışması
        gerekmez."""
        if self.has_company:
            return False, "Zaten şirketiniz var"

        if company_type not in COMPANY_TYPES:
            return False, "Geçersiz şirket tipi"

        if city and city not in ACTIVE_CITIES:
            return False, "Geçersiz şehir"

        company_data = COMPANY_TYPES[company_type]
        cost = company_data["setup_cost"]

        if self.cash < cost:
            return False, f"Yetersiz nakit. Kurulum maliyeti: {format_tl(cost)} TL"

        self._spend_cash(cost)
        self.has_company = True
        self.company_type = company_type
        self.company_name = company_name
        self.company_city = city
        self.company_credit_score = 50
        self.company_days_active = 0
        self.company_total_profit = 0.0
        self.company_monthly_revenue = 0.0
        self.company_upkeep_paid = 0

        city_text = f" ({city})" if city else ""
        return True, f"{company_name}{city_text} kuruldu. Başlangıç kredi notu: 50"

    def close_company(self) -> tuple:
        if not self.has_company:
            return False, "Aktif şirket yok"

        if self.loan_amount > 0:
            return False, "Önce kredi borcunu kapatın"

        self.has_company = False
        self.company_type = ""
        self.company_name = ""
        self.company_city = ""
        self.company_credit_score = 0
        self.company_total_profit = 0.0
        self.company_monthly_revenue = 0.0
        self.company_days_active = 0

        return True, "Şirket kapatıldı"

    def _spend_cash(self, amount: float) -> None:
        """self.cash'i doğrudan azaltan (arsa/şirket/adam alımı, rüşvet,
        ceza gibi) yerlerde kullanılır. clean_money, cash'in bir alt kümesi
        (etiketi) olduğu için, harcama clean_money'den fazla düşerse önce
        clean_money etiketi düzeltilir; böylece 'Temiz Para', 'Nakit'ten
        büyük görünmeye başlamaz."""
        amount = round(amount, 2)
        if amount <= 0:
            return
        self.cash -= amount

        if self.clean_money > self.cash:
            self._reduce_clean_money(self.clean_money - self.cash)

    def _reduce_clean_money(self, amount: float) -> None:
        """clean_money her azaldığında çağrılmalı (harcama, kredi ödemesi,
        ceza vb.)."""
        if amount <= 0:
            return
        amount = min(amount, self.clean_money)
        self.clean_money -= amount

    def process_company_daily(self) -> str:
        """Her gün: şirketiniz varsa rastgele bir aralıkta doğrudan KÂR
        üretir. Kâr hem cash'e hem clean_money'e eklenir ve kredi notunu
        bir miktar yükseltir."""
        if not self.has_company:
            return ""

        company_data = COMPANY_TYPES[self.company_type]
        profit = round(random.uniform(
            company_data["daily_profit_min"], company_data["daily_profit_max"]
        ), 2)

        self.clean_money += profit
        self.cash += profit
        self.company_monthly_revenue += profit
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        credit_boost = max(1, int(profit / 500))
        self.company_credit_score += credit_boost
        self.company_total_profit = getattr(self, "company_total_profit", 0.0) + profit

        return f"{self.company_name}: {format_tl(profit)} TL kâr elde ettiniz"

    # ----- MUHBİR METOTLARI -----

    def hire_informant(self) -> tuple:
        if self.has_informant:
            return False, "Zaten bir muhbiriniz var"

        cost = INFORMANT_CONFIG["hire_cost"]
        if self.cash < cost:
            return False, f"Yetersiz nakit. Gereken: {format_tl(cost)} TL"

        self._spend_cash(cost)
        self.has_informant = True
        return True, (
            f"Muhbir tutuldu. Kiralama masrafı: {format_tl(cost)} TL. "
            f"Günlük ücret: {format_tl(INFORMANT_CONFIG['daily_upkeep'])} TL"
        )

    def fire_informant(self) -> tuple:
        if not self.has_informant:
            return False, "Muhbiriniz yok"
        self.has_informant = False
        self.informant_warning_active = False
        return True, "Muhbir kovuldu"

    def pay_informant_upkeep(self) -> bool:
        """Her gün çağrılır: muhbir varsa günlük ücretini öder. Ödenemezse
        muhbir sizi terk eder."""
        if not self.has_informant:
            return True

        upkeep = INFORMANT_CONFIG["daily_upkeep"]
        if self.cash >= upkeep:
            self._auto_deduct(upkeep)
            return True
        else:
            self.has_informant = False
            self.informant_warning_active = False
            return False

    def check_informant_warning(self) -> bool:
        """Muhbir doğrudan polisle bağlantılı olduğu için, YARIN gerçekten
        bir baskın olup olmayacağını (mevcut duruma göre aynı ihtimalle)
        önceden haber verir. Yani muhbiriniz varsa hiçbir baskın sizi
        habersiz yakalamaz - her gerçek baskından bir gün önce
        uyarılırsınız."""
        if not self.has_informant:
            return False
        return self.roll_police_catch()

    def dump_inventory_for_evasion(self) -> tuple:
        """Muhbir uyarısı üzerine mallar GERÇEK piyasa fiyatından hızlıca
        elden çıkarılır ve o günkü polis kontrolü tamamen atlanır. (adet,
        kazanç) döner."""
        total_earned = 0.0
        total_items = 0
        for name in list(self.inventory.keys()):
            qty = self.inventory.get(name, 0)
            if qty <= 0:
                continue
            price = self.prices.get(name, 0)
            earned = round(price * qty, 2)
            total_earned += earned
            total_items += qty
            self.inventory[name] = 0

        self.cash += total_earned
        self.total_crime += total_earned
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        return total_items, round(total_earned, 2)

    def pay_company_upkeep(self) -> bool:
        if not self.has_company:
            return True

        company_data = COMPANY_TYPES[self.company_type]
        upkeep = company_data["daily_upkeep"]

        if self.cash >= upkeep:
            # _auto_deduct önce temiz paradan, sonra etiketsiz nakitten
            # düşer - böylece cash < clean_money gibi tutarsız bir duruma
            # asla düşülmez.
            self._auto_deduct(upkeep)
            self.company_upkeep_paid += upkeep
            return True
        else:
            self.has_company = False
            self.company_type = ""
            self.company_name = ""
            self.company_city = ""
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
        # Kredi tutarı gerçek paradır: hem clean_money hem cash artmalı
        # (bkz. take_land_loan() içindeki aynı düzeltme için açıklama).
        self.clean_money += amount
        self.cash += amount
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

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

        self._reduce_clean_money(debt)
        self.cash -= debt
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
        """Bir ödemeyi önce temiz paradan, sonra nakitten otomatik olarak
        çeker. Gerçekte ödenebilen miktarı döner."""
        remaining = round(amount, 2)
        if remaining <= 0:
            return 0.0

        if self.clean_money > 0:
            pay = min(self.clean_money, remaining)
            self._reduce_clean_money(pay)
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
        self.company_city = ""
        self.company_credit_score = 0

        seized = self.clean_money
        self.clean_money = 0
        self.cash -= seized

        self._clear_loan()

        return True, f"Şirket kapatıldı. {format_tl(seized)} TL temiz para musadere edildi"

    def _illegal_inventory_value(self) -> float:
        """Elde bulundurulan yasa dışı ürünlerin (Karanlık Maddeler,
        Mühimmat & Silahlar) toplam piyasa değeri. Polis riski artık kirli
        para yerine bu değere göre hesaplanır."""
        total = 0.0
        for category in ("Karanlık Maddeler", "Mühimmat & Silahlar"):
            for name in PRODUCT_CATEGORIES.get(category, []):
                total += self.inventory.get(name, 0) * self.prices.get(name, 0.0)
        return total

    def update_police_heat(self) -> None:
        """Günlük olarak çağrılır: elde bulunan yasa dışı malın değerine
        göre birikimli polis riskini (heat) büyütür. Bir yakalanma zarı
        atmaz, sadece heat'i günceller."""
        illegal_value = self._illegal_inventory_value()
        self.police_heat = min(100, self.police_heat + (illegal_value / 50000) * 10)

    def roll_police_catch(self) -> bool:
        """Heat'i DEĞİŞTİRMEDEN, mevcut duruma göre bir yakalanma zarı
        atar. Hem gerçek zamanlı polis kontrolünde, hem de muhbirin
        "yarın baskın olacak mı" tahmininde kullanılır - böylece muhbir
        gerçekte olacak baskınla birebir aynı ihtimali kullanmış olur."""
        illegal_value = self._illegal_inventory_value()
        risk = calculate_police_risk(illegal_value) * (1 + self.police_heat / 100)
        return random.random() < risk

    def police_check(self) -> dict:
        """Muhbiri olmayan oyuncular için: heat güncellenir ve aynı anda
        gerçek zamanlı bir yakalanma zarı atılır."""
        self.update_police_heat()
        caught = self.roll_police_catch()
        return {"caught": caught}

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
            # Sabit bir TL aralığından rastgele kayıp: paranız ne olursa
            # olsun aynı gerçekçi tutar geçerli. Yeterli nakdiniz olmasa
            # bile tutar tam olarak düşülür; bakiye eksiye düşebilir.
            amount = round(random.uniform(event["min_amount"], event["max_amount"]), 2)
            self._spend_cash(amount)
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
            # Nakit kısmı da sabit bir TL aralığından çekiliyor (cüzdana
            # göre değil); yetersiz nakit varsa bakiye eksiye düşebilir.
            cash_loss = round(random.uniform(event["cash_min_amount"], event["cash_max_amount"]), 2)
            self._spend_cash(cash_loss)
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
                    # ÖNEMLİ: clean_money, cash'in bir ALT KÜMESİ (etiketi).
                    # Para gerçekten müsadere ediliyorsa (default_loan(),
                    # pay_company_upkeep(), _auto_deduct() gibi) her zaman
                    # HEM clean_money HEM de cash birlikte azaltılmalı;
                    # sadece clean_money'i azaltmak parayı "kaybettirmez",
                    # onu sessizce etiketsiz/nötr paraya çevirir. Önceden
                    # cash'e dokunulmadığı için bu ceza oyuncuya gerçekte
                    # hiçbir maliyet getirmiyordu.
                    self._reduce_clean_money(risk_amount)
                    self.cash -= risk_amount
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

    def trigger_random_events(self, probability: float = 0.70, min_events: int = 1, max_events: int = 3):
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
        """Temiz paraya faiz her gün çağrılsa bile sadece 30 günde bir
        (aylık) uygulanır; günlük bileşik büyümeyi önler."""
        self.days_until_bank_interest = getattr(self, "days_until_bank_interest", 30) - 1
        if self.days_until_bank_interest > 0:
            return 0.0

        self.days_until_bank_interest = 30
        if self.clean_money > 0:
            interest = round(self.clean_money * self.BANK_INTEREST_RATE, 2)
            # Faiz gerçek kazanılmış paradır: clean_money ile birlikte
            # cash da artmalı, yoksa "Banka faizi: X TL" anonsu gerçekte
            # hiçbir karşılığı olmayan hayali bir rakam olur.
            self.clean_money += interest
            self.cash += interest
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return interest
        return 0.0

    def process_jail_day(self) -> list:
        messages = []
        self.fluctuate_prices()
        if self.has_company:
            if not self.pay_company_upkeep():
                messages.append("Şirketiniz iflas etti, işletme giderleri karşılanamadı")
            else:
                profit_msg = self.process_company_daily()
                if profit_msg:
                    messages.append(profit_msg)
        if self.has_informant:
            if not self.pay_informant_upkeep():
                messages.append("Muhbiriniz ücretini alamadı ve sizi terk etti")
        if self.loan_amount > 0:
            success, msg = self.process_loan_daily()
            if not success:
                self.default_loan()
                messages.append(f"Kredi temerrüdüne düştünüz: {msg}")
            elif msg:
                messages.append(msg)
        messages.extend(self.process_land_loans_daily())
        messages.extend(self.process_employees_daily())
        return messages


def open_help():
    help_path = resource_path("help.html")
    if os.path.exists(help_path):
        webbrowser.open(help_path)
    else:
        create_help_file(help_path)
        webbrowser.open(help_path)


def open_release_notes():
    """
    "Yenilikler" menüsü için release_notes.html dosyasını tarayıcıda açar.
    NOT: help.html'in aksine burada dosya otomatik OLUŞTURULMUYOR; bu
    dosya elle (geliştirici tarafından) sağlanıyor. Dosya henüz yoksa
    kullanıcıya sesli/bilgi mesajı verilir, hata fırlatılmaz.
    """
    notes_path = resource_path("release_notes.html")
    if os.path.exists(notes_path):
        webbrowser.open(notes_path)
    else:
        speak("Yenilikler dosyası henüz eklenmemiş.")


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
    <p>Karaborsa'da ticaret yaparak para kazanın, şirket kurun, kredi çekin ve zengin olun!</p>
</body>
</html>"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(help_content)


# ============================================================
# ARSA YÖNETİM DİALOGU (Mevduat KALDIRILDI)
# ============================================================