"""
settings_manager.py
--------------------
Oyunun HESABA DEĞİL, bu CİHAZA özel ayarlarını appdata klasöründeki
settings.json dosyasında saklar (ör. ses seviyesi, günün mesajı).

save_manager ve ticket_manager ile AYNI klasörü paylaşır (normal modda
appdirs, taşınabilir modda oyunun yanındaki KaraborsaData - bkz.
app_paths). Bu yüzden buradaki dosya adı
save_manager._RESERVED_SAVE_FILENAMES listesine de eklenmiştir -
yoksa save_manager.list_saves() bu dosyayı sahte bir oyun kaydıymış
gibi listeye ekler.
"""

import os
import json
import app_paths


APP_NAME = app_paths.APP_NAME
APP_AUTHOR = app_paths.APP_AUTHOR
SETTINGS_FILENAME = "settings.json"

_DEFAULTS = {
    "daily_message_enabled": True,
    "music_volume": 0.5,
    "sfx_volume": 0.8,
    "typing_sound_enabled": True,
    "auto_update_check_enabled": True,
    "terms_accepted_version": "",
    "language": "",
}

_cache = None


def _settings_dir() -> str:
    # Taşınabilir/normal mod değişince yol da değişir; bu yüzden
    # modül yüklenirken değil, her kullanımda hesaplanır.
    return app_paths.user_data_dir(APP_NAME, APP_AUTHOR)


def _settings_path() -> str:
    return os.path.join(_settings_dir(), SETTINGS_FILENAME)


def reload_paths() -> None:
    """Mod değiştikten sonra önbelleği atar; sonraki okuma/yazma yeni
    konumu kullanır."""
    global _cache
    _cache = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    data = dict(_DEFAULTS)
    try:
        if os.path.exists(_settings_path()):
            with open(_settings_path(), "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            if isinstance(on_disk, dict):
                data.update(on_disk)
    except Exception as e:
        print(f"[Ayarlar] settings.json okunamadı, varsayılanlar kullanılıyor: {e}")

    _cache = data
    return _cache


def _save() -> None:
    try:
        os.makedirs(_settings_dir(), exist_ok=True)
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(_cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Ayarlar] settings.json yazılamadı: {e}")


def is_daily_message_enabled() -> bool:
    """False ise, oyun açılışında 'günün mesajı' kontrolü hiç
    yapılmaz - ne sesli okunur ne de pencere açılır."""
    return bool(_load().get("daily_message_enabled", True))


def set_daily_message_enabled(enabled: bool) -> None:
    data = _load()
    data["daily_message_enabled"] = bool(enabled)
    _save()


def get_music_volume() -> float:
    """AudioManager, her yeni örnek oluşturulduğunda (ana menü, oyun
    penceresi, ayarlar ekranı vb. - her biri kendi AudioManager()
    örneğini yaratıyor) başlangıç ses seviyesini buradan okur. Böylece
    ayarlar ekranında değiştirilen seviye, sonradan açılan oyun
    penceresine de yansır - aksi halde her yeni örnek varsayılan
    değere (0.5) sıfırlanırdı."""
    return float(_load().get("music_volume", 0.5))


def set_music_volume(volume: float) -> None:
    data = _load()
    data["music_volume"] = max(0.0, min(1.0, float(volume)))
    _save()


def get_sfx_volume() -> float:
    return float(_load().get("sfx_volume", 0.8))


def set_sfx_volume(volume: float) -> None:
    data = _load()
    data["sfx_volume"] = max(0.0, min(1.0, float(volume)))
    _save()


def is_typing_sound_enabled() -> bool:
    """False ise, metin giriş alanlarına (kullanıcı adı, şifre, bilet
    mesajı vb.) yazarken çalan tık sesi (typing.wav) tamamen susar."""
    return bool(_load().get("typing_sound_enabled", True))


def set_typing_sound_enabled(enabled: bool) -> None:
    data = _load()
    data["typing_sound_enabled"] = bool(enabled)
    _save()


def is_auto_update_check_enabled() -> bool:
    """False ise, oyun açılışında updater.check_for_update_async hiç
    çağrılmaz - internet bağlantısı olsa bile açılışta güncelleme
    kontrolü için istek atılmaz. Ayarlar ekranındaki 'Güncellemeleri
    Kontrol Et' butonu bundan ETKİLENMEZ - o her zaman elle
    tetiklenebilir."""
    return bool(_load().get("auto_update_check_enabled", True))


def set_auto_update_check_enabled(enabled: bool) -> None:
    data = _load()
    data["auto_update_check_enabled"] = bool(enabled)
    _save()


def is_terms_accepted(current_version: str) -> bool:
    """Gizlilik politikası/kullanım şartları bu CİHAZDA daha önce
    kabul edilmiş mi (hesaptan bağımsız). current_version, main.py
    içindeki TERMS_VERSION sabitidir - metinler ileride değişirse bu
    sabiti artırmak yeterlidir, kullanıcı bir dahaki açılışta yeniden
    onay ekranını görür (eski kabulü otomatik geçersiz sayılır)."""
    return _load().get("terms_accepted_version", "") == current_version


def set_terms_accepted(version: str) -> None:
    data = _load()
    data["terms_accepted_version"] = version
    _save()


def get_language() -> str:
    """Oyuncunun seçtiği arayüz dili ('' = henüz seçilmedi). i18n bunu
    _language.json'a EK olarak burada da saklar; biri okunamazsa diğeri
    devreye girer."""
    return str(_load().get("language", "") or "")


def set_language(code: str) -> None:
    data = _load()
    data["language"] = code
    _save()
