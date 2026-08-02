# -*- coding: utf-8 -*-
"""
updater_app.py
--------------
Ana oyundan TAMAMEN AYRI, küçük ve kalıcı bir yardımcı .exe'nin kaynak
kodu. Derlenmiş hali (KaraborsaGuncelleyici.exe) ana oyunun onefile
paketine gömülür ve ilk çalıştırmada AppData'ya bir kez çıkarılır;
sonrasında orada kalıcı bir yardımcı program olarak durur.

NEDEN AYRI BİR EXE?
--------------------
Eskiden güncelleme, ana oyun exe'si çalışırken kendi kendine ürettiği
bir .bat betiğiyle uygulanıyordu (bkz. eski updater.py). Bu yöntemin
sorunları:
  - Bazı antivirüs / SmartScreen ürünleri "bir exe'nin kendi kendine bat
    üretip cmd.exe ile çalıştırması" davranışını şüpheli buluyor, bat'ı
    karantinaya alabiliyor ya da engelleyebiliyor.
  - "tasklist | find" ile eski sürecin kapanmasını beklemek Windows'un
    dil paketine (yerelleştirmeye) bağlı, kırılgan bir yöntemdi.
  - PyInstaller --onefile süreçleri bir Job Object içinde çalıştığı için
    cmd'nin bundan "breakaway" ile kopması gerekiyordu; bazı ortamlarda
    bu bayrak reddediliyordu.
  - Süreç yeni kapanmışken exe dosyası anlık olarak kilitli kalabiliyor,
    tek seferlik bir "copy" komutu bunu her zaman toleranslı yönetemiyor.

Bu dosya bunların hiçbirine ihtiyaç duymuyor: sadece Python stdlib
kullanıyor (os, sys, json, time, ctypes, subprocess, shutil). wx veya
pygame'e ihtiyacı yok, bu yüzden hem çok küçük hem de antivirüslerin
şüphelenebileceği bağımlılıklardan (ör. ekran görüntüsü/ses kütüphaneleri)
tamamen arınmış durumda.

ÇALIŞMA MANTIĞI:
1) Ana oyun, indirdiği yeni exe'yi ve gerekli bilgileri (hedef exe yolu,
   beklenecek PID, yeni sürüm numarası, sürüm dosyası yolu, log dosyası
   yolu) küçük bir JSON "görev dosyasına" yazar.
2) Ana oyun bu yardımcı exe'yi görev dosyasının yolunu tek komut satırı
   argümanı olarak vererek başlatır ve HEMEN kendi kapanma sürecine
   girer (bkz. updater.py: apply_pending_update_if_ready).
3) Bu yardımcı program:
   a) Ana oyunun PID'sinin GERÇEKTEN kapanmasını Windows API'siyle
      (OpenProcess + WaitForSingleObject) bekler.
   b) İndirilmiş yeni exe'yi, hedef exe'nin üzerine birkaç deneme ile
      (anlık dosya kilitlenmelerine karşı toleranslı) kopyalar.
   c) surum.txt dosyasını yeni sürüm numarasıyla günceller.
   d) Ana oyunu yeniden başlatır.
   e) Görev dosyasını siler ve sessizce kapanır.

Bu yardımcı exe KENDİ KENDİNİ güncellemez; ayrı ve kalıcı bir program
olarak AppData'da durur. Sadece ana oyun exe'si güncellenir. Yardımcı
programın kendisinin değişmesi gerekirse (çok nadir), yeni sürümü ana
oyunla birlikte tekrar gömülür ve boyut farkı tespit edildiğinde
AppData'daki kopyanın üzerine otomatik olarak yazılır (bkz. updater.py:
_ensure_helper_exe_ready).

Herhangi bir adımda beklenmeyen bir hata olursa, fonksiyon sessizce
geri döner ve loglar (varsa) log dosyasına yazılır; bu yardımcı program
asla görünür bir hata penceresi göstermez.
"""

import os
import sys
import json
import time
import shutil
import ctypes
import subprocess
import datetime


def _log(log_path: str, message: str) -> None:
    if not log_path:
        return
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(
                f"[{datetime.datetime.now().isoformat(timespec='seconds')}] "
                f"[Guncelleyici] {message}\n"
            )
    except Exception:
        pass


