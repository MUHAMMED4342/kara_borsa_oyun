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

# AppData klasörü
APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"
SAVE_DIR = appdirs.user_data_dir(APP_NAME, APP_AUTHOR)


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
        
        json_string = json.dumps(save_data, indent=2, ensure_ascii=False)
        encoded_data = base64.b64encode(json_string.encode('utf-8'))
        
        with open(get_save_path(username), 'wb') as f:
            f.write(encoded_data)
        return True
    except Exception as e:
        print(f"[Hata] Kayıt yapılamadı: {e}")
        return False


def load_game(username: str) -> dict:
    save_path = get_save_path(username)
    if not os.path.exists(save_path):
        return None
    
    try:
        with open(save_path, 'rb') as f:
            encoded_data = f.read()
        json_string = base64.b64decode(encoded_data).decode('utf-8')
        return json.loads(json_string)
    except Exception as e:
        print(f"[Hata] Kayıt yüklenemedi: {e}")
        return None


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