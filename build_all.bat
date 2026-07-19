@echo off
REM ============================================================
REM build_all.bat
REM ------------------------------------------------------------
REM Karaborsa Ticaret Simulasyonu icin TAM derleme betigi.
REM
REM Iki adimi DOGRU SIRAYLA calistirir:
REM   1) build_updater.spec  -> dist\KaraborsaGuncelleyici.exe
REM   2) build.spec          -> dist\KaraborsaSimulasyonu.exe
REM      (1. adimin ciktisini kendi icine gomer)
REM
REM Adim 2, adim 1'in ciktisi olmadan calisamaz (build.spec bunu
REM kontrol edip yoksa hata verir), bu yuzden sirayi bozmayin.
REM
REM Kullanim: Bu dosyayi main.py, updater.py, updater_app.py,
REM build.spec, build_updater.spec ile AYNI klasore koyup
REM cift tiklayin ya da "build_all.bat" yazip calistirin.
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo  1/4 - Python ve PyInstaller kontrolu
echo ============================================================
where python >nul 2>&1
if errorlevel 1 (
    echo [HATA] Python PATH'te bulunamadi. Once Python kurun.
    goto FAIL
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [BILGI] PyInstaller kurulu degil, kuruluyor...
    python -m pip install --upgrade pyinstaller
    if errorlevel 1 (
        echo [HATA] PyInstaller kurulamadi.
        goto FAIL
    )
)

echo.
echo ============================================================
echo  2/4 - Onceki derleme kalintilarini temizleme
echo ============================================================
if exist "build" (
    echo   build\ klasoru siliniyor...
    rmdir /s /q "build"
)
if exist "dist\KaraborsaGuncelleyici.exe" (
    echo   Eski KaraborsaGuncelleyici.exe siliniyor...
    del /f /q "dist\KaraborsaGuncelleyici.exe"
)
if exist "dist\KaraborsaSimulasyonu.exe" (
    echo   Eski KaraborsaSimulasyonu.exe siliniyor...
    del /f /q "dist\KaraborsaSimulasyonu.exe"
)

echo.
echo ============================================================
echo  3/4 - Yardimci guncelleyici deleniyor (build_updater.spec)
echo ============================================================
python -m PyInstaller --noconfirm build_updater.spec
if errorlevel 1 (
    echo [HATA] Yardimci guncelleyici derlenemedi.
    goto FAIL
)
if not exist "dist\KaraborsaGuncelleyici.exe" (
    echo [HATA] dist\KaraborsaGuncelleyici.exe uretilmedi.
    goto FAIL
)
echo   [OK] dist\KaraborsaGuncelleyici.exe uretildi.

echo.
echo ============================================================
echo  4/4 - Ana oyun deleniyor (build.spec)
echo ============================================================
python -m PyInstaller --noconfirm build.spec
if errorlevel 1 (
    echo [HATA] Ana oyun derlenemedi.
    goto FAIL
)
if not exist "dist\KaraborsaSimulasyonu.exe" (
    echo [HATA] dist\KaraborsaSimulasyonu.exe uretilmedi.
    goto FAIL
)

echo.
echo ============================================================
echo  BASARILI
echo ============================================================
echo   dist\KaraborsaGuncelleyici.exe  (gomulu yardimci, dagitmaniza gerek yok)
echo   dist\KaraborsaSimulasyonu.exe   (GitHub release'ine yuklenecek asil dosya)
echo.
pause
exit /b 0

:FAIL
echo.
echo ============================================================
echo  DERLEME BASARISIZ. Yukaridaki hata mesajina bakin.
echo ============================================================
pause
exit /b 1
