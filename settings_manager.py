"""
settings_manager.py
--------------------
Oyunun HESABA DEĞİL, bu CİHAZA özel ayarlarını appdata klasöründeki
settings.json dosyasında saklar (ör. buluta yedeklemeyi bu cihazda
kapatmak - hesap başka bir cihazda hâlâ yedeklenebilir).

save_manager, auth_manager ve ticket_manager ile AYNI appdirs
klasörünü paylaşır. Bu yüzden buradaki dosya adı
save_manager._RESERVED_SAVE_FILENAMES listesine de eklenmiştir -
yoksa save_manager.list_saves() bu dosyayı sahte bir oyun kaydıymış
gibi listeye ekler.
"""

import os
import json
import appdirs


APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
SETTINGS_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)
SETTINGS_FILENAME = "settings.json"
SETTINGS_PATH = os.path.join(SETTINGS_DIR, SETTINGS_FILENAME)

_DEFAULTS = {
    "cloud_backup_enabled": True,
    "daily_message_enabled": True,
    "music_volume": 0.5,
    "sfx_volume": 0.8,
    "typing_sound_enabled": True,
    "auto_update_check_enabled": True,
    "terms_accepted_version": "",
}

_cache = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    data = dict(_DEFAULTS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                on_disk = json.load(f)
            if isinstance(on_disk, dict):
                data.update(on_disk)
    except Exception as e:
        print(f"[Ayarlar] settings.json okunamadı, varsayılanlar kullanılıyor: {e}")

    _cache = data
    return _cache


def _save() -> None:
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Ayarlar] settings.json yazılamadı: {e}")


def is_cloud_backup_enabled() -> bool:
    """False ise, bu cihazda oyun kapatılırken/otomatik kayıtta
    buluta (PocketBase) SON HALİ gönderme adımı tamamen atlanır.
    Yerel diske kayıt (save_game) bundan ETKİLENMEZ - her zaman
    yapılır, sadece ağ üzerinden gönderim kapanır."""
    return bool(_load().get("cloud_backup_enabled", True))


def set_cloud_backup_enabled(enabled: bool) -> None:
    data = _load()
    data["cloud_backup_enabled"] = bool(enabled)
    _save()


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
