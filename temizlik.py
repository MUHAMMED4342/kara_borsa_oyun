import os
import shutil
import tokenize
import io

def remove_comments(source_code):
    io_obj = io.StringIO(source_code)
    out = []
    last_lineno = -1
    last_col = 0
    
    for tok in tokenize.generate_tokens(io_obj.readline):
        token_type = tok[0]
        token_string = tok[1]
        start_line, start_col = tok[2]
        end_line, end_col = tok[3]
        
        if start_line > last_lineno:
            last_col = 0
        if start_col > last_col:
            out.append(" " * (start_col - last_col))
        
        if token_type == tokenize.COMMENT:
            pass
        else:
            out.append(token_string)
            
        last_lineno = end_line
        last_col = end_col
        
    return "".join(out)

# 1. Yedek klasörünü oluştur
yedek_klasoru = "yedek"
if not os.path.exists(yedek_klasoru):
    os.makedirs(yedek_klasoru)

# 2. Bulunduğumuz klasördeki tüm .py dosyalarını tara
for dosya_adi in os.listdir("."):
    if dosya_adi.endswith(".py") and dosya_adi != os.path.basename(__file__):
        
        # Orijinal dosyayı yedek klasörüne kopyala (taşımak istersen shutil.move kullanılabilir)
        yedek_yolu = os.path.join(yedek_klasoru, dosya_adi)
        shutil.copy2(dosya_adi, yedek_yolu)
        
        # Dosyayı oku ve yorumları temizle
        with open(dosya_adi, "r", encoding="utf-8") as f:
            temiz_kod = remove_comments(f.read())
            
        # Temizlenmiş hali tekrar aynı dosyaya yaz
        with open(dosya_adi, "w", encoding="utf-8") as f:
            f.write(temiz_kod)
            
        print(f"İşlendi ve yedeği alındı: {dosya_adi}")

print("\nTüm Python dosyalarındaki yorumlar başarıyla temizlendi!")