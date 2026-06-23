# -*- coding: utf-8 -*-
"""
game_data.py
------------
Karaborsa Ticaret Simülasyonu için sabit oyun verilerini içerir:
- Ürün kategorileri ve ürün isimleri (genişletilmiş ürün havuzu)
- Her ürünün başlangıç / minimum / maksimum fiyat aralığı
- Rastgele küresel olaylar: fiyat olayları VE risk olayları (nakit/envanter kaybı-kazancı)

Bu modül tamamen veri tanımlarından oluşur, herhangi bir UI veya
mantık kodu barındırmaz; böylece kolayca test edilebilir ve
genişletilebilir (yeni ürün/olay eklemek tek satırlık bir iş olur).

ÖNEMLİ TASARIM NOTU (kullanıcı geri bildirimine göre güncellendi):
Dolar / Euro / Sterlin / Altın / Gümüş / Platin gibi "döviz ve değerli
metal" ürünleri, diğer ürünlerden (uyuşturucu, silah vb.) MEKANİK
OLARAK HİÇBİR FARKI yoktur: hepsi aynı şekilde TL ile alınıp satılır,
aynı şekilde fiyat dalgalanmasına ve olaylara tabidir. Cüzdan
göstergesinde artık özel olarak "X Dolar, Y Euro" gibi ayrı bir satır
YOKTUR; bu sadece envanterdeki normal bir ürün gibi listede görünür.
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
# min/max sınırları, fiyat dalgalanmalarının ve olay etkilerinin
# mantıksız (örn. negatif) değerlere gitmesini engeller.
# Not: Kripto varlıklar bilinçli olarak çok daha geniş bir min/max aralığına
# sahiptir; bu, gerçek hayattaki yüksek volatiliteyi ve dolayısıyla
# "yüksek risk / yüksek getiri" hissini simüle eder.
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

    # --- Döviz & Değerli Metaller (artık diğer ürünlerle TAMAMEN eşit muamele görür) ---
    "Dolar":          {"base_price": 33,    "min_price": 20,    "max_price": 60},
    "Euro":           {"base_price": 36,    "min_price": 22,    "max_price": 65},
    "Sterlin":        {"base_price": 42,    "min_price": 25,    "max_price": 75},
    "Altın":          {"base_price": 2400,  "min_price": 1500,  "max_price": 4000},
    "Gümüş":          {"base_price": 35,    "min_price": 20,    "max_price": 70},
    "Platin":         {"base_price": 1100,  "min_price": 700,   "max_price": 2200},

    # --- Kripto & Dijital Varlıklar (yüksek volatilite = yüksek risk/ödül) ---
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
# Rastgele küresel olaylar
# ---------------------------------------------------------------------------
# Her olayın bir "type" alanı vardır; main.py içindeki GameState.apply_event()
# bu tipe göre farklı bir etki uygular:
#
#   "price"        -> Belirtilen kategorideki TÜM ürünlerin fiyatı min_pct..max_pct
#                      aralığında rastgele bir yüzde kadar değişir (yüzde negatifse düşer).
#                      Etki büyüktür (%15-%80) ve günlük doğal dalgalanmanın (±%8)
#                      ÜZERİNE eklenir, böylece olayın etkisi her zaman net hissedilir.
#
#   "cash_gain"     -> Oyuncunun mevcut nakdinin min_pct..max_pct kadarı kazanç olarak eklenir.
#
#   "cash_loss"     -> Oyuncunun mevcut nakdinin min_pct..max_pct kadarı kaybedilir
#                      (RİSK: elinizdeki paradan olma ihtimali).
#
#   "inventory_loss"-> Belirtilen kategorideki envanterin min_pct..max_pct kadarı
#                      (adet bazında) müsadere edilir / kaybedilir (RİSK).
#
#   "raid_combo"    -> Aynı anda hem nakit hem de envanter kaybı yaşanır; en riskli olay tipi.
#
# message_template içindeki {pct}, {amount}, {count}, {category} alanları
# main.py tarafında gerçek/hesaplanan değerlerle doldurulur; böylece her olayın
# fiyatlara/cüzdana TAM OLARAK ne yaptığı ekran okuyucu ile açıkça duyurulur.
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

    # --- Fiyat olayları: Kripto (en oynak/volatil kategori) ---
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

    # --- Fiyat olayları: Kaçak Eşya & Elektronik ---
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

    # --- Nakit kazanç olayları (RİSK'in pozitif yüzü) ---
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

    # --- Nakit kaybı olayları (RİSK'in negatif yüzü) ---
    {
        "name": "Soygun",
        "type": "cash_loss",
        "min_pct": 0.10, "max_pct": 0.30,
        "message_template": "Soyuldunuz! Cüzdanınızdan {amount} TL çalındı.",
        "zero_message": "Soyulma girişimi oldu ama cebinizde para olmadığı için kayıp yaşamadınız.",
    },
    {
        "name": "Rüşvet Talebi",
        "type": "cash_loss",
        "min_pct": 0.05, "max_pct": 0.15,
        "message_template": "Yerel bir yetkili rüşvet istedi, {amount} TL ödemek zorunda kaldınız.",
        "zero_message": "Rüşvet istendi ama ödeyecek paranız olmadığı için sorunsuz geçtiniz.",
    },

    # --- Envanter müsadere olayları (mal kaybı riski) ---
    {
        "name": "Polis Baskını - Mal Müsadere",
        "type": "inventory_loss",
        "category": "Karanlık Maddeler",
        "min_pct": 0.30, "max_pct": 0.70,
        "message_template": "Polis baskınında {category} stoğunuzdan {count} adet ürüne el konuldu!",
        "zero_message": "Polis baskını oldu ama elinizde karanlık madde bulunmadığı için zarar görmediniz.",
    },
    {
        "name": "Silah Deposu Basıldı",
        "type": "inventory_loss",
        "category": "Mühimmat & Silahlar",
        "min_pct": 0.30, "max_pct": 0.60,
        "message_template": "Silah deponuz basıldı! {category} stoğunuzdan {count} adet ürün kayboldu.",
        "zero_message": "Bir baskın haberi geldi ama elinizde silah/mühimmat olmadığı için zarar görmediniz.",
    },

    # --- En riskli olaylar: hem nakit hem mal kaybı birlikte ---
    {
        "name": "Büyük Çete Operasyonu",
        "type": "raid_combo",
        "category": "Karanlık Maddeler",
        "cash_min_pct": 0.10, "cash_max_pct": 0.25,
        "inventory_min_pct": 0.40, "inventory_max_pct": 0.80,
        "message_template": "Büyük bir çete operasyonuna yakalandınız! {amount} TL ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Çete operasyonu haberleri geldi ama ne paranız ne de stoğunuz olduğu için etkilenmediniz.",
    },
    {
        "name": "Sınır Ötesi Yakalanma",
        "type": "raid_combo",
        "category": "Mühimmat & Silahlar",
        "cash_min_pct": 0.10, "cash_max_pct": 0.20,
        "inventory_min_pct": 0.30, "inventory_max_pct": 0.60,
        "message_template": "Sınırda yakalandınız! Ceza olarak {amount} TL ödediniz ve {category} stoğunuzdan {count} adet ürün kaybettiniz.",
        "zero_message": "Sınırda bir kontrol yapıldı ama üzerinizde para ya da mühimmat olmadığı için serbest bırakıldınız.",
    },
]


def get_flat_product_order():
    """
    Kategorilere göre gruplanmış ürünleri tek boyutlu (düz) bir liste olarak
    döndürür. wx.ListBox içindeki satır sırası ile bu liste her zaman
    bire bir eşleşmelidir; seçili satırdan ürün adına geri dönmek için kullanılır.
    """
    flat = []
    for names in PRODUCT_CATEGORIES.values():
        flat.extend(names)
    return flat
