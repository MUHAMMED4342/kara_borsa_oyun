


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
    load_names_from_file, load_cities_from_file, load_districts_from_file,
    tr_casefold,
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










def _load_people_pool() -> list:
    return load_names_from_file(resource_path("insanlar.txt"))


def _load_city_list() -> list:
    """Düz şehir (il) listesini döner (bölge kavramı YOK)."""
    return load_cities_from_file(resource_path("iller.txt"))


def _load_district_pool() -> dict:
    """ilceler.txt TEK KAYNAKTIR: il -> ilçe listesi sözlüğünü döner.
    ŞİRKET SİSTEMİ bu havuzu kullanarak, bir ilde zaten şirketiniz varsa
    o ilin ilçelerinde de ayrıca şirket açabilmenizi sağlar. Dosya
    yoksa/bozuksa/boşsa boş sözlük döner; bu durumda ilçe bazlı şirket
    açma imkanı sunulmaz ama oyun çökmez, sadece il bazlı eski davranış
    devam eder."""
    return load_districts_from_file(resource_path("ilceler.txt"))


ACTIVE_PEOPLE_POOL = _load_people_pool()
ACTIVE_CITIES = _load_city_list()
ACTIVE_DISTRICTS_BY_CITY = _load_district_pool()


def resolve_company_location(city: str):
    """Verilen 'city' değerinin geçerli bir şirket konumu olup olmadığını
    çözer. İki biçimi kabul eder:
      - Düz bir il adı (ACTIVE_CITIES içinde birebir eşleşen), örn. "Yozgat"
      - "İlçe (İl)" biçiminde bir ilçe etiketi, örn. "Boğazlıyan (Yozgat)"
        (get_available_company_cities() tarafından üretilen biçimdir)

    Dönen değer (is_valid, province, district) üçlüsüdür. Geçersiz bir
    değer verilirse (False, None, None) döner. Province-seviyesi bir
    konum içinse district None olur."""
    if not city:
        return False, None, None

    for c in ACTIVE_CITIES:
        if c == city:
            return True, c, None

    if city.endswith(")") and " (" in city:
        district_part, province_part = city.rsplit(" (", 1)
        province_name = province_part[:-1].strip()
        district_name = district_part.strip()
        matching_province = None
        for c in ACTIVE_CITIES:
            if tr_casefold(c) == tr_casefold(province_name):
                matching_province = c
                break
        if matching_province:
            districts = ACTIVE_DISTRICTS_BY_CITY.get(tr_casefold(matching_province), [])
            for d in districts:
                if tr_casefold(d) == tr_casefold(district_name):
                    return True, matching_province, d

    return False, None, None


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





ROULETTE_RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}

ROULETTE_BET_LABELS = {
    "kirmizi": "Kırmızı",
    "siyah": "Siyah",
    "cift": "Çift",
    "tek": "Tek",
    "1-18": "1-18",
    "19-36": "19-36",
    "1.duzine": "1. Düzine (1-12)",
    "2.duzine": "2. Düzine (13-24)",
    "3.duzine": "3. Düzine (25-36)",
    "sayi": "Tek Sayı",
}


def get_roulette_color(number: int) -> str:
    """0 yeşildir; kalan 36 sayı standart Avrupa ruleti düzenine göre
    kırmızı/siyah olarak dağıtılmıştır."""
    if number == 0:
        return "yeşil"
    return "kırmızı" if number in ROULETTE_RED_NUMBERS else "siyah"


