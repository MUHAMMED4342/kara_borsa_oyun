@echo off
REM ============================================================
REM build_all.bat  (PYINSTALLER SURUMU)
REM ------------------------------------------------------------
REM Karaborsa Ticaret Simulasyonu icin TAM derleme betigi.
REM
REM Nuitka yerine PYINSTALLER kullanir. C derleyicisi / mingw
REM indirme derdi yoktur, derleme genelde cok daha hizlidir.
REM game_state.py'deki resource_path() zaten sys._MEIPASS'i
REM kontrol ediyor - bu tam olarak PyInstaller'in gomulu
REM dosyalari actigi klasordur, yani DOKUNMANIZA gerek yok.
REM
REM Iki adimi DOGRU SIRAYLA calistirir:
REM   1) updater_app.py -> dist\KaraborsaGuncelleyici.exe
REM   2) main.py         -> dist\KaraborsaSimulasyonu.exe
REM      (1. adimin ciktisini kendi icine gomer)
REM
REM KULLANIM:
REM   build_all.bat            -> normal tam derleme (onefile, konsol kapali)
REM   build_all.bat debug      -> ana oyun konsollu derlenir (hata mesajlarini
REM                                gormek icin - print() ciktilari gorunur)
REM   build_all.bat clean      -> derlemeden ONCE eski build/dist kalintilarini
REM                                siler (PyInstaller cache'i --clean ile de
REM                                temizlenir)
REM   build_all.bat test       -> HIZLI ITERASYON modu: --onedir (onefile
REM                                DEGIL) ile dist\test\ klasorune derler,
REM                                updater'i atlar. Onefile'daki calisma-ani
REM                                kendi kendini acma/sikistirma adimi
REM                                olmadigi icin hem derleme hem ACILIS
REM                                cok daha hizlidir.
REM   Modlar birlikte kullanilabilir, ornek: build_all.bat test debug
REM ============================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

set "CONSOLE_FLAG=--noconsole"
set "DO_CLEAN=0"
set "TEST_MODE=0"

for %%A in (%*) do (
    if /I "%%A"=="debug" set "CONSOLE_FLAG=--console"
    if /I "%%A"=="clean" set "DO_CLEAN=1"
    if /I "%%A"=="test"  set "TEST_MODE=1"
)

if "%CONSOLE_FLAG%"=="--console" echo [BILGI] DEBUG modu: ana oyun konsollu derlenecek.
if "%TEST_MODE%"=="1"            echo [BILGI] TEST modu: hizli --onedir derleme (dist\test\), updater atlanacak.
if "%DO_CLEAN%"=="1"             echo [BILGI] CLEAN modu: eski build/dist kalintilari silinecek.

echo ============================================================
echo  1/5 - Python ve PyInstaller kontrolu
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
echo  2/5 - Onceki derleme kalintilari
echo ============================================================
set "PYI_CLEAN_FLAG="
if "%DO_CLEAN%"=="1" (
    set "PYI_CLEAN_FLAG=--clean"
    if exist "build" (
        echo   build\ klasoru siliniyor...
        rmdir /s /q "build"
    )
    if exist "dist\KaraborsaGuncelleyici.exe" del /f /q "dist\KaraborsaGuncelleyici.exe"
    if exist "dist\KaraborsaSimulasyonu.exe" del /f /q "dist\KaraborsaSimulasyonu.exe"
    if exist "dist\test" rmdir /s /q "dist\test"
) else (
    echo   Atlaniyor. Tam temiz bir build icin: build_all.bat clean
)

