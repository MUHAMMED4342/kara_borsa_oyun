# game_data.py - Güncellenmiş versiyon (Arsa Sistemi eklendi, Mevduat kaldırıldı)
# -*- coding: utf-8 -*-
"""
game_data.py
------------
Karaborsa Ticaret Simülasyonu için sabit oyun verilerini içerir:
- Ürün kategorileri ve ürün isimleri
- Her ürünün başlangıç / minimum / maksimum fiyat aralığı
- Rastgele küresel olaylar
- Şirket ve kredi sistemi (şirketler sadece kâr getirir ve kredi imkanı sağlar)
- ARSA SİSTEMİ
- MUHBİR SİSTEMİ (polis baskınlarını önceden haber verir)
"""

# ---------------------------------------------------------------------------
# Ürün kategorileri ve ürün isimleri
# ---------------------------------------------------------------------------
PRODUCT_CATEGORIES = {
    "Karanlık Maddeler": [
        "Esrar", "Eroin", "Kokain", "Amfetamin", "Metamfetamin", "Captagon", "LSD",
    ],
    "Mühimmat & Silahlar": [
        "Tabanca", "Tüfek", "Mermi", "El Bombası", "Susturucu", "Zırh Yeleği", "Av Tüfeği",
    ],
    "Döviz & Değerli Metaller": [
        "Dolar", "Euro", "Sterlin", "Altın", "Gümüş", "Platin",
    ],
    "Kripto & Dijital Varlıklar": [
        "Bitcoin", "Ethereum", "Monero",
    ],
    "Kaçak Eşya & Elektronik": [
        "Sahte Pasaport", "Çalıntı Telefon", "Kaçak Sigara", "Kaçak İçki", "Çalıntı Araç Parçası",
    ],
}

# Her ürün için: başlangıç fiyatı, alabileceği minimum ve maksimum fiyat.
PRODUCTS = {
    # --- Karanlık Maddeler ---
    "Esrar":          {"base_price": 150,   "min_price": 50,    "max_price": 500},
    "Eroin":          {"base_price": 900,   "min_price": 300,   "max_price": 3000},
    "Kokain":         {"base_price": 1200,  "min_price": 400,   "max_price": 4000},
    "Amfetamin":      {"base_price": 400,   "min_price": 150,   "max_price": 1200},
    "Metamfetamin":   {"base_price": 1100,  "min_price": 400,   "max_price": 3500},
    "Captagon":       {"base_price": 600,   "min_price": 200,   "max_price": 2000},
    "LSD":            {"base_price": 750,   "min_price": 250,   "max_price": 2500},

    # --- Mühimmat & Silahlar ---
    "Tabanca":        {"base_price": 2500,  "min_price": 1000,  "max_price": 6000},
    "Tüfek":          {"base_price": 5000,  "min_price": 2000,  "max_price": 12000},
    "Mermi":          {"base_price": 25,    "min_price": 10,    "max_price": 80},
    "El Bombası":     {"base_price": 1800,  "min_price": 700,   "max_price": 4500},
    "Susturucu":      {"base_price": 1200,  "min_price": 500,   "max_price": 3000},
    "Zırh Yeleği":    {"base_price": 3000,  "min_price": 1200,  "max_price": 7000},
    "Av Tüfeği":      {"base_price": 4000,  "min_price": 1500,  "max_price": 9000},

    # --- Döviz & Değerli Metaller ---
    "Dolar":          {"base_price": 33,    "min_price": 20,    "max_price": 60},
    "Euro":           {"base_price": 36,    "min_price": 22,    "max_price": 65},
    "Sterlin":        {"base_price": 42,    "min_price": 25,    "max_price": 75},
    "Altın":          {"base_price": 2400,  "min_price": 1500,  "max_price": 4000},
    "Gümüş":          {"base_price": 35,    "min_price": 20,    "max_price": 70},
    "Platin":         {"base_price": 1100,  "min_price": 700,   "max_price": 2200},

    # --- Kripto & Dijital Varlıklar (yüksek volatilite) ---
    "Bitcoin":        {"base_price": 50000, "min_price": 10000, "max_price": 200000},
    "Ethereum":       {"base_price": 15000, "min_price": 3000,  "max_price": 60000},
    "Monero":         {"base_price": 8000,  "min_price": 1500,  "max_price": 30000},

    # --- Kaçak Eşya & Elektronik ---
    "Sahte Pasaport":          {"base_price": 5000, "min_price": 2000, "max_price": 12000},
    "Çalıntı Telefon":         {"base_price": 800,  "min_price": 300,  "max_price": 2500},
    "Kaçak Sigara":            {"base_price": 60,   "min_price": 20,   "max_price": 150},
    "Kaçak İçki":              {"base_price": 90,   "min_price": 30,   "max_price": 250},
    "Çalıntı Araç Parçası":    {"base_price": 1500, "min_price": 500,  "max_price": 4000},
}

# ---------------------------------------------------------------------------
# ŞİRKET SİSTEMİ
# ---------------------------------------------------------------------------
# NOT: Şirketler artık para aklama yapmaz. Kurulan her şirket günlük
# olarak (rastgele bir aralıkta) doğrudan KÂR üretir ve kredi notu
# biriktirerek banka kredisi çekmenizi sağlar.

