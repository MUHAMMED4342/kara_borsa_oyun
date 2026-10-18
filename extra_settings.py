"""
extra_settings.py
-----------------
Küçük, genel amaçlı kalıcı ayar deposu (JSON). Şu an açık artırma tur
süresini tutar. Ayar OYUNCUYA aittir (kayıt dosyasına değil), yani hangi
kayıtla oynarsa oynasın, bir kez ayarlanınca sonsuza kadar geçerlidir.

Dosya, günün mesajı kayıtlarıyla aynı kullanıcı veri klasörüne yazılır
(app_paths.user_data_dir; taşınabilir mod dahil).
"""

import json
import os

import app_paths

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
FILENAME = "ekstra_ayarlar.json"


def _path() -> str:
    return os.path.join(app_paths.user_data_dir(APP_NAME, APP_AUTHOR), FILENAME)


def _load() -> dict:
    try:
        with open(_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def get_value(key: str, default=None):
    return _load().get(key, default)


def set_value(key: str, value) -> None:
    data = _load()
    data[key] = value
    try:
        os.makedirs(os.path.dirname(_path()), exist_ok=True)
        tmp = _path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, _path())
    except OSError:
        pass