echo.
echo ============================================================
echo  3/5 - Zorunlu/istege bagli dosyalarin kontrolu (ana oyun icin)
echo ============================================================
if "%TEST_MODE%"=="1" (
    echo   TEST modunda zorunlu dosya kontrolleri atlaniyor ^(sadece uyari verilir^).
    if not exist "token.txt"   echo   UYARI: token.txt yok.
    if not exist "github.txt"  echo   UYARI: github.txt yok.
    if not exist "locales" (
        echo   UYARI: locales\ klasoru yok - t^(^) her sey icin ham anahtar ^(ornek: "app.name"^) gosterecek.
    )
    for %%F in (insanlar.txt iller.txt ilceler.txt) do (
        if not exist "%%F" echo   UYARI: %%F yok.
    )
) else (
    if not exist "token.txt" (
        echo [HATA] token.txt bulunamadi.
        goto FAIL
    )
    if not exist "github.txt" (
        echo [HATA] github.txt bulunamadi. Bilet ^(destek^) sistemi icin gereken GitHub token dosyasi bu klasorde olmali.
        goto FAIL
    )
    if not exist "locales" (
        echo [HATA] locales\ klasoru bulunamadi. i18n.py bu klasordeki en.json/tr.json dosyalarini bekliyor;
        echo        olmadan TUM arayuz metinleri ham anahtar olarak gorunur ^(ornek: "app.name"^).
        goto FAIL
    )
    if not exist "locales\en.json" (
        echo [HATA] locales\en.json bulunamadi.
        goto FAIL
    )
    if not exist "locales\tr.json" (
        echo [HATA] locales\tr.json bulunamadi.
        goto FAIL
    )
    for %%F in (insanlar.txt iller.txt ilceler.txt) do (
        if not exist "%%F" (
            echo [HATA] %%F bulunamadi. Bu dosya olmadan exe paketlense bile isim/sehir/ilce havuzu bos olacaktir.
            goto FAIL
        )
    )
)

REM Bunlar olmasa da build DURMAZ, sadece uyarir ve add-data'ya eklenmez.
set "EXTRA_DATA_FLAGS="

REM --- ABD/Ingiltere/Avustralya sehir-ilce dosyalari -----------------
REM Bunlar olmadan game_state.py yine de CALISIR (Turkiye verisine
REM otomatik geri doner ve konsola bir [Uyari] yazar) - o yuzden burada
REM sadece UYARI veriyoruz, build'i DURDURMUYORUZ. Ama uyariyi gormeden
REM gecmeyin: eksikse o ulke secildiginde oyuncu sessizce Turkiye
REM sehirleriyle oynar.
for %%F in (iller_us.txt ilceler_us.txt iller_uk.txt ilceler_uk.txt iller_au.txt ilceler_au.txt) do (
    if exist "%%F" (
        set EXTRA_DATA_FLAGS=!EXTRA_DATA_FLAGS! --add-data "%%F;."
    ) else (
        echo   UYARI: %%F bulunamadi - o ulke secilirse oyun otomatik Turkiye verisine donecek.
    )
)

REM --- Yardim sayfalari (en_help.html, tr_help.html, ...) ------------
REM Sabit tek bir "help.html" YOKTUR - game_state.py/dialogs.py her
REM zaman "{dil_kodu}_help.html" arar (open_help / _open_localized_html).
REM Burada klasordeki TUM "*_help.html" dosyalarini otomatik buluyoruz;
REM yeni bir dil icin bir dosya daha eklediginizde bu dongu onu de
REM otomatik yakalar, .bat'i degistirmenize gerek kalmaz. Hicbiri yoksa
REM build durmaz - game_state.create_help_file() calisma aninda o anki
REM dilde minimal bir yardim sayfasi otomatik uretir.
set "HELP_FILE_FOUND=0"
for %%F in (*_help.html) do (
    set EXTRA_DATA_FLAGS=!EXTRA_DATA_FLAGS! --add-data "%%F;."
    set "HELP_FILE_FOUND=1"
)
if "%HELP_FILE_FOUND%"=="0" (
    echo   UYARI: Hicbir *_help.html dosyasi bulunamadi ^(ornek: en_help.html, tr_help.html^) - yardim sayfasi calisma aninda otomatik, minimal bir surumle uretilecek.
)

