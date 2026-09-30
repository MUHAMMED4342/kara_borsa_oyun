


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
    EMPLOYEE_HIRE_FEE_GROWTH, EMPLOYEE_MAX_EXPERIENCE_BONUS, SELL_COMMISSION,
    INVENTORY_GAIN_PCT_SCALE, INVENTORY_GAIN_NEW_MAX_PRODUCTS,
    INVENTORY_GAIN_NEW_VALUE_MIN, INVENTORY_GAIN_NEW_VALUE_MAX,
    INVENTORY_BASE_CAPACITY, LAND_STORAGE_RATIO, WAREHOUSE_POLICE_VISIBILITY,
    load_names_from_file, load_cities_from_file, load_districts_from_file,
    tr_casefold, EVENT_TEXT_KEYS, category_display_name, product_display_name,
    land_type_display_name,
    AUCTION_ITEMS, AUCTION_NPC_DESCRIPTOR_KEYS, auction_item_display_name,
)
from accessibility_helper import speak as _tts_speak
from history_log import log_history
from formatting import format_tl
from i18n import t, get_language


def speak(text: str):
    """Ekran okuyucuya seslendirir VE aynı mesajı geçmiş kaydına ekler."""
    _tts_speak(text)
    log_history(text)


def resource_path(relative_path: str) -> str:
    """--include-data-files/--include-data-dir (Nuitka) ya da datas=
    (PyInstaller) ile pakete gömülen dosyaların çalışma anındaki
    gerçek yolunu döndürür.

    PyInstaller, gömülü dosyaları sys._MEIPASS adlı geçici bir
    klasöre açar. Nuitka bu özniteliği HİÇ ayarlamaz - onun yerine
    (hem standalone hem onefile modunda) gömülü dosyalar, çalışma
    anında __file__'in bulunduğu klasörün altında bulunur (Nuitka'nın
    kendi belgelerindeki "Onefile: Finding files" bölümü). Bu yüzden
    sys._MEIPASS yoksa (Nuitka'da veya normal script olarak
    çalışırken) os.path.dirname(__file__)'a düşüyoruz - bu, Nuitka
    ile paketlenmiş exe'de de doğru sonucu verir."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)










def _load_people_pool() -> list:
    # İsim havuzu ÜLKEDEN BAĞIMSIZDIR: insanlar.txt artık Türkçe isimlerin
    # yanı sıra İngiliz/Amerikan/Avustralya isimlerini de içerir, hangi
    # ülke seçilirse seçilsin aynı (karışık) havuzdan rastgele isim çekilir.
    return load_names_from_file(resource_path("insanlar.txt"))


# Desteklenen ülkeler: kod -> (görünen ad çeviri anahtarı, il dosyası,
# ilçe dosyası). Yeni bir ülke eklemek için buraya bir satır ve
# iller_<kod>.txt / ilceler_<kod>.txt dosyalarını (ilceler.txt ile AYNI
# "(il) İlçe1, İlçe2, ..." biçiminde) eklemek yeterlidir.
COUNTRIES = {
    "tr": {"name_key": "country.tr", "cities_file": "iller.txt", "districts_file": "ilceler.txt"},
    "us": {"name_key": "country.us", "cities_file": "iller_us.txt", "districts_file": "ilceler_us.txt"},
    "uk": {"name_key": "country.uk", "cities_file": "iller_uk.txt", "districts_file": "ilceler_uk.txt"},
    "au": {"name_key": "country.au", "cities_file": "iller_au.txt", "districts_file": "ilceler_au.txt"},
}
DEFAULT_COUNTRY = "tr"


def _load_city_list(country: str = DEFAULT_COUNTRY) -> list:
    """Düz şehir (il) listesini döner (bölge kavramı YOK)."""
    info = COUNTRIES.get(country, COUNTRIES[DEFAULT_COUNTRY])
    return load_cities_from_file(resource_path(info["cities_file"]))


def _load_district_pool(country: str = DEFAULT_COUNTRY) -> dict:
    """ilceler*.txt TEK KAYNAKTIR: il -> ilçe listesi sözlüğünü döner.
    ŞİRKET SİSTEMİ bu havuzu kullanarak, bir ilde zaten şirketiniz varsa
    o ilin ilçelerinde de ayrıca şirket açabilmenizi sağlar. Dosya
    yoksa/bozuksa/boşsa boş sözlük döner; bu durumda ilçe bazlı şirket
    açma imkanı sunulmaz ama oyun çökmez, sadece il bazlı eski davranış
    devam eder."""
    info = COUNTRIES.get(country, COUNTRIES[DEFAULT_COUNTRY])
    return load_districts_from_file(resource_path(info["districts_file"]))


def _load_country_data(country: str) -> tuple:
    """Bir ülkenin şehir listesini ve ilçe sözlüğünü yükler. Ülkeye ait
    dosyalar bulunamazsa/boşsa (ör. iller_us.txt paket derlemesine
    EKLENMEMİŞSE - bkz. resource_path ve Nuitka/PyInstaller "datas"
    listesi) SESSİZCE boş kalmak yerine Türkiye verisine geri döner;
    böylece oyun hiçbir zaman boş şehir/ilçe listesiyle kalmaz. Bu bir
    geliştirici uyarısı ile birlikte olur (konsola/log'a yazılır) ki
    paketleme dosyaları eksikse fark edilsin."""
    cities = _load_city_list(country)
    districts = _load_district_pool(country)

    if country != DEFAULT_COUNTRY and (not cities or not districts):
        info = COUNTRIES.get(country, {})
        print(
            f"[Uyarı] '{country}' ülkesi için şehir/ilçe verisi bulunamadı "
            f"(dosyalar: {info.get('cities_file')}, {info.get('districts_file')}). "
            f"Bu dosyaların derleme (Nuitka/PyInstaller) veri dosyaları listesine "
            f"eklendiğinden emin olun. Şimdilik Türkiye verisiyle devam ediliyor."
        )
        cities = _load_city_list(DEFAULT_COUNTRY)
        districts = _load_district_pool(DEFAULT_COUNTRY)

    return cities, districts


ACTIVE_PEOPLE_POOL = _load_people_pool()
ACTIVE_COUNTRY = DEFAULT_COUNTRY
ACTIVE_CITIES, ACTIVE_DISTRICTS_BY_CITY = _load_country_data(ACTIVE_COUNTRY)


def set_active_country(country: str) -> None:
    """Aktif şehir/ilçe havuzunu verilen ülkeye göre değiştirir. Bilinmeyen
    bir kod verilirse sessizce Türkiye'ye (DEFAULT_COUNTRY) döner. Bu,
    GameState oluşturulurken (yeni oyun ya da kayıt yükleme) çağrılır;
    ACTIVE_CITIES / ACTIVE_DISTRICTS_BY_CITY modül seviyesinde birer
    global olduğundan ve bu dosyadaki tüm fonksiyonlar onları çağrı
    anında (import anında değil) okuduğundan, bu atama HER YERDE anında
    etkili olur."""
    global ACTIVE_COUNTRY, ACTIVE_CITIES, ACTIVE_DISTRICTS_BY_CITY
    if country not in COUNTRIES:
        country = DEFAULT_COUNTRY
    ACTIVE_COUNTRY = country
    ACTIVE_CITIES, ACTIVE_DISTRICTS_BY_CITY = _load_country_data(country)


def get_active_country() -> str:
    return ACTIVE_COUNTRY


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

ROULETTE_BET_LABEL_KEYS = {
    "kirmizi": "roulette.label_red",
    "siyah": "roulette.label_black",
    "cift": "roulette.label_even",
    "tek": "roulette.label_odd",
    "1-18": "roulette.label_1_18",
    "19-36": "roulette.label_19_36",
    "1.duzine": "roulette.label_dozen1",
    "2.duzine": "roulette.label_dozen2",
    "3.duzine": "roulette.label_dozen3",
    "sayi": "roulette.label_number",
}

# Geriye dönük uyumluluk: eskiden ROULETTE_BET_LABELS doğrudan Türkçe
# metin içeren bir sözlüktü. Artık her t() çağrısı o anki dile göre
# değer döndüren dinamik bir nesne - dict[...] ve .get(...) eskisi
# gibi çalışır ama sabit bir dile kilitli değildir.
class _LazyTranslatedLabels:
    def __getitem__(self, key):
        return t(ROULETTE_BET_LABEL_KEYS[key])

    def get(self, key, default=None):
        label_key = ROULETTE_BET_LABEL_KEYS.get(key)
        return t(label_key) if label_key else default


ROULETTE_BET_LABELS = _LazyTranslatedLabels()


def get_roulette_color(number: int) -> str:
    """0 yeşildir; kalan 36 sayı standart Avrupa ruleti düzenine göre
    kırmızı/siyah olarak dağıtılmıştır. Dönen değer İÇSEL bir kod
    ('red'/'black'/'green') - bahis değerlendirme mantığı bununla
    çalışır. Oyuncuya GÖSTERİLECEK metin için get_roulette_color_label()
    kullanılır."""
    if number == 0:
        return "green"
    return "red" if number in ROULETTE_RED_NUMBERS else "black"


ROULETTE_COLOR_LABEL_KEYS = {
    "red": "roulette.color_red",
    "black": "roulette.color_black",
    "green": "roulette.color_green",
}


def get_roulette_color_label(color_code: str) -> str:
    """get_roulette_color()'ın döndürdüğü içsel kodu ('red'/'black'/
    'green') o anki dilde oyuncuya gösterilecek metne çevirir."""
    return t(ROULETTE_COLOR_LABEL_KEYS.get(color_code, color_code))


def event_display_name(event: dict) -> str:
    """Bir olay sözlüğünün ('name' alanı hâlâ Türkçe, kararlı bir
    kimlik) o anki dilde gösterilecek adını döndürür. EVENT_TEXT_KEYS'te
    karşılığı yoksa (örn. ileride eklenen çevrilmemiş bir olay), ham
    Türkçe isme güvenle geri döner - oyun hiçbir zaman çökmez."""
    key_prefix = EVENT_TEXT_KEYS.get(event.get("name"))
    if key_prefix:
        return t(f"{key_prefix}.name")
    return event.get("name", t("state.unknown_event_name"))


def event_message_text(event: dict, **kwargs) -> str:
    """Bir olayın message_template'ini o anki dilde, yer tutucuları
    doldurulmuş olarak döndürür. Çeviri yoksa ham Türkçe şablona
    (aynı .format(**kwargs) mantığıyla) geri döner."""
    key_prefix = EVENT_TEXT_KEYS.get(event.get("name"))
    if key_prefix:
        return t(f"{key_prefix}.message", **kwargs)
    template = event.get("message_template", "")
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        return template


def event_zero_message_text(event: dict) -> str:
    """Bir olayın (varsa) zero_message'ını o anki dilde döndürür.
    Ne çeviri ne de ham zero_message varsa None döner - çağıran taraf
    kendi varsayılan mesajını kullanmalı (bkz. apply_event)."""
    key_prefix = EVENT_TEXT_KEYS.get(event.get("name"))
    if key_prefix:
        translated = _get_locale_safe(f"{key_prefix}.zero")
        if translated is not None:
            return translated
    return event.get("zero_message")


def _get_locale_safe(key: str):
    """t()'in aksine, anahtar hiçbir dilde yoksa None döndürür (t()
    ise anahtarın kendisini döndürür) - event_zero_message_text'in
    'hiç zero_message tanımlanmamış' ile 'çevirisi eksik' durumlarını
    birbirinden ayırt edebilmesi için kullanılır."""
    import i18n as _i18n
    text = _i18n._get_locale(_i18n.get_language()).get(key)
    if text is None and _i18n.get_language() != "en":
        text = _i18n._get_locale("en").get(key)
    return text


class GameState:
    STARTING_CASH = 15000.0
    
    
    

    def __init__(self, load_data=None, country=None):
        # ÜLKE SEÇİMİ HER ŞEYDEN ÖNCE UYGULANIR: bu satırdan sonra
        # ACTIVE_CITIES / ACTIVE_DISTRICTS_BY_CITY (game_state.py modül
        # seviyesi globalleri) artık seçilen ülkeye ait olur - şehir/ilçe
        # kullanan hiçbir kod (şirket açma, kayıtlı oyunun eski şehrini
        # çözme, vb.) bu satırdan SONRA çalışır. Kayıtlı bir oyun
        # yükleniyorsa ülke, kayıttaki "country" alanından okunur (yoksa
        # geriye dönük uyumluluk için Türkiye varsayılır); yeni bir oyunda
        # ülke, CountrySelectDialog'dan (main.py) gelen `country`
        # parametresinden alınır.
        if load_data:
            resolved_country = load_data.get("country", DEFAULT_COUNTRY)
        else:
            resolved_country = country or DEFAULT_COUNTRY
        set_active_country(resolved_country)
        self.country = resolved_country

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

        # AÇIK ARTIRMA: sahip olunan eşyalar {item_id: adet} biçiminde
        # ayrı bir envanterde tutulur (normal ürün envanterinden bağımsız,
        # çünkü çok daha pahalı ve tekil/koleksiyon niteliğindedir).
        # auction_current, o an EKRANDA CANLI ilerleyen açık artırmadır
        # (gerçek zamanlı/duvar saati bazlı olduğu için kasıtlı olarak
        # KAYDEDİLMEZ - kaydedilseydi, oyun kapalıyken geçen süre yüzünden
        # anlamsız/negatif bir geri sayımla karşılaşılırdı; her oturumda
        # Açık Artırma ekranı açıldığında start_new_auction() ile sıfırdan
        # başlar). auction_duration_seconds ise kalıcı bir tercihtir -
        # oyuncu bunu açık artırma ekranından değiştirebilir.
        self.auction_inventory = load_data.get("auction_inventory", {}) if load_data else {}
        self.auction_duration_seconds = (
            load_data.get("auction_duration_seconds", self.AUCTION_DEFAULT_DURATION_SECONDS)
            if load_data else self.AUCTION_DEFAULT_DURATION_SECONDS
        )
        self.auction_current = None

        # ARSA DEPOSU: {ürün_adı: adet}. Envanterden ayrı, ortak bir depo;
        # kapasitesi sahip olunan arsaların alış fiyatına bağlıdır
        # (bkz. get_warehouse_capacity). Eski kayıtlarda alan yoktur.
        self.warehouse = self._load_warehouse(load_data)

    def _load_warehouse(self, load_data) -> dict:
        raw = (load_data or {}).get("warehouse") or {}
        warehouse = {}
        if isinstance(raw, dict):
            for name, qty in raw.items():
                try:
                    qty = int(qty)
                except (TypeError, ValueError):
                    continue
                if name in PRODUCTS and qty > 0:
                    warehouse[name] = qty
        return warehouse

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
            return False, t("state.invalid_land_type")
        
        price = self.get_land_price(land_type)
        
        if self.cash < price:
            return False, t("state.insufficient_cash_price", price=format_tl(price))
        
        self._spend_cash(price)
        self.lands.append({
            "type": land_type,
            "purchase_price": price,
            "purchase_day": self.day
        })
        
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        
        return True, t("state.land_bought", type=land_type_display_name(land_type), price=format_tl(price))

    def sell_land(self, land_index: int) -> tuple:
        if land_index < 0 or land_index >= len(self.lands):
            return False, t("state.invalid_land_index")
        
        land = self.lands[land_index]
        land_type = land["type"]

        # Bu arsa satılırsa depo kapasitesi düşer; depodaki mal yeni
        # kapasiteye sığmıyorsa satış engellenir (önce depodan alınmalı).
        remaining_capacity = self.get_warehouse_capacity(exclude_land_index=land_index)
        stored_value = self.get_warehouse_value()
        if stored_value > remaining_capacity + 0.01:
            return False, t("state.land_sell_blocked_storage",
                            excess=format_tl(stored_value - remaining_capacity))

        current_price = self.get_land_price(land_type)
        
        commission = current_price * 0.05
        sale_price = current_price - commission
        
        self.cash += sale_price
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        
        removed = self.lands.pop(land_index)
        
        return True, t("state.land_sold", type=land_type_display_name(land_type), price=format_tl(sale_price), commission=format_tl(commission))

    def get_land_loan_limit(self, land_index: int) -> float:
        if land_index < 0 or land_index >= len(self.lands):
            return 0.0
        
        land = self.lands[land_index]
        land_type = land["type"]
        current_price = self.get_land_price(land_type)
        multiplier = LAND_TYPES[land_type]["credit_multiplier"]
        
        return current_price * multiplier

    LAND_LOAN_PRESETS = [
        ("state.loan_preset_small", 0.25, 1),
        ("state.loan_preset_medium", 0.50, 2),
        ("state.loan_preset_large", 1.00, 3),
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
        for label_key, pct, installments in self.LAND_LOAN_PRESETS:
            amount = round(limit * pct, 2)
            if amount <= 0:
                continue
            total_debt = round(amount * (1 + interest_rate), 2)
            installment_amount = round(total_debt / installments, 2)
            options.append({
                "label": t(label_key),
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
            return False, t("state.invalid_land_index")
        
        if amount <= 0:
            return False, t("state.invalid_amount")

        if self.lands[land_index].get("has_loan", False):
            return False, t("state.land_already_has_loan")
        
        limit = self.get_land_loan_limit(land_index)
        if amount > limit:
            return False, t("state.max_loan", limit=format_tl(limit))
        
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
        
        return True, t("state.land_loan_approved", amount=format_tl(amount), debt=format_tl(total_debt),
                       installments=installments, installment=format_tl(installment_amount))

    def pay_land_loan_full(self, land_index: int) -> tuple:
        """Arsa kredisini erken kapatma - kalan tüm borç tek seferde ödenir."""
        if land_index < 0 or land_index >= len(self.lands):
            return False, t("state.invalid_land_index")

        land = self.lands[land_index]
        if not land.get("has_loan", False):
            return False, t("state.no_active_land_loan")

        debt = land.get("loan_debt", 0.0)
        if self.cash < debt:
            return False, t("state.insufficient_cash_payoff", amount=format_tl(debt))

        self.cash -= debt
        land["has_loan"] = False
        land.pop("loan_amount", None)
        land.pop("loan_debt", None)
        land.pop("loan_interest_rate", None)
        land.pop("loan_total_installments", None)
        land.pop("loan_installments_paid", None)
        land.pop("loan_installment_amount", None)
        land.pop("loan_days_until_installment", None)

        return True, t("state.land_loan_paid_off", amount=format_tl(debt))

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
                messages.append(t("state.land_loan_installment_failed", type=land_type_display_name(land['type']),
                                   due=format_tl(due), paid=format_tl(paid)))
                to_remove.append(i)
                continue

            land["loan_installments_paid"] = land.get("loan_installments_paid", 0) + 1

            if debt <= 0.01:
                messages.append(t("state.land_loan_paid_full", type=land_type_display_name(land['type']), amount=format_tl(paid)))
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
                messages.append(t("state.land_loan_installment_paid", type=land_type_display_name(land['type']),
                                   amount=format_tl(paid), debt=format_tl(debt)))

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
        base = t("state.wallet_day_cash", day=self.day, cash=format_tl(self.cash))
        if self.companies:
            if len(self.companies) == 1:
                c = self.companies[0]
                base += t("state.wallet_company_single", name=c['name'], city=c['city'])
            else:
                cities = ", ".join(c["city"] for c in self.companies)
                base += t("state.wallet_companies_multi", count=len(self.companies), cities=cities)
            if self.loan_amount > 0:
                base += t("state.wallet_loan", amount=format_tl(self.loan_amount))
        if self.lands:
            base += t("state.wallet_land", count=len(self.lands))
        if self.employees:
            base += t("state.wallet_employees", count=len(self.employees))
        if self.has_informant:
            base += t("state.wallet_informant")
        if self.in_jail:
            base += t("state.wallet_jail", days=self.jail_days)
        if self.police_heat > 0:
            illegal_value = self._illegal_inventory_value()
            display_risk = min(30, calculate_police_risk(illegal_value) * (1 + self.police_heat / 100) * 100)
            base += t("state.wallet_police_risk", risk=f"{display_risk:.0f}")
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
        parts = [t("state.inventory_header")]
        has_item = False
        for category, names in PRODUCT_CATEGORIES.items():
            owned = [t("state.inventory_item_line", name=product_display_name(name), qty=self.inventory.get(name, 0)) for name in names if self.inventory.get(name, 0) > 0]
            if owned:
                has_item = True
                parts.append(f"{category_display_name(category)}: " + ", ".join(owned))
        if not has_item:
            parts.append(t("state.inventory_empty"))
        return " ".join(parts)

    def inventory_summary_text(self) -> str:
        parts = [self.wallet_text(), t("state.inventory_header")]
        has_item = False
        for category, names in PRODUCT_CATEGORIES.items():
            owned = [t("state.inventory_item_line", name=product_display_name(name), qty=self.inventory.get(name, 0)) for name in names if self.inventory.get(name, 0) > 0]
            if owned:
                has_item = True
                parts.append(f"{category_display_name(category)}: " + ", ".join(owned))
        if not has_item:
            parts.append(t("state.inventory_empty"))
        parts.append(t("state.inventory_capacity_line",
                       used=format_tl(self.get_inventory_value()),
                       cap=format_tl(self.get_inventory_capacity())))
        
        if self.lands:
            parts.append(t("state.your_lands_header"))
            for i, land in enumerate(self.lands):
                land_type = land["type"]
                price = self.get_land_price(land_type)
                parts.append(t("state.your_land_line", index=i+1, type=land_type_display_name(land_type), price=format_tl(price)))

        if self.employees:
            parts.append(t("state.your_employees_header"))
            for e in self.employees:
                parts.append(t("state.employee_salary_line", name=e['name'], city=e['city'], days=e['days_until_salary']))

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

    # ------------------------------------------------------------------
    # ENVANTER KAPASİTESİ ve ARSA DEPOSU
    # ------------------------------------------------------------------
    def get_inventory_value(self) -> float:
        """Ana envanterdeki malların güncel piyasa değeri."""
        return sum(qty * self.prices.get(name, 0.0) for name, qty in self.inventory.items() if qty > 0)

    def get_inventory_capacity(self) -> float:
        return float(INVENTORY_BASE_CAPACITY)

    def get_inventory_free_capacity(self) -> float:
        return self.get_inventory_capacity() - self.get_inventory_value()

    def get_warehouse_capacity(self, exclude_land_index: int = None) -> float:
        """Sahip olunan arsaların ALIŞ fiyatlarının toplamı x
        LAND_STORAGE_RATIO. (Alış fiyatı kullanılır: arsa piyasası
        dalgalansa da depo kapasitesi sabit ve öngörülebilir kalır.)"""
        total = 0.0
        for i, land in enumerate(self.lands):
            if exclude_land_index is not None and i == exclude_land_index:
                continue
            total += float(land.get("purchase_price", 0.0))
        return total * LAND_STORAGE_RATIO

    def get_warehouse_value(self) -> float:
        return sum(qty * self.prices.get(name, 0.0) for name, qty in self.warehouse.items() if qty > 0)

    def get_warehouse_free_capacity(self) -> float:
        return self.get_warehouse_capacity() - self.get_warehouse_value()

    def max_deposit_quantity(self, name: str) -> int:
        """Bu üründen depoya en fazla kaç adet konabilir (envanterdeki
        adet ve depoda kalan boş kapasiteyle sınırlı)."""
        price = self.prices.get(name, 0.0)
        if price <= 0:
            return 0
        free = self.get_warehouse_free_capacity()
        if free <= 0:
            return 0
        return max(0, min(self.inventory.get(name, 0), int(free // price)))

    def deposit_to_warehouse(self, name: str, quantity: int) -> tuple:
        if quantity <= 0:
            return False, t("common.enter_valid_quantity")
        if not self.lands:
            return False, t("state.warehouse_no_land")
        if self.inventory.get(name, 0) < quantity:
            return False, t("state.no_stock")
        if quantity > self.max_deposit_quantity(name):
            return False, t("state.warehouse_full",
                            free=format_tl(max(0.0, self.get_warehouse_free_capacity())),
                            max_qty=self.max_deposit_quantity(name))
        self.inventory[name] -= quantity
        self.warehouse[name] = self.warehouse.get(name, 0) + quantity
        return True, t("state.warehouse_deposited", qty=quantity, name=product_display_name(name))

    def withdraw_from_warehouse(self, name: str, quantity: int) -> tuple:
        """Depodan envantere geri alır. Ana envanter kapasitesine
        BAKMAZ (kapasite sadece yeni alımı sınırlar) - böylece oyuncu
        kendi malını asla depoda mahsur bırakılmaz."""
        if quantity <= 0:
            return False, t("common.enter_valid_quantity")
        if self.warehouse.get(name, 0) < quantity:
            return False, t("state.warehouse_not_enough")
        self.warehouse[name] -= quantity
        if self.warehouse[name] <= 0:
            del self.warehouse[name]
        self.inventory[name] = self.inventory.get(name, 0) + quantity
        return True, t("state.warehouse_withdrawn", qty=quantity, name=product_display_name(name))

    def buy_bulk(self, name: str, quantity: int) -> tuple:
        total_price = self.prices[name] * quantity
        if self.cash < total_price:
            return False, 0, t("state.insufficient_balance")
        free = self.get_inventory_free_capacity()
        if total_price > free:
            max_qty = max(0, int(free // self.prices[name])) if self.prices[name] > 0 else 0
            return False, 0, t("state.inventory_full", free=format_tl(max(0.0, free)), max_qty=max_qty)
        self.cash -= total_price
        self.inventory[name] += quantity

        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        return True, total_price, t("state.bought_line", qty=quantity, name=product_display_name(name))

    def sell_bulk(self, name: str, quantity: int) -> tuple:
        if self.inventory.get(name, 0) < quantity:
            return False, 0, t("state.no_stock")
        # Satışta piyasa fiyatından SELL_COMMISSION kadar komisyon kesilir
        # (alışta kesinti yok). Listede görünen fiyat alış fiyatıdır.
        total_price = round(self.prices[name] * quantity * (1 - SELL_COMMISSION), 2)
        self.inventory[name] -= quantity
        self.cash += total_price
        self.total_crime += total_price
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash
        speak(t("state.sold_speak", qty=quantity, name=product_display_name(name), amount=format_tl(total_price)))
        return True, total_price, t("state.sold_line", qty=quantity, name=product_display_name(name))

    

    def evaluate_roulette_bet(self, bet: dict, winning_number: int, winning_color: str) -> tuple:
        """Tek bir bahsin kazanıp kazanmadığını ve TOPLAM geri ödeme
        çarpanını (orijinal bahis dahil) döner. Örn. kırmızıya oynayıp
        kazanınca bahis 2 katına çıkar (2x); tek sayı tutunca 36x döner."""
        btype = bet["type"]
        if btype == "sayi":
            return (winning_number == bet.get("number"), 36)
        if btype == "kirmizi":
            return (winning_color == "red", 2)
        if btype == "siyah":
            return (winning_color == "black", 2)
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
            return {"success": False, "message": t("state.no_bet_entered")}
        if self.cash < total_bet:
            return {"success": False, "message": t("state.insufficient_balance")}

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
        # Her mevcut çalışan bir sonraki adamın ücretini artırır
        # (bkz. game_data.EMPLOYEE_HIRE_FEE_GROWTH).
        return float(round(EMPLOYEE_HIRE_FEE * (1 + EMPLOYEE_HIRE_FEE_GROWTH * len(self.employees))))

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
            return False, t("state.person_already_hired")

        if city not in ACTIVE_CITIES:
            return False, t("state.invalid_city")

        if city in self.get_occupied_cities():
            return False, t("state.city_already_has_employee", city=city)

        cost = self.get_employee_hire_cost()
        if self.cash < cost:
            return False, t("state.insufficient_cash_needed", amount=format_tl(cost))

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

        return True, t("state.employee_hired", name=name, city=city, cost=format_tl(cost), salary=format_tl(salary))

    def fire_employee(self, employee_id: int) -> tuple:
        for i, e in enumerate(self.employees):
            if e["id"] == employee_id:
                name, city = e["name"], e["city"]
                self.employees.pop(i)
                return True, t("state.employee_fired", name=name, city=city)
        return False, t("state.employee_not_found")

    def employee_summary_text(self) -> str:
        if not self.employees:
            return t("state.no_employees")
        parts = [t("state.employee_count_header", count=len(self.employees)), t("state.employees_header")]
        for e in self.employees:
            parts.append(t("state.employee_summary_line", name=e['name'], city=e['city'],
                            days=e['days_active'], generated=format_tl(e['total_generated']),
                            salary=format_tl(e['salary']), until=e['days_until_salary']))
        return " ".join(parts)

    def process_employees_daily(self) -> list:
        """Her gün: her adam kendi şehrinde karaborsa işi çevirip nakit
        üretir. 30 günde bir oyuncudan maaşını alır. Maaş ödenemezse adam
        sizi terk eder."""
        messages = []
        to_remove = []

        for e in self.employees:
            e["days_active"] += 1

            
            experience_bonus = min(EMPLOYEE_MAX_EXPERIENCE_BONUS, e["days_active"] / 200)
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
                    messages.append(t("state.employee_salary_failed", name=e['name'], city=e['city']))
                    to_remove.append(e["id"])
                    continue
                period_total = e["period_generated"]
                e["days_until_salary"] = 30
                e["period_generated"] = 0.0
                messages.append(t("state.employee_salary_paid", name=e['name'], city=e['city'],
                                   salary=format_tl(salary), generated=format_tl(period_total)))

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
            return t("state.jail_with_seizure", days=days, amount=format_tl(seized))
        return t("state.jail_sentence", days=days)

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
            return False, t("state.invalid_company_type")

        valid, province, district = resolve_company_location(city)
        if not valid:
            return False, t("state.invalid_city_short")

        if district and tr_casefold(province) not in self.get_company_provinces_with_active_company():
            return False, t("state.need_company_in_province", district=district, province=province)

        if city in self.get_company_cities():
            if district:
                return False, t("state.already_have_company_district", city=city)
            return False, t("state.already_have_company_province", city=city)

        company_data = COMPANY_TYPES[company_type]
        cost = company_data["setup_cost"]

        if self.cash < cost:
            return False, t("state.insufficient_cash_setup", cost=format_tl(cost))

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

        return True, t("state.company_founded", name=company_name, city=city)

    def close_company(self, company_id=None) -> tuple:
        """Belirtilen şirketi kapatır. company_id verilmezse ve tek bir
        şirketiniz varsa o kapatılır (geriye dönük uyumluluk için)."""
        if not self.companies:
            return False, t("state.no_active_company")

        if company_id is None:
            if len(self.companies) == 1:
                company = self.companies[0]
            else:
                return False, t("state.select_company_to_close")
        else:
            company = self.get_company(company_id)
            if not company:
                return False, t("state.company_not_found")

        if len(self.companies) == 1 and self.loan_amount > 0:
            return False, t("state.pay_off_loan_first")

        self.companies.remove(company)

        return True, t("state.company_closed", name=company['name'], city=company['city'])

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
            message = t("state.company_monthly_profit_single", name=c['name'], city=c['city'], amount=format_tl(total_profit))
        else:
            message = t("state.company_monthly_profit_multi", amount=format_tl(total_profit))

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

            messages.append(t("state.company_daily_profit", name=c['name'], amount=format_tl(profit)))

        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        return " ".join(messages)

    

    def hire_informant(self) -> tuple:
        if self.has_informant:
            return False, t("state.already_have_informant")

        cost = INFORMANT_CONFIG["hire_cost"]
        if self.cash < cost:
            return False, t("state.insufficient_cash_needed", amount=format_tl(cost))

        self._spend_cash(cost)
        self.has_informant = True
        return True, t("state.informant_hired", cost=format_tl(cost),
                        upkeep=format_tl(INFORMANT_CONFIG['daily_upkeep']))

    def fire_informant(self) -> tuple:
        if not self.has_informant:
            return False, t("state.no_informant")
        self.has_informant = False
        self.informant_warning_active = False
        return True, t("state.informant_fired")

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
            earned = round(price * qty * (1 - SELL_COMMISSION), 2)
            total_earned += earned
            total_items += qty
            self.inventory[name] = 0

        self.cash += total_earned
        self.total_crime += total_earned
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        return total_items, round(total_earned, 2)

    

    AUCTION_BIDDER_MIN_COUNT = 2
    AUCTION_BIDDER_MAX_COUNT = 4
    AUCTION_DEFAULT_DURATION_SECONDS = 60
    AUCTION_MIN_DURATION_SECONDS = 5
    AUCTION_MAX_DURATION_SECONDS = 120
    # Ekran okuyucunun bir anonsu RAHATÇA bitirebilmesi için, iki olay
    # (teklif ya da hatırlatma anonsu) arasında en az/en fazla bu kadar
    # saniye boşluk bırakılır - bkz. tick_auction. Bu bilinçli olarak
    # kısa süreli (5-15 sn) bir turda bile en fazla birkaç anons demektir;
    # amaç heyecan değil, HER ANONSUN net bir şekilde duyulabilmesidir.
    AUCTION_MIN_EVENT_GAP_SECONDS = 7.0
    AUCTION_MAX_EVENT_GAP_SECONDS = 7.0
    AUCTION_NPC_TICK_BID_CHANCE = 0.55  # her olay penceresinde bunun bir TEKLİF mi yoksa hatırlatma anonsu mu olacağı
    AUCTION_NPC_MIN_RAISE = 0.04
    AUCTION_NPC_MAX_RAISE = 0.18
    AUCTION_RESALE_MIN_MULT = 0.75
    AUCTION_RESALE_MAX_MULT = 1.35

    def get_auction_duration_seconds(self) -> int:
        return self.auction_duration_seconds

    def set_auction_duration_seconds(self, seconds) -> int:
        """Açık artırma süresini (saniye) değiştirir; AUCTION_MIN/MAX
        aralığına sıkıştırılır. Zaten devam eden bir açık artırmayı
        ETKİLEMEZ - yeni süre yalnızca bundan SONRA start_new_auction()
        ile başlayacak açık artırmalarda geçerli olur. Uygulanan (sınıra
        çekilmiş) değeri döner."""
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = self.AUCTION_DEFAULT_DURATION_SECONDS
        seconds = max(self.AUCTION_MIN_DURATION_SECONDS, min(self.AUCTION_MAX_DURATION_SECONDS, seconds))
        self.auction_duration_seconds = seconds
        return seconds

    def _generate_auction_bidders(self, item: dict) -> list:
        """Bir eşya için 2-4 gerçek rakip üretir. Her rakibin kendi ismi
        (insanlar.txt'ten), betimleyici bir sıfatı ("şapkalı yaşlı adam"
        gibi) ve AZAMİ BİR BÜTÇESİ vardır - bütçesi tükenen rakip
        otomatik olarak açık artırmadan çekilir. Bütçe, eşyanın min/max
        değer aralığına göre rastgele belirlenir; bu yüzden bazı
        rakipler erken pes eder, bazıları çok daha inatçı çıkar -
        gerçek bir açık artırmadaki gibi."""
        count = random.randint(self.AUCTION_BIDDER_MIN_COUNT, self.AUCTION_BIDDER_MAX_COUNT)
        used_names = set()
        bidders = []
        for _ in range(count):
            name = random.choice(ACTIVE_PEOPLE_POOL) if ACTIVE_PEOPLE_POOL else None
            tries = 0
            while name in used_names and ACTIVE_PEOPLE_POOL and tries < 6:
                name = random.choice(ACTIVE_PEOPLE_POOL)
                tries += 1
            if name:
                used_names.add(name)
            else:
                name = t("auction.default_npc_name")

            descriptor_key = random.choice(AUCTION_NPC_DESCRIPTOR_KEYS)
            label = t(descriptor_key, name=name)
            max_budget = round(random.uniform(item["min_value"] * 1.15, item["max_value"] * 1.5), 2)

            bidders.append({
                "label": label,
                "max_budget": max_budget,
                "active": True,
            })
        return bidders

    def start_new_auction(self) -> dict:
        """Yeni, CANLI bir açık artırma başlatır: AUCTION_ITEMS içinden
        rastgele TEK bir eşya seçer ("X ürünü X fiyatından satılıyor,
        teklifler nedir?" tarzı bir açılış anonsuyla), 2-4 gerçek rakip
        üretir ve gerçek zamanlı (duvar saati bazlı) geri sayımı
        başlatır. Dönen sözlük {"message":, "item_id":, "amount":}
        biçimindedir - ekranda gösterilecek/duyurulacak açılış anonsu."""
        item = random.choice(AUCTION_ITEMS)
        opening = round(random.uniform(item["min_value"], item["min_value"] * 1.15), 2)

        self.auction_current = {
            "item_id": item["id"],
            "starting_price": opening,
            "current_price": opening,
            "last_bidder": None,  # None = henüz kimse teklif vermedi
            "bidders": self._generate_auction_bidders(item),
            "bid_history": [],
            "start_time": time.time(),
            "duration_seconds": self.auction_duration_seconds,
            "resolved": False,
            # SADECE BİR anons/olay penceresi vardır (bkz. tick_auction) -
            # bir sonraki olayın (teklif YA DA hatırlatma, ikisi asla
            # AYNI ANDA değil) ne zaman değerlendirileceğini tutar.
            # Ekran okuyucunun bir önceki anonsu bitirebilmesi için
            # açılış anonsundan sonra da bir miktar boşluk bırakılır.
            "next_event_time": time.time() + random.uniform(
                self.AUCTION_MIN_EVENT_GAP_SECONDS, self.AUCTION_MAX_EVENT_GAP_SECONDS
            ),
        }

        message = t(
            "auction.opening_announcement",
            item=auction_item_display_name(item["id"]),
            amount=format_tl(opening),
        )
        self.auction_current["bid_history"].append({
            "who": "system", "label": t("auction.auctioneer_label"), "amount": opening,
        })

        return {"message": message, "item_id": item["id"], "amount": opening}

    def get_auction_time_remaining(self) -> float:
        """Şu anki canlı açık artırmada kalan saniyeyi döner (0'ın
        altına inmez). Aktif bir açık artırma yoksa 0.0 döner."""
        if not self.auction_current:
            return 0.0
        elapsed = time.time() - self.auction_current["start_time"]
        remaining = self.auction_current["duration_seconds"] - elapsed
        return max(0.0, remaining)

    def tick_auction(self) -> dict:
        """Canlı açık artırma sırasında PERİYODİK olarak (ekranın
        zamanlayıcısından, örn. saniyede bir) çağrılır.

        ÖNEMLİ - EKRAN OKUYUCU HIZI: bir önceki sürümde NPC teklifleri
        HER TICK'TE (saniyede bir) ayrı ayrı, hatırlatma anonsundan
        TAMAMEN BAĞIMSIZ bir zamanlamayla değerlendiriliyordu; bu da
        art arda (hatta AYNI ANDA) birden fazla speak() çağrısına, yani
        ekran okuyucunun anonsları üst üste bindirmesine yol açıyordu.
        Artık TEK BİR olay penceresi var: en az AUCTION_MIN_EVENT_GAP_
        SECONDS, en fazla AUCTION_MAX_EVENT_GAP_SECONDS sonra bir
        SONRAKİ olay değerlendirilir - ve bu olay YA bir teklif YA DA
        bir hatırlatma anonsudur, ASLA ikisi birden. Bu, her anonsun
        bir öncekini bitirmesi için yeterli boşluk bırakır.

        Dönen sözlük: {"bid_event": {...}|None, "announcement": str|None,
        "time_remaining": float, "resolved": bool}. Aktif bir açık
        artırma yoksa ya da zaten sonuçlandıysa resolved=True ile no-op
        döner."""
        if not self.auction_current or self.auction_current["resolved"]:
            return {"bid_event": None, "announcement": None, "time_remaining": 0.0, "resolved": True}

        entry = self.auction_current
        remaining = self.get_auction_time_remaining()

        bid_event = None
        announcement = None

        if remaining > 1.5 and time.time() >= entry["next_event_time"]:
            active_bidders = [
                b for b in entry["bidders"]
                if b["active"] and b["max_budget"] > entry["current_price"]
            ]

            if active_bidders and random.random() < self.AUCTION_NPC_TICK_BID_CHANCE:
                bidder = random.choice(active_bidders)
                raise_pct = random.uniform(self.AUCTION_NPC_MIN_RAISE, self.AUCTION_NPC_MAX_RAISE)
                proposed = min(round(entry["current_price"] * (1 + raise_pct), 2), bidder["max_budget"])
                if proposed > entry["current_price"]:
                    entry["current_price"] = proposed
                    entry["last_bidder"] = bidder["label"]
                    event = {"who": "npc", "label": bidder["label"], "amount": proposed}
                    entry["bid_history"].append(event)
                    bid_event = event
                    for b in entry["bidders"]:
                        if b["active"] and b["max_budget"] <= proposed:
                            b["active"] = False

            if bid_event is None:
                announcement = t(
                    "auction.status_announcement",
                    item=auction_item_display_name(entry["item_id"]),
                    amount=format_tl(entry["current_price"]),
                    seconds=int(remaining) + 1,
                )

            entry["next_event_time"] = time.time() + random.uniform(
                self.AUCTION_MIN_EVENT_GAP_SECONDS, self.AUCTION_MAX_EVENT_GAP_SECONDS
            )

        return {
            "bid_event": bid_event,
            "announcement": announcement,
            "time_remaining": remaining,
            "resolved": False,
        }

    def place_live_auction_bid(self, bid_amount: float) -> dict:
        """Oyuncu, o an EKRANDA CANLI ilerleyen açık artırmaya teklif
        verir. Rakiplerin buna tepkisi SENKRON değildir - bir sonraki
        tick_auction() çağrısında (ekranın zamanlayıcısı üzerinden)
        kendiliğinden gerçekleşir, tıpkı gerçek bir açık artırmadaki
        gibi. Dönen sözlük: {"success":, "message":}."""
        if not self.auction_current or self.auction_current["resolved"]:
            return {"success": False, "message": t("auction.no_active_auction")}

        if self.get_auction_time_remaining() <= 0:
            return {"success": False, "message": t("auction.time_up_cannot_bid")}

        entry = self.auction_current
        if bid_amount <= entry["current_price"]:
            return {"success": False, "message": t("auction.bid_too_low", amount=format_tl(entry["current_price"]))}

        if bid_amount > self.cash:
            return {"success": False, "message": t("auction.insufficient_cash")}

        entry["current_price"] = bid_amount
        entry["last_bidder"] = "player"
        entry["bid_history"].append({
            "who": "player", "label": t("auction.you_label"), "amount": bid_amount,
        })

        for b in entry["bidders"]:
            if b["active"] and b["max_budget"] <= bid_amount:
                b["active"] = False

        # Oyuncunun kendi teklif onayı da bir anonstur (dialog bunu ayrıca
        # speak() eder) - hemen ardından bir NPC/hatırlatma anonsunun
        # üstüne binmemesi için bir sonraki otomatik olayı öteliyoruz.
        entry["next_event_time"] = max(
            entry["next_event_time"],
            time.time() + random.uniform(self.AUCTION_MIN_EVENT_GAP_SECONDS, self.AUCTION_MAX_EVENT_GAP_SECONDS),
        )

        return {
            "success": True,
            "message": t(
                "auction.player_bid_message",
                item=auction_item_display_name(entry["item_id"]),
                amount=format_tl(bid_amount),
            ),
        }

    def resolve_current_auction(self) -> dict:
        """Süre dolduğunda (get_auction_time_remaining() <= 0) çağrılır:
        son teklifi verene satar. Oyuncuysa nakit düşülür ve eşya
        auction_inventory'ye eklenir; bir NPC'yse sadece bilgilendirici
        bir mesaj döner (oyuncunun parasına/envanterine dokunulmaz); hiç
        teklif verilmediyse eşya satılmamış sayılır. auction_current
        "resolved" olarak işaretlenir - bir sonraki start_new_auction()
        çağrısı yeni bir eşya seçer.

        Dönen sözlük: {"message":, "won_by_player":, "item_id":, "amount":}."""
        if not self.auction_current:
            return {"message": "", "won_by_player": False, "item_id": None, "amount": 0}

        entry = self.auction_current
        entry["resolved"] = True
        item_id = entry["item_id"]
        final_price = entry["current_price"]

        if entry["last_bidder"] == "player":
            self._spend_cash(final_price)
            self.auction_inventory[item_id] = self.auction_inventory.get(item_id, 0) + 1
            message = t(
                "auction.player_won_message",
                item=auction_item_display_name(item_id), amount=format_tl(final_price),
            )
            won_by_player = True
        elif entry["last_bidder"]:
            message = t(
                "auction.npc_won_message",
                item=auction_item_display_name(item_id),
                npc=entry["last_bidder"], amount=format_tl(final_price),
            )
            won_by_player = False
        else:
            message = t("auction.unsold_message", item=auction_item_display_name(item_id))
            won_by_player = False

        return {"message": message, "won_by_player": won_by_player, "item_id": item_id, "amount": final_price}

    def get_auction_bid_history(self) -> list:
        """O an ekranda ilerleyen (ya da az önce sonuçlanan) açık
        artırmanın teklif geçmişini [{"label":, "amount":}, ...]
        biçiminde, en eskiden en yeniye sırayla döner."""
        if not self.auction_current:
            return []
        return list(self.auction_current.get("bid_history", []))

    def get_auction_active_bidder_count(self) -> int:
        """O an ekranda ilerleyen açık artırmada hâlâ bütçesi yeten
        (çekilmemiş) rakip sayısını döner."""
        if not self.auction_current:
            return 0
        return sum(1 for b in self.auction_current["bidders"] if b["active"])

    def sell_auction_item(self, item_id: str) -> tuple:
        """Elinizdeki bir açık artırma eşyasını satar. Fiyat, eşyanın
        orijinal değer aralığı üzerinden HER SATIŞTA rastgele belirlenir
        (AUCTION_RESALE_MIN_MULT..MAX_MULT arası bir çarpanla) - böylece
        koleksiyon parçaları normal ürünler gibi sabit bir piyasa
        fiyatına sahip değildir, her alıcı farklı bir teklif yapar.
        (başarı, mesaj) döner."""
        owned = self.auction_inventory.get(item_id, 0)
        if owned <= 0:
            return False, t("auction.not_owned")

        item_data = next((i for i in AUCTION_ITEMS if i["id"] == item_id), None)
        if item_data is None:
            return False, t("auction.item_not_found")

        base = random.uniform(item_data["min_value"], item_data["max_value"])
        price = round(base * random.uniform(self.AUCTION_RESALE_MIN_MULT, self.AUCTION_RESALE_MAX_MULT), 2)

        self.auction_inventory[item_id] = owned - 1
        if self.auction_inventory[item_id] <= 0:
            del self.auction_inventory[item_id]

        self.cash += price
        if self.cash > self.highest_cash:
            self.highest_cash = self.cash

        return True, t("auction.sold_message", item=auction_item_display_name(item_id), amount=format_tl(price))

    def get_auction_inventory_summary(self) -> list:
        """[(item_id, adet, görünen_ad), ...] biçiminde, sahip olunan
        açık artırma eşyalarının listesini döner."""
        result = []
        for item_id, qty in self.auction_inventory.items():
            if qty > 0:
                result.append((item_id, qty, auction_item_display_name(item_id)))
        return result

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
                closed_messages.append(t("state.company_closed_bankrupt", name=c['name'], city=c['city']))

        self.companies = still_open
        return closed_messages

    LOAN_PRESETS = [
        ("state.loan_preset_small", 0.25, 1),
        ("state.loan_preset_medium", 0.50, 2),
        ("state.loan_preset_large", 1.00, 3),
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
        for label_key, pct, installments in self.LOAN_PRESETS:
            amount = round(limit * pct, 2)
            if amount <= 0:
                continue
            total_debt = round(amount * (1 + rate), 2)
            installment_amount = round(total_debt / installments, 2)
            options.append({
                "label": t(label_key),
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
            return False, t("state.need_company_first")

        if self.loan_amount > 0:
            return False, t("state.loan_already_active")

        if amount <= 0:
            return False, t("state.invalid_amount")

        limit = self.get_loan_limit()
        if amount > limit:
            return False, t("state.max_loan", limit=format_tl(limit))

        tier = self.get_credit_tier()
        if not tier or not tier["can_loan"]:
            return False, t("state.loan_credit_insufficient")

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

        return True, t("state.loan_approved", amount=format_tl(amount), rate=f"{tier['interest_rate']*100:.1f}",
                        installments=installments, installment=format_tl(self.loan_installment_amount))

    def pay_loan_full(self) -> tuple:
        """Krediyi erken kapatma - kalan tüm borç tek seferde ödenir."""
        if self.loan_amount <= 0:
            return False, t("state.no_active_loan")

        debt = self.loan_total_debt
        if self.cash < debt:
            return False, t("state.insufficient_cash_payoff", amount=format_tl(debt))

        self.cash -= debt
        self._clear_loan()
        return True, t("state.loan_paid_off", amount=format_tl(debt))

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
            return False, t("state.loan_installment_failed", due=format_tl(due), paid=format_tl(paid))

        self.loan_installments_paid += 1

        if self.loan_total_debt <= 0.01:
            msg = t("state.loan_final_installment", amount=format_tl(paid))
            self._clear_loan()
            return True, msg

        self.loan_days_until_installment = 30
        return True, t("state.loan_installment_paid", amount=format_tl(paid), debt=format_tl(self.loan_total_debt))

    def default_loan(self) -> tuple:
        if not self.companies:
            return False, t("state.no_active_company")

        self.companies = []
        self._clear_loan()

        return True, t("state.business_bankrupt")

    def _illegal_inventory_value(self) -> float:
        """Elde bulundurulan yasa dışı ürünlerin (Karanlık Maddeler,
        Mühimmat & Silahlar) toplam piyasa değeri. Polis riski artık kirli
        para yerine bu değere göre hesaplanır."""
        total = 0.0
        for category in ("Karanlık Maddeler", "Mühimmat & Silahlar"):
            for name in PRODUCT_CATEGORIES.get(category, []):
                total += self.inventory.get(name, 0) * self.prices.get(name, 0.0)
                total += (self.warehouse.get(name, 0) * self.prices.get(name, 0.0)
                          * WAREHOUSE_POLICE_VISIBILITY)
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

        total += self.get_warehouse_value()

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
            return event_message_text(event, category=category_display_name(category), pct=f"{abs(pct) * 100:.1f}")
        elif etype == "cash_gain":
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event_message_text(event, amount=f"{format_tl(amount)}")
        elif etype == "cash_loss":
            
            
            
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self._spend_cash(amount)
            return event_message_text(event, amount=f"{format_tl(amount)}")
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
                return event_zero_message_text(event) or t("state.zero_no_loss", name=event_display_name(event))
            return event_message_text(event, category=category_display_name(category), count=total_lost)
        elif etype == "inventory_gain":
            
            
            
            
            
            
            
            
            
            
            
            
            category = event["category"]
            raw_pct = random.uniform(event["min_pct"], event["max_pct"])
            total_gained = 0
            not_held = []
            for name in PRODUCT_CATEGORIES[category]:
                qty = self.inventory.get(name, 0)
                if qty > 0:
                    # Stoğu olan ürün: stoğun ölçeklenmiş yüzdesi kadar,
                    # "en az 1" YOK (kayıp olaylarıyla aynı yuvarlama).
                    gained = int(round(qty * raw_pct * INVENTORY_GAIN_PCT_SCALE))
                    if gained > 0:
                        self.inventory[name] = qty + gained
                        total_gained += gained
                else:
                    not_held.append(name)

            # Stoğu olmayan ürünlerden en fazla birkaçına küçük bir değer
            # kadar mal. Değere sığmayan pahalı ürünler (Bitcoin, Elmas
            # vb.) elenir; eskiden bunlara da 1 adet verilirdi.
            baseline_value = random.uniform(
                INVENTORY_GAIN_NEW_VALUE_MIN, INVENTORY_GAIN_NEW_VALUE_MAX
            ) * (raw_pct / event["max_pct"])
            affordable = [
                n for n in not_held
                if max(self.prices.get(n) or PRODUCTS.get(n, {}).get("base_price", 500), 1) <= baseline_value
            ]
            random.shuffle(affordable)
            for name in affordable[:INVENTORY_GAIN_NEW_MAX_PRODUCTS]:
                price = max(self.prices.get(name) or PRODUCTS.get(name, {}).get("base_price", 500), 1)
                gained = int(baseline_value / price)
                if gained > 0:
                    self.inventory[name] = self.inventory.get(name, 0) + gained
                    total_gained += gained
            if total_gained == 0:
                return event_zero_message_text(event) or t("state.zero_no_gain", name=event_display_name(event))
            return event_message_text(event, category=category_display_name(category), count=total_gained)
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
                return event_zero_message_text(event) or t("state.zero_no_loss", name=event_display_name(event))
            return event_message_text(event, amount=f"{format_tl(cash_loss)}", category=category_display_name(category), count=total_lost)
        elif etype == "company_audit":
            
            
            
            return t("state.company_audit_passed")
        elif etype == "company_reputation":
            if self.companies:
                boost = event.get("credit_boost", 0)
                penalty = event.get("credit_penalty", 0)
                if boost:
                    for c in self.companies:
                        c["credit_score"] = c.get("credit_score", 50) + boost
                    return event_message_text(event, credit_boost=boost)
                elif penalty:
                    for c in self.companies:
                        c["credit_score"] = max(0, c.get("credit_score", 50) + penalty)
                    return event_message_text(event, credit_penalty=abs(penalty))
                return event_message_text(event)
            return t("state.no_company_unaffected", name=event_display_name(event))
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
            return event_message_text(event, pct=f"{abs(pct) * 100:.1f}")
        elif etype == "inheritance":
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self.cash += amount
            if self.cash > self.highest_cash:
                self.highest_cash = self.cash
            return event_message_text(event, amount=f"{format_tl(amount)}")
        elif etype == "disaster":
            
            
            wealth = self._total_wealth()
            pct = random.uniform(event["min_pct_of_wealth"], event["max_pct_of_wealth"])
            amount = round(wealth * pct, 2)
            self._spend_cash(amount)
            return event_message_text(event, amount=f"{format_tl(amount)}")
        elif etype == "death":
            self.deaths_caused += 1
            return t("state.death_total", name=event_display_name(event), count=self.deaths_caused)
        return t("state.unknown_event", name=event_display_name(event))

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
                messages.append(t("state.jail_company_bankrupt"))
            else:
                profit_msg = self.process_company_daily()
                if profit_msg:
                    messages.append(profit_msg)
        if self.has_informant:
            if not self.pay_informant_upkeep():
                messages.append(t("state.jail_informant_left"))
        if self.loan_amount > 0:
            success, msg = self.process_loan_daily()
            if not success:
                self.default_loan()
                messages.append(t("state.jail_loan_default", message=msg))
            elif msg:
                messages.append(msg)
        messages.extend(self.process_land_loans_daily())
        messages.extend(self.process_employees_daily())
        return messages


def open_help():
    """Aktif dile göre yerelleştirilmiş bir yardım dosyası açar (ör.
    'en_help.html', 'tr_help.html', ...). Dosya henüz yoksa, o anki
    dilde otomatik olarak oluşturulur (bkz. create_help_file). Bu
    isimlendirme, dialogs.py'deki _open_localized_html'in kullandığı
    kalıpla ('{dil_kodu}_help.html') birebir aynıdır."""
    lang = get_language()
    help_path = resource_path(f"{lang}_help.html")
    if not os.path.exists(help_path):
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
        speak(t("state.release_notes_missing"))


def create_help_file(path):
    """Yardım sayfasını o anki aktif dilde (get_language()) üretir.
    Başlıklar/açıklamalar locales/<dil>.json'daki help.* anahtarlarından
    gelir - yeni bir dil eklendiğinde bu anahtarlar çevrilirse yardım
    sayfası da otomatik olarak o dilde üretilir."""
    lang_attr = get_language()
    help_content = f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
    <meta charset="UTF-8">
    <title>{t("help.page_title")}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 25px; }}
        .shortcut {{ background: #2c3e50; color: white; padding: 2px 8px; border-radius: 4px; font-family: monospace; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 8px 0; }}
    </style>
</head>
<body>
    <h1>{t("help.heading")}</h1>
    <h2>{t("help.shortcuts_heading")}</h2>
    <ul>
        <li><span class="shortcut">F1</span> - {t("help.shortcut_f1")}</li>
        <li><span class="shortcut">F2</span> - {t("help.shortcut_f2")}</li>
        <li><span class="shortcut">F5</span> - {t("help.shortcut_f5")}</li>
        <li><span class="shortcut">F6</span> - {t("help.shortcut_f6")}</li>
        <li><span class="shortcut">C</span> - {t("help.shortcut_c")}</li>
        <li><span class="shortcut">D</span> - {t("help.shortcut_d")}</li>
        <li><span class="shortcut">E</span> - {t("help.shortcut_e")}</li>
        <li><span class="shortcut">PgUp</span> - {t("help.shortcut_pgup")}</li>
        <li><span class="shortcut">PgDn</span> - {t("help.shortcut_pgdn")}</li>
    </ul>
    <h2>{t("help.land_heading")}</h2>
    <ul>
        <li><strong>{t("help.land_buy")}</strong> {t("help.land_buy_desc")}</li>
        <li><strong>{t("help.land_sell")}</strong> {t("help.land_sell_desc")}</li>
        <li><strong>{t("help.land_loan")}</strong> {t("help.land_loan_desc")}</li>
        <li><strong>{t("help.land_fluctuation")}</strong> {t("help.land_fluctuation_desc")}</li>
    </ul>
    <h2>{t("help.about_heading")}</h2>
    <p>{t("help.about_text")}</p>
</body>
</html>"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(help_content)




