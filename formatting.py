# -*- coding: utf-8 -*-
"""
formatting.py
--------------
Para/sayı tutarlarını ekran okuyucu dostu şekilde biçimlendiren ortak
yardımcı fonksiyon.

NEDEN: Kodun her yerinde "{tutar:,.2f} TL" kullanılıyordu. Tutar tam
sayı olsa bile (ör. 3000.0) hep ".00" ekleniyordu; ekran okuyucular
bunu "nokta sıfır sıfır" diye okuyunca gereksiz yere can sıkıcı
oluyordu. format_tl() tutar tam sayıysa küsuratı hiç göstermez,
gerçek küsurat varsa 2 hane gösterir.
"""


def format_tl(value) -> str:
    """
    Bir parasal tutarı ekran okuyucu dostu biçimde döndürür (TL eki
    dahil DEĞİL, çağıran yer ekler).

    3000.0    -> "3,000"
    3150.5    -> "3,150.50"
    -250.0    -> "-250"
    """
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)

    if abs(value - round(value)) < 0.005:
        return f"{value:,.0f}"
    return f"{value:,.2f}"
