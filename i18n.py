"""
i18n.py
-------
Lightweight JSON-based translation system for Karaborsa.

- All in-game text is written in English by default (source language).
- Every user-facing string in the code is wrapped with `t("some.key")`
  instead of being hardcoded.
- `locales/en.json` holds the English (source) text for every key.
- `locales/tr.json` (and any other `locales/<lang>.json`) holds the
  translation of each key into that language.
- The in-game "Translation Editor" panel (see translation_editor.py)
  lets someone see the English text for each key and type in the
  Turkish (or any other language, including brand new ones they
  create themselves) translation, saving it straight to the matching
  locale file - no code changes required to add/update a translation.

Where the files live
---------------------
Two different "locales" folders exist:

1. The BUNDLED folder, shipped next to the .exe (or next to this
   .py file when running from source). This is the game's own copy
   of every locale file, the one you as the developer control and
   ship with each release.

2. The USER folder, at %LOCALAPPDATA%\\Karaborsa\\locales. This is
   the one the game actually reads from and writes to at runtime.
   It's writable even when the game is installed somewhere the
   player doesn't have write access to (e.g. Program Files).

The very FIRST time the game runs on a machine (i.e. the user folder
doesn't exist yet), the bundled folder is copied there in full. From
then on the user folder is left alone and is the single source of
truth - any translations added or edited through the Translation
Editor (including brand new languages a player creates themselves)
live only there, and are never overwritten by the game.

The one exception: if a later game update ships NEW keys in the
bundled en.json (e.g. a new screen was added), those specific missing
keys are quietly added to the user's en.json on startup so the new
text has an English fallback to show. This never touches tr.json or
any other language file, and never overwrites a value the user (or a
translator) already set - it only ever fills in keys that don't exist
yet. If you don't want this, delete the `_merge_missing_source_keys()`
call in `_bootstrap()`.

Sharing a new language
-----------------------
A player can use the Translation Editor to create a brand new
language (e.g. German) from scratch, fill it in, and then send you
the resulting file - it's just
%LOCALAPPDATA%\\Karaborsa\\locales\\de.json (the Translation Editor's
"Open Locales Folder" button opens that folder directly). Drop that
file into the bundled locales folder before your next release and
every player will have it built in from their first run.
"""

import json
import os
import shutil
import sys
import threading

_SOURCE_LANGUAGE = "en"
_DEFAULT_LANGUAGE = "en"

# Names for the two languages the game ships with. Any language a
# player creates gets its display name stored in _meta.json instead
# (see _load_meta / create_language) since we can't hardcode names
# for languages we don't know about yet.
_BUILTIN_LANGUAGE_NAMES = {
    "en": "English",
    "tr": "Türkçe",
}


def _bundled_locales_dir() -> str:
    """Where the locale files ship WITH the game (read-only at
    runtime, in practice - this is the install folder)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        # PyInstaller one-file build: data files are unpacked to a
        # temp folder at sys._MEIPASS.
        base = sys._MEIPASS
    elif getattr(sys, "frozen", False):
        # PyInstaller one-folder build: next to the .exe.
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "locales")


def _user_locales_dir() -> str:
    """Where the game actually reads/writes locale files at
    runtime - always writable, survives updates/reinstalls."""
    appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(appdata, "Karaborsa", "locales")


_LOCALES_DIR = _user_locales_dir()
_META_FILE = os.path.join(_LOCALES_DIR, "_meta.json")
_LANG_SETTINGS_FILE = os.path.join(_LOCALES_DIR, "_language.json")

_lock = threading.Lock()
_cache = {}          # lang -> {key: text}
_current_language = _DEFAULT_LANGUAGE
_bootstrapped = False


def _detect_system_language(candidate_codes: list) -> str:
    """Best-effort guess of the player's OS language, used only the
    very first time the game ever runs on a machine (no saved
    preference yet). Falls back to English if detection fails or the
    OS language isn't one of the languages we have available."""
    detected = None

    # Windows: ask the OS directly for the user's UI language, which
    # is far more reliable than environment variables (those are
    # often unset/wrong on Windows, especially for GUI apps launched
    # via a shortcut/exe rather than a terminal).
    if sys.platform == "win32":
        try:
            import ctypes
            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            # LANGID'in düşük baytı birincil dil kimliğidir (LCID
            # MAKELANGID makrosunun tersi); yaygın diller için basit
            # bir eşleme yeterli, tam bir LCID tablosuna gerek yok.
            primary_lang_id = lang_id & 0x3FF
            LANGID_TO_CODE = {
                0x01: "ar", 0x04: "zh", 0x07: "de", 0x09: "en",
                0x0A: "es", 0x0C: "fr", 0x10: "it", 0x11: "ja",
                0x12: "ko", 0x13: "nl", 0x16: "pt", 0x19: "ru",
                0x1F: "tr", 0x22: "uk", 0x29: "fa", 0x2A: "vi",
                0x2D: "eu", 0x30: "el",
            }
            detected = LANGID_TO_CODE.get(primary_lang_id)
        except Exception:
            detected = None

    if not detected:
        try:
            import locale
            sys_locale = locale.getdefaultlocale()[0]  # e.g. 'tr_TR'
            if sys_locale and sys_locale.lower() not in ("c", "posix"):
                detected = sys_locale.split("_")[0].lower()
        except Exception:
            detected = None

    if not detected:
        # locale.getdefaultlocale() only reports a real value if that
        # locale's data is actually installed on the machine, so on a
        # lot of systems (and in minimal/server environments) it just
        # falls back to 'C'. Read the standard POSIX env vars
        # ourselves as a more reliable fallback.
        for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            value = os.environ.get(var)
            if value:
                detected = value.split(":")[0].split(".")[0].split("_")[0].lower()
                break

    if detected and detected in candidate_codes:
        return detected
    return _SOURCE_LANGUAGE


