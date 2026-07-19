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
}

# NOT (daily_profit_min/max): Her gün şirketiniz bu aralıkta rastgele bir
# kâr üretir. Kârın tamamı hem "Nakit"e hem de "Temiz Para"ya eklenir ve
# kredi notunuzu bir miktar yükseltir. Büyük/kurumsal görünümlü işletmeler
# (Kripto Madenciliği, Gece Kulübü) daha yüksek kâr aralığına sahiptir
# ama günlük gideri de yüksektir.

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
            key = c.casefold()
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

    # --- Nakit kazanç olayları ---
    {
        "name": "Beklenmedik Bahşiş",
        "type": "cash_gain",
        "min_pct": 0.05, "max_pct": 0.20,
        "message_template": "Şanslı bir gündesiniz! Cüzdanınıza {amount} TL eklendi.",
    },
    {
        "name": "Eski Bir Borç Geri Ödendi",
        "type": "cash_gain",
        "min_pct": 0.03, "max_pct": 0.10,
        "message_template": "Size borçlu olan biri parayı geri ödedi: {amount} TL kazandınız.",
    },
    {
        "name": "Yerde Duran Çanta",
        "type": "cash_gain",
        "min_pct": 0.08, "max_pct": 0.25,
        "message_template": "Arka sokaklarda içinde para unutulmuş sahipsiz bir çanta buldunuz! Cüzdanınıza {amount} TL eklendi."
    },
    {
        "name": "Yasa Dışı Kumar Kazancı",
        "type": "cash_gain",
        "min_pct": 0.10, "max_pct": 0.35,
        "message_template": "Dün gece girdiğiniz gizli bir poker masasında şansınız yaver gitti: {amount} TL kazandınız."
    },
    {
        "name": "Kaçakçılıktan Komisyon",
        "type": "cash_gain",
        "min_pct": 0.05, "max_pct": 0.15,
        "message_template": "Aracılık yaptığınız kaçakçılık işinden komisyon aldınız: {amount} TL."
    },
    {
        "name": "Eski Müşteriden Sipariş",
        "type": "cash_gain",
        "min_pct": 0.04, "max_pct": 0.12,
        "message_template": "Eski bir müşteriniz sizi arayıp acil bir sipariş verdi: {amount} TL kazandınız."
    },
    {
        "name": "Nakit Sayım Fazlası",
        "type": "cash_gain",
        "min_pct": 0.03, "max_pct": 0.10,
        "message_template": "Kasanızı sayarken unuttuğunuz bir tomar para çıktı: {amount} TL."
    },
    {
        "name": "Küçük Bahis Kazancı",
        "type": "cash_gain",
        "min_pct": 0.05, "max_pct": 0.18,
        "message_template": "Sokak arasında girdiğiniz küçük bir bahiste şanslıydınız: {amount} TL kazandınız."
    },

    # --- Nakit kaybı olayları ---
    # NOT: Bu olaylar artık cüzdandaki paranın YÜZDESİ değil, SABİT bir TL
    # aralığından rastgele seçilen bir miktar kaybettirir. Böylece zengin bir
    # oyuncu orantısız büyük, fakir bir oyuncu da anlamsız derecede küçük
    # ("1 TL'niz varken 50 kuruş ceza" gibi) bir kayıp yaşamıyor. Cüzdanda
    # yeterli para olmasa bile tutar tamamen düşülür; bakiye eksiye
    # düşebilir (gerçek hayatta olduğu gibi borçlanmış olursunuz).
    # Tutarlar bilinçli olarak KÜÇÜK tutuluyor: olaylar sık sık çıkabiliyor,
    # ama her biri cüzdanı ciddi şekilde eritmesin diye hafif kalıyor.
    {
        "name": "Soygun",
        "type": "cash_loss",
        "min_amount": 200, "max_amount": 1000,
        "message_template": "Soyuldunuz! Cüzdanınızdan {amount} TL çalındı.",
    },
    {
        "name": "Rüşvet Talebi",
        "type": "cash_loss",
        "min_amount": 100, "max_amount": 400,
        "message_template": "Yerel bir yetkili rüşvet istedi, {amount} TL ödemek zorunda kaldınız.",
    },
    {
        "name": "Siber Dolandırıcılık",
        "type": "cash_loss",
        "min_amount": 150, "max_amount": 600,
        "message_template": "Kripto cüzdanınızın şifresini bir oltalama (phishing) sitesine kaptırdınız! {amount} TL kaybettiniz.",
    },
    {
        "name": "Haraç Kesilmesi",
        "type": "cash_loss",
        "min_amount": 200, "max_amount": 800,
        "message_template": "Bölgenin ağır abileri mekanınızı bastı ve koruma parası adı altında {amount} TL haraç aldı.",
    },
    {
        "name": "Sahte Para Basma Hatası",
        "type": "cash_loss",
        "min_amount": 250, "max_amount": 1000,
        "message_template": "Sahte para basma operasyonunuzda baskı hatası yaptınız! {amount} TL zarar ettiniz.",
    },
    {
        "name": "Ceza Kesildi",
        "type": "cash_loss",
        "min_amount": 75, "max_amount": 300,
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

    # --- Büyük Risk / Kombo Olaylar ---
    # NOT: cash_* alanları da artık nakdin yüzdesi değil, sabit bir TL
    # aralığı ("cash_min_amount"/"cash_max_amount"). Envanter kaybı
    # (inventory_*) hâlâ elinizdeki stoğun yüzdesi olarak kalıyor, çünkü o
    # zaten cüzdana göre değil sahip olunan mala göre hesaplanıyordu; ama
    # bu yüzdeler de aynı sebeple ciddi şekilde küçültüldü.
    {
        "name": "Rakip Çete Baskını",
        "type": "raid_combo",
        "category": "Mühimmat & Silahlar",
        "cash_min_amount": 300, "cash_max_amount": 1200,
        "inventory_min_pct": 0.08, "inventory_max_pct": 0.18,
        "message_template": "Rakip bir çete güvenli evinize baskın yaptı! Çatışmada {amount} TL ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Rakip çete baskın yapacaktı ancak istihbaratı erken alıp mekanı boşalttınız. Kayıp yok!"
    },
    {
        "name": "Büyük Çete Operasyonu",
        "type": "raid_combo",
        "category": "Karanlık Maddeler",
        "cash_min_amount": 250, "cash_max_amount": 1000,
        "inventory_min_pct": 0.08, "inventory_max_pct": 0.20,
        "message_template": "Büyük bir çete operasyonuna yakalandınız! {amount} TL ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Çete operasyonu haberleri geldi ama ne paranız ne de stoğunuz olduğu için etkilenmediniz.",
    },
    {
        "name": "Sınır Ötesi Yakalanma",
        "type": "raid_combo",
        "category": "Mühimmat & Silahlar",
        "cash_min_amount": 200, "cash_max_amount": 900,
        "inventory_min_pct": 0.06, "inventory_max_pct": 0.15,
        "message_template": "Sınırda yakalandınız! Ceza olarak {amount} TL ödediniz ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Sınırda bir kontrol yapıldı ama üzerinizde para ya da mühimmat olmadığı için serbest bırakıldınız.",
    },

    # --- Şirket ile ilgili olaylar ---
    {
        "name": "Maliye Denetimi",
        "type": "company_audit",
        "message_template": "Maliye müfettişleri şirketinizi denetliyor! Şirket geliriniz risk altında.",
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
        "message_template": "Ekonomik durgunluk nedeniyle arsa fiyatları yüzde {pct} düştü.",
    },
    {
        "name": "Deprem Riski Uyarısı",
        "type": "land_price",
        "min_pct": -0.15, "max_pct": -0.05,
        "message_template": "Bölgede deprem riski uyarısı yapıldı! Arsa fiyatları yüzde {pct} geriledi.",
    },
    {
        "name": "Yeni Metro Hattı",
        "type": "land_price",
        "min_pct": 0.20, "max_pct": 0.50,
        "message_template": "Bölgeye yeni metro hattı müjdesi geldi! Arsa fiyatları yüzde {pct} fırladı!",
    },
    {
        "name": "Tarım Desteklemesi",
        "type": "land_price",
        "min_pct": 0.10, "max_pct": 0.25,
        "message_template": "Devlet tarım desteklemesi açıkladı! Tarla fiyatları yüzde {pct} arttı.",
    },
    {
        "name": "Sahil Kirliliği",
        "type": "land_price",
        "min_pct": -0.25, "max_pct": -0.10,
        "message_template": "Sahil şeridinde kirlilik tespit edildi! Sahil arsa fiyatları yüzde {pct} düştü.",
    },
]

# ---------------------------------------------------------------------------
# NADİR / BÜYÜK OLAYLAR
# ---------------------------------------------------------------------------
# Bu olaylar normal EVENTS havuzunun dışında, ayrı ve çok düşük bir
# ihtimalle (her gün için "chance" alanındaki olasılıkla) kontrol edilir.
# Böylece diğer onlarca olayla eşit şansta seçilip sık sık tetiklenmezler.
RARE_EVENTS = [
    {
        "name": "Miras Kaldı",
        "type": "inheritance",
        "chance": 0.004,  # ortalama ~250 günde bir
        "min_amount": 500000,
        "max_amount": 1000000,
        "message_template": "Hiç tanımadığınız uzak bir akrabanızdan dev bir miras kaldı! Hesabınıza {amount} TL yatırıldı.",
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