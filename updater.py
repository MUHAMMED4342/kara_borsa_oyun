# -*- coding: utf-8 -*-
"""
updater.py
----------
Tek dosyalık (onefile) .exe için otomatik güncelleme mekanizması.

Akış:
1) Kurulu olan sürüm, AppData'daki güncelleme klasöründe tutulan
   'surum.txt' dosyasından okunur (get_installed_version). Bu dosya hiç
   yoksa — yani uygulama daha önce hiç kendini güncellememişse —
   koddaki CURRENT_VERSION başlangıç değerine geri düşülür. Yani
   CURRENT_VERSION SADECE ilk sürüm için gereklidir; sonraki her
   güncellemede sürüm bilgisi kendiliğinden bu dosyaya yazılır,
   geliştiricinin kodda bir şey değiştirip yeniden derlemesi GEREKMEZ.
   Geliştirici tek yapması gereken: yeni exe'yi GitHub release'ine
   yükleyip VERSION_URL'deki (versiyon.txt) metni güncellemektir.
2) VERSION_URL adresinden sunucudaki sürüm metni okunur ve kurulu sürümle
   karşılaştırılır (basit string kıyaslama değil, (1,0,10) > (1,0,9)
   gibi doğru sayısal kıyaslama yapılır).
3) Daha yeni bir sürüm varsa, kullanıcıya "indirilsin mi?" diye sorulur.
4) Kullanıcı onaylarsa, indirme sırasında uygulama-modal bir ilerleme
   çubuğu (wx.ProgressDialog) gösterilir; kullanıcı indirme bitene kadar
   oyunla etkileşemez, yüzde olarak ilerlemeyi görür. İndirilen geçici
   dosya, exe'nin bulunduğu klasöre DEĞİL, AppData'daki güncelleme
   klasörüne kaydedilir (kullanıcının kendi indirdiği klasörde
   kendisinin indirmediği dosyalar belirmesin diye).
5) İndirme tamamlanınca "Güncelleme indirildi, uygulama kapanıp yeniden
   başlatılacak" mesajı gösterilir ve güncelleme HEMEN uygulanmaya
   başlanır (bkz. apply_pending_update_if_ready).
6) apply_pending_update_if_ready(): ARTIK bir .bat betiği ÜRETMİYORUZ.
   Bunun yerine, ana oyun exe'sinin içine GÖMÜLÜ, ayrı ve kalıcı küçük
   bir yardımcı program (KaraborsaGuncelleyici.exe, bkz. updater_app.py)
   AppData'ya bir kez çıkarılır ve indirilen güncellemenin bilgileriyle
   (hedef exe yolu, beklenecek PID, yeni sürüm, sürüm dosyası yolu)
   birlikte başlatılır. Bu yardımcı exe, mevcut oyun süreci GERÇEKTEN
   kapanana kadar Windows API'siyle (OpenProcess + WaitForSingleObject)
   bekler, eski exe'nin üzerine yeni dosyayı birkaç deneme ile kopyalar,
   kopyalama başarılıysa 'surum.txt'yi günceller ve oyunu yeniden başlatır.

   Eski yöntemde (dinamik üretilen .bat + "cmd /c" + "tasklist | find")
   şu sorunlar vardı: bazı antivirüsler bat üretip çalıştırma davranışını
   şüpheli buluyordu; "tasklist | find" Windows dil paketine bağlıydı;
   PyInstaller onefile'ın Job Object'inden "breakaway" bazı ortamlarda
   reddedilebiliyordu. Ayrı, stdlib-only (wx/pygame'siz) bir yardımcı
   exe kullanmak bu sorunların hepsini ortadan kaldırıyor.

GÜVENLİK / DAYANIKLILIK:
- Her ağ isteği ve dosya işlemi try/except içindedir. İnternet yoksa,
  sunucuya ulaşılamazsa, indirme yarıda koparsa veya beklenmeyen bir
  hata oluşursa fonksiyonlar sessizce geri döner; oyunun normal akışı
  HİÇBİR ZAMAN bundan etkilenmez, herhangi bir hata kullanıcıya
  yansıtılmaz ya da programı çökertmez.
- Mekanizma SADECE PyInstaller ile derlenmiş, dondurulmuş (frozen) bir
  .exe içinde çalışırken devreye girer. "python main.py" ile doğrudan
  script olarak çalıştırıldığında hiçbir şey yapmaz; aksi halde
  python.exe'nin üzerine yazmaya çalışıp geliştirme ortamını bozardı.
"""

import os
import sys
import json
import shutil
import threading
import subprocess

