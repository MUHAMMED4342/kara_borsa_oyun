# Karaborsa Ticaret Simülasyonu (Erişilebilir wxPython Oyunu)

Görme engelli oyuncuların ekran okuyucu (NVDA, JAWS vb.) ile rahatça
oynayabileceği, metin tabanlı bir karaborsa ticaret simülasyonu.

## Kurulum

```bash
pip install -r requirements.txt
```

> **Not:** `wxPython` bazı Linux dağıtımlarında kaynak koddan derlenir ve
> bunun için GTK geliştirme paketlerine ihtiyaç duyar. Eğer kurulum
> başarısız olursa önce şunu deneyin:
>
> ```bash
> sudo apt-get install libgtk-3-dev   # Debian/Ubuntu
> ```
>
> Windows ve macOS'ta genellikle önceden derlenmiş "wheel" dosyaları
> indirildiği için ek bir işlem gerekmez.

## Çalıştırma

```bash
python main.py
```

Ses dosyalarını `sounds/` klasörüne koyun (bkz. `sounds/NEREYE_KOYMALI.txt`):
- `game_music.mp3` — arka plan müziği (döngülü)
- `para.mp3` — satın alma efekti
- `buy.ogg` — satış efekti

Dosyalar eksikse oyun çökmez, sadece sessiz kalır.

## Dosya Yapısı

| Dosya | Görev |
|---|---|
| `main.py` | wxPython arayüzü + `GameState` oyun mantığı |
| `game_data.py` | Ürünler, kategoriler, rastgele olaylar (sabit veri) |
| `accessibility_helper.py` | `accessible_output2` için güvenli sarmalayıcı (`speak()`) |
| `audio_manager.py` | `pygame.mixer` ile müzik/efekt yönetimi |

## Klavye Kısayolları

| Tuş | İşlev |
|---|---|
| `Tab` | Ürün Listesi → Satın Al → Sat → Gün Atla sırasıyla gezinme |
| `↑ / ↓` | Ürün listesinde gezinme (seçili ürün otomatik seslendirilir) |
| `C` | Cüzdan + detaylı envanter özetini seslendirir |
| `Page Up` | Arka plan müziğinin sesini artırır |
| `Page Down` | Arka plan müziğinin sesini azaltır |

## Oyun Mekaniği Özeti

- Oyuncu 5.000 TL nakit ile başlar.
- Her ürün TL üzerinden alınıp satılır; Dolar/Euro/Altın da bu mekanizmaya
  dahildir (örn. "Dolar" satın almak, cüzdandaki Dolar miktarını artırır).
- "Gün Atla" butonu basıldığında:
  1. Tüm ürün fiyatları ±%15 aralığında rastgele dalgalanır.
  2. %30 ihtimalle 1-3 rastgele küresel olay tetiklenir (Ekonomik Kriz,
     Polis Baskını, Sınır Kapılarının Kapanması vb.), bu olaylar ilgili
     ürün kategorisinin fiyatını dinamik olarak artırır/azaltır.
  3. Tüm sonuçlar ekran okuyucu ile özetlenerek duyurulur.

## Genişletme Noktaları

- Yeni ürün eklemek: `game_data.py` → `PRODUCTS` ve `PRODUCT_CATEGORIES`
- Yeni rastgele olay eklemek: `game_data.py` → `EVENTS` listesine bir
  sözlük eklemek yeterli (name, category, effect_pct, description).
- `GameState` sınıfı UI'dan tamamen bağımsızdır; birim testleri
  `import main` edip `wx` modülünü stub'layarak (veya `unittest.mock`
  ile) UI'sız çalıştırılabilir.