# Şirket Tipleri ve Kuruluş Maliyetleri
COMPANY_TYPES = {
    "Oto Galeri": {
        "setup_cost": 15000,
        "description": "İkinci el araç alım-satımı yapan bir galeri",
        "daily_upkeep": 100,
        "daily_profit_min": 150,
        "daily_profit_max": 400,
        "credit_multiplier": 1.0,
    },
    "Gece Kulübü": {
        "setup_cost": 25000,
        "description": "Yüksek cirolu bir eğlence mekanı",
        "daily_upkeep": 250,
        "daily_profit_min": 400,
        "daily_profit_max": 900,
        "credit_multiplier": 1.5,
    },
    "Restoran": {
        "setup_cost": 10000,
        "description": "Nakit ağırlıklı çalışan bir yemek işletmesi",
        "daily_upkeep": 150,
        "daily_profit_min": 200,
        "daily_profit_max": 500,
        "credit_multiplier": 1.2,
    },
    "Tekstil Atölyesi": {
        "setup_cost": 8000,
        "description": "Küçük ölçekli tekstil üretimi",
        "daily_upkeep": 80,
        "daily_profit_min": 100,
        "daily_profit_max": 300,
        "credit_multiplier": 0.8,
    },
    "Kripto Madenciliği": {
        "setup_cost": 30000,
        "description": "Yasal görünümlü kripto madencilik operasyonu",
        "daily_upkeep": 500,
        "daily_profit_min": 600,
        "daily_profit_max": 1400,
        "credit_multiplier": 2.0,
    },
    "Oto Yıkama": {
        "setup_cost": 5000,
        "description": "Düşük maliyetli, hızlı kurulan küçük bir işletme",
        "daily_upkeep": 60,
        "daily_profit_min": 80,
        "daily_profit_max": 220,
        "credit_multiplier": 0.7,
    },
    "İnternet Kafe": {
        "setup_cost": 6000,
        "description": "Gençlerin uğrak noktası, düzenli ama mütevazı ciro",
        "daily_upkeep": 70,
        "daily_profit_min": 90,
        "daily_profit_max": 250,
        "credit_multiplier": 0.75,
    },
    "Emlak Ofisi": {
        "setup_cost": 18000,
        "description": "Konut ve arsa alım-satımına aracılık eden ofis",
        "daily_upkeep": 180,
        "daily_profit_min": 260,
        "daily_profit_max": 650,
        "credit_multiplier": 1.3,
    },
    "Nakliyat Şirketi": {
        "setup_cost": 20000,
        "description": "Şehirler arası kamyon filosuyla yük taşımacılığı",
        "daily_upkeep": 220,
        "daily_profit_min": 300,
        "daily_profit_max": 750,
        "credit_multiplier": 1.4,
    },
    "Market Zinciri": {
        "setup_cost": 22000,
        "description": "Yoğun nakit akışı olan bir süpermarket zinciri",
        "daily_upkeep": 240,
        "daily_profit_min": 330,
        "daily_profit_max": 800,
        "credit_multiplier": 1.3,
    },
    "İnşaat Firması": {
        "setup_cost": 35000,
        "description": "Konut projeleri yürüten büyük ölçekli bir müteahhitlik firması",
        "daily_upkeep": 450,
        "daily_profit_min": 550,
        "daily_profit_max": 1300,
        "credit_multiplier": 1.8,
    },
    "Otel": {
        "setup_cost": 40000,
        "description": "Turistik bölgede lüks, yüksek cirolu bir otel işletmesi",
        "daily_upkeep": 550,
        "daily_profit_min": 700,
        "daily_profit_max": 1600,
        "credit_multiplier": 2.2,
    },
}

# NOT (daily_profit_min/max): Her gün şirketiniz bu aralıkta rastgele bir
# kâr üretir. Kârın tamamı doğrudan "Nakit"e eklenir ve kredi notunuzu bir
# miktar yükseltir. Büyük/kurumsal görünümlü işletmeler (Kripto Madenciliği,
# Gece Kulübü) daha yüksek kâr aralığına sahiptir ama günlük gideri de
# yüksektir.

# Kredi Notu Seviyeleri
CREDIT_TIERS = [
    {
        "min_score": 0,
        "name": "Sicil Bozuk",
        "description": "Henüz kredi geçmişi oluşmamış",
        "loan_limit_multiplier": 0,
        "interest_rate": 0,
        "can_loan": False,
    },
    {
        "min_score": 50,
        "name": "Başlangıç",
        "description": "Yeni kurulmuş şirket",
        "loan_limit_multiplier": 1.5,
        "interest_rate": 0.35,
        "can_loan": True,
    },
    {
        "min_score": 150,
        "name": "Güvenilir İşletme",
        "description": "Düzenli ciro oluşmaya başlamış",
        "loan_limit_multiplier": 3.0,
        "interest_rate": 0.25,
        "can_loan": True,
    },
    {
        "min_score": 300,
        "name": "Kurumsal",
        "description": "Sektörde saygın konumda",
        "loan_limit_multiplier": 5.0,
        "interest_rate": 0.15,
        "can_loan": True,
    },
    {
        "min_score": 500,
        "name": "Premium",
        "description": "Bankanın en prestijli müşterisi",
        "loan_limit_multiplier": 8.0,
        "interest_rate": 0.08,
        "can_loan": True,
    },
]

# ---------------------------------------------------------------------------
# ARSA SİSTEMİ - Mevduat sistemi KALDIRILDI
# ---------------------------------------------------------------------------

LAND_TYPES = {
    "Arsa": {
        "base_price": 50000,
        "min_price": 25000,
        "max_price": 150000,
        "description": "Standart inşaat arsası",
        "credit_multiplier": 0.70,
    },
    "Tarla": {
        "base_price": 30000,
        "min_price": 15000,
        "max_price": 100000,
        "description": "Tarım arazisi",
        "credit_multiplier": 0.50,
    },
    "İmarlı Arsa": {
        "base_price": 100000,
        "min_price": 50000,
        "max_price": 300000,
        "description": "İmar izni olan değerli arsa",
        "credit_multiplier": 0.75,
    },
    "Sahil Arsa": {
        "base_price": 200000,
        "min_price": 100000,
        "max_price": 500000,
        "description": "Sahil şeridinde lüks arsa",
        "credit_multiplier": 0.60,
    },
    "Sanayi Arsa": {
        "base_price": 80000,
        "min_price": 40000,
        "max_price": 200000,
        "description": "Sanayi bölgesinde arsa",
        "credit_multiplier": 0.65,
    },
}

def calculate_police_risk(illegal_inventory_value: float) -> float:
    """Elinizde bulunan yasa dışı ürünlerin (Karanlık Maddeler, Mühimmat &
    Silahlar) toplam piyasa değerine göre polis yakalama riskini hesaplar."""
    if illegal_inventory_value <= 0:
        return 0.0
    risk = min(0.80, (illegal_inventory_value / 10000) * 0.05)
    return risk

# ---------------------------------------------------------------------------
# MUHBİR SİSTEMİ
# ---------------------------------------------------------------------------
# Bir muhbir tutulduğunda, her gün belirli bir ihtimalle yaklaşan bir polis
# operasyonunu ÖNCEDEN haber verir. Oyuncu bu uyarıyı alırsa, o gün elindeki
# malları gerçek piyasa fiyatına hızlıca elden çıkarıp polis kontrolünü
# tamamen atlatabilir. Uyarıyı görmezden gelip mallarını elden çıkarmazsa,
# o gün polis KESİN olarak yakalar.
INFORMANT_CONFIG = {
    "hire_cost": 8000,
    "daily_upkeep": 300,
}