import appdirs
import wx

CURRENT_VERSION = "1.0.0"  # SADECE ilk sürüm için başlangıç değeri; bkz. aşağıdaki not
VERSION_URL = "https://bilgisayar.netlify.app/versiyon.txt"
DOWNLOAD_URL = (
    "https://github.com/MUHAMMED4342/kara_borsa_oyun/releases/latest/"
    "download/KaraborsaSimulasyonu.exe"
)

# save_manager.py ile aynı uygulama kimliği — aynı AppData klasörünü
# paylaşıyoruz (ayrı bir alt klasörde, kayıt dosyalarıyla karışmasın).
_APP_NAME = "KaraborsaSimulasyonu"
_APP_AUTHOR = "Karaborsa"

_TEMP_UPDATE_NAME = "temp_update.exe"
_HELPER_EXE_NAME = "KaraborsaGuncelleyici.exe"
_TASK_FILE_NAME = "guncelleme_gorevi.json"
_LOCAL_VERSION_FILE = "surum.txt"
_LOG_FILE = "update_log.txt"

_update_ready = {"path": None, "version": None, "applied": False}
_lock = threading.Lock()


def _is_frozen() -> bool:
    """Sadece PyInstaller ile paketlenmiş .exe içinde True döner."""
    return bool(getattr(sys, "frozen", False))


def _version_tuple(v: str):
    try:
        return tuple(int(p) for p in v.strip().split("."))
    except Exception:
        # Sunucudan beklenmeyen bir formatta veri gelirse güncelleme
        # yokmuş gibi davranmak için en düşük değeri döndür.
        return (0,)


def _is_newer(remote: str, local: str) -> bool:
    try:
        return _version_tuple(remote) > _version_tuple(local)
    except Exception:
        return False


def _get_exe_path() -> str:
    return sys.executable if _is_frozen() else os.path.abspath(__file__)


def _get_update_dir() -> str:
    """
    Tüm güncelleme destek dosyalarının (indirilen geçici exe, yardımcı
    güncelleyici exe, görev/sürüm/log dosyaları) tutulduğu klasör. Kasıtlı olarak exe'nin kendi
    klasörü (kullanıcının Downloads'ı olabilir) DEĞİL, AppData altında
    gizli bir klasör: gerçek kullanıcılar exe'yi indirdikleri klasörde
    tutacak, oraya "surum.txt", "temp_update.exe" gibi kendilerinin
    indirmediği dosyaların belirmesi kafa karıştırıcı olur (silinme
    riski de var, bu da güncelleme takibini bozar). AppData kullanıcının
    normalde hiç görmediği bir yer, hem de her zaman yazılabilir —
    exe nerede kurulu olursa olsun (Program Files gibi korumalı bir
    klasörde bile) bu dosyalar için izin sorunu yaşanmaz.
    """
    path = appdirs.user_data_dir(_APP_NAME, _APP_AUTHOR)
    path = os.path.join(path, "guncelleme")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _get_local_version_path() -> str:
    return os.path.join(_get_update_dir(), _LOCAL_VERSION_FILE)


def _get_helper_exe_path() -> str:
    """Yardımcı güncelleyici exe'nin AppData'daki KALICI konumu."""
    return os.path.join(_get_update_dir(), _HELPER_EXE_NAME)


def _get_bundled_helper_exe_path():
    """
    Ana oyunun onefile paketine gömülü olan yardımcı güncelleyici
    exe'nin, çalışma anında açılan geçici klasördeki (_MEIPASS) yolunu
    döndürür. Script olarak (frozen değilken) çalışıyorsa ya da
    build.spec'e gömme adımı atlanmışsa None döner.
    """
    base = getattr(sys, "_MEIPASS", None)
    if not base:
        return None
    candidate = os.path.join(base, _HELPER_EXE_NAME)
    return candidate if os.path.exists(candidate) else None