def _bootstrap():
    """Her process başına bir kez çalışır. Kullanıcının klasöründe
    HENÜZ OLMAYAN her .json dil dosyasını (ilk kurulumda hepsi, daha
    sonraki bir güncellemede eklenen YENİ diller de dahil) bundled
    klasörden kopyalar - var olan hiçbir dosyaya asla dokunmaz, o
    yüzden oyuncunun/çevirmenin üzerinde çalıştığı bir dil kesinlikle
    ezilmez. Ayrıca en.json'a (ve varsa _meta.json'a) eksik anahtarları
    ekler - böylece bir oyun güncellemesi yeni metin/yeni dil
    eklediğinde, DAHA ÖNCE bu bilgisayarda çalışmış bir kurulum da
    otomatik olarak bunlara kavuşur."""
    global _bootstrapped
    if _bootstrapped:
        return
    _bootstrapped = True

    bundled_dir = _bundled_locales_dir()

    try:
        os.makedirs(_LOCALES_DIR, exist_ok=True)

        if os.path.isdir(bundled_dir):
            for fname in os.listdir(bundled_dir):
                if not fname.endswith(".json"):
                    continue
                dest_path = os.path.join(_LOCALES_DIR, fname)
                if not os.path.exists(dest_path):
                    # Bu dosya bu bilgisayarda hiç yok - ya gerçek ilk
                    # çalıştırma (hiçbir şey yok), ya da geliştiricinin
                    # SONRADAN eklediği yeni bir dil (ör. de.json). İki
                    # durumda da güvenle tam kopyalanır, çünkü üzerine
                    # yazılacak bir şey yok.
                    shutil.copy2(os.path.join(bundled_dir, fname), dest_path)

        _merge_missing_source_keys(bundled_dir)
        _merge_missing_meta_entries(bundled_dir)
    except Exception as e:
        print(f"[i18n] Could not initialize locales folder: {e}")


def _merge_missing_source_keys(bundled_dir: str):
    """Adds any keys present in a BUNDLED locale file (the developer's
    own shipped translations) but missing from the user's copy of that
    same file - e.g. after a game update added new screens/text (new
    keys land in en.json) or new official Turkish translations (new
    keys land in tr.json). Never overwrites a value that already
    exists in the user's file (so a translator's own edits, or a
    player-created custom language, are never touched) - it only ever
    fills in gaps using the bundled file as the source of truth.

    This runs for EVERY bundled locale file that ships with the game
    (currently en.json and tr.json), not just en.json - a bug fix from
    an earlier version that left tr.json (and any other bundled,
    developer-maintained language) permanently missing new keys on any
    machine that already had a tr.json from a previous version, which
    made new UI text (auction/country screens, etc.) silently fall
    back to English for Turkish players until they wiped their locales
    folder. Locale files that do NOT exist in the bundled folder (a
    language a player created themselves via the Translation Editor)
    are correctly left alone, since there's no bundled source to merge
    from for those."""
    if not os.path.isdir(bundled_dir):
        return

    for fname in os.listdir(bundled_dir):
        if not fname.endswith(".json") or fname.startswith("_"):
            continue
        lang = fname[:-5]
        bundled_path = os.path.join(bundled_dir, fname)
        try:
            with open(bundled_path, "r", encoding="utf-8") as f:
                bundled_locale = json.load(f)
        except Exception:
            continue

        user_locale = _load_locale(lang)
        added = False
        for key, value in bundled_locale.items():
            if key not in user_locale:
                user_locale[key] = value
                added = True

        if added:
            _cache[lang] = user_locale
            try:
                save_locale(lang)
            except Exception as e:
                print(f"[i18n] Could not save merged locale ({lang}): {e}")