if exist "release_notes.html" (
    set EXTRA_DATA_FLAGS=!EXTRA_DATA_FLAGS! --add-data "release_notes.html;."
) else (
    echo   UYARI: release_notes.html bulunamadi, paketlenmeyecek.
)

REM Turkce "i" harfi (noktasiz i) icin joker karakter kullaniyoruz -
REM boylece dosya adini .bat icinde harf harf yazmamiza (ve konsolun
REM kod sayfasina bagli kalmamiza) gerek kalmiyor; hangi kod sayfasi
REM aktif olursa olsun dogru dosyayi bulur.
set "GDPR_FILE="
for %%F in (gizlilik*.txt) do set "GDPR_FILE=%%F"
if defined GDPR_FILE (
    set EXTRA_DATA_FLAGS=!EXTRA_DATA_FLAGS! --add-data "!GDPR_FILE!;."
) else (
    echo   UYARI: gizlilik politikasi dosyasi bulunamadi, paketlenmeyecek. Ilk acilis onay ekrani "dosya bulunamadi" yedek metniyle gorunecek.
)

if exist "kullanimsartlari.txt" (
    set EXTRA_DATA_FLAGS=!EXTRA_DATA_FLAGS! --add-data "kullanimsartlari.txt;."
) else (
    echo   UYARI: kullanimsartlari.txt bulunamadi, paketlenmeyecek. Ilk acilis onay ekrani "dosya bulunamadi" yedek metniyle gorunecek.
)

if "%TEST_MODE%"=="1" goto TEST_BUILD

echo.
echo ============================================================
echo  4/5 - Yardimci guncelleyici derleniyor (updater_app.py)
echo ============================================================
python -m PyInstaller ^
    --onefile ^
    --noconsole ^
    %PYI_CLEAN_FLAG% ^
    --distpath dist ^
    --name KaraborsaGuncelleyici ^
    updater_app.py
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
echo  5/5 - Ana oyun derleniyor (main.py)
echo ============================================================
python -m PyInstaller ^
    --onefile ^
    %CONSOLE_FLAG% ^
    %PYI_CLEAN_FLAG% ^
    --collect-all accessible_output2 ^
    --collect-all pygame ^
    --add-data "locales;locales" ^
    --add-data "sounds;sounds" ^
    --add-data "insanlar.txt;." ^
    --add-data "iller.txt;." ^
    --add-data "ilceler.txt;." ^
    --add-data "dist\KaraborsaGuncelleyici.exe;." ^
    --add-data "token.txt;." ^
    --add-data "github.txt;." ^
    !EXTRA_DATA_FLAGS! ^
    --distpath dist ^
    --name KaraborsaSimulasyonu ^
    main.py
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

:TEST_BUILD
echo.
echo ============================================================
echo  TEST BUILD - sadece main.py, --onedir (onefile YOK)
echo ============================================================
echo   Not: Guncelleyici gomulmez, updater butonu bu build'de
echo   calismayacaktir. Sadece hizli kod/ses/erisilebilirlik testi icindir.
python -m PyInstaller ^
    --onedir ^
    %CONSOLE_FLAG% ^
    %PYI_CLEAN_FLAG% ^
    --collect-all accessible_output2 ^
    --collect-all pygame ^
    --add-data "locales;locales" ^
    --add-data "sounds;sounds" ^
    --add-data "insanlar.txt;." ^
    --add-data "iller.txt;." ^
    --add-data "ilceler.txt;." ^
    !EXTRA_DATA_FLAGS! ^
    --distpath dist\test ^
    --name KaraborsaSimulasyonu ^
    main.py
if errorlevel 1 (
    echo [HATA] Test derlemesi basarisiz.
    goto FAIL
)
echo.
echo ============================================================
echo  TEST BUILD TAMAM
echo ============================================================
echo   dist\test\KaraborsaSimulasyonu\KaraborsaSimulasyonu.exe
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
