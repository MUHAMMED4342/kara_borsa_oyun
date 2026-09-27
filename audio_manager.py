
"""
audio_manager.py
-----------------
Arka plan müziği ve efekt seslerini yöneten modül.

pygame.mixer kullanılır çünkü:
- mp3 ve ogg formatlarını platform bağımsız şekilde çalabilir,
- arka plan müziğini döngüye (loop) almak tek satırlık bir işlemdir,
- ses seviyesi kontrolü (Page Up / Page Down kısayolları için) basittir.

Ses dosyaları bulunamazsa veya pygame mixer başlatılamazsa
(uygun ses kartı/driver yoksa) modül sessizce devre dışı kalır;
oyun mantığı bundan etkilenmez.
"""

import math
import os

import settings_manager

try:
    import pygame

    _PYGAME_AVAILABLE = True
except Exception:
    _PYGAME_AVAILABLE = False

try:
    import numpy as np

    if _PYGAME_AVAILABLE:
        import pygame.sndarray  # noqa: F401  (sadece kullanılabilirliğini test etmek için)
    _NUMPY_AVAILABLE = True
except Exception:
    _NUMPY_AVAILABLE = False


class AudioManager:
    """Arka plan müziği ve kısa efekt seslerini yöneten sınıf."""

    # İnsan kafası için tipik maksimum kulaklar arası ZAMAN farkı
    # (Interaural Time Difference). Gerçek yön algımızın büyük kısmı
    # -sadece ses seviyesi farkı değil- BU zaman farkından gelir; bu
    # yüzden "kafada dönüyor" hissi için bunu simüle etmek şart.
    HEAD_ITD_MAX_SECONDS = 0.00066

    _mixer_initialized = False

    def __init__(self, initial_music_volume: float = None, initial_sfx_volume: float = None):
        # Varsayılan olarak None bırakılıyor ki her yeni AudioManager()
        # örneği (ana menü, oyun penceresi, ayarlar ekranı - her biri
        # kendi örneğini yaratıyor) settings_manager'daki KAYITLI
        # seviyeden başlasın. Sabit bir varsayılan (0.5/0.8) kullanılsa,
        # ayarlar ekranında yapılan bir değişiklik bir sonraki
        # AudioManager örneğinde (ör. oyun penceresi açılınca) kaybolurdu.
        if initial_music_volume is None:
            initial_music_volume = settings_manager.get_music_volume()
        if initial_sfx_volume is None:
            initial_sfx_volume = settings_manager.get_sfx_volume()

        self.music_volume = initial_music_volume
        self.sfx_volume = initial_sfx_volume
        self.available = False
        self.music_playing = False
        self.current_music = None
        # play_rotating_spin_sound() içinde aynı dosyayı (örn.
        # cark.mp3) her çevirişte yeniden diskten okuyup mono'ya
        # indirmemek için önbelleğe alıyoruz: path -> (mono_samples, sr)
        self._mono_sample_cache = {}

        if _PYGAME_AVAILABLE:
            if AudioManager._mixer_initialized:
                
                
                
                self.available = True
            else:
                try:
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                    AudioManager._mixer_initialized = True
                    self.available = True
                    print("[Ses] Pygame mixer başlatıldı.")
                    if _NUMPY_AVAILABLE:
                        print("[Ses] numpy bulundu - 3D binaural döndürme efekti AKTİF.")
                    else:
                        print(
                            "[Ses Uyarısı] numpy bulunamadı - 3D binaural döndürme "
                            "efekti KAPALI, basit sol/sağ pan'a düşülecek. "
                            "Kurmak için: pip install numpy"
                        )
                except Exception as e:
                    print(f"[Ses Uyarısı] Mixer başlatılamadı: {e}")
                    self.available = False

    def play_music(self, path: str, loop: bool = True) -> None:
        """Arka plan müziğini (örn. game_music.mp3) döngülü olarak çalar."""
        if not self.available:
            return
        
        if not os.path.exists(path):
            print(f"[Ses Uyarısı] Müzik dosyası bulunamadı: {path}")
            return
        
        try:
            
            if self.current_music == path and self.music_playing:
                return
                
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1 if loop else 0)
            self.music_playing = True
            self.current_music = path
            print(f"[Ses] Müzik başlatıldı: {path}")
        except Exception as exc:
            print(f"[Ses Hatası] Müzik çalınamadı: {exc}")
            self.music_playing = False

    def stop_music(self) -> None:
        """Arka plan müziğini durdurur."""
        if not self.available:
            return
        try:
            pygame.mixer.music.stop()
            self.music_playing = False
            self.current_music = None
        except Exception as exc:
            print(f"[Ses Hatası] Müzik durdurulamadı: {exc}")

    def pause_music(self) -> None:
        """Müziği duraklatır."""
        if not self.available or not self.music_playing:
            return
        try:
            pygame.mixer.music.pause()
        except Exception as exc:
            print(f"[Ses Hatası] Müzik duraklatılamadı: {exc}")

    def unpause_music(self) -> None:
        """Duraklatılmış müziği devam ettirir."""
        if not self.available:
            return
        try:
            pygame.mixer.music.unpause()
        except Exception as exc:
            print(f"[Ses Hatası] Müzik devam ettirilemedi: {exc}")

    def play_sound(self, path: str) -> None:
        """Kısa bir efekt sesini (örn. para.mp3, buy.ogg) bir defa çalar."""
        if not self.available:
            return
        
        if not os.path.exists(path):
            print(f"[Ses Uyarısı] Efekt dosyası bulunamadı: {path}")
            return
        
        try:
            sound = pygame.mixer.Sound(path)
            sound.set_volume(self.sfx_volume)
            sound.play()
        except Exception as exc:
            print(f"[Ses Hatası] Efekt çalınamadı: {exc}")

    def play_panned_sound(self, path: str):
        """Kısa bir efekt sesini, çalarken stereo pan (sol/sağ payı)
        canlı olarak değiştirilebilecek ÖZEL bir kanalda çalar - rulet
        çarkı gibi 'dönüyor' hissi verilmesi gereken efektler için.

        Normal play_sound() pygame'in otomatik/geçici bir kanalını
        kullanır ve sonradan o kanala erişip pan ayarlamak mümkün
        olmayabilir; bu yüzden burada sound.play()'in döndürdüğü
        Channel nesnesini SAKLAYIP çağırana geri veriyoruz.

        (channel, süre_saniye) döner. Ses çalınamazsa (mixer kapalı,
        dosya yok, vb.) (None, 0.0) döner - çağıran taraf bu durumda
        normal play_sound() + sabit süre bekleme mantığına dönmelidir.
        """
        if not self.available:
            return None, 0.0

        if not os.path.exists(path):
            print(f"[Ses Uyarısı] Efekt dosyası bulunamadı: {path}")
            return None, 0.0

        try:
            sound = pygame.mixer.Sound(path)
            length = sound.get_length()
            channel = sound.play()
            if channel is not None:
                channel.set_volume(self.sfx_volume, self.sfx_volume)
            return channel, length
        except Exception as exc:
            print(f"[Ses Hatası] Döner efekt çalınamadı: {exc}")
            return None, 0.0

    def set_channel_pan(self, channel, pan: float) -> None:
        """Verilen pygame kanalının stereo pan değerini ayarlar.

        pan -1.0 (tam sol) ile +1.0 (tam sağ) arasındadır, 0.0 tam
        ortadır. 'Sabit güç' (constant-power / equal-power) panning
        formülü kullanılır: sol ve sağ kanal seviyeleri cos/sin ile
        hesaplanır ki ses ortadan kenara kayarken toplam algılanan
        yüksekliği düşüp 'kısılmış' gibi hissettirmesin - kulaklıkta
        gerçekten SOLDAN SAĞA (veya tam tersi) hareket ediyormuş gibi
        duyulsun.

        NOT: Bu, yalnızca sol<->sağ SEVİYE farkı uygular (ILD). Gerçek
        bir 'kafanın etrafında dönüyor' hissi için play_rotating_spin_sound()
        kullanın - o hem seviye hem de ZAMAN farkını (ITD) uygulayarak
        çok daha ikna edici bir 3D/binaural etki üretir. Bu metod yalnızca
        numpy yokken devreye giren basit bir yedek (fallback) yoldur."""
        if channel is None or not self.available:
            return
        pan = max(-1.0, min(1.0, pan))
        angle = (pan + 1.0) * (math.pi / 4.0)  # -1..1 -> 0..pi/2
        left = self.sfx_volume * math.cos(angle)
        right = self.sfx_volume * math.sin(angle)
        try:
            channel.set_volume(left, right)
        except Exception:
            pass

    def _load_mono_samples(self, path: str):
        """Bir efekt dosyasını (mixer'ın çalışma formatına - 44100Hz,
        16-bit - göre) diskten okuyup MONO (tek kanal, float32) örnek
        dizisine çevirir; hem orijinal (net/parlak) hali hem de
        "arkadan geliyormuş gibi" boğuk/kısık bir kutu-filtre (box
        low-pass) uygulanmış halini önbelleğe alır.

        Kaynak zaten mono ise olduğu gibi, stereo ise iki kanalın
        ortalaması alınarak kullanılır - çünkü tek bir 'nokta ses
        kaynağı'nı istediğimiz yöne konumlandırmak istiyoruz, orijinal
        stereo görüntüsünü değil."""
        if path in self._mono_sample_cache:
            return self._mono_sample_cache[path]

        raw_sound = pygame.mixer.Sound(path)
        raw_bytes = raw_sound.get_raw()
        init = pygame.mixer.get_init()
        sample_rate = init[0] if init else 44100
        channels = init[2] if init else 2

        arr = np.frombuffer(raw_bytes, dtype=np.int16)
        if channels == 2:
            arr = arr.reshape(-1, 2).astype(np.float32)
            mono = arr.mean(axis=1)
        else:
            mono = arr.astype(np.float32)

        # "Arkadan geliyor" hissi için basit ama GERÇEK bir alçak-geçiren
        # (low-pass) filtre: birkaç düzine örnekten oluşan bir kutu
        # (moving-average) penceresiyle konvolüsyon - tam bir HRTF kadar
        # gerçekçi değil ama insan kulağının, arkadan gelen seslerin
        # tiz frekanslarının kulak kepçesi tarafından süzülmesiyle
        # duyduğu 'boğuklaşma'yı taklit ediyor.
        window = max(1, int(sample_rate / 1400))
        if window > 1:
            kernel = np.ones(window, dtype=np.float32) / window
            muffled = np.convolve(mono, kernel, mode="same").astype(np.float32)
        else:
            muffled = mono.copy()

        self._mono_sample_cache[path] = (mono, muffled, sample_rate)
        return mono, muffled, sample_rate

    def create_rotating_spin_sound(self, path: str, duration: float, initial_speed_rps: float):
        """cark.mp3 gibi bir efekti, kulaklık takan birinin kafasının
        ETRAFINDA GERÇEKTEN dönüyormuş hissi verecek şekilde yeniden
        işleyip yeni bir pygame.mixer.Sound olarak döndürür.

        initial_speed_rps: dönüşün BAŞLANGIÇTAKİ hızı (saniyede tam
        tur sayısı). Gerçek bir çark/topaç gibi SABİT bir yavaşlama
        (friksiyon) ile, tam olarak `duration` saniyenin sonunda hızı
        sıfıra düşecek şekilde modellenir: v(t) = v0 * (1 - t/T).
        Bu kinematik model önemlidir çünkü:
        - Kulak, saniyede ~1 turu geçen dönüşleri YÖN olarak değil,
          bir titreşim/tremolo gibi algılar - bu yüzden v0'ı kasıtlı
          olarak düşük (insan kafası döngü algısı için makul) tutuyoruz,
        - Gerçekçi bir rulet çarkı da sabit ivmeyle değil, sürtünmeyle
          YAVAŞ YAVAŞ durur; bu da tam olarak bunu üretir.

        Üç ayrı binaural ipucu birlikte uygulanır:
        - ITD (Interaural Time Difference): kulaklar arası ZAMAN farkı
          (~0-0.66ms) - insan yön algısının ASIL kaynağı,
        - ILD (Interaural Level Difference): kulaklar arası SES
          SEVİYESİ farkı (sabit güç panning),
        - Basit bir low-pass "boğukluk" ipucu: ses arkadaysa net/parlak
          değil, hafif boğuk sese doğru karıştırılır (gerçek kulakların
          arkadan gelen tiz sesleri süzmesini taklit eder) - bu, SADECE
          ses seviyesi ile yapılamayan ön/arka ayrımını sağlar.

        numpy/pygame.sndarray yoksa veya işlem sırasında bir hata
        olursa None döner - çağıran taraf bu durumda play_panned_sound()
        ile basit (canlı güncellenen) sol/sağ pan'a geri dönmelidir."""
        if not self.available or not _NUMPY_AVAILABLE:
            return None
        if not os.path.exists(path):
            print(f"[Ses Uyarısı] Efekt dosyası bulunamadı: {path}")
            return None
        if duration <= 0:
            return None

        try:
            mono, muffled, sample_rate = self._load_mono_samples(path)
            n = len(mono)
            if n == 0:
                return None

            t = np.arange(n, dtype=np.float32) / sample_rate
            t = np.clip(t, 0.0, duration)

            # Sabit yavaşlama (friksiyon) kinematiği: v(t) = v0*(1 - t/T)
            # theta(t) = v0*t - v0*t^2/(2T)  [tam tur cinsinden]
            v0 = initial_speed_rps
            rotations = v0 * t - (v0 * t * t) / (2.0 * duration)
            theta = rotations * 2.0 * np.pi
            total_rotations = v0 * duration / 2.0  # sadece bilgi/log amaçlı

            # pan: -1 (tam sol) .. +1 (tam sağ) - sesin o anki yatay
            # (azimut) konumunu, kulaklar arası eksene göre verir.
            pan = np.sin(theta)
            # front_back: +1 tam ÖN, -1 tam ARKA.
            front_back = np.cos(theta)

            # --- ILD: sabit güç (constant power) genlik panı ---
            pan_angle = (pan + 1.0) * (np.pi / 4.0)
            left_gain = np.cos(pan_angle)
            right_gain = np.sin(pan_angle)

            # --- Ön/arka boğukluk ipucu: net <-> boğuk sesi karıştır ---
            # back_amount: 0 (tam ön) .. 1 (tam arka)
            back_amount = np.clip(-front_back, 0.0, 1.0)
            source = mono * (1.0 - back_amount) + muffled * back_amount
            # Ekstra olarak arkadayken toplam sesi de bir miktar kısıyoruz
            # (mesafe/boğukluk hissini pekiştirmek için).
            distance_cue = 1.0 - 0.30 * back_amount

            left_gain = left_gain * distance_cue
            right_gain = right_gain * distance_cue

            # --- ITD: kulaklar arası ZAMAN farkı (örnek cinsinden) ---
            max_itd_samples = self.HEAD_ITD_MAX_SECONDS * sample_rate
            itd = pan * max_itd_samples

            idx = np.arange(n, dtype=np.float32)
            # pan > 0 (ses sağda) -> sol kulağa GEÇ ulaşır -> sol kanalı geciktir.
            left_src_idx = idx - np.clip(itd, 0.0, None)
            # pan < 0 (ses solda) -> sağ kulağa GEÇ ulaşır -> sağ kanalı geciktir.
            right_src_idx = idx - np.clip(-itd, 0.0, None)

            # Kesirli (fractional) gecikme - lineer interpolasyonla.
            left = np.interp(left_src_idx, idx, source) * left_gain
            right = np.interp(right_src_idx, idx, source) * right_gain

            left = np.clip(left * self.sfx_volume, -32767, 32767).astype(np.int16)
            right = np.clip(right * self.sfx_volume, -32767, 32767).astype(np.int16)

            stereo = np.empty((n, 2), dtype=np.int16)
            stereo[:, 0] = left
            stereo[:, 1] = right

            print(
                f"[Ses] 3D binaural döndürme uygulandı: başlangıç hızı "
                f"{v0:.2f} tur/sn, toplam ~{total_rotations:.1f} tur, "
                f"süre {duration:.2f} sn."
            )
            return pygame.sndarray.make_sound(stereo)
        except Exception as exc:
            print(f"[Ses Hatası] 3D döndürme efekti oluşturulamadı: {exc}")
            return None

    def play_rotating_spin_sound(self, path: str, duration: float, initial_speed_rps: float):
        """create_rotating_spin_sound() ile gerçek bir 3D/binaural
        döndürme (ITD + ILD + ön/arka boğukluk) uygulanmış efekti
        üretir ve hemen çalar.

        Bu, ses ÇALINIRKEN pan'ı canlı olarak güncellemeye gerek
        bırakmaz - dönüş zaten ses dosyasının içine baştan işlenmiştir;
        bu yüzden dönen bir kanal (Channel) ve GERÇEK süresini döner.

        (channel, süre_saniye) döner. Üretim başarısız olursa
        (None, 0.0) döner - çağıran taraf play_panned_sound() ile basit
        canlı pan güncellemesine geri dönmelidir."""
        if not self.available:
            return None, 0.0

        sound = self.create_rotating_spin_sound(path, duration, initial_speed_rps)
        if sound is None:
            return None, 0.0

        try:
            channel = sound.play()
            return channel, sound.get_length()
        except Exception as exc:
            print(f"[Ses Hatası] 3D döner efekt çalınamadı: {exc}")
            return None, 0.0

    def volume_up(self, step: float = 0.1) -> float:
        """Müzik sesini bir kademe yükseltir, yeni seviyeyi döndürür
        ve kalıcı olması için diske de yazar."""
        self.music_volume = min(1.0, round(self.music_volume + step, 2))
        if self.available:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
        settings_manager.set_music_volume(self.music_volume)
        return self.music_volume

    def volume_down(self, step: float = 0.1) -> float:
        """Müzik sesini bir kademe düşürür, yeni seviyeyi döndürür
        ve kalıcı olması için diske de yazar."""
        self.music_volume = max(0.0, round(self.music_volume - step, 2))
        if self.available:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
        settings_manager.set_music_volume(self.music_volume)
        return self.music_volume

    def sfx_volume_up(self, step: float = 0.1) -> float:
        """Efekt (kısa ses) seviyesini bir kademe yükseltir, yeni
        seviyeyi döndürür ve diske yazar. play_sound() her efekti
        ANLIK olarak self.sfx_volume ile çaldığı için (pygame.mixer'da
        efektler için tekil/kalıcı bir kanal olmadığından), burada
        şu an çalmakta olan bir sesi güncellemeye gerek yok - bir
        sonraki play_sound() çağrısı yeni seviyeyi otomatik kullanır."""
        self.sfx_volume = min(1.0, round(self.sfx_volume + step, 2))
        settings_manager.set_sfx_volume(self.sfx_volume)
        return self.sfx_volume

    def sfx_volume_down(self, step: float = 0.1) -> float:
        """sfx_volume_up ile aynı mantık, ters yönde."""
        self.sfx_volume = max(0.0, round(self.sfx_volume - step, 2))
        settings_manager.set_sfx_volume(self.sfx_volume)
        return self.sfx_volume

    def set_music_volume(self, volume: float) -> None:
        """Müzik ses seviyesini doğrudan ayarlar (sürgü/slider için -
        volume_up/volume_down'ın aksine göreli değil, mutlak değer
        alır) ve kalıcı olması için diske de yazar."""
        self.music_volume = max(0.0, min(1.0, volume))
        if self.available:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
        settings_manager.set_music_volume(self.music_volume)

    def set_sfx_volume(self, volume: float) -> None:
        """Efekt ses seviyesini doğrudan ayarlar (ve diske yazar)."""
        self.sfx_volume = max(0.0, min(1.0, volume))
        settings_manager.set_sfx_volume(self.sfx_volume)