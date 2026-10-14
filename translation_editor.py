"""
translation_editor.py
----------------------
The in-game Translation Editor panel.

Open it with Ctrl+Alt+L (or the hidden "/dil" command in the developer
console). It lists every text key used in the game, shows the English
(source) text, and gives you an editable box to type the translation
for whichever language you pick at the top (Turkish by default). Hit
"Save" (or just move to the next row - changes are kept in memory and
written to disk on Save/Save All) and the translation is written to
locales/<lang>.json immediately - no restart needed, no code changes.

This is a plain wx.Dialog so it works with the same screen-reader
setup as the rest of the game (every row is keyboard-navigable).
"""

import os
import wx
import i18n


class TranslationEditorDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title="Translation Editor",
                          size=(820, 560),
                          style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.keys = i18n.all_keys()
        self._dirty = False

        outer = wx.BoxSizer(wx.VERTICAL)

        # --- top bar: language picker + search -----------------------
        top = wx.BoxSizer(wx.HORIZONTAL)

        top.Add(wx.StaticText(self, label="Language:"), 0, wx.ALL | wx.CENTER, 6)
        langs = i18n.available_languages()
        self.lang_choice = wx.Choice(
            self, choices=[f"{name} ({code})" for code, name in langs]
        )
        self._lang_codes = [code for code, _ in langs]
        default_lang = "tr" if "tr" in self._lang_codes else self._lang_codes[0]
        self.lang_choice.SetSelection(self._lang_codes.index(default_lang))
        self.lang_choice.Bind(wx.EVT_CHOICE, self.on_language_changed)
        top.Add(self.lang_choice, 0, wx.ALL | wx.CENTER, 6)

        self.new_lang_btn = wx.Button(self, label="New Language...")
        self.new_lang_btn.Bind(wx.EVT_BUTTON, self.on_new_language)
        top.Add(self.new_lang_btn, 0, wx.ALL | wx.CENTER, 6)

        top.Add(wx.StaticText(self, label="Search:"), 0, wx.ALL | wx.CENTER, 6)
        self.search_ctrl = wx.TextCtrl(self)
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search)
        top.Add(self.search_ctrl, 1, wx.ALL | wx.CENTER, 6)

        self.untranslated_only = wx.CheckBox(self, label="Only untranslated")
        self.untranslated_only.Bind(wx.EVT_CHECKBOX, self.on_search)
        top.Add(self.untranslated_only, 0, wx.ALL | wx.CENTER, 6)

        outer.Add(top, 0, wx.EXPAND)

        # --- grid: key | English text | translation -------------------
        self.grid = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.grid.SetName("Translation keys list")
        self.grid.InsertColumn(0, "Key", width=220)
        self.grid.InsertColumn(1, "English (source)", width=280)
        self.grid.InsertColumn(2, "Translation", width=280)
        self.grid.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_row_selected)
        self.grid.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_row_activated)
        outer.Add(self.grid, 1, wx.EXPAND | wx.ALL, 6)

        hint = wx.StaticText(self, label="Tip: press Enter on a row to jump straight to the translation box below.")
        outer.Add(hint, 0, wx.LEFT | wx.BOTTOM, 6)

        # --- edit area for the selected row ----------------------------
        # ÖNEMLİ: Windows'un erişilebilirlik katmanı (MSAA/UIA), bir
        # statik yazıyı "hemen ardından oluşturulan" kontrolün örtük
        # etiketi olarak eşler - bu eşleme OLUŞTURMA SIRASINA göre
        # çalışır, sizer'a ekleme sırasına göre DEĞİL. Bu yüzden her
        # etiket, ait olduğu metin kutusundan HEMEN ÖNCE oluşturulmalı;
        # aksi halde ekran okuyucu yanlış kutuyu yanlış isimle okur
        # (bir önceki denemede tam olarak bu hataya düşülmüştü).
        edit_box = wx.StaticBoxSizer(wx.VERTICAL, self, "Selected key")
        self.key_label = wx.StaticText(self, label="(no key selected)")
        edit_box.Add(self.key_label, 0, wx.ALL, 4)

        english_label = wx.StaticText(self, label="Original (English, read-only):")
        edit_box.Add(english_label, 0, wx.LEFT | wx.TOP, 4)
        self.english_display = wx.TextCtrl(self, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 50))
        self.english_display.SetName("Original English text, read only")
        edit_box.Add(self.english_display, 0, wx.EXPAND | wx.ALL, 4)

        self.translation_label = wx.StaticText(self, label="Translation:")
        edit_box.Add(self.translation_label, 0, wx.LEFT | wx.TOP, 4)
        self.translation_input = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 50))
        edit_box.Add(self.translation_input, 0, wx.EXPAND | wx.ALL, 4)

        row_btns = wx.BoxSizer(wx.HORIZONTAL)
        self.save_row_btn = wx.Button(self, label="Save this translation")
        self.save_row_btn.Bind(wx.EVT_BUTTON, self.on_save_row)
        row_btns.Add(self.save_row_btn, 0, wx.ALL, 4)
        edit_box.Add(row_btns, 0)

        outer.Add(edit_box, 0, wx.EXPAND | wx.ALL, 6)

        # --- bottom buttons ---------------------------------------------
        bottom = wx.BoxSizer(wx.HORIZONTAL)
        self.apply_lang_btn = wx.Button(self, label="Use this language in-game")
        self.apply_lang_btn.Bind(wx.EVT_BUTTON, self.on_apply_language)
        bottom.Add(self.apply_lang_btn, 0, wx.ALL, 4)

        self.open_folder_btn = wx.Button(self, label="Open Locales Folder")
        self.open_folder_btn.Bind(wx.EVT_BUTTON, self.on_open_folder)
        bottom.Add(self.open_folder_btn, 0, wx.ALL, 4)

        bottom.AddStretchSpacer()
        close_btn = wx.Button(self, wx.ID_CLOSE, label="Close")
        close_btn.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))
        bottom.Add(close_btn, 0, wx.ALL, 4)

        outer.Add(bottom, 0, wx.EXPAND)

        self.SetSizer(outer)

        self._current_key = None
        self._update_translation_label()
        self._populate_grid()
        if self.grid.GetItemCount():
            self.grid.Select(0)
            self.grid.Focus(0)

    # -- helpers ------------------------------------------------------

    @property
    def current_lang(self) -> str:
        return self._lang_codes[self.lang_choice.GetSelection()]

    def _update_translation_label(self):
        """'Translation:' etiketini seçili dilin adıyla günceller (ör.
        'French translation:') - böylece yeni bir dil ekleyen biri
        hangi kutuya yazması gerektiğini tahmin etmek zorunda kalmaz.
        SetLabel() tek başına bazı durumlarda ekranı hemen yenilemez,
        bu yüzden sonunda Layout()/Refresh() ile zorluyoruz. SetName()
        ise görsel etiketten bağımsız olarak ekran okuyucunun
        duyuracağı erişilebilir ismi belirliyor - ikisi birbirinin
        yerini tutmaz, ikisi de gerekli."""
        lang_name = i18n.language_display_name(self.current_lang)
        self.translation_label.SetLabel(f"{lang_name} translation:")
        self.translation_input.SetName(f"{lang_name} translation")
        header = self.grid.GetColumn(2)
        header.SetText(f"{lang_name} translation")
        self.grid.SetColumn(2, header)
        self.translation_label.GetParent().Layout()
        self.translation_label.Refresh()
        self.grid.Refresh()

    def _populate_grid(self):
        self.grid.DeleteAllItems()
        query = self.search_ctrl.GetValue().strip().lower()
        only_untranslated = self.untranslated_only.GetValue()
        lang = self.current_lang

        for key in self.keys:
            english = i18n.source_text(key)
            translation = i18n.translation_for(key, lang)

            if only_untranslated and translation:
                continue
            if query and query not in key.lower() and query not in english.lower():
                continue

            idx = self.grid.InsertItem(self.grid.GetItemCount(), key)
            self.grid.SetItem(idx, 1, english)
            self.grid.SetItem(idx, 2, translation if translation else "(not translated)")

    def on_search(self, event):
        self._populate_grid()

    def on_language_changed(self, event):
        self._update_translation_label()
        self._populate_grid()
        if self._current_key:
            self.translation_input.SetValue(
                i18n.translation_for(self._current_key, self.current_lang)
            )

    def on_row_selected(self, event):
        idx = event.GetIndex()
        key = self.grid.GetItemText(idx, 0)
        self._current_key = key
        self.key_label.SetLabel(key)
        self.english_display.SetValue(i18n.source_text(key))
        self.translation_input.SetValue(i18n.translation_for(key, self.current_lang))

    def on_row_activated(self, event):
        """Enter tuşu (ya da çift tık) bir satırda basıldığında tetiklenir.
        Ekran okuyucu kullanıcıları için en güvenilir yol budur - Tab
        sırasına güvenmek yerine, satırı 'aktive edince' doğrudan çeviri
        kutusuna odaklanır ve içindeki metni seçili hale getirir, böylece
        yazmaya hemen başlanabilir."""
        self.on_row_selected(event)
        self.translation_input.SetFocus()
        self.translation_input.SelectAll()

    def on_save_row(self, event):
        if not self._current_key:
            return
        lang = self.current_lang
        text = self.translation_input.GetValue()
        i18n.set_translation(self._current_key, lang, text, save=True)
        self._populate_grid()
        # Reselect the same key after refresh so you can keep typing
        # through the list without losing your place.
        for i in range(self.grid.GetItemCount()):
            if self.grid.GetItemText(i, 0) == self._current_key:
                self.grid.Select(i)
                self.grid.Focus(i)
                break
        wx.MessageBox(f"Saved '{self._current_key}' to {lang}.json",
                       "Saved", wx.OK | wx.ICON_INFORMATION)

    def on_apply_language(self, event):
        i18n.set_language(self.current_lang)
        wx.MessageBox(
            "The game will use this language for any new text shown from now on.",
            "Language changed", wx.OK | wx.ICON_INFORMATION,
        )

    def on_new_language(self, event):
        """Lets someone create a brand new language from scratch (not
        just edit Turkish). It starts completely empty - every line
        shows English until translated - and shows up in the language
        list immediately, ready to fill in below."""
        code_dlg = wx.TextEntryDialog(
            self,
            "Language code (e.g. 'de' for German, 'fr' for French, 'pt-br' for Brazilian Portuguese):",
            "New Language - Step 1 of 2"
        )
        if code_dlg.ShowModal() != wx.ID_OK:
            code_dlg.Destroy()
            return
        code = code_dlg.GetValue().strip()
        code_dlg.Destroy()
        if not code:
            return

        name_dlg = wx.TextEntryDialog(
            self,
            "Display name for this language (shown in the language list):",
            "New Language - Step 2 of 2",
            value=code,
        )
        if name_dlg.ShowModal() != wx.ID_OK:
            name_dlg.Destroy()
            return
        display_name = name_dlg.GetValue().strip()
        name_dlg.Destroy()

        success, message = i18n.create_language(code, display_name)
        if not success:
            wx.MessageBox(message, "Could Not Create Language", wx.OK | wx.ICON_ERROR)
            return

        # Dil listesini yenile ve yeni dili seçili hale getir, böylece
        # kullanıcı hemen çevirmeye başlayabilir.
        langs = i18n.available_languages()
        self.lang_choice.SetItems([f"{name} ({c})" for c, name in langs])
        self._lang_codes = [c for c, _ in langs]
        self.lang_choice.SetSelection(self._lang_codes.index(code.lower()))
        self._update_translation_label()
        self._populate_grid()
        if self._current_key:
            self.translation_input.SetValue(
                i18n.translation_for(self._current_key, self.current_lang)
            )

        wx.MessageBox(message, "Language Created", wx.OK | wx.ICON_INFORMATION)

    def on_open_folder(self, event):
        """Opens the folder the game actually reads/writes translations
        from (%LOCALAPPDATA%\\Karaborsa\\locales). This is where to
        find a finished language file to send to the developer, or
        where to drop one in by hand."""
        folder = i18n.get_locales_folder()
        try:
            os.startfile(folder)
        except AttributeError:
            # os.startfile Windows'a özgü; başka bir platformda
            # çalışıyorsa klasörü mesajla göster.
            wx.MessageBox(folder, "Locales Folder", wx.OK | wx.ICON_INFORMATION)
        except OSError as e:
            wx.MessageBox(f"Could not open folder:\n{e}\n\n{folder}",
                           "Error", wx.OK | wx.ICON_ERROR)
