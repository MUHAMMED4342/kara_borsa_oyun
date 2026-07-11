# Karaborsa Ticaret Simülasyonu — Proje Rehberi

Bu dosya, projeye AI (Claude vb.) ile çalışırken **hangi durumda hangi dosyayı
yüklemeniz/güncellemeniz gerektiğini** hatırlamanız için hazırlandı.

## 1. Dosya Yapısı ve Görevleri

| Dosya | Görevi |
|---|---|
| `main.py` | Giriş noktası. `MainFrame` (ana oyun penceresi), `App` sınıfı, gün atlama, klavye kısayolları (F1–F6, C/D/E), polis/hapis akışı. |
| `game_state.py` | `GameState` sınıfı: nakit, envanter, kredi, arsa, aklama, polis riski gibi tüm oyun **mantığı ve hesaplamaları**. Ekranla (wx) neredeyse ilgisi yok. |
| `dialogs.py` | Tüm pencereler: Ana Menü, Arsa Yönetimi, Kayıt Yükle, Şirket, Aklama, Kredi, Bankacılık, Hapis dialogları. Buton/tuş davranışları ve ses tetikleme burada. |
| `game_data.py`* | Sabit oyun verileri: `PRODUCTS`, `EVENTS`, `LAND_TYPES`, `COMPANY_TYPES`, `CREDIT_TIERS` vb. |
| `accessibility_helper.py`* | `speak()` fonksiyonu — ekran okuyucuya (SAPI5/NVDA/JAWS) metin gönderir. |
| `audio_manager.py`* | `AudioManager` sınıfı — müzik/efekt çalma, ses seviyesi. |
| `save_manager.py`* | `save_game`, `load_game`, `list_saves`, `delete_save` — kayıt dosyası okuma/yazma. |
| `updater.py`* | Oyun içi otomatik güncelleme kontrolü (`check_for_update_async`, `apply_pending_update_if_ready`). |
| `updater_app.py`* | Ayrı, gömülü çalışan **yardımcı güncelleyici** programın kaynak kodu (`KaraborsaGuncelleyici.exe` bundan derlenir). |
| `build.spec` | Ana oyunu (`KaraborsaSimulasyonu.exe`) PyInstaller ile tek-dosya olarak derleyen betik. |
| `build_updater.spec`* | Yardımcı güncelleyiciyi (`KaraborsaGuncelleyici.exe`) derleyen betik. |
| `build_all.bat` | İki spec'i doğru sırayla çalıştıran toplu Windows derleme betiği. |
| `help.html` | Oyun içi yardım sayfası (yoksa `game_state.py` içindeki `create_help_file` otomatik üretir). |
| `sounds/` | Ses/müzik dosyaları klasörü. |

`*` işaretli dosyalar henüz benimle paylaşılmadı — içeriklerini bilmiyorum,
sadece diğer dosyalardaki `import` satırlarından ne işe yaradıklarını
çıkarabiliyorum. Bunlarla ilgili bir sorun/istek geldiğinde **o dosyayı da
yüklemeniz gerekir**, yoksa körlemesine tahmin ederim.

## 2. Hangi Durumda Hangi Dosyayı Yüklemeliyim?

| Senaryo / Şikayet | Yüklenecek Dosya(lar) |
|---|---|
| Menüde buton/tuş çalışmıyor, dialog penceresi (Arsa, Kredi, Banka, Şirket, Aklama, Hapis, Kayıt Yükle, Ana Menü) hatalı davranıyor | `dialogs.py` |
| Para/kredi/faiz/polis riski/arsa fiyatı/envanter hesabı yanlış | `game_state.py` |
| Ana pencere, gün atlama, klavye kısayolları (F1–F6, C/D/E), oyunu başlatma/kapatma | `main.py` |
| Ürün, olay, şirket tipi, arsa tipi, kredi katmanı gibi **sabit veriler** yanlış/eksik | `game_data.py` |
| Ekran okuyucu hiç konuşmuyor / yanlış konuşuyor | `accessibility_helper.py` |
| Ses/müzik çalmıyor, kesiliyor, ses seviyesi çalışmıyor | `audio_manager.py` + ilgili sesi çağıran dosya (genelde `dialogs.py` veya `main.py`) |
| Kayıt yükleme/kaydetme, kayıt silme sorunları | `save_manager.py` |
| Oyun içi otomatik güncelleme kontrolü çalışmıyor | `updater.py` |
| Gömülü güncelleyici exe'nin kendi davranışı (indirme, uygulama) | `updater_app.py`, `build_updater.spec` |
| `.exe` derlenmiyor / PyInstaller hatası | `build.spec`, `build_all.bat` — **ve hatanın tam metni** |
| İki adımlı derleme sırası karışıyor | `build_all.bat`, `build.spec`, `build_updater.spec` |
| "Programı çalıştırınca hata alıyorum" (traceback var) | Traceback'in **en altında gösterdiği dosya** — hata mesajını tam kopyalayıp yapıştırın, hangi dosya olduğunu oradan söyleyebilirim |

**Altın kural:** Elinizde bir hata mesajı / traceback varsa, önce onu tam
olarak yapıştırın. Python traceback'i zaten "şu dosyanın şu satırında hata
oluştu" der — hangi dosyayı yükleyeceğinizi orası netleştirir.

## 3. Bağımlılık Haritası (kim kimi import ediyor)

```
main.py
 ├── game_state.py
 │     ├── game_data.py
 │     └── accessibility_helper.py
 ├── dialogs.py
 │     ├── game_state.py
 │     ├── game_data.py
 │     ├── accessibility_helper.py
 │     ├── audio_manager.py
 │     └── save_manager.py
 ├── game_data.py
 ├── accessibility_helper.py
 ├── audio_manager.py
 ├── save_manager.py
 └── updater.py
```

Bir dosyada değişiklik yaptığınızda, o dosyayı import eden üstteki dosyaları
**yeniden yüklemenize gerek yok** — sadece değişen dosyanın kendisini
göndermeniz yeterli, ben zaten önceki konuşmadan diğerlerinin son halini
hatırlıyorum (hafıza açıksa) ya da siz proje klasörünüzde zaten güncel
tutuyorsunuzdur.

## 4. Pratik İpucu

Yeni bir konuşma başlatıyorsanız ve AI'nın önceki değişiklikleri
hatırlamasını bekleyemiyorsanız, en azından şunları birlikte yükleyin:
- Şikayetin ilgili olduğu dosya (yukarıdaki tablo)
- Varsa tam hata mesajı / traceback
- Kısa bir "şu an ne bekliyorum, ne oluyor" açıklaması

Bu üçü genelde tek mesajda sorunu tam teşhis etmek için yeterli olur.
