# -*- coding: utf-8 -*-
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

import os

try:
    import pygame

    _PYGAME_AVAILABLE = True
except Exception:
    _PYGAME_AVAILABLE = False


class AudioManager:
    """Arka plan müziği ve kısa efekt seslerini yöneten sınıf."""

    # Process genelinde TEK bir global pygame.mixer kaynağı var.
    # Birden fazla AudioManager() oluşturulduğunda (her dialog kendi
    # AudioManager'ını yaratıyor) pygame.mixer.init()'in tekrar tekrar
    # çağrılması, özellikle Windows ses sürücülerinde (WASAPI/DirectSound)
    # cihazın arka planda yeniden kurulmasına (teardown/rebuild) yol açıp
    # ana thread'i birkaç saniye bloke edebiliyor. Bu yüzden init'i
    # sınıf seviyesinde bir bayrakla SADECE BİR KEZ çalıştırıyoruz.
    _mixer_initialized = False

    def __init__(self, initial_music_volume: float = 0.5, initial_sfx_volume: float = 0.8):
        self.music_volume = initial_music_volume
        self.sfx_volume = initial_sfx_volume
        self.available = False
        self.music_playing = False
        self.current_music = None

        if _PYGAME_AVAILABLE:
            if AudioManager._mixer_initialized:
                # Mixer zaten başka bir AudioManager örneği tarafından
                # başlatıldı; tekrar init etmeden mevcut global kaynağı
                # kullan.
                self.available = True
            else:
                try:
                    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                    AudioManager._mixer_initialized = True
                    self.available = True
                    print("[Ses] Pygame mixer başlatıldı.")
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
            # Eğer aynı müzik çalıyorsa tekrar yükleme
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

    def volume_up(self, step: float = 0.1) -> float:
        """Müzik sesini bir kademe yükseltir, yeni seviyeyi döndürür."""
        self.music_volume = min(1.0, round(self.music_volume + step, 2))
        if self.available:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
        return self.music_volume

    def volume_down(self, step: float = 0.1) -> float:
        """Müzik sesini bir kademe düşürür, yeni seviyeyi döndürür."""
        self.music_volume = max(0.0, round(self.music_volume - step, 2))
        if self.available:
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
        return self.music_volume

    def set_sfx_volume(self, volume: float) -> None:
        """Efekt ses seviyesini ayarlar."""
        self.sfx_volume = max(0.0, min(1.0, volume))