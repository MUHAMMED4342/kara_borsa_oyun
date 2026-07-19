# -*- mode: python ; coding: utf-8 -*-

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

_token_file = 'token.txt'
if not os.path.exists(_token_file):
    raise SystemExit(
        "HATA: token.txt bulunamadi."
    )

# release_notes.html kontrolü (Opsiyonel ama hata almamak için önerilir)
if not os.path.exists('release_notes.html'):
    print("UYARI: release_notes.html bulunamadi, paketlenmeyecek.")

# insanlar.txt / iller.txt kontrolü (Adam Yönetimi özelliği için gerekli)
for _pool_file in ('insanlar.txt', 'iller.txt'):
    if not os.path.exists(_pool_file):
        raise SystemExit(
            f"HATA: {_pool_file} bulunamadi. Bu dosya olmadan exe "
            "paketlense bile isim/sehir havuzu bos olacaktir.\n"
            f"{_pool_file} dosyasini main.py ile ayni klasore koyup "
            "tekrar deneyin."
        )

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('help.html', '.'),
        ('release_notes.html', '.'),  # Buraya eklendi
        ('sounds', 'sounds'),
        ('insanlar.txt', '.'),
        ('iller.txt', '.'),
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

try:
    import accessible_output2.outputs as ao_outputs
    for _, modname, _ in pkgutil.iter_modules(ao_outputs.__path__):
        a.hiddenimports.append(f"accessible_output2.outputs.{modname}")
except ImportError:
    pass

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)