# ---------------------------------------------------------------------------
# ADAM TUTMA & ŞUBE (ÇOKLU ŞİRKET) SİSTEMİ
# ---------------------------------------------------------------------------
# Oyuncu, insanlar.txt'teki isim havuzundan adam tutup, iller.txt'teki
# şehirlerden birine gönderebilir. Her şehirde en fazla bir adam bulunabilir.
# Tutulan adam o ildeki karaborsa satışını kendi kendine yönetir; oyuncu
# sadece kâr toplar ve her 30 günde bir maaş öder.

# NOT: Şehir ve isim listeleri artık burada sabit kodlanmıyor. Tek
# kaynak insanlar.txt / iller.txt dosyalarıdır (bkz. load_names_from_file
# ve load_cities_from_file). Bu dosyalar bulunamazsa/boşsa fonksiyonlar
# boş liste döner; oyun çökmez, sadece "adam tutma" / "şehir seçimi"
# ekranlarında ilgili liste boş görünür.

# Bir adamı bulup ikna etmenin sabit maliyeti. Adamlar artık şirket
# kurmuyor, bu yüzden şirket kuruluş maliyeti EKLENMİYOR.
EMPLOYEE_HIRE_FEE = 5000

# Taban maaş (30 günde bir). Sabit: tüm adamlar aynı maaşı alır.
EMPLOYEE_BASE_SALARY = 1500

# Bir adamın günlük ürettiği brüt (karaborsa) kazanç aralığı. Tamamı
# doğrudan nakit olarak oyuncuya gider.
EMPLOYEE_DAILY_MIN = 150
EMPLOYEE_DAILY_MAX = 600


# ---------------------------------------------------------------------------
# TÜRKÇE CASEFOLD DÜZELTMESİ
# ---------------------------------------------------------------------------
# Python'un standart str.casefold()/str.lower() metodları Türkçe'ye özgü
# İ/I - i/ı çiftini doğru işlemez:
#   "İstanbul".casefold() -> "i̇stanbul"  (noktalı i + görünmez birleşim işareti)
#   "istanbul".casefold() -> "istanbul"  (düz i)
#   -> bu ikisi EŞİT DEĞİLDİR, oysa aynı ilin farklı yazımlarıdır.
#   "Iğdır".casefold()    -> "iğdır"      (büyük I'yı yanlışlıkla noktalı i yapar)
#   "ığdır".casefold()    -> "ığdır"      (noktasız ı)
#   -> bunlar da eşit değildir.
# Bu yüzden il/ilçe adı karşılaştırmalarında (ve dosyalardan okunan
# isimlerin normalize edilmesinde) casefold() yerine bu fonksiyon
# kullanılmalıdır. Önce Türkçe'ye özgü harfler elle normalize edilir,
# sonra geri kalanı için standart casefold uygulanır.
_TR_CASEFOLD_MAP = str.maketrans({
    "İ": "i",
    "I": "ı",
    "Ç": "ç",
    "Ğ": "ğ",
    "Ö": "ö",
    "Ş": "ş",
    "Ü": "ü",
})


def tr_casefold(text: str) -> str:
    """Türkçe İ/I harflerini doğru şekilde küçük harfe çeviren casefold.
    İl/ilçe adı karşılaştırmalarında str.casefold() yerine HER ZAMAN bu
    fonksiyon kullanılmalıdır (bkz. yukarıdaki açıklama)."""
    if text is None:
        return ""
    return text.translate(_TR_CASEFOLD_MAP).casefold()


def load_names_from_file(path: str) -> list:
    """insanlar.txt gibi bir dosyadan, 'insanlar:' başlığı altındaki
    satırları isim listesi olarak okur. Dosya yoksa/bozuksa/boşsa boş
    liste döner (yedek/kopya bir isim listesi ARTIK YOK; insanlar.txt
    tek kaynaktır)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f.readlines()]
        names = []
        started = False
        for ln in lines:
            if not ln:
                continue
            if ln.lower().startswith("insanlar"):
                started = True
                continue
            if started:
                names.append(ln)
        return names
    except OSError:
        return []


def load_districts_from_file(path: str) -> dict:
    """ilceler.txt gibi bir dosyadan il -> ilçe listesi sözlüğü okur.

    Beklenen format, her satırda (tırnaklı ya da tırnaksız):
        "(il_adı) İlçe1, İlçe2, İlçe3, ..."

    Örnek:
        "(yozgat) Merkez, Akdağmadeni, Boğazlıyan, ..."

    Dönen sözlüğün anahtarları il adının sadeleştirilmiş (casefold)
    halidir; böylece iller.txt'teki farklı büyük/küçük harf yazımıyla
    güvenle eşleştirilebilir. Değerler ise o ile ait, sırası korunmuş
    ve yinelenenlerden arındırılmış ilçe adları listesidir.

    Dosya yoksa/bozuksa/boşsa ya da bir satır beklenen formatta değilse
    o satır sessizce atlanır; hiçbir durumda oyun çökmez, ilgili il
    için ilçe listesi olmadan devam edilir (boş sözlük dönebilir)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return {}

    districts_by_city = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        # Çevreleyen tırnakları (varsa) temizle.
        if len(line) >= 2 and line[0] == '"' and line[-1] == '"':
            line = line[1:-1].strip()
        if not line.startswith("("):
            continue
        close_idx = line.find(")")
        if close_idx == -1:
            continue
        city_name = line[1:close_idx].strip()
        rest = line[close_idx + 1:].strip()
        if not city_name or not rest:
            continue

        districts = []
        seen = set()
        for part in rest.split(","):
            name = part.strip().rstrip(".").strip()
            if not name:
                continue
            key = tr_casefold(name)
            if key not in seen:
                seen.add(key)
                districts.append(name)

        if districts:
            districts_by_city[tr_casefold(city_name)] = districts

    return districts_by_city


