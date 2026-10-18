"""
anti_cheat.py
-------------
Skor tablosu olduğu için, Cheat Engine çalışırken oyunun oynanmasını
engelleyen basit bir koruma. Windows'ta çalışan işlemleri ve pencere
başlıklarını tarar (ctypes; ek paket gerekmez). Windows dışında hiçbir
şey yapmaz.

NOT: Bu, kararlı biriyle başa çıkacak bir koruma DEĞİLDİR (oyun açık
kaynak, işlem adı değiştirilebilir). Amacı, sıradan kullanımı engellemek
ve bir oturumda hile aracı görüldüyse o oturumda skor göndermeyi ve haftalık
ödülü kapatmaktır. Gerçek güvence ancak skorun sunucu tarafında
doğrulanmasıyla sağlanabilir.
"""

import re
import sys
import time

# İşlem adında (küçük harfle) bu parçalardan biri geçerse hile aracı sayılır.
BLOCKED_PROCESS_PARTS = ("cheatengine", "cheat engine", "cheat-engine")

# Pencere başlığı bu kalıpla BAŞTAN SONA eşleşirse (ör. "Cheat Engine 7.5")
# ve pencerenin sahibi bir tarayıcı DEĞİLSE hile aracı sayılır. Tarayıcı
# sekmesinde "Cheat Engine" yazması (haber/forum okumak) yanlış alarm
# vermesin diye tarayıcılar hariç tutulur.
_WINDOW_TITLE_RE = re.compile(r"^cheat engine( v?\d[\d.]*)?$", re.IGNORECASE)
_BROWSERS = ("chrome.exe", "firefox.exe", "msedge.exe", "opera.exe",
             "brave.exe", "vivaldi.exe", "iexplore.exe", "safari.exe")

_tainted = False


def is_tainted() -> bool:
    """Bu oturumda hile aracı görüldü mü? Görüldüyse skor gönderimi ve
    haftalık ödül, araç kapatılmış olsa bile oturum boyunca kapalı kalır."""
    return _tainted


def mark_tainted() -> None:
    global _tainted
    _tainted = True


def _snapshot_processes() -> dict:
    """{pid: exe_adı_küçük_harf}. Hata olursa boş sözlük."""
    if not sys.platform.startswith("win"):
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * 260),
            ]

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        k32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        k32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        k32.CloseHandle.argtypes = [wintypes.HANDLE]

        TH32CS_SNAPPROCESS = 0x00000002
        snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snap in (None, -1, ctypes.c_void_p(-1).value):
            return {}
        procs = {}
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = k32.Process32FirstW(snap, ctypes.byref(entry))
            while ok:
                procs[entry.th32ProcessID] = entry.szExeFile.lower()
                ok = k32.Process32NextW(snap, ctypes.byref(entry))
        finally:
            k32.CloseHandle(snap)
        return procs
    except Exception:
        return {}


def _visible_window_titles() -> list:
    """[(pid, başlık)] - görünür üst düzey pencereler."""
    if not sys.platform.startswith("win"):
        return []
    try:
        import ctypes
        from ctypes import wintypes

        u32 = ctypes.WinDLL("user32", use_last_error=True)
        result = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def _cb(hwnd, lparam):
            try:
                if u32.IsWindowVisible(hwnd):
                    length = u32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        u32.GetWindowTextW(hwnd, buf, length + 1)
                        pid = wintypes.DWORD()
                        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        result.append((pid.value, buf.value))
            except Exception:
                pass
            return True

        u32.EnumWindows(WNDENUMPROC(_cb), 0)
        return result
    except Exception:
        return []


def find_cheat_tool():
    """Çalışan bir hile aracı bulursa adını (işlem adı veya pencere
    başlığı), yoksa None döner. Hiçbir koşulda istisna fırlatmaz."""
    try:
        procs = _snapshot_processes()
        for name in procs.values():
            if any(part in name for part in BLOCKED_PROCESS_PARTS):
                return name
        for pid, title in _visible_window_titles():
            if _WINDOW_TITLE_RE.match(title.strip()):
                if procs.get(pid, "") not in _BROWSERS:
                    return title
    except Exception:
        pass
    return None


def show_blocking_message(parent=None) -> int:
    """Uyarıyı hem gösterir hem ekran okuyucuya okutur. wx.ID_OK ('Tekrar
    dene') veya wx.ID_CANCEL ('Kapat' - oyundan çık) döner."""
    import wx
    from i18n import t
    message = t("anticheat.cheat_engine_detected")
    try:
        from accessibility_helper import speak
        speak(message)
    except Exception:
        pass
    dlg = wx.MessageDialog(
        parent, message, "Cheat Engine",
        wx.OK | wx.CANCEL | wx.ICON_WARNING,
    )
    dlg.SetOKCancelLabels(t("anticheat.try_again_btn"), t("common.close"))
    result = dlg.ShowModal()
    dlg.Destroy()
    return result


def ensure_clear(parent=None) -> bool:
    """Hile aracı kapanana kadar uyarıyı tekrar gösterir. Araç kapandıysa
    True, oyuncu 'Kapat' dediyse False döner (çağıran oyundan çıkmalı)."""
    import wx
    while find_cheat_tool():
        mark_tainted()
        if show_blocking_message(parent) == wx.ID_CANCEL:
            return False
        time.sleep(1.0)  # kapanan işlemin listeden düşmesi için kısa bekleme
    return True