class GameState:
    STARTING_CASH = 15000.0
    
    
    

    def __init__(self, load_data=None):
        self.lands = []
        self.land_prices = {}
        
        if load_data:
            self.cash = load_data.get("cash", self.STARTING_CASH)
            
            
            self.cash += load_data.get("clean_money", 0.0)
            self.day = load_data.get("day", 1)
            self.inventory = load_data.get("inventory", {name: 0 for name in PRODUCTS})
            self.prices = load_data.get("prices", {name: float(data["base_price"]) for name, data in PRODUCTS.items()})
            self.in_jail = load_data.get("in_jail", False)
            self.jail_days = load_data.get("jail_days", 0)

            
            
            
            
            
            self.companies = load_data.get("companies")
            if self.companies is None:
                self.companies = []
                if load_data.get("has_company", False):
                    legacy_city = load_data.get("company_city", "") or (ACTIVE_CITIES[0] if ACTIVE_CITIES else "")
                    self.companies.append({
                        "id": 1,
                        "type": load_data.get("company_type", ""),
                        "name": load_data.get("company_name", "Şirketim"),
                        "city": legacy_city,
                        "credit_score": load_data.get("company_credit_score", 50),
                        "days_active": load_data.get("company_days_active", 0),
                        "total_profit": load_data.get("company_total_profit", 0.0),
                        "monthly_revenue": load_data.get("company_monthly_revenue", 0.0),
                        "upkeep_paid": load_data.get("company_upkeep_paid", 0.0),
                    })

            
            
            
            
            
            
            for c in self.companies:
                if "province" not in c or "district" not in c:
                    valid, province, district = resolve_company_location(c.get("city", ""))
                    c["province"] = province if valid else c.get("city", "")
                    c["district"] = district if valid else None

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
            self.day = 1
            self.inventory = {name: 0 for name in PRODUCTS}
            self.prices = {name: float(data["base_price"]) for name, data in PRODUCTS.items()}
            self.in_jail = False
            self.jail_days = 0
            self.companies = []
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
            "period_generated": 0.0,
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

    @property
    def clean_money(self) -> float:
        """Geriye dönük uyumluluk için bırakıldı: 'temiz para' etiketi
        tamamen kaldırıldığından her zaman 0 döner, kazanılan her şey
        artık doğrudan self.cash içindedir."""
        return 0.0

    @clean_money.setter
    def clean_money(self, value):
        """Eski/harici kod (ör. save_manager.py) hâlâ 'state.clean_money = x'
        yazmaya çalışırsa uygulamanın çökmemesi için değeri sessizce yok
        sayar."""
        pass

    @property
    def has_company(self) -> bool:
        """En az bir aktif şirketiniz var mı."""
        return bool(self.companies)

    def get_company(self, company_id) -> dict:
        for c in self.companies:
            if c["id"] == company_id:
                return c
        return None

    def get_company_cities(self) -> set:
        """Aktif şirketlerinizin bulunduğu TÜM konumların (il ve ilçe
        etiketleri karışık) kümesi."""
        return {c["city"] for c in self.companies}

    def get_company_provinces_with_active_company(self) -> set:
        """İl SEVİYESİNDE (ilçe değil) aktif şirketiniz olan illerin
        casefold edilmiş adlarının kümesi. Bir ilçede şirket
        açabilmeniz için önce o ilin kendisinde bir şirketiniz olması
        gerekir - "Yozgat iline şirket açtıysak ilçesine de açabilelim"
        mantığı burada uygulanır."""
        return {
            tr_casefold(c.get("province", c["city"]))
            for c in self.companies
            if not c.get("district")
        }

    def get_available_company_cities(self) -> list:
        """Şirket açılabilecek konumların listesi:
          - Henüz il seviyesinde şirket açılmamış TÜM iller, ve
          - Zaten il seviyesinde bir şirketiniz bulunan illerin, henüz
            şirket açılmamış ilçeleri ("İlçe (İl)" biçiminde etiketlenir).
        Her il için en fazla bir il-seviyesi, her ilçe için en fazla bir
        ilçe-seviyesi şirket açılabilir."""
        occupied = self.get_company_cities()
        unlocked_provinces = self.get_company_provinces_with_active_company()

        locations = []
        for city in ACTIVE_CITIES:
            if city not in occupied:
                locations.append(city)
            if tr_casefold(city) in unlocked_provinces:
                for district in ACTIVE_DISTRICTS_BY_CITY.get(tr_casefold(city), []):
                    label = f"{district} ({city})"
                    if label not in occupied:
                        locations.append(label)
        return locations

    def _next_company_id(self) -> int:
        used = [c.get("id", 0) for c in self.companies]
        return (max(used) + 1) if used else 1

    
    
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
        if self.cash < debt:
            return False, f"Erken kapatma için yetersiz nakit. Gereken: {format_tl(debt)} TL"

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
        if self.companies:
            if len(self.companies) == 1:
                c = self.companies[0]
                base += f" | Şirket: {c['name']} ({c['city']})"
            else:
                cities = ", ".join(c["city"] for c in self.companies)
                base += f" | Şirketler ({len(self.companies)}): {cities}"
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
            illegal_value = self._illegal_inventory_value()
            display_risk = min(30, calculate_police_risk(illegal_value) * (1 + self.police_heat / 100) * 100)
            base += f" | Polis riski: %{display_risk:.0f}"
        return base

    def get_average_credit_score(self) -> int:
        """Tüm şirketlerinizin ortalama kredi notu (banka kredisi bu
        ortalamaya göre değerlendirilir). Şirketiniz yoksa 0 döner."""
        if not self.companies:
            return 0
        return round(sum(c["credit_score"] for c in self.companies) / len(self.companies))

    def get_credit_tier(self):
        """Kredi notu artık tüm şirketlerinizin ortalamasına göre hesaplanır
        (banka kredisi işletmenizin bütünü üzerinden değerlendirilir)."""
        if not self.companies:
            return None
        avg_score = sum(c["credit_score"] for c in self.companies) / len(self.companies)
        tier = CREDIT_TIERS[0]
        for t in CREDIT_TIERS:
            if avg_score >= t["min_score"]:
                tier = t
        return tier

    def get_loan_limit(self) -> float:
        tier = self.get_credit_tier()
        if not tier or not tier["can_loan"]:
            return 0.0
        total_monthly_income = 0.0
        for c in self.companies:
            days_active = c.get("days_active", 0)
            if days_active > 0:
                days_this_month = (days_active - 1) % 30 + 1
            else:
                days_this_month = 1
            total_monthly_income += (c.get("monthly_revenue", 0.0) / days_this_month) * 30
        base_limit = total_monthly_income * 2
        return base_limit * tier["loan_limit_multiplier"]

    def inventory_items_text(self) -> str:
        """Sadece envanterdeki ürünleri okur; nakit, gün, şirket, arsa,
        adam gibi diğer bilgileri İÇERMEZ. 'I' kısayolu bunu kullanır."""
        parts = ["Envanter özeti:"]
        has_item = False
        for category, names in PRODUCT_CATEGORIES.items():
            owned = [f"{name}: {self.inventory.get(name, 0)} adet" for name in names if self.inventory.get(name, 0) > 0]
            if owned:
                has_item = True
                parts.append(f"{category}: " + ", ".join(owned))
        if not has_item:
            parts.append("Envanterinizde ürün yok.")
        return " ".join(parts)

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

    

    def evaluate_roulette_bet(self, bet: dict, winning_number: int, winning_color: str) -> tuple:
        """Tek bir bahsin kazanıp kazanmadığını ve TOPLAM geri ödeme
        çarpanını (orijinal bahis dahil) döner. Örn. kırmızıya oynayıp
        kazanınca bahis 2 katına çıkar (2x); tek sayı tutunca 36x döner."""
        btype = bet["type"]
        if btype == "sayi":
            return (winning_number == bet.get("number"), 36)
        if btype == "kirmizi":
            return (winning_color == "kırmızı", 2)
        if btype == "siyah":
            return (winning_color == "siyah", 2)
        if btype == "cift":
            return (winning_number != 0 and winning_number % 2 == 0, 2)
        if btype == "tek":
            return (winning_number != 0 and winning_number % 2 == 1, 2)
        if btype == "1-18":
            return (1 <= winning_number <= 18, 2)
        if btype == "19-36":
            return (19 <= winning_number <= 36, 2)
        if btype == "1.duzine":
            return (1 <= winning_number <= 12, 3)
        if btype == "2.duzine":
            return (13 <= winning_number <= 24, 3)
        if btype == "3.duzine":
            return (25 <= winning_number <= 36, 3)
        return (False, 0)

    def play_roulette(self, bets: list) -> dict:
        """
        Verilen bahis listesini tek seferde işler:
        - Toplam bahis tutarını nakitten düşer (bakiye yetersizse hiçbir
          şey yapmadan hata döner)
        - Çarkı çevirir (0-36 arası rastgele sayı)
        - Her bahsi ayrı ayrı değerlendirir, kazançları nakde ekler
        - Net kumar kazancı pozitifse "suç geliri"ne (total_crime) eklenir;
          bu, oyunun karaborsa temasıyla tutarlıdır (bkz. game_data.py
          içindeki "Yasa Dışı Kumar Kazancı" rastgele olayı)

        bets: [{"type": "kirmizi"/"siyah"/"cift"/"tek"/"1-18"/"19-36"/
                        "1.duzine"/"2.duzine"/"3.duzine"/"sayi",
                "number": int|None (yalnızca "sayi" türü için 0-36),
                "amount": float}]

        Dönen sözlük:
            success (bool), message (str, yalnızca hata durumunda dolu),
            winning_number (int), winning_color (str),
            total_bet (float), total_payout (float), net (float),
            bet_results (list of dict: type, number, amount, won, payout)
        """
        total_bet = sum(b["amount"] for b in bets)
        if total_bet <= 0:
            return {"success": False, "message": "Bahis girilmedi"}
        if self.cash < total_bet:
            return {"success": False, "message": "Yetersiz bakiye"}

        self.cash -= total_bet

        winning_number = random.randint(0, 36)
        winning_color = get_roulette_color(winning_number)

        total_payout = 0.0
        bet_results = []
        for b in bets:
            won, multiplier = self.evaluate_roulette_bet(b, winning_number, winning_color)
            payout = b["amount"] * multiplier if won else 0.0
            total_payout += payout
            bet_results.append({
                "type": b["type"],
                "number": b.get("number"),
                "amount": b["amount"],
                "won": won,
                "payout": payout,
            })

        self.cash += total_payout
        net = total_payout - total_bet

        if net > 0:
            self.total_crime += net

        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        return {
            "success": True,
            "winning_number": winning_number,
            "winning_color": winning_color,
            "total_bet": total_bet,
            "total_payout": total_payout,
            "net": net,
            "bet_results": bet_results,
        }

    

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
            "period_generated": 0.0,
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

            
            experience_bonus = min(0.5, e["days_active"] / 200)
            gross = round(random.uniform(EMPLOYEE_DAILY_MIN, EMPLOYEE_DAILY_MAX) * (1 + experience_bonus), 2)

            self.cash += gross
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash

            e["total_generated"] += gross
            e["period_generated"] = e.get("period_generated", 0.0) + gross

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
                period_total = e["period_generated"]
                e["days_until_salary"] = 30
                e["period_generated"] = 0.0
                messages.append(
                    f"{e['name']} ({e['city']}): maaş ödendi ({format_tl(salary)} TL). "
                    f"Bu dönem ürettiği: {format_tl(period_total)} TL"
                )

        if to_remove:
            self.employees = [e for e in self.employees if e["id"] not in to_remove]

        return messages

    def go_to_jail(self, days: int) -> str:
        seized = round(self.cash * 0.10, 2)
        if seized > 0:
            self.cash -= seized
            if self.cash < 0:
                self.cash = 0.0
        self.in_jail = True
        self.jail_days = days
        if seized > 0:
            return f"{days} gün hapis cezası. Ayrıca paranızın yüzde 10'una ({format_tl(seized)} TL) el konuldu"
        return f"{days} gün hapis cezası"

    def setup_company(self, company_type: str, company_name: str, city: str = "") -> tuple:
        """Yeni bir şirket kurar ve listeye ekler. Aynı anda farklı
        konumlarda birden fazla şirketiniz olabilir; her il için en
        fazla bir il-seviyesi, her ilçe için en fazla bir ilçe-seviyesi
        şirket açılabilir. Bir ilçede şirket açabilmek için önce o ilin
        kendisinde (il seviyesinde) bir şirketiniz olması gerekir.
        Adamlar sisteminden TAMAMEN bağımsızdır.

        'city' parametresi ya düz bir il adı (ör. "Yozgat") ya da
        get_available_company_cities() tarafından üretilen "İlçe (İl)"
        biçiminde bir ilçe etiketi (ör. "Boğazlıyan (Yozgat)") olabilir."""
        if company_type not in COMPANY_TYPES:
            return False, "Geçersiz şirket tipi"

        valid, province, district = resolve_company_location(city)
        if not valid:
            return False, "Geçersiz şehir"

        if district and tr_casefold(province) not in self.get_company_provinces_with_active_company():
            return False, (
                f"{district} ilçesinde şirket açabilmek için önce "
                f"{province} ilinde bir şirketiniz olmalı"
            )

        if city in self.get_company_cities():
            location_word = "ilçesinde" if district else "ilinde"
            return False, f"{city} {location_word} zaten bir şirketiniz var"

        company_data = COMPANY_TYPES[company_type]
        cost = company_data["setup_cost"]

        if self.cash < cost:
            return False, f"Yetersiz nakit. Kurulum maliyeti: {format_tl(cost)} TL"

        self._spend_cash(cost)
        company = {
            "id": self._next_company_id(),
            "type": company_type,
            "name": company_name,
            "city": city,
            "province": province,
            "district": district,
            "credit_score": 50,
            "days_active": 0,
            "total_profit": 0.0,
            "monthly_revenue": 0.0,
            "upkeep_paid": 0.0,
        }
        self.companies.append(company)

        return True, f"{company_name} ({city}) kuruldu. Başlangıç kredi notu: 50"

    def close_company(self, company_id=None) -> tuple:
        """Belirtilen şirketi kapatır. company_id verilmezse ve tek bir
        şirketiniz varsa o kapatılır (geriye dönük uyumluluk için)."""
        if not self.companies:
            return False, "Aktif şirket yok"

        if company_id is None:
            if len(self.companies) == 1:
                company = self.companies[0]
            else:
                return False, "Kapatılacak şirketi seçin"
        else:
            company = self.get_company(company_id)
            if not company:
                return False, "Şirket bulunamadı"

        if len(self.companies) == 1 and self.loan_amount > 0:
            return False, "Önce kredi borcunu kapatın"

        self.companies.remove(company)

        return True, f"{company['name']} ({company['city']}) kapatıldı"

    def _spend_cash(self, amount: float) -> None:
        """self.cash'i doğrudan azaltan (arsa/şirket/adam alımı, rüşvet,
        ceza gibi) yerlerde kullanılır."""
        amount = round(amount, 2)
        if amount <= 0:
            return
        self.cash -= amount

    def advance_companies_day(self) -> list:
        """Her şirket için aktif gün sayısını artırır ve 30 günde bir
        (adamlardaki maaş duyurusuyla aynı mantıkla) o ayki toplam kârı
        seslendirilmek üzere bildirip aylık ciroyu sıfırlar. Her şirket
        kendi takvimine göre ilerler.

        Çok şirketi olan oyuncularda eskiden her şirket için ayrı bir
        cümle okunuyordu (onlarca şirketle bu, tek bir gün geçişinde
        dakikalarca sürebiliyordu). Artık bu ay dönümüne denk gelen
        TÜM şirketlerin kârı tek bir cümlede toplanıp okunuyor; tek
        şirket varsa ismiyle, birden fazlaysa "şirketleriniz" diyerek
        toplam üzerinden bildiriliyor."""
        due_companies = []
        for c in self.companies:
            c["days_active"] = c.get("days_active", 0) + 1
            if c["days_active"] % 30 == 0:
                due_companies.append(c)

        if not due_companies:
            return []

        total_profit = sum(c.get("monthly_revenue", 0.0) for c in due_companies)
        for c in due_companies:
            c["monthly_revenue"] = 0.0

        if len(due_companies) == 1:
            c = due_companies[0]
            message = f"{c['name']} ({c['city']}) bu ay {format_tl(total_profit)} TL kâr üretti"
        else:
            message = f"Şirketleriniz bu ay toplam {format_tl(total_profit)} TL kâr üretti"

        return [message]

    def process_company_daily(self) -> str:
        """Her gün: sahip olduğunuz HER şirket ayrı ayrı rastgele bir
        aralıkta doğrudan KÂR üretir. Kâr sadece cash'e eklenir; temiz
        para (clean_money) mantığı şirket için tamamen kaldırıldı."""
        if not self.companies:
            return ""

        messages = []
        for c in self.companies:
            company_data = COMPANY_TYPES[c["type"]]
            profit = round(random.uniform(
                company_data["daily_profit_min"], company_data["daily_profit_max"]
            ), 2)

            self.cash += profit
            c["monthly_revenue"] = c.get("monthly_revenue", 0.0) + profit
            credit_boost = max(1, int(profit / 500))
            c["credit_score"] = c.get("credit_score", 50) + credit_boost
            c["total_profit"] = c.get("total_profit", 0.0) + profit

            messages.append(f"{c['name']}: {format_tl(profit)} TL kâr elde ettiniz")

        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        return " ".join(messages)

    

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

    def pay_company_upkeep(self) -> list:
        """Her şirket için günlük işletme giderini ayrı ayrı öder.
        Ödeyemeyen şirket batar ve listeden çıkarılır; diğer şirketleriniz
        etkilenmez. Kapanan şirketler için mesaj listesi döner (boşsa
        hiçbir şirket kapanmamış demektir)."""
        closed_messages = []
        still_open = []
        for c in self.companies:
            company_data = COMPANY_TYPES[c["type"]]
            upkeep = company_data["daily_upkeep"]

            if self.cash >= upkeep:
                self._auto_deduct(upkeep)
                c["upkeep_paid"] = c.get("upkeep_paid", 0.0) + upkeep
                still_open.append(c)
            else:
                closed_messages.append(
                    f"{c['name']} ({c['city']}) kapandı. İşletme giderleri karşılanamadı."
                )

        self.companies = still_open
        return closed_messages

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
        if self.cash < debt:
            return False, f"Erken kapatma için yetersiz nakit. Gereken: {format_tl(debt)} TL"

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
        """Bir ödemeyi nakitten otomatik olarak çeker. Gerçekte ödenebilen
        miktarı döner."""
        remaining = round(amount, 2)
        if remaining <= 0:
            return 0.0

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
        if not self.companies:
            return False, "Aktif şirket yok"

        self.companies = []
        self._clear_loan()

        return True, "İşletmeniz iflas etti. Tüm şirketleriniz kapatıldı."

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
        göre birikimli polis riskini (heat) büyütür. Envanter düşükse ya
        da yoksa heat zamanla geriler. Bir yakalanma zarı atmaz, sadece
        heat'i günceller."""
        illegal_value = self._illegal_inventory_value()
        if illegal_value > 0:
            gain = min(12, 5 * ((illegal_value / 130000) ** 0.5))
            self.police_heat = min(100, self.police_heat + gain)
        else:
            self.police_heat = max(0, self.police_heat - 10)

    def roll_police_catch(self) -> bool:
        """Heat'i DEĞİŞTİRMEDEN, mevcut duruma göre bir yakalanma zarı
        atar. Hem gerçek zamanlı polis kontrolünde, hem de muhbirin
        "yarın baskın olacak mı" tahmininde kullanılır - böylece muhbir
        gerçekte olacak baskınla birebir aynı ihtimali kullanmış olur."""
        illegal_value = self._illegal_inventory_value()
        risk = calculate_police_risk(illegal_value) * (1 + self.police_heat / 100)
        return random.random() < min(0.30, risk)

    def police_check(self) -> dict:
        """Muhbiri olmayan oyuncular için: heat güncellenir ve aynı anda
        gerçek zamanlı bir yakalanma zarı atılır."""
        self.update_police_heat()
        caught = self.roll_police_catch()
        return {"caught": caught}

    def _total_wealth(self) -> float:
        """Nakit + envanter (güncel piyasa fiyatıyla) + şirket değeri +
        arsa değeri toplamı. Servete göre dinamik olay tutarlarını
        (cash_gain/cash_loss/raid_combo/inheritance/disaster) hesaplamak
        için kullanılır. game_data.calculate_total_wealth burada
        kullanılamaz çünkü o fonksiyon companies/lands için dict
        bekliyor, ancak GameState bunları liste olarak tutuyor."""
        total = self.cash

        for name, qty in self.inventory.items():
            total += qty * self.prices.get(name, 0.0)

        for c in self.companies:
            company_data = COMPANY_TYPES.get(c.get("type"), {})
            setup_cost = company_data.get("setup_cost", 0)
            total_profit = c.get("total_profit", 0.0)
            total += setup_cost + total_profit

        for land in self.lands:
            land_type = land.get("type")
            total += self.get_land_price(land_type) if land_type else land.get("purchase_price", 0)

        return max(total, 0.0)

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
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event["message_template"].format(amount=f"{format_tl(amount)}")
        elif etype == "cash_loss":
            
            
            
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
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
        elif etype == "inventory_gain":
            
            
            
            
            
            
            
            
            
            
            
            
            category = event["category"]
            pct = random.uniform(event["min_pct"], event["max_pct"])
            total_gained = 0
            for name in PRODUCT_CATEGORIES[category]:
                qty = self.inventory.get(name, 0)
                if qty > 0:
                    gained = max(1, int(round(qty * pct)))
                else:
                    price = self.prices.get(name) or PRODUCTS.get(name, {}).get("base_price", 500)
                    
                    
                    
                    baseline_value = random.uniform(300, 1500) * (pct / event["max_pct"])
                    gained = max(1, int(round(baseline_value / max(price, 1))))
                self.inventory[name] = qty + gained
                total_gained += gained
            if total_gained == 0:
                return event.get("zero_message", f"{event['name']}: kazanç yok")
            return event["message_template"].format(category=category, count=total_gained)
        elif etype == "raid_combo":
            
            
            wealth = self._total_wealth()
            cash_pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            cash_loss = round(wealth * cash_pct, 2)
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
            
            
            
            return "Maliye denetimi geçti"
        elif etype == "company_reputation":
            if self.companies:
                boost = event.get("credit_boost", 0)
                penalty = event.get("credit_penalty", 0)
                if boost:
                    for c in self.companies:
                        c["credit_score"] = c.get("credit_score", 50) + boost
                    return event["message_template"].format(credit_boost=boost)
                elif penalty:
                    for c in self.companies:
                        c["credit_score"] = max(0, c.get("credit_score", 50) + penalty)
                    return event["message_template"].format(credit_penalty=abs(penalty))
                return event["message_template"]
            return f"{event['name']}: Şirketiniz olmadığı için etkilenmediniz"
        elif etype == "land_price":
            
            
            
            
            
            
            pct = random.uniform(event["min_pct"], event["max_pct"])
            land_type_filter = event.get("land_type")
            if land_type_filter is None:
                target_types = list(LAND_TYPES.keys())
            elif isinstance(land_type_filter, (list, tuple, set)):
                target_types = list(land_type_filter)
            else:
                target_types = [land_type_filter]
            for land_type in target_types:
                data = LAND_TYPES[land_type]
                new_price = self.land_prices.get(land_type, data["base_price"]) * (1 + pct)
                new_price = max(data["min_price"], min(data["max_price"], new_price))
                self.land_prices[land_type] = round(new_price, 2)
            return event["message_template"].format(pct=f"{abs(pct) * 100:.1f}")
        elif etype == "inheritance":
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event["message_template"].format(amount=f"{format_tl(amount)}")
        elif etype == "disaster":
            
            
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self._spend_cash(amount)
            return event["message_template"].format(amount=f"{format_tl(amount)}")
        elif etype == "death":
            self.deaths_caused += 1
            return f"{event['name']}. Toplam ölüm: {self.deaths_caused}"
        return f"{event.get('name', 'Bilinmeyen olay')} gerçekleşti"

    def trigger_random_events(self, probability: float = 0.70, min_events: int = 1, max_events: int = 3):
        if random.random() >= probability:
            return []
        
        
        count = random.randint(min_events, min(max_events, len(EVENTS)))
        chosen = random.sample(EVENTS, count)
        results = [self.apply_event(event) for event in chosen]
        
        
        for rare in RARE_EVENTS:
            if random.random() < rare.get("chance", 0.001):
                results.append(self.apply_event(rare))
        
        return results

    def apply_bank_interest(self) -> float:
        """Banka/temiz para faizi sistemi tamamen kaldırıldı: nakit kendi
        kendine büyümez. Tek faiz kaynağı, alınan kredi borcudur (bkz.
        take_loan / take_land_loan). Bu metod geriye dönük uyumluluk için
        (main.py günlük döngüde çağırıyor olabilir) duruyor ama artık
        hiçbir para üretmez."""
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




