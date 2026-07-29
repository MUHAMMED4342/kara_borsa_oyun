# -*- coding: utf-8 -*-
"""
save_manager.py
---------------
Oyun kayıtlarını appdata klasöründe Base64 ile kodlayarak yönetir.
"""

import os
import json
import base64
import appdirs
import re
import hmac
import hashlib

# AppData klasörü
APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
SAVE_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)

# Kayıt dosyalarını imzalamak için kullanılan gizli anahtar.
# NOT: Bu anahtar istemci koduyla birlikte dağıtıldığı için %100 gizli
# tutulamaz; kararlı bir kullanıcı anahtarı koddan çıkarıp kayıtları
# yeniden imzalayabilir. Bu mekanizma "dosyayı aç, düzenle, kaydet"
# seviyesindeki kolay hile denemelerini engellemek içindir, tam bir
# güvenlik garantisi vermez. Gerçek anti-cheat için sunucu taraflı
# doğrulama gerekir.
_SAVE_SECRET_KEY = b"KaraborsaSimulasyonu::save-integrity::v1::9f3a7c1e"


def _sign(data_bytes: bytes) -> str:
    return hmac.new(_SAVE_SECRET_KEY, data_bytes, hashlib.sha256).hexdigest()


def _write_signed_save(path: str, save_data: dict) -> None:
    """Kayıt verisini JSON'a çevirir, imzalar ve dosyaya base64 olarak yazar."""
    json_string = json.dumps(save_data, indent=2, ensure_ascii=False)
    data_bytes = json_string.encode('utf-8')
    signature = _sign(data_bytes)

    package = {
        "sig": signature,
        "payload": base64.b64encode(data_bytes).decode('ascii'),
    }
    package_bytes = json.dumps(package).encode('utf-8')
    encoded_data = base64.b64encode(package_bytes)

    with open(path, 'wb') as f:
        f.write(encoded_data)


def _read_signed_save(path: str) -> dict:
    """Dosyayı okur, imzayı doğrular ve geçerliyse kayıt verisini (dict) döner.
    İmza uyuşmuyorsa veya format bozuksa None döner."""
    with open(path, 'rb') as f:
        encoded_data = f.read()

    package_bytes = base64.b64decode(encoded_data)
    package = json.loads(package_bytes.decode('utf-8'))

    signature = package["sig"]
    data_bytes = base64.b64decode(package["payload"])
    expected_signature = _sign(data_bytes)

    if not hmac.compare_digest(signature, expected_signature):
        print("[Hata] Kayıt dosyası bozulmuş veya değiştirilmiş görünüyor (imza uyuşmuyor).")
        return None

    return json.loads(data_bytes.decode('utf-8'))


def clean_username(username: str) -> str:
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


def get_save_path(username: str) -> str:
    os.makedirs(SAVE_DIR, exist_ok=True)
    return os.path.join(SAVE_DIR, f"{username}.json")


def save_game(username: str, game_state) -> bool:
    try:
        save_data = {
            "username": username,
            "cash": game_state.cash,
            "dirty_cash": getattr(game_state, "dirty_cash", 0.0),
            "clean_money": getattr(game_state, "clean_money", 0.0),
            "day": game_state.day,
            "inventory": game_state.inventory,
            "prices": game_state.prices,
            "in_jail": getattr(game_state, "in_jail", False),
            "jail_days": getattr(game_state, "jail_days", 0),
            # ÖNEMLİ: Oyun artık çoklu şirket sistemi (il + ilçe bazlı)
            # kullanıyor; tüm şirketler bu listede saklanıyor. Aşağıdaki
            # "company_*" tekil alanlar SADECE eski/harici araçlarla
            # geriye dönük uyumluluk için tutuluyor ve artık gerçek veri
            # taşımıyor - asıl kaynak her zaman "companies" listesidir.
            "companies": getattr(game_state, "companies", []),
            "has_company": getattr(game_state, "has_company", False),
            "company_type": getattr(game_state, "company_type", ""),
            "company_name": getattr(game_state, "company_name", ""),
            "company_city": getattr(game_state, "company_city", ""),
            "company_credit_score": getattr(game_state, "company_credit_score", 0),
            "company_total_laundered": getattr(game_state, "company_total_laundered", 0.0),
            "company_monthly_revenue": getattr(game_state, "company_monthly_revenue", 0.0),
            "company_days_active": getattr(game_state, "company_days_active", 0),
            "company_upkeep_paid": getattr(game_state, "company_upkeep_paid", 0),
            "loan_amount": getattr(game_state, "loan_amount", 0.0),
            "loan_interest_rate": getattr(game_state, "loan_interest_rate", 0.0),
            "loan_days_remaining": getattr(game_state, "loan_days_remaining", 0),
            "loan_total_debt": getattr(game_state, "loan_total_debt", 0.0),
            "loan_total_installments": getattr(game_state, "loan_total_installments", 0),
            "loan_installments_paid": getattr(game_state, "loan_installments_paid", 0),
            "loan_installment_amount": getattr(game_state, "loan_installment_amount", 0.0),
            "loan_days_until_installment": getattr(game_state, "loan_days_until_installment", 0),
            "laundering_in_progress": getattr(game_state, "laundering_in_progress", False),
            "laundering_days_left": getattr(game_state, "laundering_days_left", 0),
            "laundering_amount": getattr(game_state, "laundering_amount", 0.0),
            "laundering_method": getattr(game_state, "laundering_method", ""),
            "has_informant": getattr(game_state, "has_informant", False),
            "informant_warning_active": getattr(game_state, "informant_warning_active", False),
            "police_heat": getattr(game_state, "police_heat", 0),
            "total_crime": getattr(game_state, "total_crime", 0.0),
            "deaths_caused": getattr(game_state, "deaths_caused", 0),
            "highest_cash": getattr(game_state, "highest_cash", game_state.cash),
            "days_until_bank_interest": getattr(game_state, "days_until_bank_interest", 30),
            "last_sent_score": getattr(game_state, "last_sent_score", 0.0),
            "lands": getattr(game_state, "lands", []),
            "land_prices": getattr(game_state, "land_prices", {}),
            "employees": getattr(game_state, "employees", []),
        }
        
        _write_signed_save(get_save_path(username), save_data)
        return True
    except Exception as e:
        print(f"[Hata] Kayıt yapılamadı: {e}")
        return False