def _ensure_helper_exe_ready():
    """
    Gömülü yardımcı güncelleyici exe'yi AppData'daki kalıcı konumuna
    kopyalar. Zaten aynı boyutta bir kopya oradaysa (ör. daha önceki bir
    çalıştırmada kopyalanmış) tekrar kopyalamaz — yardımcı exe böylece
    normalde SADECE BİR KEZ diske yazılır ve kalıcı bir yardımcı program
    olarak kalır. Boyut farkı varsa (yardımcının kendisi güncellenmiş
    demektir, çok nadir) üzerine yazar.

    Başarılı olursa kalıcı yoldaki exe'nin tam yolunu, hiçbir şekilde
    hazırlanamazsa None döner.
    """
    bundled = _get_bundled_helper_exe_path()
    dest = _get_helper_exe_path()

    if not bundled:
        # Gömülü kopya yok (script modu ya da eski bir build). Daha
        # önce kopyalanmış bir yardımcı zaten varsa onu kullanmaya
        # devam edelim.
        return dest if os.path.exists(dest) else None

    try:
        if os.path.exists(dest) and os.path.getsize(dest) == os.path.getsize(bundled):
            return dest
        shutil.copyfile(bundled, dest)
        return dest
    except Exception as e:
        _log(f"yardimci guncelleyici exe kopyalanamadi: {e}")
        return dest if os.path.exists(dest) else None


def _log(message: str) -> None:
    """Hata ayıklama için AppData'daki güncelleme klasörüne
    'update_log.txt' dosyasına zaman damgalı bir satır ekler. Asla hata
    fırlatmaz; loglama başarısız olsa bile oyunun akışını etkilemez."""
    try:
        import datetime
        log_path = os.path.join(_get_update_dir(), _LOG_FILE)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except Exception:
        pass