def _merge_missing_meta_entries(bundled_dir: str):
    """en.json'daki anahtarlar için yapılan ekleme-birleştirmenin
    aynısını _meta.json (dil görünen adları) için yapar. Örneğin
    geliştirici sonradan 'de.json'u bundled klasöre ekleyip _meta.json'a
    "de": "Deutsch" satırını koyarsa, bu bilgisayarda zaten var olan bir
    kurulum bu ismi otomatik alır - mevcut hiçbir dil adı asla
    değiştirilmez/silinmez."""
    bundled_meta_path = os.path.join(bundled_dir, "_meta.json")
    if not os.path.exists(bundled_meta_path):
        return
    try:
        with open(bundled_meta_path, "r", encoding="utf-8") as f:
            bundled_meta = json.load(f)
    except Exception:
        return

    user_meta = _load_meta()
    added = False
    for code, name in bundled_meta.items():
        if code not in user_meta:
            user_meta[code] = name
            added = True

    if added:
        try:
            _save_meta(user_meta)
        except Exception as e:
            print(f"[i18n] Could not save merged language names: {e}")


def _locale_path(lang: str) -> str:
    return os.path.join(_LOCALES_DIR, f"{lang}.json")


def _load_locale(lang: str) -> dict:
    path = _locale_path(lang)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[i18n] Could not load locale '{lang}': {e}")
        return {}


def _get_locale(lang: str) -> dict:
    _bootstrap()
    with _lock:
        if lang not in _cache:
            _cache[lang] = _load_locale(lang)
        return _cache[lang]


def reload_locales():
    """Clears the in-memory cache so files just edited by the
    Translation Editor (or by hand) are picked up immediately."""
    with _lock:
        _cache.clear()