def load_game(username: str) -> dict:
    save_path = get_save_path(username)
    if not os.path.exists(save_path):
        return None
    
    try:
        return _read_signed_save(save_path)
    except Exception:
        pass

    # Geriye dönük uyumluluk: imza sistemi eklenmeden önce kaydedilmiş
    # eski (düz base64+JSON) dosyaları da okuyabiliyoruz. Böyle bir kayıt
    # bulunursa bir sonraki save_game() çağrısında otomatik olarak
    # imzalı yeni formata dönüştürülür.
    try:
        with open(save_path, 'rb') as f:
            encoded_data = f.read()
        json_string = base64.b64decode(encoded_data).decode('utf-8')
        return json.loads(json_string)
    except Exception as e:
        print(f"[Hata] Kayıt yüklenemedi: {e}")
        return None


def rename_save(old_username: str, new_username: str) -> tuple:
    """Var olan bir kaydın kullanıcı adını (ve kayıt dosyasının adını)
    değiştirir. Kayıt içindeki TÜM ilerleme (nakit, envanter, şirketler,
    arsalar, çalışanlar, kredi, hapis durumu vb.) olduğu gibi korunur -
    sadece "username" alanı ve dosya adı güncellenir. Bu sayede "tek
    hesap kuralı" yüzünden bir oyuncu kullanıcı adını yanlış yazmışsa
    ya da değiştirmek istiyorsa, mevcut kaydını silip sıfırdan
    başlamak zorunda kalmaz.

    Dönen değer (başarılı_mı, mesaj) biçimindedir. Başarılıysa mesaj
    alanında temizlenmiş yeni kullanıcı adı, başarısızsa hata sebebi
    döner."""
    old_username = (old_username or "").strip()
    if not old_username:
        return False, "Geçersiz mevcut kullanıcı adı"

    old_path = get_save_path(old_username)
    if not os.path.exists(old_path):
        return False, f"'{old_username}' adlı bir kayıt bulunamadı"

    new_clean = clean_username((new_username or "").strip())
    if not new_clean:
        return False, "Kullanıcı adı boş olamaz"

    if new_clean.casefold() == old_username.casefold():
        return False, "Yeni kullanıcı adı mevcut adla aynı"

    new_path = get_save_path(new_clean)
    if os.path.exists(new_path):
        return False, f"'{new_clean}' adında zaten bir kayıt var"

    data = load_game(old_username)
    if data is None:
        return False, "Mevcut kayıt okunamadı"

    data["username"] = new_clean

    try:
        _write_signed_save(new_path, data)
    except Exception as e:
        print(f"[Hata] Kullanıcı adı değiştirilemedi: {e}")
        return False, f"Yeni kayıt yazılamadı: {e}"

    try:
        os.remove(old_path)
    except OSError:
        pass

    return True, new_clean


def list_saves() -> list:
    os.makedirs(SAVE_DIR, exist_ok=True)
    saves = []
    for file in os.listdir(SAVE_DIR):
        if file.endswith('.json'):
            saves.append(file[:-5])
    return saves


def delete_save(username: str) -> bool:
    save_path = get_save_path(username)
    if os.path.exists(save_path):
        os.remove(save_path)
        return True
    return False


def delete_all_saves() -> bool:
    try:
        for user in list_saves():
            delete_save(user)
        return True
    except Exception as e:
        print(f"[Hata] Tüm kayıtlar silinemedi: {e}")
        return False