# -*- mode: python ; coding: utf-8 -*-
#
# KaraborsaGuncelleyici.exe - Ayrı, küçük, kalıcı yardımcı güncelleyici
#
# ÖNEMLİ: Bu, ana oyundan (build.spec) TAMAMEN AYRI bir derlemedir ve
# ana oyunu derlemeden ÖNCE çalıştırılmalıdır, çünkü ana oyunun
# build.spec dosyası bu derlemenin çıktısını (dist/KaraborsaGuncelleyici.exe)
# kendi içine veri dosyası olarak gömüyor.
#
# Kullanım sırası:
#   1) pyinstaller build_updater.spec      -> dist/KaraborsaGuncelleyici.exe üretir
#   2) pyinstaller build.spec              -> ana oyunu, yardımcı exe'yi
#                                              içine gömerek üretir
#
# Bu yardımcı program SADECE Python stdlib kullanır (os, sys, json,
# time, ctypes, subprocess, shutil, datetime) — wx veya pygame'e
# ihtiyacı YOKTUR. Bu yüzden hem çok küçük hem de antivirüs
# taramalarında şüphe uyandırabilecek ses/GUI kütüphanelerinden
# tamamen arınmıştır.

block_cipher = None

a = Analysis(
    ['updater_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='KaraborsaGuncelleyici',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                  # arka planda sessizce çalışır
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