def load_cities_from_file(path: str) -> list:
    """iller.txt gibi bir dosyadan düz bir şehir listesi okur. Dosyada
    şehirler virgülle ayrılmış tek/çok satır halinde durabilir, örn:

        istanbul, ankara, gazi antep, izmir

    ya da her satırda bir şehir olabilir. Başlıktaki "iller:" satırı
    varsa (opsiyonel) atlanır. Dosya yoksa/bozuksa/boşsa boş liste
    döner (yedek/kopya bir şehir listesi ARTIK YOK; iller.txt tek
    kaynaktır)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        cities = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith("iller"):
                # "iller:" başlığını (varsa) at, aynı satırda şehir de
                # yazılmış olabilir ("iller: istanbul, ankara").
                line = line.split(":", 1)[1] if ":" in line else ""
                if not line.strip():
                    continue
            for part in line.split(","):
                name = part.strip().rstrip(".").strip()
                if name:
                    cities.append(name)
        # Yinelenenleri, sırayı bozmadan temizle.
        seen = set()
        unique_cities = []
        for c in cities:
            key = tr_casefold(c)
            if key not in seen:
                seen.add(key)
                unique_cities.append(c)
        return unique_cities
    except OSError:
        return []


# ---------------------------------------------------------------------------
# Oyun Hedefleri
# ---------------------------------------------------------------------------
GAME_GOALS = [
    {"name": "Çırak Tüccar", "days": 30, "target_cash": 25000, "description": "30 günde 25.000 TL kazan"},
    {"name": "Usta Tüccar", "days": 45, "target_cash": 75000, "description": "45 günde 75.000 TL kazan"},
    {"name": "Efsane Tüccar", "days": 60, "target_cash": 200000, "description": "60 günde 200.000 TL kazan"},
    {"name": "Karaborsa Kralı", "days": 90, "target_cash": 500000, "description": "90 günde 500.000 TL kazan"},
]

# ---------------------------------------------------------------------------
# Rastgele küresel olaylar
# ---------------------------------------------------------------------------
# NOT: Cash kaybı/kazancı olayları artık sabit değil, oyuncunun toplam 
# servetine göre dinamik olarak hesaplanır. Bu nedenle min_amount/max_amount
# yerine "min_pct_of_wealth" ve "max_pct_of_wealth" kullanılıyor.
# Bu yüzdelikler oyuncunun toplam varlığına (nakit + envanter değeri + şirket değeri + arsa değeri)
# uygulanır. Böylece zengin oyuncular daha büyük, fakir oyuncular daha küçük
# kayıplar/kazançlar yaşar.

EVENTS = [
    # --- Fiyat olayları: Döviz & Değerli Metaller ---
    {
        "name": "Ekonomik Kriz",
        "type": "price",
        "category": "Döviz & Değerli Metaller",
        "min_pct": 0.15, "max_pct": 0.40,
        "message_template": "Ekonomik kriz patlak verdi! {category} fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Ekonomik Rahatlama",
        "type": "price",
        "category": "Döviz & Değerli Metaller",
        "min_pct": -0.30, "max_pct": -0.10,
        "message_template": "Piyasalar rahatladı. {category} fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Merkez Bankası Müdahalesi",
        "type": "price",
        "category": "Döviz & Değerli Metaller",
        "min_pct": -0.20, "max_pct": -0.05,
        "message_template": "Merkez bankası piyasaya müdahale etti. {category} fiyatları yüzde {pct} geriledi.",
    },
    {
        "name": "Altın Rezervi Keşfi",
        "type": "price",
        "category": "Döviz & Değerli Metaller",
        "min_pct": -0.25, "max_pct": -0.10,
        "message_template": "Yeni bir altın rezervi keşfedildi! {category} fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Dolar Baskısı",
        "type": "price",
        "category": "Döviz & Değerli Metaller",
        "min_pct": 0.10, "max_pct": 0.25,
        "message_template": "Merkez bankası dolara müdahale etti! {category} fiyatları yüzde {pct} arttı.",
    },

    # --- Fiyat olayları: Karanlık Maddeler ---
    {
        "name": "Polis Baskını (Piyasa Etkisi)",
        "type": "price",
        "category": "Karanlık Maddeler",
        "min_pct": 0.20, "max_pct": 0.45,
        "message_template": "Bölgede baskınlar arttığı için arz daraldı! {category} fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Yeni Tedarik Hattı",
        "type": "price",
        "category": "Karanlık Maddeler",
        "min_pct": -0.35, "max_pct": -0.15,
        "message_template": "Yeni bir tedarik hattı açıldı. {category} fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Uluslararası Kartel Savaşı",
        "type": "price",
        "category": "Karanlık Maddeler",
        "min_pct": 0.50, "max_pct": 0.90,
        "message_template": "Büyük karteller birbirine girdi, tedarik zinciri felç oldu! {category} fiyatları yüzde {pct} fırladı."
    },
    {
        "name": "Laboratuvar Patlaması",
        "type": "price",
        "category": "Karanlık Maddeler",
        "min_pct": 0.25, "max_pct": 0.50,
        "message_template": "Şehirdeki ana üretim laboratuvarında patlama oldu! {category} fiyatları yüzde {pct} arttı."
    },
    {
        "name": "Afganistan'dan Büyük Sevkiyat",
        "type": "price",
        "category": "Karanlık Maddeler",
        "min_pct": -0.30, "max_pct": -0.15,
        "message_template": "Doğudan büyük bir sevkiyat geldi! {category} fiyatları yüzde {pct} düştü."
    },

    # --- Fiyat olayları: Mühimmat & Silahlar ---
    {
        "name": "Sınır Kapılarının Kapanması",
        "type": "price",
        "category": "Mühimmat & Silahlar",
        "min_pct": 0.15, "max_pct": 0.35,
        "message_template": "Sınır kapıları kapatıldı, tedarik zorlaştı. {category} fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Silah Fabrikası Anlaşması",
        "type": "price",
        "category": "Mühimmat & Silahlar",
        "min_pct": -0.30, "max_pct": -0.10,
        "message_template": "Gizli bir tedarik anlaşması yapıldı. {category} fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Yerel Çete Savaşları",
        "type": "price",
        "category": "Mühimmat & Silahlar",
        "min_pct": 0.30, "max_pct": 0.60,
        "message_template": "Sokaklarda çatışmalar başladı, silaha talep tavan yaptı! {category} fiyatları yüzde {pct} yükseldi."
    },
    {
        "name": "Askeri Depodan Sızıntı",
        "type": "price",
        "category": "Mühimmat & Silahlar",
        "min_pct": -0.40, "max_pct": -0.20,
        "message_template": "Ordu depolarından piyasaya çok sayıda kaçak silah sızdı! {category} fiyatları yüzde {pct} düştü."
    },
    {
        "name": "Barış Anlaşması",
        "type": "price",
        "category": "Mühimmat & Silahlar",
        "min_pct": -0.50, "max_pct": -0.25,
        "message_template": "Bölgede barış anlaşması imzalandı! {category} talebi düştü, fiyatlar yüzde {pct} geriledi."
    },
    {
        "name": "Uluslararası Ambargo",
        "type": "price",
        "category": "Mühimmat & Silahlar",
        "min_pct": 0.20, "max_pct": 0.45,
        "message_template": "Ülkeye silah ambargosu kondu, kaçak tedarik neredeyse imkansız hale geldi! {category} fiyatları yüzde {pct} fırladı."
    },

    # --- Fiyat olayları: Kripto ---
    {
        "name": "Kripto Balinası Alım Yaptı",
        "type": "price",
        "category": "Kripto & Dijital Varlıklar",
        "min_pct": 0.30, "max_pct": 0.80,
        "message_template": "Büyük bir yatırımcı (balina) ani alım yaptı! {category} fiyatları yüzde {pct} fırladı.",
    },
    {
        "name": "Kripto Piyasası Çöktü",
        "type": "price",
        "category": "Kripto & Dijital Varlıklar",
        "min_pct": -0.60, "max_pct": -0.30,
        "message_template": "Ani bir satış dalgasıyla piyasa çöktü! {category} fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Ünlü Milyarderin Tweeti",
        "type": "price",
        "category": "Kripto & Dijital Varlıklar",
        "min_pct": 0.40, "max_pct": 1.00,
        "message_template": "Eksantrik bir milyarder manipülatif bir tweet attı! {category} fiyatları yüzde {pct} uçuşa geçti."
    },
    {
        "name": "Büyük Kripto Borsası Hacklendi",
        "type": "price",
        "category": "Kripto & Dijital Varlıklar",
        "min_pct": -0.50, "max_pct": -0.25,
        "message_template": "Dünyanın en büyük dijital borsası siber saldırıya uğradı. {category} fiyatları yüzde {pct} eridi."
    },
    {
        "name": "Kripto Piyasası Düzeldi",
        "type": "price",
        "category": "Kripto & Dijital Varlıklar",
        "min_pct": 0.10, "max_pct": 0.30,
        "message_template": "Kripto piyasası toparlanıyor! {category} fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Yeni Kripto Düzenlemesi",
        "type": "price",
        "category": "Kripto & Dijital Varlıklar",
        "min_pct": -0.25, "max_pct": -0.10,
        "message_template": "Hükümet kripto düzenlemesi açıkladı! {category} fiyatları yüzde {pct} düştü.",
    },

    # --- Fiyat olayları: Kaçak Eşya ---
    {
        "name": "Elektronik Kaçakçılığı Talebi Arttı",
        "type": "price",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": 0.15, "max_pct": 0.35,
        "message_template": "Talep arttı! {category} fiyatları yüzde {pct} yükseldi.",
    },
    {
        "name": "Gümrük Denetimi Gevşetildi",
        "type": "price",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": -0.25, "max_pct": -0.10,
        "message_template": "Gümrük denetimleri gevşetildi. {category} fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Sınırda Yeni X-Ray Cihazları",
        "type": "price",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": 0.20, "max_pct": 0.40,
        "message_template": "Gümrük kapılarına son teknoloji tarayıcılar kuruldu. {category} getirmek zorlaştı, fiyatlar yüzde {pct} arttı."
    },
    {
        "name": "Büyük Depo Tasfiyesi",
        "type": "price",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": -0.30, "max_pct": -0.15,
        "message_template": "Kaçakçılar ellerindeki malları nakde çevirmek için ucuza bırakıyor. {category} fiyatları yüzde {pct} düştü."
    },
    {
        "name": "Kaçak Telefon Fabrikası Açıldı",
        "type": "price",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": -0.20, "max_pct": -0.05,
        "message_template": "Bölgede yeni bir kaçak telefon montaj hattı kuruldu. {category} fiyatları yüzde {pct} düştü."
    },
    {
        "name": "Liman Grevi",
        "type": "price",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": 0.15, "max_pct": 0.30,
        "message_template": "Liman işçileri greve gitti, ithalat durma noktasına geldi! {category} fiyatları yüzde {pct} arttı."
    },

    # --- Nakit kazanç olayları (Dinamik - servete göre) ---
    {
        "name": "Beklenmedik Bahşiş",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.03,
        "message_template": "Şanslı bir gündesiniz! Cüzdanınıza {amount} TL eklendi.",
    },
    {
        "name": "Eski Bir Borç Geri Ödendi",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.05,
        "message_template": "Size borçlu olan biri parayı geri ödedi: {amount} TL kazandınız.",
    },
    {
        "name": "Yerde Duran Çanta",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.04,
        "message_template": "Arka sokaklarda içinde para unutulmuş sahipsiz bir çanta buldunuz! Cüzdanınıza {amount} TL eklendi."
    },
    {
        "name": "Yasa Dışı Kumar Kazancı",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.03, "max_pct_of_wealth": 0.08,
        "message_template": "Dün gece girdiğiniz gizli bir poker masasında şansınız yaver gitti: {amount} TL kazandınız."
    },
    {
        "name": "Kaçakçılıktan Komisyon",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.06,
        "message_template": "Aracılık yaptığınız kaçakçılık işinden komisyon aldınız: {amount} TL."
    },
    {
        "name": "Eski Müşteriden Sipariş",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.03,
        "message_template": "Eski bir müşteriniz sizi arayıp acil bir sipariş verdi: {amount} TL kazandınız."
    },
    {
        "name": "Nakit Sayım Fazlası",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.005, "max_pct_of_wealth": 0.02,
        "message_template": "Kasanızı sayarken unuttuğunuz bir tomar para çıktı: {amount} TL."
    },
    {
        "name": "Sahte Evrak Komisyonu",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.015, "max_pct_of_wealth": 0.04,
        "message_template": "Sahte kimlik/ehliyet işine aracılık ettiniz ve komisyonunuzu aldınız: {amount} TL."
    },
    {
        "name": "Eski Ortaktan Pay",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.05,
        "message_template": "Yıllar önce ortak olduğunuz bir işten unuttuğunuz payınızı gönderdiler: {amount} TL kazandınız."
    },
    {
        "name": "Sigorta Ödemesi",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.06,
        "message_template": "Geçmişteki küçük bir hasar için sigorta şirketi tazminat yatırdı: {amount} TL."
    },
    {
        "name": "Nakit Taşıma İşinden Pay",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.05,
        "message_template": "Kara parayı bir yerden bir yere taşıma işinde kurye olarak kullanıldınız, payınızı aldınız: {amount} TL."
    },
    {
        "name": "Gizli Turnuva Kazancı",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.07,
        "message_template": "Katıldığınız gizli bir bahis turnuvasını kazandınız: {amount} TL."
    },
    {
        "name": "Tedarikçiden İndirim İadesi",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.035,
        "message_template": "Sadık müşteri olduğunuz için tedarikçiniz size nakit iade yaptı: {amount} TL."
    },
    {
        "name": "Rakipten Ele Geçirilen Kasa",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.015, "max_pct_of_wealth": 0.045,
        "message_template": "Rakip bir ekibin terk edilmiş kasasını bulup el koydunuz: {amount} TL kazandınız."
    },
    {
        "name": "Yüklü Bahşiş Verildi",
        "type": "cash_gain",
        "min_pct_of_wealth": 0.005, "max_pct_of_wealth": 0.025,
        "message_template": "Memnun bir müşteri beklediğinizden çok daha fazla ödeme yaptı: {amount} TL."
    },

    # --- Envanter kazanç olayları (Dinamik - stoğa göre) ---
    # inventory_loss olaylarının dengeleyicisi: karşılıksız stok kazandırır.
    {
        "name": "Bedava Numune Kutusu",
        "type": "inventory_gain",
        "category": "Karanlık Maddeler",
        "min_pct": 0.04, "max_pct": 0.10,
        "message_template": "Tedarikçiniz size bedava numune gönderdi! {category} stoğunuza {count} adet ürün eklendi.",
        "zero_message": "Tedarikçi bedava numune göndermek istedi ama elinizde ilgili kategoriden ürün olmadığı için teklifi değerlendiremediniz.",
    },
    {
        "name": "Yanlış Adrese Gelen Sevkiyat",
        "type": "inventory_gain",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": 0.05, "max_pct": 0.12,
        "message_template": "Başka birine ait bir kaçak sevkiyat yanlışlıkla size teslim edildi! {category} stoğunuza {count} adet ürün eklendi.",
        "zero_message": "Yanlış adrese bir sevkiyat geldi ama elinizde bu kategoriden mal olmadığı için değerlendiremediniz.",
    },
    {
        "name": "Terk Edilmiş Depo Keşfi",
        "type": "inventory_gain",
        "category": "Mühimmat & Silahlar",
        "min_pct": 0.04, "max_pct": 0.10,
        "message_template": "Şehir dışında terk edilmiş eski bir depo buldunuz! {category} stoğunuza {count} adet ürün eklendi.",
        "zero_message": "Terk edilmiş bir depo buldunuz ama elinizde bu kategoriden mal olmadığı için taşıyacak bir şeyiniz yoktu.",
    },
    {
        "name": "Kapkaççıdan Ele Geçirilen Çanta",
        "type": "inventory_gain",
        "category": "Döviz & Değerli Metaller",
        "min_pct": 0.03, "max_pct": 0.08,
        "message_template": "Sokakta bir kapkaççıyı yakalayıp çantasına el koydunuz! {category} stoğunuza {count} adet ürün eklendi.",
        "zero_message": "Bir kapkaççıyı yakaladınız ama çantasında değerli döviz/metal çıkmadığı için elinize bir şey geçmedi.",
    },

    # --- Nakit kaybı olayları (Dinamik - servete göre) ---
    # Artık sabit TL değil, toplam servetin yüzdesi kadar kaybediliyor.
    # Yüzdeler zenginleri daha çok, fakirleri daha az etkileyecek şekilde ayarlandı.
    {
        "name": "Soygun",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.05,
        "message_template": "Soyuldunuz! Cüzdanınızdan {amount} TL çalındı.",
    },
    {
        "name": "Rüşvet Talebi",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.035,
        "message_template": "Yerel bir yetkili rüşvet istedi, {amount} TL ödemek zorunda kaldınız.",
    },
    {
        "name": "Siber Dolandırıcılık",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.015, "max_pct_of_wealth": 0.04,
        "message_template": "Kripto cüzdanınızın şifresini bir oltalama (phishing) sitesine kaptırdınız! {amount} TL kaybettiniz.",
    },
    {
        "name": "Haraç Kesilmesi",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.02, "max_pct_of_wealth": 0.05,
        "message_template": "Bölgenin ağır abileri mekanınızı bastı ve koruma parası adı altında {amount} TL haraç aldı.",
    },
    {
        "name": "Sahte Ürün Tazminatı",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.03,
        "message_template": "Sattığınız malın bozuk/sahte çıktığını öğrenen öfkeli bir müşteriye tazminat ödediniz: {amount} TL.",
    },
    {
        "name": "Zula Baskını",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.015, "max_pct_of_wealth": 0.045,
        "message_template": "Gizli para saklama noktanızı bulan biri nakdinizin bir kısmını alıp kaçtı: {amount} TL kaybettiniz.",
    },
    {
        "name": "Ceza Kesildi",
        "type": "cash_loss",
        "min_pct_of_wealth": 0.005, "max_pct_of_wealth": 0.02,
        "message_template": "Trafik cezası, izinsiz çalışma ve benzeri nedenlerle {amount} TL ceza ödediniz.",
    },

    # --- Envanter müsadere olayları ---
    # NOT: Yüzdeler önceden çok yüksekti (ör. %20-%50), bu da art arda
    # gelen olaylarda stoğun günden güne çok hızlı erimesine yol açıyordu
    # (50 -> 40 -> 20 gibi). Artık her olay stoğun sadece küçük bir
    # kısmını (~%3-%12) götürüyor.
    {
        "name": "Polis Baskını - Mal Müsadere",
        "type": "inventory_loss",
        "category": "Karanlık Maddeler",
        "min_pct": 0.05, "max_pct": 0.12,
        "message_template": "Polis baskınında {category} stoğunuzdan {count} adet ürüne el konuldu!",
        "zero_message": "Polis baskını oldu ama elinizde karanlık madde bulunmadığı için zarar görmediniz.",
    },
    {
        "name": "Silah Deposu Basıldı",
        "type": "inventory_loss",
        "category": "Mühimmat & Silahlar",
        "min_pct": 0.05, "max_pct": 0.12,
        "message_template": "Silah deponuz basıldı! {category} stoğunuzdan {count} adet ürün kayboldu.",
        "zero_message": "Bir baskın haberi geldi ama elinizde silah/mühimmat olmadığı için zarar görmediniz.",
    },
    {
        "name": "Fare İstilası",
        "type": "inventory_loss",
        "category": "Karanlık Maddeler",
        "min_pct": 0.03, "max_pct": 0.08,
        "message_template": "Deponuzu lağım fareleri bastı! {category} stoklarınız kemirildi, {count} adet ürün çöpe gitti.",
        "zero_message": "Depoda fareler cirit atıyor ama içeride karanlık madde olmadığı için bir şey kaybetmediniz."
    },
    {
        "name": "Köstebek İhaneti",
        "type": "inventory_loss",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": 0.04, "max_pct": 0.10,
        "message_template": "Güvendiğiniz bir elemanınız {category} stoğunuzdan {count} adet ürünü çalıp sırra kadem bastı!",
        "zero_message": "Yanınızdaki eleman sizi dolandırmaya çalıştı ama depoda mal olmadığı için amacına ulaşamadı."
    },
    {
        "name": "Gümrükte Mallara El Konuldu",
        "type": "inventory_loss",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct": 0.04, "max_pct": 0.10,
        "message_template": "Gümrükteki kaçak eşyanıza el konuldu! {category} stoğunuzdan {count} adet ürün gitti.",
        "zero_message": "Gümrük kontrolünü atlattınız, kayıp yok."
    },
    {
        "name": "Kasa Soygunu",
        "type": "inventory_loss",
        "category": "Döviz & Değerli Metaller",
        "min_pct": 0.03, "max_pct": 0.08,
        "message_template": "Kasanıza göz koyan biri bir kısım döviz/değerli metalinizi çaldı! {category} stoğunuzdan {count} adet ürün eksildi.",
        "zero_message": "Kasanıza yönelik bir soygun girişimi oldu ama içeride döviz/değerli metal olmadığı için kayıp yaşamadınız."
    },

    # --- Büyük Risk / Kombo Olaylar (Dinamik - servete göre) ---
    # Hem nakit hem envanter kaybı içerir. Nakit kısmı servete göre dinamik,
    # envanter kısmı ise stok yüzdesi olarak.
    {
        "name": "Rakip Çete Baskını",
        "type": "raid_combo",
        "category": "Mühimmat & Silahlar",
        "min_pct_of_wealth": 0.015, "max_pct_of_wealth": 0.05,
        "inventory_min_pct": 0.05, "inventory_max_pct": 0.12,
        "message_template": "Rakip bir çete güvenli evinize baskın yaptı! Çatışmada {amount} TL ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Rakip çete baskın yapacaktı ancak istihbaratı erken alıp mekanı boşalttınız. Kayıp yok!"
    },
    {
        "name": "Büyük Çete Operasyonu",
        "type": "raid_combo",
        "category": "Karanlık Maddeler",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.045,
        "inventory_min_pct": 0.05, "inventory_max_pct": 0.14,
        "message_template": "Büyük bir çete operasyonuna yakalandınız! {amount} TL ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Çete operasyonu haberleri geldi ama ne paranız ne de stoğunuz olduğu için etkilenmediniz.",
    },
    {
        "name": "Sınır Ötesi Yakalanma",
        "type": "raid_combo",
        "category": "Mühimmat & Silahlar",
        "min_pct_of_wealth": 0.008, "max_pct_of_wealth": 0.03,
        "inventory_min_pct": 0.04, "inventory_max_pct": 0.10,
        "message_template": "Sınırda yakalandınız! Ceza olarak {amount} TL ödediniz ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Sınırda bir kontrol yapıldı ama üzerinizde para ya da mühimmat olmadığı için serbest bırakıldınız.",
    },
    {
        "name": "Muhbir İhbarı",
        "type": "raid_combo",
        "category": "Kaçak Eşya & Elektronik",
        "min_pct_of_wealth": 0.01, "max_pct_of_wealth": 0.035,
        "inventory_min_pct": 0.04, "inventory_max_pct": 0.11,
        "message_template": "Yakınınızdaki biri sizi polise ihbar etti! Baskında {amount} TL ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Bir ihbar geldi ama üzerinizde ne nakit ne de kaçak mal bulunduğundan zarar görmeden kurtuldunuz.",
    },

    # --- Şirket ile ilgili olaylar ---
    {
        "name": "Yılın Girişimcisi Ödülü",
        "type": "company_reputation",
        "message_template": "Yerel bir iş insanları derneği sizi 'Yılın Girişimcisi' seçti! Kredi notunuz yükseldi.",
        "credit_boost": 20,
    },
    {
        "name": "Sosyal Medyada Skandal İddiası",
        "type": "company_reputation",
        "message_template": "Şirketinizle ilgili asılsız bir skandal iddiası sosyal medyada yayıldı! Kredi notunuz düştü.",
        "credit_penalty": -18,
    },
    {
        "name": "Şirket İtibarı Arttı",
        "type": "company_reputation",
        "message_template": "Şirketiniz yerel ticaret odasından ödül aldı! Kredi notunuz yükseldi.",
        "credit_boost": 25,
    },
    {
        "name": "Rakip Şirket İftirası",
        "type": "company_reputation",
        "message_template": "Rakip bir şirket dedikodu yaydı! Kredi notunuz düştü.",
        "credit_penalty": -20,
    },
    {
        "name": "Devlet Teşviği",
        "type": "company_reputation",
        "message_template": "Şirketinize devlet teşviki verildi! Kredi notunuz yükseldi.",
        "credit_boost": 15,
    },
    {
        "name": "Ticari Casusluk",
        "type": "company_reputation",
        "message_template": "Rakibiniz ticari sırlarınızı çaldı! Kredi notunuz düştü.",
        "credit_penalty": -15,
    },

    # --- ARSA OLAYLARI ---
    {
        "name": "Arsa Değerinde Patlama",
        "type": "land_price",
        "min_pct": 0.15, "max_pct": 0.40,
        "message_template": "Bölgede imar düzenlemesi yapıldı! Tüm arsa fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Arsa Değerinde Düşüş",
        "type": "land_price",
        "min_pct": -0.20, "max_pct": -0.10,
        "message_template": "Ekonomik durgunluk nedeniyle tüm arsa fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Deprem Riski Uyarısı",
        "type": "land_price",
        "land_type": ["Arsa", "İmarlı Arsa"],
        "min_pct": -0.15, "max_pct": -0.05,
        "message_template": "Bölgede deprem riski uyarısı yapıldı! Arsa fiyatları yüzde {pct} geriledi.",
    },
    {
        "name": "Yeni Metro Hattı",
        "type": "land_price",
        "land_type": ["Arsa", "İmarlı Arsa"],
        "min_pct": 0.20, "max_pct": 0.50,
        "message_template": "Bölgeye yeni metro hattı müjdesi geldi! Arsa fiyatları yüzde {pct} fırladı!",
    },
    {
        "name": "Tarım Desteklemesi",
        "type": "land_price",
        "land_type": "Tarla",
        "min_pct": 0.10, "max_pct": 0.25,
        "message_template": "Devlet tarım desteklemesi açıkladı! Tarla fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Sahil Kirliliği",
        "type": "land_price",
        "land_type": "Sahil Arsa",
        "min_pct": -0.25, "max_pct": -0.10,
        "message_template": "Sahil şeridinde kirlilik tespit edildi! Sahil arsa fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Turizm Bölgesi İlanı",
        "type": "land_price",
        "land_type": "Sahil Arsa",
        "min_pct": 0.20, "max_pct": 0.45,
        "message_template": "Bölge resmi olarak turizm bölgesi ilan edildi! Sahil arsa fiyatları yüzde {pct} fırladı.",
    },
    {
        "name": "Yeni Organize Sanayi Bölgesi",
        "type": "land_price",
        "land_type": "Sanayi Arsa",
        "min_pct": 0.15, "max_pct": 0.35,
        "message_template": "Bölgeye yeni bir organize sanayi bölgesi kuruluyor! Sanayi arsa fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Fabrika Kapanmaları",
        "type": "land_price",
        "land_type": "Sanayi Arsa",
        "min_pct": -0.20, "max_pct": -0.08,
        "message_template": "Bölgedeki fabrikaların art arda kapanması talebi düşürdü. Sanayi arsa fiyatları yüzde {pct} geriledi.",
    },
]

# ---------------------------------------------------------------------------
# NADİR / BÜYÜK OLAYLAR
# ---------------------------------------------------------------------------
# Bu olaylar normal EVENTS havuzunun dışında, ayrı ve çok düşük bir
# ihtimalle (her gün için "chance" alanındaki olasılıkla) kontrol edilir.
# Böylece diğer onlarca olayla eşit şansta seçilip sık sık tetiklenmezler.
# Büyük olaylar da artık servete göre dinamik!
RARE_EVENTS = [
    {
        "name": "Miras Kaldı",
        "type": "inheritance",
        "chance": 0.004,  # ortalama ~250 günde bir
        "min_pct_of_wealth": 0.20,
        "max_pct_of_wealth": 0.50,
        "message_template": "Hiç tanımadığınız uzak bir akrabanızdan dev bir miras kaldı! Hesabınıza {amount} TL yatırıldı.",
    },
    {
        "name": "Büyük İkramiye",
        "type": "inheritance",
        "chance": 0.002,  # ortalama ~500 günde bir
        "min_pct_of_wealth": 0.50,
        "max_pct_of_wealth": 1.00,
        "message_template": "Bir piyango biletinde büyük ikramiye kazandınız! {amount} TL hesabınıza yatırıldı!",
    },
    {
        "name": "Büyük Felaket",
        "type": "disaster",
        "chance": 0.003,  # ortalama ~333 günde bir
        "min_pct_of_wealth": 0.10,
        "max_pct_of_wealth": 0.30,
        "message_template": "Depolama alanınızda yangın çıktı! Tüm mal varlığınız zarar gördü, {amount} TL kaybettiniz!",
    },
]


def get_flat_product_order():
    flat = []
    for names in PRODUCT_CATEGORIES.values():
        flat.extend(names)
    return flat


def clean_username(username: str) -> str:
    import re
    
    if not username:
        return "Anonim"
    
    turkish_map = {
        'ğ': 'g', 'ü': 'u', 'ş': 's', 'ı': 'i', 'ö': 'o', 'ç': 'c',
        'Ğ': 'G', 'Ü': 'U', 'Ş': 'S', 'İ': 'I', 'Ö': 'O', 'Ç': 'C'
    }
    for tr_char, en_char in turkish_map.items():
        username = username.replace(tr_char, en_char)
    
    username = re.sub(r'[^a-zA-Z0-9_]', '_', username)
    
    if len(username) > 20:
        username = username[:20]
    
    return username or "Anonim"


# ---------------------------------------------------------------------------
# SERVET HESAPLAMA YARDIMCISI
# ---------------------------------------------------------------------------
def calculate_total_wealth(player_data: dict) -> float:
    """
    Oyuncunun toplam servetini hesaplar.
    player_data: Oyuncunun tüm verilerini içeren sözlük
    Döner: Toplam servet (float)
    """
    total = 0.0
    
    # Nakit
    total += player_data.get("cash", 0.0)
    
    # Envanter değeri (mevcut piyasa fiyatlarıyla)
    inventory = player_data.get("inventory", {})
    current_prices = player_data.get("current_prices", {})
    for product, quantity in inventory.items():
        price_info = current_prices.get(product, {})
        price = price_info.get("price", 0) if isinstance(price_info, dict) else 0
        total += quantity * price
    
    # Şirket değeri (yaklaşık)
    companies = player_data.get("companies", {})
    for company_data in companies.values():
        # Şirket kurulum maliyeti + (günlük kar * 30) gibi basit bir değerleme
        if isinstance(company_data, dict):
            setup_cost = company_data.get("setup_cost", 0)
            daily_profit = company_data.get("daily_profit", 0)
            total += setup_cost + (daily_profit * 30)
    
    # Arsa değeri
    lands = player_data.get("lands", {})
    for land_data in lands.values():
        if isinstance(land_data, dict):
            total += land_data.get("current_price", land_data.get("purchase_price", 0))
    
    return total