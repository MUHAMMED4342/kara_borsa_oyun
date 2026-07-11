import requests
import json

# Bilgilerin
GIST_ID = "5cde0d504dec8aac37cdfc211d91a891"

# token.txt dosyasını oku
with open("token.txt", "r") as f:
    TOKEN = f.read().strip()

def test_skor():
    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {TOKEN}"}
    
    # Mevcut veriyi çek
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = json.loads(response.json()['files']['skorlar.json']['content'])
        
        # Yeni bir deneme skoru ekle
        data.append({"isim": "Deneme", "puan": 100})
        
        # GitHub'a gönder (HTTPS kullanılarak)
        payload = {"files": {"skorlar.json": {"content": json.dumps(data)}}}
        update_response = requests.patch(url, headers=headers, data=json.dumps(payload))
        
        if update_response.status_code == 200:
            print("Başarılı! GitHub dosyası güncellendi.")
        else:
            print(f"Hata oluştu: {update_response.status_code} - {update_response.text}")
    else:
        print(f"Veri çekme hatası: {response.status_code}")

test_skor()