def _load_meta() -> dict:
    if not os.path.exists(_META_FILE):
        return {}
    try:
        with open(_META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_meta(meta: dict):
    os.makedirs(_LOCALES_DIR, exist_ok=True)
    with open(_META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2, sort_keys=True)


def language_display_name(code: str) -> str:
    if code in _BUILTIN_LANGUAGE_NAMES:
        return _BUILTIN_LANGUAGE_NAMES[code]
    return _load_meta().get(code, code)


def available_languages() -> list:
    """Returns [(code, display_name), ...] for every locales/<code>.json
    file found on disk, source language first. Includes any languages
    a player has created themselves through the Translation Editor."""
    _bootstrap()
    if not os.path.isdir(_LOCALES_DIR):
        return [(_SOURCE_LANGUAGE, language_display_name(_SOURCE_LANGUAGE))]
    codes = []
    for fname in os.listdir(_LOCALES_DIR):
        if fname.endswith(".json") and not fname.startswith("_"):
            codes.append(fname[:-5])
    if _SOURCE_LANGUAGE not in codes:
        codes.append(_SOURCE_LANGUAGE)
    codes.sort(key=lambda c: (c != _SOURCE_LANGUAGE, c))
    return [(c, language_display_name(c)) for c in codes]


def create_language(code: str, display_name: str) -> tuple:
    """Creates a brand new, empty translation file for `code` (e.g.
    'de' for German) so it shows up in the Translation Editor and can
    be filled in from there. Returns (success, message).

    The new file starts empty - every key will show the English text
    until translated, thanks to t()'s fallback chain. Nothing here
    ever overwrites an existing language file."""
    code = (code or "").strip().lower()
    display_name = (display_name or "").strip()

    if not code or not code.replace("-", "").isalnum():
        return False, "Language code must contain only letters/digits (e.g. 'de', 'fr', 'pt-br')."
    if len(code) > 10:
        return False, "Language code is too long."
    if not display_name:
        display_name = code

    path = _locale_path(code)
    if os.path.exists(path):
        return False, f"A language with the code '{code}' already exists."

    os.makedirs(_LOCALES_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({}, f, ensure_ascii=False, indent=2)

    meta = _load_meta()
    meta[code] = display_name
    _save_meta(meta)

    with _lock:
        _cache[code] = {}

    return True, f"'{display_name}' created. Fill it in from the list below."


def get_locales_folder() -> str:
    """The folder the game actually reads/writes locale files from -
    used by the Translation Editor's 'Open Locales Folder' button so
    a player can find a file to send you, or drop one in by hand."""
    _bootstrap()
    os.makedirs(_LOCALES_DIR, exist_ok=True)
    return _LOCALES_DIR


def get_language() -> str:
    return _current_language


def set_language(lang: str, persist: bool = True):
    global _current_language
    _current_language = lang
    if persist:
        try:
            os.makedirs(_LOCALES_DIR, exist_ok=True)
            with open(_LANG_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"language": lang}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[i18n] Could not persist language setting: {e}")


def _restore_saved_language():
    global _current_language
    try:
        _bootstrap()
        if os.path.exists(_LANG_SETTINGS_FILE):
            with open(_LANG_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lang = data.get("language")
                if lang:
                    _current_language = lang
                    return
        # No saved preference yet -> this is the very first run.
        # Guess the player's language from their OS settings among
        # whatever languages are actually available (built-in ones
        # plus any bundled with the game), and remember the choice
        # so this detection only ever runs once.
        candidate_codes = [code for code, _ in available_languages()]
        _current_language = _detect_system_language(candidate_codes)
        set_language(_current_language, persist=True)
    except Exception:
        pass


def t(key, /, **kwargs) -> str:
    """Returns the translated text for `key` in the current language.

    `key` is POSITIONAL-ONLY (the `/` above) on purpose: several
    translation templates legitimately need a placeholder literally
    named "key" (e.g. company.type_choice_line uses {key} for the
    company type's own display name). Before this fix, `def t(key,
    **kwargs)` meant any call like `t("company.type_choice_line",
    key=...)` crashed with "got multiple values for argument 'key'",
    because the caller's key=... kwarg collided with this function's
    own `key` parameter. Making `key` positional-only removes that
    collision entirely: it can only ever bind positionally, so `key=`
    is always free to be used as a template placeholder name.

    Fallback order: current language -> source language (en) -> the
    key itself (so missing translations never crash the game, they
    just show up in English or as a raw key that's easy to spot).

    Every template can use a {currency} placeholder (e.g. "{amount}
    {currency}") without the caller having to pass it explicitly -
    it's auto-filled from the "currency.unit" key, so the entire
    game's money unit can be changed by editing that ONE key instead
    of hunting through every template that mentions an amount.
    """
    text = _get_locale(_current_language).get(key)
    if text is None and _current_language != _SOURCE_LANGUAGE:
        text = _get_locale(_SOURCE_LANGUAGE).get(key)
    if text is None:
        text = key

    if "{currency}" in text and "currency" not in kwargs and key != "currency.unit":
        kwargs["currency"] = t("currency.unit")

    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


def source_text(key: str) -> str:
    """The English (source) text for a key, regardless of the current
    active language. Used by the Translation Editor to show what's
    being translated."""
    return _get_locale(_SOURCE_LANGUAGE).get(key, key)


def translation_for(key: str, lang: str) -> str:
    """Raw translated text for `key` in `lang`, or '' if not yet
    translated (used by the Translation Editor - it needs to tell
    'not translated yet' apart from 'translated to the empty string')."""
    return _get_locale(lang).get(key, "")


def set_translation(key: str, lang: str, text: str, save: bool = True):
    """Sets (and optionally persists to disk) the translation for one
    key in one language. Used by the Translation Editor's Save."""
    locale = _get_locale(lang)
    locale[key] = text
    if save:
        save_locale(lang)


def save_locale(lang: str):
    os.makedirs(_LOCALES_DIR, exist_ok=True)
    locale = _get_locale(lang)
    with open(_locale_path(lang), "w", encoding="utf-8") as f:
        json.dump(locale, f, ensure_ascii=False, indent=2, sort_keys=True)


def all_keys() -> list:
    """Every known key, in the order they appear in the English
    (source) file - that file is the master list."""
    return list(_get_locale(_SOURCE_LANGUAGE).keys())


# Runs once at import time, after every function above is defined -
# restores the player's saved language choice (bootstrapping the
# locales folder on first run if needed along the way).
_restore_saved_language()
