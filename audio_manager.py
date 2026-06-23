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

    def __init__(self, initial_music_volume: float = 0.5, initial_sfx_volume: float = 0.8):
        self.music_volume = initial_music_volume
        self.sfx_volume = initial_sfx_volume
        self.available = False

        if _PYGAME_AVAILABLE:
            try:
                pygame.mixer.init()
                self.available = True
            except Exception:
                self.available = False

    def play_music(self, path: str, loop: bool = True) -> None:
        """Arka plan müziğini (örn. game_music.mp3) döngülü olarak çalar."""
        if not self.available:
            return
        if not os.path.exists(path):
            print(f"[Ses Uyarısı] Müzik dosyası bulunamadı: {path}")
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(self.music_volume)
            pygame.mixer.music.play(-1 if loop else 0)
        except Exception as exc:
            print(f"[Ses Hatası] Müzik çalınamadı: {exc}")

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
            pygame.mixer.music.set_volume(self.music_volume)
        return self.music_volume

    def volume_down(self, step: float = 0.1) -> float:
        """Müzik sesini bir kademe düşürür, yeni seviyeyi döndürür."""
        self.music_volume = max(0.0, round(self.music_volume - step, 2))
        if self.available:
            pygame.mixer.music.set_volume(self.music_volume)
        return self.music_volume