def _wait_for_pid_exit(pid: int, timeout: float = 60.0) -> bool:
    """
    Windows API ile PID'nin gerçekten kapanmasını bekler.
    "tasklist | find" gibi dile/yerelleştirmeye bağlı bir komut yerine
    doğrudan OpenProcess + WaitForSingleObject kullanır; bu yüzden çok
    daha güvenilirdir ve cmd.exe gerektirmez.

    PID zaten yoksa ya da açılamıyorsa (süreç çoktan kapanmış demektir)
    True döner. Zaman aşımına uğrarsa False döner (yine de çağıran taraf
    kopyalamayı denemeye devam eder; en kötü ihtimalle birkaç deneme
    daha yapılır).
    """
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        SYNCHRONIZE = 0x00100000
        WAIT_TIMEOUT = 0x00000102

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, int(pid)
        )
        if not handle:
            return True

        try:
            result = kernel32.WaitForSingleObject(handle, int(timeout * 1000))
            return result != WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        # ctypes/WinAPI bir sebeple çalışmazsa, yine de devam edebilmek
        # için "kapanmış say" diyoruz; kopyalama denemeleri zaten
        # kilitliyse kendi retry mekanizmasıyla bekleyecek.
        return True


def _copy_with_retry(src: str, dst: str, log_path: str,
                      attempts: int = 12, delay: float = 0.5) -> bool:
    """
    Dosya anlık olarak kilitli olabileceğinden (AV taraması, dosya
    sistemi gecikmesi vb.) kopyalamayı birkaç kez, aralarla dener.
    """
    last_error = None
    for i in range(attempts):
        try:
            shutil.copyfile(src, dst)
            return True
        except Exception as e:
            last_error = e
            _log(log_path, f"kopyalama denemesi {i + 1}/{attempts} basarisiz: {e}")
            time.sleep(delay)
    _log(log_path, f"kopyalama tum denemelerden sonra basarisiz: {last_error}")
    return False


def _fallback_log_path() -> str:
    """
    task.json'daki log_file yolu bile okunamadığında kullanılacak,
    yardımcı exe'nin YANINDAKİ (yani AppData/guncelleme klasöründeki)
    sabit bir yedek log dosyası. Böylece "hiç iz kalmadı" durumu
    ortadan kalkar; her zaman en azından buraya bir satır düşer.
    """
    try:
        base = os.path.dirname(os.path.abspath(sys.argv[0]))
    except Exception:
        base = os.getcwd()
    return os.path.join(base, "guncelleyici_kritik_hata.log")


def main() -> None:
    fallback_log = _fallback_log_path()
    _log(fallback_log, f"guncelleyici baslatildi, argv={sys.argv}")

    if len(sys.argv) < 2:
        _log(fallback_log, "argv eksik: task_path verilmemis, cikiliyor")
        return

    task_path = sys.argv[1]

    try:
        with open(task_path, "r", encoding="utf-8") as f:
            task = json.load(f)
    except Exception as e:
        # Görev dosyası okunamadıysa bile artık bunu bir yere yazıyoruz.
        _log(fallback_log, f"gorev dosyasi okunamadi ({task_path}): {e}")
        return

    log_path = task.get("log_file", "") or fallback_log
    pid = task.get("pid", 0)
    target_exe = task.get("target_exe", "")
    new_exe = task.get("new_exe", "")
    new_version = task.get("new_version", "")
    version_file = task.get("version_file", "")

    _log(
        log_path,
        f"basladi: pid={pid} target={target_exe} new={new_exe} "
        f"version={new_version}",
    )

    if pid:
        exited = _wait_for_pid_exit(pid, timeout=60.0)
        _log(log_path, f"ana surec kapandi mi: {exited}")

    if not new_exe or not os.path.exists(new_exe):
        _log(log_path, "yeni exe bulunamadi, guncelleme iptal")
        return

    if not target_exe:
        _log(log_path, "hedef exe yolu bos, guncelleme iptal")
        return

    ok = _copy_with_retry(new_exe, target_exe, log_path)
    if not ok:
        _log(log_path, "kopyalama basarisiz, guncelleme uygulanamadi, "
                        "bir sonraki acilista tekrar denenecek")
        return

    _log(log_path, "kopyalama basarili")

    try:
        os.remove(new_exe)
    except Exception:
        pass

    if version_file and new_version:
        try:
            with open(version_file, "w", encoding="utf-8") as f:
                f.write(new_version)
            _log(log_path, "surum dosyasi guncellendi")
        except Exception as e:
            _log(log_path, f"surum dosyasi yazilamadi: {e}")

    try:
        subprocess.Popen([target_exe], close_fds=True)
        _log(log_path, "oyun yeniden baslatildi")
    except Exception as e:
        _log(log_path, f"oyun yeniden baslatilamadi: {e}")

    try:
        os.remove(task_path)
    except Exception:
        pass

    _log(log_path, "guncelleyici gorevi tamamladi, kapaniyor")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Buraya kadar hiçbir try/except yakalayamadıysa (ör. os/sys
        # modül seviyesinde beklenmedik bir durum), en azından bunu
        # exe'nin yanındaki sabit log dosyasına yazalım.
        try:
            _log(_fallback_log_path(), f"beklenmeyen kritik hata: {e}")
        except Exception:
            pass
