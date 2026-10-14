"""
app_paths.py
------------
Oyunun TÜM kalıcı verisinin (kayıtlar, ayarlar, hesap, biletler, dil
dosyaları) nerede tutulacağını tek yerden belirler.

- NORMAL mod      : %LOCALAPPDATA%\\Karaborsa\\...  (eski davranış, appdirs)
- TAŞINABİLİR mod : oyunun ana exe dosyasının yanındaki "KaraborsaData"
  klasörü. Exe'nin yanında "portable.flag" adlı boş bir işaret dosyası
  varsa oyun taşınabilir moddadır. İşaret dosyası settings.json'un
  İÇİNDE tutulamaz: settings.json'un nerede olduğunu bulmak için önce
  modu bilmemiz gerekir.

Diğer modüller (save_manager, ticket_manager, daily_message, ...)
appdirs.user_data_dir(APP_NAME, APP_AUTHOR) yerine
app_paths.user_data_dir(APP_NAME, APP_AUTHOR) çağırmalıdır.
"""

import os
import sys
import shutil

import appdirs

APP_NAME = "KaraborsaSimulasyonu"
APP_AUTHOR = "Karaborsa"

PORTABLE_MARKER_NAME = "portable.flag"
PORTABLE_DATA_DIRNAME = "KaraborsaData"


def exe_dir() -> str:
    """Oyunun ANA exe dosyasının klasörü."""
    if getattr(sys, "frozen", False):
        # PyInstaller (onefile/onedir): sys.executable gerçek exe'dir.
        return os.path.dirname(os.path.abspath(sys.executable))
    if "__compiled__" in globals():
        # Nuitka onefile: sys.executable geçici klasörü gösterebilir,
        # sys.argv[0] ise başlatılan gerçek exe'dir.
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


def _marker_path() -> str:
    return os.path.join(exe_dir(), PORTABLE_MARKER_NAME)


def _portable_root() -> str:
    return os.path.join(exe_dir(), PORTABLE_DATA_DIRNAME)


def is_portable() -> bool:
    return os.path.exists(_marker_path())


def _normal_data_dir(app_name=APP_NAME, app_author=APP_AUTHOR) -> str:
    return appdirs.user_data_dir(app_name, app_author)


def _normal_locales_dir() -> str:
    appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "Karaborsa", "locales")


def user_data_dir(app_name=APP_NAME, app_author=APP_AUTHOR) -> str:
    """appdirs.user_data_dir yerine kullanılır (kayıt/ayar/bilet)."""
    if is_portable():
        return os.path.join(_portable_root(), app_name)
    return _normal_data_dir(app_name, app_author)


def locales_dir() -> str:
    """i18n'in çalışma zamanında okuyup yazdığı dil klasörü."""
    if is_portable():
        return os.path.join(_portable_root(), "locales")
    return _normal_locales_dir()


# Skor gönderimi (leaderboard.py) normal modda bu eski konuma yazar
# (%LOCALAPPDATA%\\KaraborsaSimulasyonu), appdirs klasöründen FARKLI.
_LEGACY_LEADERBOARD_FILES = ("skor_ayarlari.json", "skor_log.txt")


def _legacy_leaderboard_dir() -> str:
    appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "KaraborsaSimulasyonu")
    return os.path.join(os.path.expanduser("~"), ".karaborsa_simulasyonu")


def _copy_leaderboard_files(src_dir: str, dst_dir: str) -> None:
    for name in _LEGACY_LEADERBOARD_FILES:
        src = os.path.join(src_dir, name)
        if os.path.isfile(src):
            os.makedirs(dst_dir, exist_ok=True)
            shutil.copy2(src, os.path.join(dst_dir, name))


def _copy_tree(src: str, dst: str) -> None:
    if os.path.isdir(src):
        shutil.copytree(src, dst, dirs_exist_ok=True)


def can_write_exe_dir() -> bool:
    test = os.path.join(exe_dir(), ".write_test.tmp")
    try:
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return True
    except OSError:
        return False


def enable_portable() -> tuple:
    """Normal moddan taşınabilir moda geçer: verileri exe'nin yanına
    KOPYALAR, en son işaret dosyasını oluşturur. Bir adım başarısız
    olursa işaret dosyası oluşmaz ve eski veri yerinde kalır.
    Döner: (başarılı_mı, hata_mesajı)."""
    if is_portable():
        return True, ""
    if not can_write_exe_dir():
        return False, "No write permission in the game folder."
    try:
        root = _portable_root()
        _copy_tree(_normal_data_dir(), os.path.join(root, APP_NAME))
        _copy_tree(_normal_locales_dir(), os.path.join(root, "locales"))
        _copy_leaderboard_files(_legacy_leaderboard_dir(), os.path.join(root, APP_NAME))
        os.makedirs(root, exist_ok=True)
        with open(_marker_path(), "w", encoding="utf-8") as f:
            f.write("Karaborsa portable mode\n")
        return True, ""
    except Exception as e:
        return False, str(e)


def disable_portable() -> tuple:
    """Taşınabilir moddan normal moda döner: verileri AppData'ya geri
    kopyalar, işaret dosyasını siler; kopya başarılıysa exe yanındaki
    veri klasörünü de kaldırır (yoksa yeniden taşınabilir moda geçişte
    eski kopya güncel verinin üzerine yazılırdı)."""
    if not is_portable():
        return True, ""
    try:
        root = _portable_root()
        _copy_tree(os.path.join(root, APP_NAME), _normal_data_dir())
        _copy_tree(os.path.join(root, "locales"), _normal_locales_dir())
        _copy_leaderboard_files(os.path.join(root, APP_NAME), _legacy_leaderboard_dir())
        # Taşınabilir klasördeki skor dosyaları AppData'da kayıt klasörüne
        # değil eski konuma gitti; kayıt klasörüne kopyalanan kalıntıları sil.
        for name in _LEGACY_LEADERBOARD_FILES:
            try:
                os.remove(os.path.join(_normal_data_dir(), name))
            except OSError:
                pass
        os.remove(_marker_path())
    except Exception as e:
        return False, str(e)
    shutil.rmtree(_portable_root(), ignore_errors=True)
    return True, ""