def get_installed_version() -> str:
    """
    Şu an kurulu olan sürümü döndürür. AppData'daki güncelleme
    klasöründe 'surum.txt' dosyası varsa oradan okur (uygulama daha önce
    en az bir kez kendini güncellemiş demektir); yoksa (ilk kurulum)
    koddaki CURRENT_VERSION başlangıç değerine döner. Böylece
    geliştirici her yeni derlemede kodu değiştirip yeniden derlemek
    zorunda kalmaz — sürüm bilgisi bir kez güncelleme uygulandıktan
    sonra kendiliğinden bu dosyada saklanır.
    """
    try:
        with open(_get_local_version_path(), "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    except Exception:
        pass
    return CURRENT_VERSION


def _ask_on_gui_thread_sync(question_fn, *args, timeout: float = 120.0):
    """
    question_fn ana GUI thread'inde (wx.CallAfter ile) çalıştırılır ve
    dönüş değeri arka plan thread'ine aktarılır. Arka plan thread'i bu
    cevabı bekler (event.wait). Zaman aşımına uğrarsa veya herhangi bir
    hata olursa False döner (yani "indirme" için varsayılan cevap
    HAYIR'dır — kullanıcı onaylamadan hiçbir şey indirilmez).
    """
    result_holder = {"answer": False}
    done = threading.Event()

    def _run_on_gui():
        try:
            result_holder["answer"] = bool(question_fn(*args))
        except Exception:
            result_holder["answer"] = False
        finally:
            done.set()

    try:
        wx.CallAfter(_run_on_gui)
    except Exception:
        return False

    done.wait(timeout=timeout)
    return result_holder["answer"]


def check_for_update_async(ask_user_callback=None) -> None:
    """
    Sürüm kontrolünü arka planda (ayrı thread) yapar; çağıran kodu ASLA
    bloklamaz. Script olarak (frozen değilken) çalışıyorsa hiçbir şey
    yapmaz.

    ask_user_callback: yeni bir sürüm bulunduğunda çağrılacak,
    remote_version (str) parametresi alan ve kullanıcı indirmeyi
    onaylarsa True, onaylamazsa False dönmesi beklenen bir fonksiyon.
    Bu fonksiyon otomatik olarak ANA GUI THREAD'İNDE çalıştırılır (wx
    diyalogları güvenle açılabilir); çağıranın ayrıca wx.CallAfter
    kullanmasına gerek yoktur. None verilirse hiçbir onay istenmeden
    otomatik indirilir.
    """
    if not _is_frozen():
        return

    _log("check_for_update_async baslatildi")

    def _worker():
        try:
            _check_and_download(ask_user_callback)
        except Exception as e:
            _log(f"beklenmeyen hata: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def _check_and_download(ask_user_callback=None) -> None:
    try:
        import requests
    except Exception:
        return

    try:
        resp = requests.get(VERSION_URL, timeout=5)
        resp.raise_for_status()
        remote_version = resp.text.strip()
    except Exception as e:
        _log(f"versiyon.txt okunamadi: {e}")
        return

    installed = get_installed_version()
    _log(f"kurulu surum={installed}, sunucudaki surum={remote_version}")

    if not remote_version or not _is_newer(remote_version, installed):
        _log("yeni surum yok, cikiliyor")
        return

    if ask_user_callback:
        should_download = _ask_on_gui_thread_sync(ask_user_callback, remote_version)
        _log(f"kullanici onayi: {should_download}")
        if not should_download:
            return

    temp_path = os.path.join(_get_update_dir(), _TEMP_UPDATE_NAME)
    _log(f"indirme basliyor -> {temp_path}")

    success = _download_with_progress(DOWNLOAD_URL, temp_path)
    _log(f"indirme sonucu: {success}")
    if not success:
        return

    # Yarım/bozuk bir indirmeyi kabul etme (çok küçük dosya şüphelidir)
    try:
        size = os.path.getsize(temp_path)
        _log(f"indirilen dosya boyutu: {size} byte")
        if size < 100 * 1024:
            _log("dosya cok kucuk, silindi, iptal")
            os.remove(temp_path)
            return
    except Exception as e:
        _log(f"boyut kontrolu hatasi: {e}")
        return

    global _update_ready
    with _lock:
        _update_ready = {"path": temp_path, "version": remote_version, "applied": False}
    _log("guncelleme hazir olarak isaretlendi, kapanis bildirimi gonderiliyor")

    # Kullanıcıya "indirildi, kapanıp yeniden başlayacak" bilgisi ver ve
    # açık pencereleri kapat. Pencereler kapanıp MainLoop bittikten sonra
    # main.py zaten apply_pending_update_if_ready()'yi çağırıyor; o da
    # ayrı yardımcı güncelleyici exe'yi başlatıp güncellemeyi kurup
    # programı yeniden açacak.
    wx.CallAfter(_notify_download_complete_and_close)


def _download_with_progress(url: str, dest_path: str) -> bool:
    """
    Ana GUI thread'inde uygulama-modal bir wx.ProgressDialog gösterip
    (kullanıcı indirme bitene kadar oyunla etkileşemez), dosyayı bu
    fonksiyonun çalıştığı (arka plan) thread'de indirir. İlerleme
    yüzdesi her parça indikçe wx.CallAfter ile diyaloga aktarılır.
    Başarılıysa True, herhangi bir sorunda (ağ hatası, iptal vb.) False
    döner; hiçbir durumda istisna dışarı sızmaz.
    """
    try:
        import requests
    except Exception:
        return False

    dialog_holder = {}
    created = threading.Event()

    def _create_dialog():
        try:
            dlg = wx.ProgressDialog(
                "Güncelleniyor",
                "Yeni sürüm indiriliyor, lütfen bekleyin...",
                maximum=100,
                style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME,
            )
            dialog_holder["dlg"] = dlg
        except Exception:
            dialog_holder["dlg"] = None
        finally:
            created.set()

    try:
        wx.CallAfter(_create_dialog)
    except Exception:
        return False

    created.wait(timeout=10)
    dlg = dialog_holder.get("dlg")

    def _update_dialog(percent, message):
        if dlg:
            try:
                dlg.Update(percent, message)
            except Exception:
                pass

    def _destroy_dialog():
        if dlg:
            try:
                dlg.Destroy()
            except Exception:
                pass

    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length") or 0) or None
            downloaded = 0
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=256 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        percent = min(100, int(downloaded * 100 / total))
                        message = (
                            f"İndiriliyor... {downloaded // 1024} KB / "
                            f"{total // 1024} KB"
                        )
                    else:
                        percent = 0
                        message = f"İndiriliyor... {downloaded // 1024} KB"
                    wx.CallAfter(_update_dialog, percent, message)
    except Exception:
        wx.CallAfter(_destroy_dialog)
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
        except Exception:
            pass
        return False

    wx.CallAfter(_update_dialog, 100, "Tamamlandı")
    wx.CallAfter(_destroy_dialog)
    return True


def _notify_download_complete_and_close():
    """Ana GUI thread'inde çalışır: bilgi verir, güncellemeyi HEMEN
    uygular (yardımcı güncelleyici exe'yi başlatır) ve ardından
    pencereleri kapatmayı dener.

    ÖNEMLİ: Güncellemeyi burada, MainLoop bitmesini beklemeden uygularız.
    Bu oyunda MainMenu, App.OnInit() içinde ShowModal() ile açılıyor;
    henüz "Yeni Oyun/Devam Et" seçilmemişken bu pencereyi Close() ile
    kapatmak, OnInit()'in False dönmesine ve wx'in MainLoop'a HİÇ
    girmeden uygulamayı sonlandırmasına yol açabiliyor. Bu durumda
    MainLoop sonrasına konan kod (main.py'deki apply çağrısı) hiçbir
    zaman çalışmıyordu. Bu yüzden apply işlemini artık burada, pencere
    kapatmadan önce, garanti şekilde tetikliyoruz."""
    try:
        dlg = wx.MessageDialog(
            None,
            "Güncelleme indirildi. Uygulama şimdi kapanıp yeniden başlatılacak.",
            "Güncelleme",
            wx.OK | wx.ICON_INFORMATION,
        )
        dlg.ShowModal()
        dlg.Destroy()
    except Exception as e:
        _log(f"bilgi mesaji gosterilemedi: {e}")

    apply_pending_update_if_ready()

    try:
        for win in list(wx.GetTopLevelWindows()):
            try:
                win.Close(True)
            except Exception:
                pass
    except Exception:
        pass

    # Pencereler bir sebeple kapanmasa/MainLoop düzgün bitmese bile
    # süreç kesin olarak sonlansın diye kısa bir gecikmeyle zorla çık.
    # (Yardımcı güncelleyici exe zaten bağımsız bir süreç olarak
    # başlatıldı, bizim sürecimiz kapanması onu etkilemez.)
    def _force_exit():
        _log("guvenlik agi: surec zorla sonlandiriliyor")
        try:
            wx.GetApp().ExitMainLoop()
        except Exception:
            pass
        os._exit(0)

    threading.Timer(1.5, _force_exit).start()


def is_update_ready() -> bool:
    with _lock:
        path = _update_ready.get("path")
    return bool(path and os.path.exists(path))


def apply_pending_update_if_ready() -> None:
    """
    Uygulama kapanırken (mainloop bittikten hemen sonra) çağrılmalıdır.
    İndirilmiş ve doğrulanmış bir güncelleme varsa, ayrı ve kalıcı
    yardımcı güncelleyici exe'yi (KaraborsaGuncelleyici.exe) küçük bir
    JSON görev dosyasıyla başlatır; asıl kopyalama/yeniden başlatma işini
    bu ayrı süreç üstlenir (bkz. updater_app.py). Herhangi bir sorun
    olursa sessizce hiçbir şey yapmaz; kullanıcı normal şekilde kapanmış
    olur.
    """
    if not _is_frozen():
        return

    with _lock:
        temp_path = _update_ready.get("path")
        new_version = _update_ready.get("version")
        already_applied = _update_ready.get("applied", False)

    _log(
        f"apply_pending_update_if_ready cagrildi, temp_path={temp_path}, "
        f"version={new_version}, already_applied={already_applied}"
    )

    if already_applied:
        _log("bu guncelleme zaten uygulanmis, tekrar calistirilmiyor")
        return

    if not temp_path or not os.path.exists(temp_path) or not new_version:
        _log("uygulanacak guncelleme yok, cikiliyor")
        return

    helper_exe = _ensure_helper_exe_ready()
    if not helper_exe:
        _log("yardimci guncelleyici exe hazirlanamadi, guncelleme uygulanamiyor "
             "(bir sonraki acilista tekrar denenecek)")
        return

    try:
        exe_path = _get_exe_path()
        version_file = _get_local_version_path()
        log_path = os.path.join(_get_update_dir(), _LOG_FILE)
        task_path = os.path.join(_get_update_dir(), _TASK_FILE_NAME)

        task = {
            "pid": os.getpid(),
            "target_exe": exe_path,
            "new_exe": temp_path,
            "new_version": new_version,
            "version_file": version_file,
            "log_file": log_path,
        }
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task, f)

        _log(f"yardimci guncelleyici baslatiliyor: {helper_exe} (gorev: {task_path})")

        # PyInstaller --onefile Job Object'inden kopmak için breakaway
        # bayrağı; olmazsa normal modla dene. Burada artık cmd.exe /
        # bat betiği YOK — doğrudan derlenmiş yardımcı exe çalıştırılıyor.
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_BREAKAWAY_FROM_JOB
        try:
            subprocess.Popen([helper_exe, task_path], creationflags=flags, close_fds=True)
        except OSError as e:
            _log(f"breakaway ile baslatilamadi ({e}), normal modla deneniyor")
            subprocess.Popen(
                [helper_exe, task_path],
                creationflags=subprocess.CREATE_NO_WINDOW,
                close_fds=True,
            )

        _log("yardimci guncelleyici basariyla baslatildi")
        with _lock:
            _update_ready["applied"] = True
    except Exception as e:
        _log(f"yardimci guncelleyici baslatilamadi: {e}")
        # Güncelleme uygulanamadı; bir sonraki açılışta tekrar
        # denenecek (temp_update.exe kalıntısı varsa yeniden indirilip
        # üzerine yazılacaktır).
        pass
