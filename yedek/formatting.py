# -*- coding: utf-8 -*-
"""
formatting.py
--------------
Para/sayı tutarlarını ekran okuyucu dostu şekilde biçimlendiren ortak
yardımcı fonksiyon.

NEDEN: Kodun her yerinde "{tutar:,.2f} TL" kullanılıyordu. Tutar tam
sayı olsa bile (ör. 3000.0) hep ".00" ekleniyordu; ekran okuyucular
bunu "nokta sıfır sıfır" diye okuyunca gereksiz yere can sıkıcı
oluyordu. format_tl() artık kuruş göstermiyor: tutar ne olursa olsun
en yakın tam sayıya yuvarlanıp düz TL olarak döndürülüyor
("100 TL, 10 kuruş" yerine direkt "110 TL" gibi).
"""


def format_tl(value) -> str:
    """
    Bir parasal tutarı ekran okuyucu dostu biçimde döndürür (TL eki
    dahil DEĞİL, çağıran yer ekler). Kuruş hiçbir zaman gösterilmez;
    tutar en yakın tam sayıya yuvarlanır.

    3000.0    -> "3,000"
    3150.5    -> "3,151"
    -250.0    -> "-250"
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    return f"{round(value):,.0f}"
