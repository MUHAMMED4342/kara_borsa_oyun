# -*- mode: python ; coding: utf-8 -*-
#
# Karaborsa Ticaret Simülasyonu - Windows onefile / no-console build
#
# ÖNEMLİ - DERLEME SIRASI:
#   1) Önce yardımcı güncelleyiciyi derle:
#        pyinstaller build_updater.spec
#      Bu, dist/KaraborsaGuncelleyici.exe dosyasını üretir.
#   2) SONRA ana oyunu derle:
#        pyinstaller build.spec
#      Bu adım, 1. adımda üretilen KaraborsaGuncelleyici.exe'yi kendi
#      içine gömülü bir veri dosyası olarak paketler (bkz. datas=[...]
#      aşağıda). Oyun ilk açıldığında bu gömülü exe'yi AppData'ya bir
#      kez çıkarır ve güncellemeleri artık kırılgan bir .bat betiği
#      yerine bu ayrı, kalıcı yardımcı exe ile uygular (bkz. updater.py).
#
# 1. adım atlanırsa ya da dist/KaraborsaGuncelleyici.exe bulunamazsa,
# aşağıdaki datas girişi PyInstaller'ı derleme sırasında HATA ile
# durdurur; bu kasıtlıdır (sessizce eksik bir güncelleyiciyle
# derlenmiş bir oyun dağıtmamak için).
#
# Çıktı: dist/KaraborsaSimulasyonu.exe  (tek dosya, konsol penceresi açmaz)

import os
import pkgutil

block_cipher = None

_updater_exe = os.path.join('dist', 'KaraborsaGuncelleyici.exe')
if not os.path.exists(_updater_exe):
    raise SystemExit(
        "HATA: dist/KaraborsaGuncelleyici.exe bulunamadi.\n"
        "Once 'pyinstaller build_updater.spec' calistirip yardimci\n"
        "guncelleyici exe'yi uretmeniz gerekiyor, sonra bu spec'i tekrar\n"
        "calistirin."
    )

# token.txt exe'nin İÇİNE gömülüyor (sounds/help.html ile aynı mantık),
# böylece dağıttığınız tek exe dosyası kendi başına çalışır; kullanıcının
# ayrıca yanına token.txt koymasına gerek kalmaz. Bu dosya build.spec ile
# AYNI klasörde (main.py'nin yanında) durmalı - derleme zamanında okunup
# exe'nin içine paketlenir.
_token_file = 'token.txt'
if not os.path.exists(_token_file):
    raise SystemExit(
        "HATA: token.txt bulunamadi.\n"
        "GitHub 'gist' izinli personal access token'inizi icerecek\n"
        "sekilde, bu build.spec ile ayni klasore bir token.txt dosyasi\n"
        "olusturup tekrar deneyin."
    )

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('help.html', '.'),
        ('sounds', 'sounds'),
        (_updater_exe, '.'),
        (_token_file, '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# accessible_output2, hangi ekran okuyucunun (SAPI5, NVDA, JAWS, ...)
# kurulu olduğunu ÇALIŞMA ANINDA dinamik import ile tespit ediyor.
# PyInstaller'ın statik analizi bu alt modülleri göremediği için, elle
# hiddenimports listesine ekliyoruz. Bu adım atlanırsa exe sessizce
# hiç seslendirme yapmaz (SCREEN_READER_AVAILABLE = False'a düşer).
try:
    import accessible_output2.outputs as ao_outputs
    for _, modname, _ in pkgutil.iter_modules(ao_outputs.__path__):
        a.hiddenimports.append(f"accessible_output2.outputs.{modname}")
except ImportError:
    pass

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Tek EXE() çağrısı + a.binaries/a.zipfiles/a.datas'in doğrudan içine
# verilmesi = ONEFILE mod (ayrı bir COLLECT() adımı YOK).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KaraborsaSimulasyonu',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # --windowed / no-console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,                      # istersen 'icon.ico' yolunu yaz
)
