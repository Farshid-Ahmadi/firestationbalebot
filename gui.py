# -*- coding: utf-8 -*-
import os
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter import font as tkfont
import arabic_reshaper
from bidi import get_display

from file_manager import Messages, QuickResponses, Subjects, Preferences


BASE_DIR = Path(__file__).resolve().parent
MAIN_PATH = BASE_DIR / "main.py"
CHAT_HISTORY_DIR = BASE_DIR / "Chat History"


class AdminGUI(tk.Tk):
    _BIDI_CONTROL_TRANSLATION = str.maketrans("", "", "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")

    def __init__(self):
        super().__init__()
        self.title("پنل گرافیکی مدیریت ربات آتش‌نشانی")
        self.geometry("1200x800")
        self.minsize(1000, 700)
        self._setup_fonts()

        self.bot_process = None
        self.bot_output_thread = None

        self.messages = Messages()
        self.quick = QuickResponses()
        self.subjects = Subjects()
        self.preferences = Preferences()

        self._build_ui()
        self._load_all()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_fonts(self):
        """Pick fonts that render Persian text and emojis better across OSes."""
        families = set(tkfont.families())

        persian_candidates = [
            "Noto Naskh Arabic",
            "Noto Sans Arabic",
            "Tahoma",
            "Vazirmatn",
            "IRANSans",
            "Segoe UI",
            "DejaVu Sans",
            "Arial",
        ]

        picked = None
        for name in persian_candidates:
            if name in families:
                picked = name
                break
        if not picked:
            picked = tkfont.nametofont("TkDefaultFont").cget("family")

        self.ui_font = (picked, 10)
        self.ui_font_bold = (picked, 10, "bold")

        # Apply to tkinter default fonts.
        for tk_name in ["TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkCaptionFont"]:
            try:
                tkfont.nametofont(tk_name).configure(family=picked, size=10)
            except Exception:
                pass

    def _rtl(self, text: str) -> str:
        cleaned = self._clean_bidi_controls(text)
        if not cleaned:
            return ""
        has_arabic = any("\u0600" <= ch <= "\u06ff" for ch in cleaned)
        if not has_arabic:
            return cleaned
        try:
            return get_display(arabic_reshaper.reshape(cleaned))
        except Exception:
            return cleaned

    def _clean_bidi_controls(self, text: str) -> str:
        """Remove invisible bidi control chars that can reverse/break Persian display."""
        return (text or "").translate(self._BIDI_CONTROL_TRANSLATION)

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)

        self.btn_start_bot = ttk.Button(top, text=self._rtl("اجرای ربات (main.py)"), command=self.start_bot)
        self.btn_start_bot.pack(side="right")
        self.btn_stop_bot = ttk.Button(top, text=self._rtl("توقف ربات"), command=self.stop_bot)
        self.btn_stop_bot.pack(side="right", padx=6)

        self.lbl_status = ttk.Label(top, text=self._rtl("وضعیت ربات: متوقف"))
        self.lbl_status.pack(side="right", padx=12)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self._build_messages_tab()
        self._build_quick_tab()
        self._build_subjects_tab()
        self._build_settings_tab()
        self._build_history_tab()
        self._build_bot_log_tab()

    def _build_messages_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self._rtl("پیام‌ها"))

        left = ttk.Frame(tab)
        left.pack(side="right", fill="y", padx=8, pady=8)
        right = ttk.Frame(tab)
        right.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        self.lst_messages = tk.Listbox(left, width=35, exportselection=False, justify="right")
        self.lst_messages.pack(fill="y", expand=True)
        self.lst_messages.bind("<<ListboxSelect>>", self._on_select_message_key)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text=self._rtl("بارگذاری مجدد"), command=self.load_messages).pack(side="right")

        ttk.Label(right, text=self._rtl("متن پیام"), anchor="e", justify="right").pack(anchor="e")
        self.txt_message_value = tk.Text(right, wrap="word")
        self.txt_message_value.pack(fill="both", expand=True)
        self.txt_message_value.tag_configure("rtl", justify="right")
        ttk.Button(right, text=self._rtl("ذخیره پیام انتخاب‌شده"), command=self.save_selected_message).pack(anchor="e", pady=6)

    def _build_quick_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self._rtl("پاسخ‌های سریع"))

        top = ttk.Frame(tab)
        top.pack(fill="both", expand=True, padx=8, pady=8)

        left_box = ttk.LabelFrame(top, text=self._rtl("انتقاد"))
        left_box.pack(side="right", fill="both", expand=True, padx=4)
        right_box = ttk.LabelFrame(top, text=self._rtl("گزارش"))
        right_box.pack(side="right", fill="both", expand=True, padx=4)

        self.lst_quick_crit = tk.Listbox(left_box, exportselection=False, justify="right")
        self.lst_quick_crit.pack(fill="both", expand=True, padx=4, pady=4)
        self.lst_quick_report = tk.Listbox(right_box, exportselection=False, justify="right")
        self.lst_quick_report.pack(fill="both", expand=True, padx=4, pady=4)

        c_btns = ttk.Frame(left_box)
        c_btns.pack(fill="x", padx=4, pady=4)
        ttk.Button(c_btns, text=self._rtl("افزودن"), command=lambda: self.quick_add("crit")).pack(side="right")
        ttk.Button(c_btns, text=self._rtl("ویرایش"), command=lambda: self.quick_edit("crit")).pack(side="right", padx=4)
        ttk.Button(c_btns, text=self._rtl("حذف"), command=lambda: self.quick_remove("crit")).pack(side="right")

        r_btns = ttk.Frame(right_box)
        r_btns.pack(fill="x", padx=4, pady=4)
        ttk.Button(r_btns, text=self._rtl("افزودن"), command=lambda: self.quick_add("report")).pack(side="right")
        ttk.Button(r_btns, text=self._rtl("ویرایش"), command=lambda: self.quick_edit("report")).pack(side="right", padx=4)
        ttk.Button(r_btns, text=self._rtl("حذف"), command=lambda: self.quick_remove("report")).pack(side="right")

        ttk.Button(tab, text=self._rtl("بارگذاری مجدد"), command=self.load_quick).pack(anchor="e", padx=8, pady=8)

    def _build_subjects_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self._rtl("موضوعات و متن‌های آماده"))

        root = ttk.Frame(tab)
        root.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.LabelFrame(root, text=self._rtl("موضوعات"))
        left.pack(side="right", fill="both", expand=True, padx=4)
        right = ttk.LabelFrame(root, text=self._rtl("متن‌های آماده موضوع انتخاب‌شده"))
        right.pack(side="right", fill="both", expand=True, padx=4)

        self.lst_subjects = tk.Listbox(left, exportselection=False, justify="right")
        self.lst_subjects.pack(fill="both", expand=True, padx=4, pady=4)
        self.lst_subjects.bind("<<ListboxSelect>>", self._on_select_subject)

        s_btns = ttk.Frame(left)
        s_btns.pack(fill="x", padx=4, pady=4)
        ttk.Button(s_btns, text=self._rtl("افزودن"), command=self.subject_add).pack(side="right")
        ttk.Button(s_btns, text=self._rtl("ویرایش"), command=self.subject_edit).pack(side="right", padx=4)
        ttk.Button(s_btns, text=self._rtl("حذف"), command=self.subject_remove).pack(side="right")

        self.lst_defined = tk.Listbox(right, exportselection=False, justify="right")
        self.lst_defined.pack(fill="both", expand=True, padx=4, pady=4)

        d_btns = ttk.Frame(right)
        d_btns.pack(fill="x", padx=4, pady=4)
        ttk.Button(d_btns, text=self._rtl("افزودن"), command=self.defined_add).pack(side="right")
        ttk.Button(d_btns, text=self._rtl("ویرایش"), command=self.defined_edit).pack(side="right", padx=4)
        ttk.Button(d_btns, text=self._rtl("حذف"), command=self.defined_remove).pack(side="right")

        ttk.Button(tab, text=self._rtl("بارگذاری مجدد"), command=self.load_subjects).pack(anchor="e", padx=8, pady=8)

    def _build_settings_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self._rtl("تنظیمات"))

        frm = ttk.Frame(tab)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=0)

        self.var_crit_enable = tk.BooleanVar()
        self.var_crit_anon = tk.BooleanVar()
        self.var_crit_text = tk.StringVar()
        self.var_target_cmd = tk.StringVar()
        self.var_active_exp = tk.StringVar()
        self.var_chat_life = tk.StringVar()
        self.var_admin_password = tk.StringVar()
        self.var_admin_ban_hours = tk.StringVar()

        row = 0
        ttk.Checkbutton(frm, text=self._rtl("انتقاد فعال"), variable=self.var_crit_enable).grid(
            row=row, column=1, columnspan=2, sticky="e"
        )
        row += 1
        ttk.Checkbutton(frm, text=self._rtl("انتقاد ناشناس"), variable=self.var_crit_anon).grid(
            row=row, column=1, columnspan=2, sticky="e"
        )
        row += 1
        self._add_labeled_entry(frm, row, "متن موضوع انتقاد:", self.var_crit_text)
        row += 1
        self._add_labeled_entry(frm, row, "دستور تعیین گروه:", self.var_target_cmd)
        row += 1
        self._add_labeled_entry(frm, row, "عمر گفتگوی فعال (ساعت):", self.var_active_exp)
        row += 1
        self._add_labeled_entry(frm, row, "مدت پاسخ‌گویی (ساعت):", self.var_chat_life)
        row += 1
        self._add_labeled_entry(frm, row, "رمز ادمین:", self.var_admin_password)
        row += 1
        self._add_labeled_entry(frm, row, "محدودیت رمز اشتباه (ساعت):", self.var_admin_ban_hours)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=2, sticky="e", pady=10)
        ttk.Button(btns, text=self._rtl("بارگذاری مجدد"), command=self.load_settings).pack(side="right")
        ttk.Button(btns, text=self._rtl("ذخیره"), command=self.save_settings).pack(side="right", padx=6)

    def _add_labeled_entry(self, parent, row, label, var):
        ttk.Label(parent, text=self._rtl(label), anchor="e", justify="right").grid(row=row, column=1, sticky="e", pady=4, padx=(10, 0))
        entry = ttk.Entry(parent, textvariable=var, width=50, justify="right")
        entry.grid(row=row, column=0, sticky="e", pady=4)

    def _build_history_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self._rtl("تاریخچه گفتگو"))

        left = ttk.Frame(tab)
        left.pack(side="right", fill="y", padx=8, pady=8)
        right = ttk.Frame(tab)
        right.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        self.lst_history_files = tk.Listbox(left, width=35, exportselection=False, justify="right")
        self.lst_history_files.pack(fill="y", expand=True)
        self.lst_history_files.bind("<<ListboxSelect>>", self._on_select_history_file)

        ttk.Button(left, text=self._rtl("بارگذاری مجدد"), command=self.load_history_files).pack(fill="x", pady=6)

        self.lst_history_entries = tk.Listbox(right, height=12, exportselection=False, justify="right")
        self.lst_history_entries.pack(fill="x")
        self.lst_history_entries.bind("<<ListboxSelect>>", self._on_select_history_entry)

        self.txt_history_entry = tk.Text(right, wrap="word")
        self.txt_history_entry.pack(fill="both", expand=True, pady=6)
        self.txt_history_entry.tag_configure("rtl", justify="right")

    def _build_bot_log_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=self._rtl("خروجی ربات"))
        self.txt_bot_log = tk.Text(tab, wrap="word")
        self.txt_bot_log.pack(fill="both", expand=True, padx=8, pady=8)

    def _load_all(self):
        self.load_messages()
        self.load_quick()
        self.load_subjects()
        self.load_settings()
        self.load_history_files()

    # ---------------- Bot process ----------------
    def start_bot(self):
        if self.bot_process and self.bot_process.poll() is None:
            messagebox.showinfo("Info", "Bot is already running.")
            return

        if not MAIN_PATH.exists():
            messagebox.showerror("Error", f"main.py not found at:\n{MAIN_PATH}")
            return

        try:
            self.bot_process = subprocess.Popen(
                [sys.executable, "-u", str(MAIN_PATH)],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.lbl_status.config(text=f"Bot Status: Running (PID {self.bot_process.pid})")
            self._append_log("Bot started.\n")
            self.bot_output_thread = threading.Thread(target=self._stream_bot_output, daemon=True)
            self.bot_output_thread.start()
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to run bot:\n{exc}")

    def stop_bot(self):
        if not self.bot_process or self.bot_process.poll() is not None:
            self.lbl_status.config(text="Bot Status: Stopped")
            return
        self.bot_process.terminate()
        try:
            self.bot_process.wait(timeout=5)
        except Exception:
            self.bot_process.kill()
        self.lbl_status.config(text="Bot Status: Stopped")
        self._append_log("Bot stopped.\n")

    def _stream_bot_output(self):
        if not self.bot_process or not self.bot_process.stdout:
            return
        for line in self.bot_process.stdout:
            self.after(0, self._append_log, line)
        self.after(0, self.lbl_status.config, {"text": "Bot Status: Stopped"})

    def _append_log(self, text):
        self.txt_bot_log.insert("end", text)
        self.txt_bot_log.see("end")

    # ---------------- Messages ----------------
    def load_messages(self):
        self.messages = Messages()
        self.lst_messages.delete(0, "end")
        self.message_keys = sorted(self.messages.getAllMessages().keys())
        for key in self.message_keys:
            self.lst_messages.insert("end", self._rtl(key))
        self.txt_message_value.delete("1.0", "end")

    def _on_select_message_key(self, _event=None):
        sel = self.lst_messages.curselection()
        if not sel:
            return
        key = self.message_keys[sel[0]]
        self.txt_message_value.delete("1.0", "end")
        self.txt_message_value.insert("1.0", self._rtl(self.messages.get(key)), "rtl")

    def save_selected_message(self):
        sel = self.lst_messages.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a message key first.")
            return
        key = self.message_keys[sel[0]]
        value = self._clean_bidi_controls(self.txt_message_value.get("1.0", "end").strip())
        self.messages.set(key, value)
        messagebox.showinfo("Saved", "Message updated.")

    # ---------------- Quick responses ----------------
    def load_quick(self):
        self.quick = QuickResponses()
        self.lst_quick_crit.delete(0, "end")
        self.lst_quick_report.delete(0, "end")

        self.quick_crit = [self._clean_bidi_controls(item) for item in self.quick.getCriticismQuickResponse()]
        self.quick_report = [self._clean_bidi_controls(item) for item in self.quick.getReportQuickResponses()]

        for item in self.quick_crit:
            self.lst_quick_crit.insert("end", self._rtl(item))
        for item in self.quick_report:
            self.lst_quick_report.insert("end", self._rtl(item))

    def quick_add(self, kind):
        text = simpledialog.askstring("Add", "Enter new text:")
        if not text:
            return
        text = self._clean_bidi_controls(text.strip())
        if not text:
            return
        if kind == "crit":
            self.quick.addCriticismQuickResponse(text)
        else:
            self.quick.addReportQuickResponse(text)
        self.load_quick()

    def quick_edit(self, kind):
        if kind == "crit":
            sel = self.lst_quick_crit.curselection()
            items = self.quick_crit
            set_func = self.quick.setCriticismQuickResponse
        else:
            sel = self.lst_quick_report.curselection()
            items = self.quick_report
            set_func = self.quick.setReportQuickResponse

        if not sel:
            messagebox.showwarning("Warning", "Select an item first.")
            return
        idx = sel[0] + 1
        old = items[sel[0]]
        new = simpledialog.askstring("Edit", "Edit text:", initialvalue=old)
        if not new:
            return
        new = self._clean_bidi_controls(new.strip())
        if not new:
            return
        set_func(str(idx), new)
        self.load_quick()

    def quick_remove(self, kind):
        if kind == "crit":
            sel = self.lst_quick_crit.curselection()
            rem_func = self.quick.removeCriticismQuickResponse
        else:
            sel = self.lst_quick_report.curselection()
            rem_func = self.quick.removeReportQuickResponse
        if not sel:
            messagebox.showwarning("Warning", "Select an item first.")
            return
        rem_func(str(sel[0] + 1))
        self.load_quick()

    # ---------------- Subjects ----------------
    def load_subjects(self):
        self.subjects = Subjects()
        self.subject_names = list(self.subjects.keys())
        self.lst_subjects.delete(0, "end")
        for s in self.subject_names:
            self.lst_subjects.insert("end", self._rtl(s))
        self.lst_defined.delete(0, "end")
        self.defined_items = []

    def _on_select_subject(self, _event=None):
        self.lst_defined.delete(0, "end")
        self.defined_items = []
        sel = self.lst_subjects.curselection()
        if not sel:
            return
        subject = self.subject_names[sel[0]]
        self.defined_items = [self._clean_bidi_controls(item) for item in self.subjects.getDefinedTexts(subject)]
        for item in self.defined_items:
            self.lst_defined.insert("end", self._rtl(item))

    def subject_add(self):
        text = simpledialog.askstring("Add Subject", "Subject text:")
        if not text:
            return
        text = self._clean_bidi_controls(text.strip())
        if not text:
            return
        idx = simpledialog.askinteger("Add Subject", "Position (optional):", minvalue=1)
        self.subjects.addSubject(text, idx)
        self.load_subjects()

    def subject_edit(self):
        sel = self.lst_subjects.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a subject first.")
            return
        old = self.subject_names[sel[0]]
        new = simpledialog.askstring("Edit Subject", "New subject text:", initialvalue=old)
        if not new:
            return
        new = self._clean_bidi_controls(new.strip())
        if not new:
            return
        self.subjects.editSubjects(old, new)
        self.load_subjects()

    def subject_remove(self):
        sel = self.lst_subjects.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a subject first.")
            return
        self.subjects.removeSubject(self.subject_names[sel[0]])
        self.load_subjects()

    def defined_add(self):
        sel = self.lst_subjects.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Select a subject first.")
            return
        subject = self.subject_names[sel[0]]
        text = simpledialog.askstring("Add Defined Text", "Text:")
        if not text:
            return
        text = self._clean_bidi_controls(text.strip())
        if not text:
            return
        idx = simpledialog.askinteger("Add Defined Text", "Position (optional):", minvalue=1)
        self.subjects.addDefinedText(subject, text, idx)
        self.load_subjects()
        self._reselect_subject(subject)

    def defined_edit(self):
        ssel = self.lst_subjects.curselection()
        dsel = self.lst_defined.curselection()
        if not ssel or not dsel:
            messagebox.showwarning("Warning", "Select a subject and a defined text first.")
            return
        subject = self.subject_names[ssel[0]]
        idx = dsel[0] + 1
        old = self.defined_items[dsel[0]]
        new = simpledialog.askstring("Edit Defined Text", "New text:", initialvalue=old)
        if not new:
            return
        new = self._clean_bidi_controls(new.strip())
        if not new:
            return
        self.subjects.editDefinedText(subject, idx, new)
        self.load_subjects()
        self._reselect_subject(subject)

    def defined_remove(self):
        ssel = self.lst_subjects.curselection()
        dsel = self.lst_defined.curselection()
        if not ssel or not dsel:
            messagebox.showwarning("Warning", "Select a subject and a defined text first.")
            return
        subject = self.subject_names[ssel[0]]
        idx = dsel[0] + 1
        self.subjects.removeDefinedText(subject, idx)
        self.load_subjects()
        self._reselect_subject(subject)

    def _reselect_subject(self, subject):
        if subject in self.subject_names:
            idx = self.subject_names.index(subject)
            self.lst_subjects.selection_clear(0, "end")
            self.lst_subjects.selection_set(idx)
            self.lst_subjects.activate(idx)
            self._on_select_subject()

    # ---------------- Settings ----------------
    def load_settings(self):
        self.preferences = Preferences()
        self.var_crit_enable.set(self.preferences.isCriticismEnabled())
        self.var_crit_anon.set(self.preferences.isCriticismAnonymous())
        self.var_crit_text.set(self._rtl(self.preferences.getCriticismText()))
        self.var_target_cmd.set(self._rtl(self.preferences.getSetTargetCommand()))
        self.var_active_exp.set(self.preferences.getActiveChatExpiration())
        self.var_chat_life.set(self.preferences.getChatLifeSpan())
        self.var_admin_password.set(self._rtl(self.preferences.getAdminPassword()))
        self.var_admin_ban_hours.set(self.preferences.getAdminRequestBanDuration())

    def save_settings(self):
        try:
            if int(self.var_active_exp.get()) < 1 or int(self.var_chat_life.get()) < 1:
                raise ValueError("Report hours must be >= 1")
            if int(self.var_admin_ban_hours.get()) < 1:
                raise ValueError("Admin ban hours must be >= 1")
        except Exception as exc:
            messagebox.showerror("Validation Error", str(exc))
            return

        self.preferences.setCriticismEnabled(self.var_crit_enable.get())
        self.preferences.setCriticismAnonymous(self.var_crit_anon.get())
        self.preferences.setCriticismText(self._clean_bidi_controls(self.var_crit_text.get().strip()))
        self.preferences.setSetTargetCommand(self._clean_bidi_controls(self.var_target_cmd.get().strip()))
        self.preferences.setActiveChatExpiration(self.var_active_exp.get().strip())
        self.preferences.setChatLifeSpan(self.var_chat_life.get().strip())
        self.preferences.setAdminPassword(self._clean_bidi_controls(self.var_admin_password.get().strip()))
        self.preferences.setAdminRequestBanDuration(self.var_admin_ban_hours.get().strip())
        messagebox.showinfo("Saved", "Settings updated.")
        self.load_settings()

    # ---------------- Chat history ----------------
    def load_history_files(self):
        self.lst_history_files.delete(0, "end")
        self.lst_history_entries.delete(0, "end")
        self.txt_history_entry.delete("1.0", "end")
        self.history_entries = []

        if not CHAT_HISTORY_DIR.exists():
            return
        self.history_files = sorted(
            [p for p in CHAT_HISTORY_DIR.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in self.history_files:
            self.lst_history_files.insert("end", self._rtl(p.name))

    def _on_select_history_file(self, _event=None):
        sel = self.lst_history_files.curselection()
        if not sel:
            return
        file_path = self.history_files[sel[0]]
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("Read Error", str(exc))
            return

        self.history_entries = self._split_history_entries(content)
        self.lst_history_entries.delete(0, "end")
        self.txt_history_entry.delete("1.0", "end")
        for i, entry in enumerate(self.history_entries, start=1):
            first_line = entry.splitlines()[0] if entry.strip() else "(empty)"
            preview = first_line if len(first_line) <= 80 else first_line[:77] + "..."
            self.lst_history_entries.insert("end", self._rtl(f"{i}) {preview}"))

    def _on_select_history_entry(self, _event=None):
        sel = self.lst_history_entries.curselection()
        if not sel:
            return
        entry = self.history_entries[sel[0]]
        self.txt_history_entry.delete("1.0", "end")
        self.txt_history_entry.insert("1.0", self._rtl(entry), "rtl")

    def _split_history_entries(self, content):
        entries = []
        current = []
        for line in content.splitlines():
            if line.strip() == "----------":
                block = "\n".join(current).strip()
                if block:
                    entries.append(block)
                current = []
            else:
                current.append(line)
        block = "\n".join(current).strip()
        if block:
            entries.append(block)
        return entries

    def _on_close(self):
        self.stop_bot()
        self.destroy()


def main():
    os.chdir(BASE_DIR)
    app = AdminGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
