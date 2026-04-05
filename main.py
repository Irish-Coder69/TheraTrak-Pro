"""
TheraTrak Pro
Combined therapy practice management + CMS-1500 billing application.
Merges the functionality of Notes 444 (H: drive) and CMS1500v6 (E: drive).

Python 3.10+  ·  Tkinter + ttk  ·  SQLite backend
"""

import json
import os
import re
import shutil
import subprocess
import sys
import traceback
import tkinter as tk
import tkinter.font as tkFont
import urllib.request
import webbrowser
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

import database as db
import version_manager as vm
from app_paths import APP_ROOT, ASSETS_DIR, DB_FILE, ICON_FILE, VERSION_FILE

# ─── Colour / Style constants ──────────────────────────────────────────────────

BG       = "#f0f4f8"
HDR_BG   = "#1e3a5f"
HDR_FG   = "#ffffff"
ACCENT   = "#2563eb"
ACCENT2  = "#1d4ed8"
SUCCESS  = "#16a34a"
DANGER   = "#dc2626"
MUTED    = "#6b7280"
ROW_ODD  = "#ffffff"
ROW_EVEN = "#eff6ff"
SEL_BG   = "#bfdbfe"

FONT_UI   = ("Arial", 12)
FONT_SM   = ("Arial", 12)
FONT_LG   = ("Arial", 12, "bold")
FONT_H1   = ("Arial", 12, "bold")
FONT_MONO = ("Arial", 12)

SESSION_TYPES  = ["Individual", "Group", "Couples/Family", "Intake/Evaluation", "Crisis", "Telehealth"]
PLACE_CODES    = [("11 – Office", "11"), ("02 – Telehealth", "02"), ("12 – Home", "12"),
                  ("21 – Inpatient Hospital", "21"), ("22 – Outpatient Hospital", "22"),
                  ("23 – Emergency Room", "23")]
CPT_CODES      = ["90791", "90792", "90832", "90834", "90837", "90845",
                  "90846", "90847", "90853", "90863", "99213", "99214"]

STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
          "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
          "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
          "VA","WA","WV","WI","WY","DC"]

GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/Irish-Coder69/TheraTrak-Pro/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/Irish-Coder69/TheraTrak-Pro/releases/latest"
UPDATE_TEMP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Temp" / "TheraTrakUpdates"
STARTUP_LOG_FILE = APP_ROOT / "startup.log"


# ─── Utilities ─────────────────────────────────────────────────────────────────

def _append_startup_log(message: str):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with STARTUP_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except OSError:
        pass


def _startup_self_check():
    _append_startup_log("=== Application startup ===")
    _append_startup_log(f"Executable: {sys.executable}")
    _append_startup_log(f"Python: {sys.version.split()[0]}")
    _append_startup_log(f"App root: {APP_ROOT}")
    _append_startup_log(f"CWD: {Path.cwd()}")

    checks = [
        ("ICON_FILE", ICON_FILE),
        ("VERSION_FILE", VERSION_FILE),
        ("DB_FILE", DB_FILE),
    ]
    for name, path in checks:
        _append_startup_log(f"{name}: {'OK' if path.exists() else 'MISSING'} ({path})")


def _install_crash_logger():
    def _handle_uncaught(exc_type, exc_value, exc_tb):
        _append_startup_log("Uncaught exception:")
        _append_startup_log("".join(traceback.format_exception(exc_type, exc_value, exc_tb)).rstrip())
        try:
            messagebox.showerror(
                "TheraTrak Pro Error",
                "An unexpected error occurred.\n\n"
                f"Details were written to:\n{STARTUP_LOG_FILE}"
            )
        except Exception:
            pass

    sys.excepthook = _handle_uncaught

def ttk_style():
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    # Force Arial 12 as the default for all classic Tk widgets
    style.master.option_add("*Font", ("Arial", 12))
    style.master.option_add("*Text.Font", ("Arial", 12))
    style.master.option_add("*Entry.Font", ("Arial", 12))
    style.configure("TFrame",       background=BG)
    style.configure("TLabel",       background=BG, font=FONT_UI)
    style.configure("TButton",      font=FONT_UI, padding=4)
    style.configure("TEntry",       font=FONT_UI, padding=3)
    style.configure("TCombobox",    font=FONT_UI)
    style.configure("TNotebook",    background=HDR_BG, tabmargins=[2, 4, 2, 0])
    style.configure("TNotebook.Tab",background=HDR_BG, foreground="white",
                    font=("Arial", 12, "bold"), padding=[10, 5])
    style.map("TNotebook.Tab",
              background=[("selected", BG), ("active", ACCENT)],
              foreground=[("selected", HDR_BG), ("active", "white")])
    style.configure("Accent.TButton", background=ACCENT,  foreground="white",
                    font=("Arial", 12, "bold"), padding=5)
    style.map("Accent.TButton",
              background=[("active", ACCENT2), ("pressed", ACCENT2)])
    style.configure("Danger.TButton", background=DANGER, foreground="white",
                    font=("Arial", 12, "bold"), padding=5)
    style.configure("Treeview",       font=FONT_UI, rowheight=24,
                    background=ROW_ODD, fieldbackground=ROW_ODD)
    style.configure("Treeview.Heading", font=("Arial", 12, "bold"),
                    background=HDR_BG, foreground="white")
    style.map("Treeview", background=[("selected", SEL_BG)],
              foreground=[("selected", "#1e3a5f")])
    return style


def lframe(parent, text, **kw):
    """Labelled ttk.LabelFrame with consistent styling."""
    f = ttk.LabelFrame(parent, text=text, padding=8, **kw)
    return f


def btn(parent, text, cmd, style="TButton", **kw):
    return ttk.Button(parent, text=text, command=cmd, style=style, **kw)


def labeled_entry(parent, label, row, col=0, width=20, colspan=1):
    """Place a Label + Entry pair at grid position (row, col)."""
    ttk.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=(4, 2), pady=2)
    var = tk.StringVar()
    e = ttk.Entry(parent, textvariable=var, width=width)
    e.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=2,
           columnspan=colspan)
    return var, e


def labeled_combo(parent, label, values, row, col=0, width=18):
    ttk.Label(parent, text=label).grid(row=row, column=col, sticky="e", padx=(4, 2), pady=2)
    var = tk.StringVar()
    c = ttk.Combobox(parent, textvariable=var, values=values, width=width, state="readonly")
    c.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=2)
    return var, c


def current_date_str():
    return date.today().strftime("%Y-%m-%d")


def fmt_date(d: str) -> str:
    """YYYY-MM-DD → MM/DD/YYYY display string."""
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return d or ""


def fmt_money(v) -> str:
    try:
        return f"${float(v):.2f}"
    except (ValueError, TypeError):
        return "$0.00"


def apply_window_icon(window):
    try:
        if ICON_FILE.exists():
            window.iconbitmap(default=str(ICON_FILE))
    except tk.TclError:
        pass


class UserDirectoryDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        apply_window_icon(self)
        self.title("User Directory")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{max(1150, screen_w - 30)}x{max(540, screen_h - 90)}+0+0")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._edit_uid = None
        self._rows = []
        self._vars = {}
        self._active_var = tk.BooleanVar(value=True)
        self._build()
        self._load_users()
        self.grab_set()

    def _build(self):
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)

        # ── Left: treeview ───────────────────────────────────────────────────
        left = ttk.Frame(container)
        left.pack(side="left", fill="both", expand=True)

        cols = ("id", "username", "name", "role", "email", "phone", "active")
        self.tv = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [
            ("id", "ID", 40),
            ("username", "Username", 120),
            ("name", "Name", 170),
            ("role", "Role", 90),
            ("email", "Email", 180),
            ("phone", "Phone", 110),
            ("active", "Active", 70),
        ]:
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=w, stretch=c in ("name", "email"))

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)

        # ── Right: edit form ─────────────────────────────────────────────────
        right_outer = lframe(container, "Edit User")
        right_outer.pack(side="left", fill="both", expand=True, padx=(8, 0))

        scroll_canvas = tk.Canvas(right_outer, background=BG, highlightthickness=0)
        vsb2 = ttk.Scrollbar(right_outer, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=vsb2.set)
        scroll_canvas.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        form = ttk.Frame(scroll_canvas)
        fid = scroll_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfigure(fid, width=e.width))

        def fv(name):
            v = tk.StringVar()
            self._vars[name] = v
            return v

        # Full-width entry (spans all 6 data columns)
        def fe(lbl, name, r):
            ttk.Label(form, text=lbl).grid(row=r, column=0, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(name)).grid(row=r, column=1, columnspan=5, sticky="ew", padx=(0, 8), pady=3)

        # Two-field row  (label | entry | label | entry)
        def fe2(lbl1, n1, lbl2, n2, r):
            ttk.Label(form, text=lbl1).grid(row=r, column=0, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n1)).grid(row=r, column=1, sticky="ew", padx=(0, 4), pady=3)
            ttk.Label(form, text=lbl2).grid(row=r, column=2, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n2)).grid(row=r, column=3, sticky="ew", padx=(0, 8), pady=3)

        # Three-field row (label | entry | label | entry | label | entry)
        def fe3(lbl1, n1, lbl2, n2, lbl3, n3, r):
            ttk.Label(form, text=lbl1).grid(row=r, column=0, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n1)).grid(row=r, column=1, sticky="ew", padx=(0, 4), pady=3)
            ttk.Label(form, text=lbl2).grid(row=r, column=2, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n2)).grid(row=r, column=3, sticky="ew", padx=(0, 4), pady=3)
            ttk.Label(form, text=lbl3).grid(row=r, column=4, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(form, textvariable=fv(n3)).grid(row=r, column=5, sticky="ew", padx=(0, 8), pady=3)

        for c in (1, 3, 5):
            form.columnconfigure(c, weight=1)

        # ── Read-only info row
        info_frm = ttk.Frame(form)
        info_frm.grid(row=0, column=0, columnspan=6, sticky="ew", padx=4, pady=(4, 2))
        self._info_id    = ttk.Label(info_frm, text="ID: —",          foreground="#888")
        self._info_cr    = ttk.Label(info_frm, text="Created: —",     foreground="#888")
        self._info_login = ttk.Label(info_frm, text="Last Login: —",  foreground="#888")
        self._info_id.pack(side="left", padx=(0, 14))
        self._info_cr.pack(side="left", padx=(0, 14))
        self._info_login.pack(side="left")

        ttk.Separator(form, orient="horizontal").grid(row=1, column=0, columnspan=6, sticky="ew", pady=(2, 6))

        # ── Identity
        fe("Username:", "username", 2)
        fe2("First Name:", "first_name", "Last Name:", "last_name", 3)
        ttk.Label(form, text="Middle Name:").grid(row=4, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(form, textvariable=fv("middle_name")).grid(row=4, column=1, sticky="ew", padx=(0, 4), pady=3)
        ttk.Label(form, text="Role:").grid(row=4, column=4, sticky="e", padx=(4, 2), pady=3)
        ttk.Combobox(
            form, textvariable=fv("role"),
            values=["Admin", "User", "Provider", "Billing", "Read-Only"],
            state="readonly",
        ).grid(row=4, column=5, sticky="ew", padx=(0, 8), pady=3)

        ttk.Separator(form, orient="horizontal").grid(row=5, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Contact
        fe2("Email:", "email", "Phone:", "phone", 6)
        fe2("Taxonomy Codes:", "license_number", "NPI #:", "npi_number", 7)

        ttk.Separator(form, orient="horizontal").grid(row=8, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Primary address
        ttk.Label(form, text="Address:", font=("Arial", 9, "bold")).grid(row=9, column=0, columnspan=6, sticky="w", padx=4, pady=(2, 0))
        fe("Street:", "address", 10)
        fe3("City:", "city", "State:", "state", "Zip:", "zip", 11)

        ttk.Separator(form, orient="horizontal").grid(row=12, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Billing address
        ttk.Label(form, text="Billing Address:", font=("Arial", 9, "bold")).grid(row=13, column=0, columnspan=6, sticky="w", padx=4, pady=(2, 0))
        fe("Street:", "billing_address", 14)
        fe3("City:", "billing_city", "State:", "billing_state", "Zip:", "billing_zip", 15)

        ttk.Separator(form, orient="horizontal").grid(row=16, column=0, columnspan=6, sticky="ew", pady=6)

        # ── Password & active
        ttk.Label(form, text="New Password:").grid(row=17, column=0, sticky="e", padx=(4, 2), pady=3)
        ttk.Entry(form, textvariable=fv("password"), show="*").grid(row=17, column=1, columnspan=3, sticky="ew", padx=(0, 4), pady=3)
        ttk.Label(form, text="(leave blank to keep current)", foreground="#888").grid(row=17, column=4, columnspan=2, sticky="w", padx=(0, 8))

        ttk.Checkbutton(form, text="Active", variable=self._active_var).grid(
            row=18, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 4)
        )

        # ── Bottom buttons ───────────────────────────────────────────────────
        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        btn(bottom, "+ Add User", self._add_user).pack(side="left", padx=(0, 4))
        btn(bottom, "Refresh", self._load_users).pack(side="left")
        btn(bottom, "Save Changes", self._save_changes, "Accent.TButton").pack(side="right")
        btn(bottom, "Close", self.destroy).pack(side="right", padx=(0, 4))

    def _load_users(self):
        self._rows = db.get_all_users()
        self.tv.delete(*self.tv.get_children())
        for r in self._rows:
            name = f"{r['first_name']} {r['last_name']}"
            self.tv.insert(
                "", "end", iid=str(r["id"]),
                values=(r["id"], r["username"], name, r["role"],
                        r["email"], r["phone"], "Yes" if r["is_active"] else "No"),
            )

    def _on_select(self, event=None):
        sel = self.tv.selection()
        if not sel:
            return
        uid = int(sel[0])
        row = next((r for r in self._rows if r["id"] == uid), None)
        if not row:
            return
        self._edit_uid = uid
        for key in ("username", "first_name", "middle_name", "last_name",
            "email", "phone", "role", "license_number", "npi_number",
                    "address", "city", "state", "zip",
                    "billing_address", "billing_city", "billing_state", "billing_zip"):
            self._vars[key].set(str(row[key] or ""))
        self._vars["password"].set("")
        self._active_var.set(bool(row["is_active"]))
        self._info_id.config(text=f"ID: {row['id']}")
        self._info_cr.config(text=f"Created: {row['created_at'] or '—'}")
        self._info_login.config(text=f"Last Login: {row['last_login'] or 'Never'}")

    def _save_changes(self):
        if self._edit_uid is None:
            messagebox.showinfo("Select", "Please select a user to edit.", parent=self)
            return
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["is_active"] = int(self._active_var.get())
        try:
            db.update_user(self._edit_uid, data)
        except ValueError as e:
            messagebox.showerror("Validation Error", str(e), parent=self)
            return
        messagebox.showinfo("Saved", "User updated successfully.", parent=self)
        self._vars["password"].set("")
        self._load_users()

    def _add_user(self):
        CreateAccountDialog(self)
        self.after(600, self._load_users)


class CreateAccountDialog(tk.Toplevel):
    def __init__(self, parent, after_create=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.after_create = after_create
        self.title("Create Account")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{max(1000, screen_w - 30)}x{max(700, screen_h - 90)}+0+0")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._vars = {}
        self._billing_widgets = {}
        self._same_addr_var = tk.BooleanVar(value=False)
        self._build()
        self.grab_set()

    def _field(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)  # left spacer
        outer.columnconfigure(1, weight=0)  # content
        outer.columnconfigure(2, weight=1)  # right spacer
        outer.rowconfigure(0, weight=1)

        frm = ttk.Frame(outer, padding=20)
        frm.grid(row=0, column=1, sticky="n", pady=120)
        frm.columnconfigure(0, weight=0, minsize=130)
        frm.columnconfigure(1, weight=0, minsize=200)
        frm.columnconfigure(2, weight=0, minsize=40)  # spacer
        frm.columnconfigure(3, weight=0, minsize=160)
        frm.columnconfigure(4, weight=0, minsize=200)

        # ── Title ────────────────────────────────────────────────
        ttk.Label(frm, text="Create User Account", font=FONT_H1).grid(
            row=0, column=0, columnspan=5, sticky="w", pady=(0, 10))

        # ── Row 1: First Name | Username ─────────────────────────
        ttk.Label(frm, text="First Name*").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        _e_first = ttk.Entry(frm, textvariable=self._field("first_name"), width=24)
        _e_first.grid(row=1, column=1, sticky="w")
        ttk.Label(frm, text="Username*").grid(row=1, column=3, sticky="e", padx=4, pady=4)
        _e_username = ttk.Entry(frm, textvariable=self._field("username"), width=24)
        _e_username.grid(row=1, column=4, sticky="w")

        # ── Row 2: Middle Name | Password ────────────────────────
        ttk.Label(frm, text="Middle Name").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        _e_middle = ttk.Entry(frm, textvariable=self._field("middle_name"), width=24)
        _e_middle.grid(row=2, column=1, sticky="w")
        ttk.Label(frm, text="Password*").grid(row=2, column=3, sticky="e", padx=4, pady=4)
        _e_password = ttk.Entry(frm, textvariable=self._field("password"), show="*", width=24)
        _e_password.grid(row=2, column=4, sticky="w")

        # ── Row 3: Last Name | Confirm Password ──────────────────
        ttk.Label(frm, text="Last Name*").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        _e_last = ttk.Entry(frm, textvariable=self._field("last_name"), width=24)
        _e_last.grid(row=3, column=1, sticky="w")
        ttk.Label(frm, text="Confirm Password*").grid(row=3, column=3, sticky="e", padx=4, pady=4)
        _e_confirm = ttk.Entry(frm, textvariable=self._field("confirm_password"), show="*", width=24)
        _e_confirm.grid(row=3, column=4, sticky="w")

        # ── Row 4: Show Password toggle ───────────────────────────
        _show_pw_var = tk.BooleanVar(value=False)
        def _toggle_show_pw():
            ch = "" if _show_pw_var.get() else "*"
            _e_password.config(show=ch)
            _e_confirm.config(show=ch)
        ttk.Checkbutton(
            frm, text="Show Password", variable=_show_pw_var,
            command=_toggle_show_pw
        ).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # ── Row 5: Phone | Role ───────────────────────────────────
        ttk.Label(frm, text="Phone").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        _e_phone = ttk.Entry(frm, textvariable=self._field("phone"), width=24)
        _e_phone.grid(row=5, column=1, sticky="w")
        ttk.Label(frm, text="Role").grid(row=5, column=3, sticky="e", padx=4, pady=4)
        _cb_role = ttk.Combobox(frm, textvariable=self._field("role", "User"),
                     values=["Admin", "User", "Billing", "ReadOnly"],
                     width=21, state="readonly")
        _cb_role.grid(row=5, column=4, sticky="w")

        # ── Row 6: Email | (empty right) ─────────────────────────
        ttk.Label(frm, text="Email").grid(row=6, column=0, sticky="e", padx=4, pady=4)
        _e_email = ttk.Entry(frm, textvariable=self._field("email"), width=24)
        _e_email.grid(row=6, column=1, sticky="w")

        # ── Mailing Address header ────────────────────────────────
        ttk.Separator(frm, orient="horizontal").grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 2))
        ttk.Label(frm, text="Mailing Address", font=FONT_LG).grid(row=8, column=0, columnspan=2, sticky="w", padx=4, pady=(0, 2))

        # ── Billing Address header (same row) ─────────────────────
        ttk.Separator(frm, orient="horizontal").grid(row=7, column=3, columnspan=2, sticky="ew", pady=(10, 2))
        ttk.Label(frm, text="Billing Address", font=FONT_LG).grid(row=8, column=3, columnspan=2, sticky="w", padx=4, pady=(0, 2))
        ttk.Checkbutton(
            frm, text="Same as mailing address",
            variable=self._same_addr_var,
            command=self._toggle_same_addr
        ).grid(row=9, column=3, columnspan=2, sticky="w", padx=4, pady=(0, 4))

        # ── Mailing | Billing fields ──────────────────────────────
        ttk.Label(frm, text="Address").grid(row=9, column=0, sticky="e", padx=4, pady=4)
        _e_address = ttk.Entry(frm, textvariable=self._field("address"), width=28)
        _e_address.grid(row=9, column=1, sticky="w")

        ttk.Label(frm, text="Billing Address").grid(row=10, column=3, sticky="e", padx=4, pady=4)
        _ba = ttk.Entry(frm, textvariable=self._field("billing_address"), width=24)
        _ba.grid(row=10, column=4, sticky="w")
        self._billing_widgets["billing_address"] = _ba

        ttk.Label(frm, text="City").grid(row=10, column=0, sticky="e", padx=4, pady=4)
        _e_city = ttk.Entry(frm, textvariable=self._field("city"), width=24)
        _e_city.grid(row=10, column=1, sticky="w")

        ttk.Label(frm, text="Billing City").grid(row=11, column=3, sticky="e", padx=4, pady=4)
        _bc = ttk.Entry(frm, textvariable=self._field("billing_city"), width=24)
        _bc.grid(row=11, column=4, sticky="w")
        self._billing_widgets["billing_city"] = _bc

        ttk.Label(frm, text="State").grid(row=11, column=0, sticky="e", padx=4, pady=4)
        _cb_state = ttk.Combobox(frm, textvariable=self._field("state"), values=STATES, width=8, state="readonly")
        _cb_state.grid(row=11, column=1, sticky="w")

        ttk.Label(frm, text="Billing State").grid(row=12, column=3, sticky="e", padx=4, pady=4)
        _bs = ttk.Combobox(frm, textvariable=self._field("billing_state"), values=STATES, width=8, state="readonly")
        _bs.grid(row=12, column=4, sticky="w")
        self._billing_widgets["billing_state"] = _bs

        ttk.Label(frm, text="Zip").grid(row=12, column=0, sticky="e", padx=4, pady=4)
        _e_zip = ttk.Entry(frm, textvariable=self._field("zip"), width=12)
        _e_zip.grid(row=12, column=1, sticky="w")

        ttk.Label(frm, text="Billing Zip").grid(row=13, column=3, sticky="e", padx=4, pady=4)
        _bz = ttk.Entry(frm, textvariable=self._field("billing_zip"), width=12)
        _bz.grid(row=13, column=4, sticky="w")
        self._billing_widgets["billing_zip"] = _bz

        # ── Taxonomy / NPI ───────────────────────────────────────
        ttk.Label(frm, text="Taxonomy Codes*").grid(row=13, column=0, sticky="e", padx=4, pady=4)
        _e_license = ttk.Entry(frm, textvariable=self._field("license_number"), width=24)
        _e_license.grid(row=13, column=1, sticky="w")

        ttk.Label(frm, text="NPI Number*").grid(row=14, column=0, sticky="e", padx=4, pady=4)
        _e_npi = ttk.Entry(frm, textvariable=self._field("npi_number"), width=24)
        _e_npi.grid(row=14, column=1, sticky="w")

        # ── Tab order: left column top→bottom, then right column ──
        self._set_tab_order([
            _e_first, _e_middle, _e_last, _e_phone, _e_email,
            _e_address, _e_city, _cb_state, _e_zip, _e_license, _e_npi,
            _e_username, _e_password, _e_confirm, _cb_role,
            self._billing_widgets["billing_address"],
            self._billing_widgets["billing_city"],
            self._billing_widgets["billing_state"],
            self._billing_widgets["billing_zip"],
        ])

        # ── Footer ────────────────────────────────────────────────
        msg = "Password must be at least 8 characters. Required fields are marked with *"
        ttk.Label(frm, text=msg, foreground=MUTED).grid(row=15, column=0, columnspan=5, sticky="w", pady=(6, 2))

        bottom = ttk.Frame(frm)
        bottom.grid(row=16, column=0, columnspan=5, sticky="ew", pady=(10, 0))
        btn(bottom, "Create Account", self._create, "Accent.TButton").pack(side="left", padx=4)
        btn(bottom, "Cancel", self.destroy).pack(side="left")

    def _set_tab_order(self, widgets):
        """Bind Tab/Shift-Tab to enforce left-column-first traversal."""
        for i, w in enumerate(widgets):
            nw = widgets[(i + 1) % len(widgets)]
            pw = widgets[(i - 1) % len(widgets)]
            w.bind("<Tab>", lambda e, nw=nw: nw.focus_set() or "break")
            w.bind("<Shift-Tab>", lambda e, pw=pw: pw.focus_set() or "break")

    def _toggle_same_addr(self):
        if self._same_addr_var.get():
            self._vars["billing_address"].set(self._vars.get("address", tk.StringVar()).get())
            self._vars["billing_city"].set(self._vars.get("city", tk.StringVar()).get())
            self._vars["billing_state"].set(self._vars.get("state", tk.StringVar()).get())
            self._vars["billing_zip"].set(self._vars.get("zip", tk.StringVar()).get())
            for w in self._billing_widgets.values():
                w.config(state="disabled")
        else:
            for w in self._billing_widgets.values():
                w.config(state="normal" if not isinstance(w, ttk.Combobox) else "readonly")

    def _create(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        password = data.pop("password", "")
        confirm_password = data.pop("confirm_password", "")
        if password != confirm_password:
            messagebox.showerror("Password", "Password and confirm password do not match.", parent=self)
            return
        data["password"] = password
        try:
            db.create_user(data)
        except ValueError as ex:
            messagebox.showerror("Create Account", str(ex), parent=self)
            return
        except Exception as ex:
            messagebox.showerror("Create Account", f"Could not create account: {ex}", parent=self)
            return

        messagebox.showinfo("Account Created", "User account created successfully.", parent=self)
        if self.after_create:
            self.after_create(data.get("username", ""))
        self.destroy()


class LoginDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        apply_window_icon(self)
        self.user = None
        self.title("TheraTrak Pro Login")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{max(1000, screen_w - 30)}x{max(700, screen_h - 90)}+0+0")
        self.resizable(True, True)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass
        self._build()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _build(self):
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        center = ttk.Frame(frm)
        center.pack(expand=True)

        ttk.Label(center, text="TheraTrak Pro", font=FONT_H1).pack(anchor="center")

        self.v_user = tk.StringVar()
        self.v_pass = tk.StringVar()

        row1 = ttk.Frame(center)
        row1.pack(pady=3)
        ttk.Label(row1, text="Username", width=12).pack(side="left")
        e_user = ttk.Entry(row1, textvariable=self.v_user, width=30)
        e_user.pack(side="left")

        row2 = ttk.Frame(center)
        row2.pack(pady=3)
        ttk.Label(row2, text="Password", width=12).pack(side="left")
        e_pass = ttk.Entry(row2, textvariable=self.v_pass, width=30, show="*")
        e_pass.pack(side="left")

        _show_pw_var = tk.BooleanVar(value=False)
        row3 = ttk.Frame(center)
        row3.pack()
        ttk.Label(row3, width=12).pack(side="left")  # spacer to align with labels above
        ttk.Checkbutton(
            row3, text="Show Password", variable=_show_pw_var,
            command=lambda: e_pass.config(show="" if _show_pw_var.get() else "*")
        ).pack(side="left")

        self.lbl_msg = ttk.Label(center, text="", foreground=DANGER)
        self.lbl_msg.pack(anchor="center", pady=(5, 2))

        action = ttk.Frame(center)
        action.pack(pady=(8, 0))
        btn(action, "Login", self._login, "Accent.TButton").pack(side="left", padx=3)
        btn(action, "Create Account", self._open_create).pack(side="left", padx=3)
        btn(action, "View Users", self._open_users).pack(side="left", padx=3)
        btn(action, "Exit", self._cancel).pack(side="left", padx=3)

        first_use = db.count_users() == 0
        if first_use:
            self.lbl_msg.config(text="No users found. Please create the first account.")

        e_user.focus_set()
        self.bind("<Return>", lambda e: self._login())

    def _open_users(self):
        UserDirectoryDialog(self)

    def _open_create(self):
        CreateAccountDialog(self, after_create=lambda u: self.v_user.set(u))

    def _login(self):
        username = self.v_user.get().strip()
        password = self.v_pass.get()
        if not username or not password:
            self.lbl_msg.config(text="Enter username and password.")
            return
        user = db.verify_user_credentials(username, password)
        if not user:
            self.lbl_msg.config(text="Invalid username or password.")
            return
        self.user = user
        self.destroy()

    def _cancel(self):
        self.user = None
        self.destroy()


# ─── DSM Picker Dialog ─────────────────────────────────────────────────────────

class DSMPicker(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        apply_window_icon(self)
        self.title("DSM-5 / ICD-10 Code Lookup")
        self.geometry("680x480")
        self.resizable(True, True)
        self.callback = callback
        self.result = None
        self._build()
        self.grab_set()

    def _build(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Search:").pack(side="left")
        self.sv = tk.StringVar()
        self.sv.trace_add("write", lambda *a: self._search())
        ttk.Entry(top, textvariable=self.sv, width=40).pack(side="left", padx=6)

        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        cols = ("code", "description", "category")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        self.tv.heading("code",        text="Code",       anchor="w")
        self.tv.heading("description", text="Description",anchor="w")
        self.tv.heading("category",    text="Category",   anchor="w")
        self.tv.column("code",        width=80,  stretch=False)
        self.tv.column("description", width=400, stretch=True)
        self.tv.column("category",    width=140, stretch=False)
        sb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=sb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", self._select)

        bot = ttk.Frame(self, padding=8)
        bot.pack(fill="x")
        btn(bot, "Select", self._select, "Accent.TButton").pack(side="left", padx=4)
        btn(bot, "Cancel", self.destroy).pack(side="left")

        self._load_all()

    def _load_all(self):
        self.tv.delete(*self.tv.get_children())
        for r in db.get_all_dsm():
            self.tv.insert("", "end", iid=r["code"],
                           values=(r["code"], r["description"], r["category"]))

    def _search(self):
        term = self.sv.get().strip()
        self.tv.delete(*self.tv.get_children())
        rows = db.search_dsm(term) if term else db.get_all_dsm()
        for r in rows:
            self.tv.insert("", "end", iid=r["code"],
                           values=(r["code"], r["description"], r["category"]))

    def _select(self, event=None):
        sel = self.tv.selection()
        if sel:
            code = sel[0]
            self.callback(code)
            self.destroy()


# ─── Patient Form Dialog ───────────────────────────────────────────────────────

class PatientDialog(tk.Toplevel):
    def __init__(self, parent, pid=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.pid = pid
        self.on_save = on_save
        self.title("Edit Patient" if pid else "New Patient")
        self.geometry("820x680")
        self.resizable(True, True)
        self._vars = {}
        self._build()
        if pid:
            self._load()
        self.grab_set()

    def _fld(self, name):
        v = tk.StringVar()
        self._vars[name] = v
        return v

    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Demographics tab ──────────────────────────────────────────────────
        f1 = ttk.Frame(nb, padding=10)
        nb.add(f1, text=" Demographics ")
        for c in range(6): f1.columnconfigure(c, weight=1)

        ttk.Label(f1, text="Last Name*").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("last_name"), width=22).grid(row=0, column=1, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="First Name*").grid(row=0, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("first_name"), width=20).grid(row=0, column=3, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="MI").grid(row=0, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("middle_name"), width=5).grid(row=0, column=5, sticky="w")

        ttk.Label(f1, text="Date of Birth").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("dob"), width=14).grid(row=1, column=1, sticky="w")
        ttk.Label(f1, text="(YYYY-MM-DD)").grid(row=1, column=2, sticky="w", padx=2)

        ttk.Label(f1, text="Sex").grid(row=1, column=3, sticky="e", padx=4)
        sex_cb = ttk.Combobox(f1, textvariable=self._fld("sex"),
                              values=["M", "F", "U"], width=5, state="readonly")
        sex_cb.grid(row=1, column=4, sticky="w")

        ttk.Label(f1, text="Status").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(f1, textvariable=self._fld("status"),
                     values=["Active", "Inactive"], width=10, state="readonly"
                     ).grid(row=2, column=1, sticky="w")

        ttk.Label(f1, text="Intake Date").grid(row=2, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("intake_date"), width=14).grid(row=2, column=3, sticky="w")

        ttk.Label(f1, text="Address").grid(row=3, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("address"), width=30).grid(row=3, column=1, sticky="ew", columnspan=3, padx=(0,8))

        ttk.Label(f1, text="City").grid(row=4, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("city"), width=22).grid(row=4, column=1, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="State").grid(row=4, column=2, sticky="e", padx=4)
        ttk.Combobox(f1, textvariable=self._fld("state"), values=STATES, width=6, state="readonly").grid(row=4, column=3, sticky="w")
        ttk.Label(f1, text="Zip").grid(row=4, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("zip"), width=10).grid(row=4, column=5, sticky="w")

        ttk.Label(f1, text="Phone (Home)").grid(row=5, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("phone_home"), width=16).grid(row=5, column=1, sticky="w")
        ttk.Label(f1, text="Cell").grid(row=5, column=2, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("phone_cell"), width=16).grid(row=5, column=3, sticky="w")
        ttk.Label(f1, text="Work").grid(row=5, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("phone_work"), width=16).grid(row=5, column=5, sticky="w")

        ttk.Label(f1, text="Email").grid(row=6, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("email"), width=30).grid(row=6, column=1, sticky="ew", columnspan=3)

        ttk.Label(f1, text="Emergency Contact").grid(row=7, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(f1, textvariable=self._fld("emr_name"), width=22).grid(row=7, column=1, sticky="ew", padx=(0,8))
        ttk.Label(f1, text="Relation").grid(row=7, column=2, sticky="e", padx=4)
        ttk.Combobox(
            f1,
            textvariable=self._fld("emr_relation"),
            values=["Self", "Spouse", "Child", "Other"],
            width=12,
            state="readonly",
        ).grid(row=7, column=3, sticky="w")
        ttk.Label(f1, text="Phone").grid(row=7, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("emr_phone"), width=16).grid(row=7, column=5, sticky="w")

        # Diagnoses
        dx_frame = lframe(f1, "Primary Diagnoses (ICD-10)")
        dx_frame.grid(row=8, column=0, columnspan=6, sticky="ew", pady=(10, 4))
        for i, dx in enumerate(["dx1", "dx2", "dx3", "dx4"]):
            ttk.Label(dx_frame, text=f"Dx {i+1}").grid(row=0, column=i*2, sticky="e", padx=4)
            e = ttk.Entry(dx_frame, textvariable=self._fld(dx), width=12)
            e.grid(row=0, column=i*2+1, sticky="w", padx=(0,4))

        b_dx = ttk.Frame(dx_frame)
        b_dx.grid(row=1, column=0, columnspan=8, pady=4)
        ttk.Button(b_dx, text="Lookup DSM Code",
                   command=lambda: DSMPicker(self, self._dx_pick)).pack(side="left", padx=4)

        # Notes
        ttk.Label(f1, text="Admin Notes").grid(row=9, column=0, sticky="ne", padx=4, pady=3)
        self._notesbox = tk.Text(f1, width=60, height=4, font=FONT_UI, wrap="word")
        self._notesbox.grid(row=9, column=1, columnspan=5, sticky="ew")

        # ── Insurance tab ─────────────────────────────────────────────────────
        f2 = ttk.Frame(nb, padding=10)
        nb.add(f2, text=" Insurance ")
        for c in range(6): f2.columnconfigure(c, weight=1)

        pri = lframe(f2, "Primary Insurance")
        pri.grid(row=0, column=0, columnspan=6, sticky="ew", pady=4)
        for c in range(6): pri.columnconfigure(c, weight=1)

        ins_fields = [
            ("Insurance Name", "ins_name", 0), ("Plan Name", "ins_plan", 1),
            ("Member/Policy ID", "ins_id", 2), ("Group Number", "ins_group", 3),
            ("Insured Name", "ins_holder", 4), ("Insured DOB", "ins_holder_dob", 5),
        ]
        for lbl, key, rr in ins_fields:
            ttk.Label(pri, text=lbl).grid(row=rr, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(pri, textvariable=self._fld(key), width=28).grid(row=rr, column=1, sticky="ew", columnspan=5)

        ttk.Label(pri, text="Insured Sex").grid(row=6, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(pri, textvariable=self._fld("ins_holder_sex"), values=["M","F","U"], width=5, state="readonly").grid(row=6, column=1, sticky="w")
        ttk.Label(pri, text="Relationship to Patient").grid(row=6, column=2, sticky="e", padx=4)
        ttk.Combobox(pri, textvariable=self._fld("ins_relation"),
                     values=["Self","Spouse","Child","Other"], width=12, state="readonly").grid(row=6, column=3, sticky="w")

        ttk.Label(pri, text="Insured Address").grid(row=7, column=0, sticky="e", padx=4, pady=2)
        ttk.Entry(pri, textvariable=self._fld("ins_address"), width=28).grid(row=7, column=1, sticky="ew", columnspan=2)
        ttk.Label(pri, text="City").grid(row=7, column=3, sticky="e", padx=4)
        ttk.Entry(pri, textvariable=self._fld("ins_city"), width=16).grid(row=7, column=4, sticky="ew")
        ttk.Label(pri, text="State").grid(row=8, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(pri, textvariable=self._fld("ins_state"), values=STATES, width=6, state="readonly").grid(row=8, column=1, sticky="w")
        ttk.Label(pri, text="Zip").grid(row=8, column=2, sticky="e", padx=4)
        ttk.Entry(pri, textvariable=self._fld("ins_zip"), width=10).grid(row=8, column=3, sticky="w")
        ttk.Label(pri, text="Phone").grid(row=8, column=4, sticky="e", padx=4)
        ttk.Entry(pri, textvariable=self._fld("ins_phone"), width=16).grid(row=8, column=5, sticky="w")

        sec = lframe(f2, "Secondary Insurance")
        sec.grid(row=1, column=0, columnspan=6, sticky="ew", pady=4)
        for c in range(6): sec.columnconfigure(c, weight=1)
        sec_fields = [
            ("Insurance Name", "ins2_name", 0), ("Plan Name", "ins2_plan", 1),
            ("Member/Policy ID", "ins2_id", 2), ("Group Number", "ins2_group", 3),
            ("Insured Name", "ins2_holder", 4),
        ]
        for lbl, key, rr in sec_fields:
            ttk.Label(sec, text=lbl).grid(row=rr, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(sec, textvariable=self._fld(key), width=28).grid(row=rr, column=1, sticky="ew", columnspan=5)
        ttk.Label(sec, text="Relationship").grid(row=5, column=0, sticky="e", padx=4, pady=2)
        ttk.Combobox(sec, textvariable=self._fld("ins2_relation"),
                     values=["Self","Spouse","Child","Other"], width=12, state="readonly").grid(row=5, column=1, sticky="w")

        # ── Referral tab ──────────────────────────────────────────────────────
        f3 = ttk.Frame(nb, padding=10)
        nb.add(f3, text=" Referral ")
        for c in range(4): f3.columnconfigure(c, weight=1)
        ttk.Label(f3, text="Referring Provider Name").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("referring_name"), width=30).grid(row=0, column=1, sticky="ew")
        ttk.Label(f3, text="Referring NPI").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("referring_npi"), width=14).grid(row=1, column=1, sticky="w")

        # ── Save / Cancel ─────────────────────────────────────────────────────
        bot = ttk.Frame(self, padding=8)
        bot.pack(fill="x", side="bottom")
        btn(bot, "Save Patient", self._save, "Accent.TButton").pack(side="left", padx=6)
        btn(bot, "Cancel", self.destroy).pack(side="left")

    def _dx_pick(self, code):
        # Fill the first empty dx slot
        for key in ["dx1", "dx2", "dx3", "dx4"]:
            if not self._vars[key].get():
                self._vars[key].set(code)
                return
        self._vars["dx4"].set(code)

    def _load(self):
        pt = db.get_patient(self.pid)
        if not pt:
            return
        for key, var in self._vars.items():
            v = pt[key] if key in pt.keys() else ""
            var.set(v or "")
        if pt["notes"]:
            self._notesbox.insert("1.0", pt["notes"])

    def _save(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        if not data.get("last_name") or not data.get("first_name"):
            messagebox.showerror("Required", "Last Name and First Name are required.", parent=self)
            return
        data["notes"] = self._notesbox.get("1.0", "end-1c")
        if self.pid:
            data["id"] = self.pid
        pid = db.save_patient(data)
        if self.on_save:
            self.on_save(pid)
        self.destroy()


# ─── Session Note Dialog ───────────────────────────────────────────────────────

class SessionDialog(tk.Toplevel):
    def __init__(self, parent, sid=None, pid=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.sid = sid
        self.pid = pid
        self.on_save = on_save
        self.title("Edit Session" if sid else "New Session Note")
        self.geometry("780x700")
        self.resizable(True, True)
        self._vars = {}
        self._build()
        if sid:
            self._load()
        elif pid:
            self._vars["patient_id"].set(str(pid))
            self._vars["session_date"].set(current_date_str())
        self.grab_set()

    def _fld(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        for c in range(8): top.columnconfigure(c, weight=1)

        # Patient selector
        ttk.Label(top, text="Patient*").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.pt_var = tk.StringVar()
        self.pt_combo = ttk.Combobox(top, textvariable=self.pt_var, width=30, state="readonly")
        self.pt_combo.grid(row=0, column=1, columnspan=2, sticky="ew")
        self._load_patients()
        self._fld("patient_id")

        ttk.Label(top, text="Session Date*").grid(row=0, column=3, sticky="e", padx=4)
        ttk.Entry(top, textvariable=self._fld("session_date"), width=12).grid(row=0, column=4, sticky="w")
        ttk.Label(top, text="(YYYY-MM-DD)").grid(row=0, column=5, sticky="w")

        ttk.Label(top, text="Duration (min)").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        ttk.Entry(top, textvariable=self._fld("duration", "50"), width=6).grid(row=1, column=1, sticky="w")

        ttk.Label(top, text="Session Type").grid(row=1, column=2, sticky="e", padx=4)
        ttk.Combobox(top, textvariable=self._fld("session_type", "Individual"),
                     values=SESSION_TYPES, width=18, state="readonly").grid(row=1, column=3, sticky="w")

        ttk.Label(top, text="Place of Service").grid(row=1, column=4, sticky="e", padx=4)
        pos_cb = ttk.Combobox(top, textvariable=self._fld("place_of_service", "11"),
                               values=[p[0] for p in PLACE_CODES], width=20)
        pos_cb.grid(row=1, column=5, sticky="w")

        ttk.Label(top, text="CPT Code").grid(row=2, column=0, sticky="e", padx=4, pady=3)
        ttk.Combobox(top, textvariable=self._fld("cpt_code", "90834"),
                     values=CPT_CODES, width=10).grid(row=2, column=1, sticky="w")
        ttk.Label(top, text="Modifier").grid(row=2, column=2, sticky="e", padx=4)
        ttk.Entry(top, textvariable=self._fld("cpt_modifier"), width=6).grid(row=2, column=3, sticky="w")
        ttk.Label(top, text="Fee ($)").grid(row=2, column=4, sticky="e", padx=4)
        ttk.Entry(top, textvariable=self._fld("fee", "0.00"), width=10).grid(row=2, column=5, sticky="w")

        # Diagnoses row
        dx_frame = lframe(self, "Diagnoses")
        dx_frame.pack(fill="x", padx=10, pady=4)
        for c in range(8): dx_frame.columnconfigure(c, weight=1)
        for i, dx in enumerate(["dx1","dx2","dx3","dx4"]):
            ttk.Label(dx_frame, text=f"Dx {i+1}").grid(row=0, column=i*2, sticky="e", padx=4)
            ttk.Entry(dx_frame, textvariable=self._fld(dx), width=10).grid(row=0, column=i*2+1, sticky="w", padx=(0,6))
        ttk.Button(dx_frame, text="Lookup Code",
                   command=lambda: DSMPicker(self, self._dx_pick)).grid(row=1, column=0, columnspan=8, pady=4)

        # Note text
        nb2 = ttk.Notebook(self)
        nb2.pack(fill="both", expand=True, padx=10, pady=4)

        def note_tab(lbl, attr, h=8):
            frm = ttk.Frame(nb2, padding=4)
            nb2.add(frm, text=lbl)
            t = tk.Text(frm, font=FONT_UI, wrap="word", height=h,
                        relief="solid", borderwidth=1)
            sb = ttk.Scrollbar(frm, orient="vertical", command=t.yview)
            t.configure(yscrollcommand=sb.set)
            t.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            setattr(self, attr, t)
            return frm

        note_tab(" Progress Note ", "_nt",  12)
        note_tab(" Goals Addressed ", "_goals", 6)
        note_tab(" Interventions ", "_interventions", 6)
        note_tab(" Response ", "_response", 6)
        note_tab(" Plan ", "_plan", 6)

        # Signed
        bot = ttk.Frame(self, padding=8)
        bot.pack(fill="x", side="bottom")
        self.signed_var = tk.IntVar()
        ttk.Checkbutton(bot, text="Mark as Signed / Finalized",
                        variable=self.signed_var).pack(side="left", padx=6)
        btn(bot, "Save Session", self._save, "Accent.TButton").pack(side="right", padx=6)
        btn(bot, "Cancel", self.destroy).pack(side="right")

    def _load_patients(self):
        self._pts = db.get_all_patients("Active")
        names = [f"{p['last_name']}, {p['first_name']}  (ID:{p['id']})" for p in self._pts]
        self.pt_combo["values"] = names

    def _dx_pick(self, code):
        for key in ["dx1","dx2","dx3","dx4"]:
            if not self._vars[key].get():
                self._vars[key].set(code)
                return
        self._vars["dx4"].set(code)

    def _load(self):
        s = db.get_session(self.sid)
        if not s:
            return
        for key, var in self._vars.items():
            if key == "patient_id":
                continue
            v = s[key] if key in s.keys() else ""
            var.set(str(v) if v is not None else "")
        # Set patient combo
        for i, p in enumerate(self._pts):
            if p["id"] == s["patient_id"]:
                self.pt_combo.current(i)
                self._vars["patient_id"].set(str(s["patient_id"]))
                break
        self._nt.insert("1.0", s["note_text"] or "")
        self._goals.insert("1.0", s["goals"] or "")
        self._interventions.insert("1.0", s["interventions"] or "")
        self._response.insert("1.0", s["response"] or "")
        self._plan.insert("1.0", s["plan"] or "")
        self.signed_var.set(s["signed"] or 0)

    def _save(self):
        # Resolve patient ID from combo
        sel = self.pt_combo.current()
        if sel < 0:
            messagebox.showerror("Required", "Please select a patient.", parent=self)
            return
        pid = self._pts[sel]["id"]
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["patient_id"] = pid
        if not data.get("session_date"):
            messagebox.showerror("Required", "Session date is required.", parent=self)
            return
        data["note_text"]     = self._nt.get("1.0", "end-1c")
        data["goals"]         = self._goals.get("1.0", "end-1c")
        data["interventions"] = self._interventions.get("1.0", "end-1c")
        data["response"]      = self._response.get("1.0", "end-1c")
        data["plan"]          = self._plan.get("1.0", "end-1c")
        data["signed"]        = self.signed_var.get()
        if data["signed"]:
            data["signed_date"] = current_date_str()
        try:
            data["fee"] = float(data.get("fee", 0) or 0)
            data["duration"] = int(data.get("duration", 50) or 50)
        except ValueError:
            pass
        if self.sid:
            data["id"] = self.sid
        sid = db.save_session(data)
        if self.on_save:
            self.on_save(sid)
        self.destroy()


# ─── Billing Record Dialog ─────────────────────────────────────────────────────

class BillingDialog(tk.Toplevel):
    def __init__(self, parent, rid=None, pid=None, on_save=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.rid = rid
        self.pid = pid
        self.on_save = on_save
        self.title("Edit Record" if rid else "New Billing Record")
        self.geometry("560x420")
        self.resizable(False, False)
        self._vars = {}
        self._build()
        if rid:
            self._load()
        elif pid:
            self._vars["patient_id"].set(str(pid))
            self._vars["record_date"].set(current_date_str())
        self.grab_set()

    def _fld(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        f = ttk.Frame(self, padding=14)
        f.pack(fill="both", expand=True)
        for c in range(4): f.columnconfigure(c, weight=1)

        # Patient
        ttk.Label(f, text="Patient*").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.pt_var = tk.StringVar()
        self.pt_combo = ttk.Combobox(f, textvariable=self.pt_var, width=32, state="readonly")
        self.pt_combo.grid(row=0, column=1, columnspan=3, sticky="ew")
        self._load_patients()
        self._fld("patient_id")

        ttk.Label(f, text="Record Date*").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("record_date"), width=14).grid(row=1, column=1, sticky="w")
        ttk.Label(f, text="Service Date").grid(row=1, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("service_date"), width=14).grid(row=1, column=3, sticky="w")

        ttk.Label(f, text="Description").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("description"), width=36).grid(row=2, column=1, columnspan=3, sticky="ew")

        ttk.Label(f, text="Charge ($)").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("charge", "0.00"), width=10).grid(row=3, column=1, sticky="w")
        ttk.Label(f, text="Pt. Payment ($)").grid(row=3, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("payment", "0.00"), width=10).grid(row=3, column=3, sticky="w")

        ttk.Label(f, text="Ins. Payment ($)").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("ins_payment", "0.00"), width=10).grid(row=4, column=1, sticky="w")
        ttk.Label(f, text="Adjustment ($)").grid(row=4, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("adjustment", "0.00"), width=10).grid(row=4, column=3, sticky="w")

        ttk.Label(f, text="Payment Type").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(f, textvariable=self._fld("payment_type"),
                     values=["","Cash","Check","Credit Card","Debit Card","Insurance","Write-off","Other"],
                     width=16).grid(row=5, column=1, sticky="w")
        ttk.Label(f, text="Check #").grid(row=5, column=2, sticky="e", padx=4)
        ttk.Entry(f, textvariable=self._fld("check_number"), width=12).grid(row=5, column=3, sticky="w")

        ttk.Label(f, text="Claim #").grid(row=6, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f, textvariable=self._fld("claim_number"), width=20).grid(row=6, column=1, sticky="w")

        bot = ttk.Frame(self, padding=8)
        bot.pack(fill="x", side="bottom")
        btn(bot, "Save", self._save, "Accent.TButton").pack(side="left", padx=6)
        btn(bot, "Cancel", self.destroy).pack(side="left")

    def _load_patients(self):
        self._pts = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        names = [f"{p['last_name']}, {p['first_name']}  (ID:{p['id']})" for p in self._pts]
        self.pt_combo["values"] = names

    def _load(self):
        r = db.get_connection().execute("SELECT * FROM billing_records WHERE id=?", (self.rid,)).fetchone()
        db.get_connection().close()
        if not r:
            return
        # Manually close connection
        conn = db.get_connection()
        r = conn.execute("SELECT * FROM billing_records WHERE id=?", (self.rid,)).fetchone()
        conn.close()
        for key, var in self._vars.items():
            if key == "patient_id":
                continue
            v = r[key] if key in r.keys() else ""
            var.set(str(v) if v is not None else "")
        for i, p in enumerate(self._pts):
            if p["id"] == r["patient_id"]:
                self.pt_combo.current(i)
                break

    def _save(self):
        sel = self.pt_combo.current()
        if sel < 0:
            messagebox.showerror("Required", "Please select a patient.", parent=self)
            return
        pid = self._pts[sel]["id"]
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["patient_id"] = pid
        for money_key in ["charge","payment","ins_payment","adjustment"]:
            try:
                data[money_key] = float(data.get(money_key, 0) or 0)
            except ValueError:
                data[money_key] = 0.0
        data["balance"] = (data["charge"] - data["payment"]
                           - data["ins_payment"] - data["adjustment"])
        if self.rid:
            data["id"] = self.rid
        db.save_billing_record(data)
        if self.on_save:
            self.on_save()
        self.destroy()


# ─── Patients Tab ──────────────────────────────────────────────────────────────

class PatientsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._status_filter = tk.StringVar(value="Active")
        self._build()
        self.refresh()

    def _build(self):
        # Toolbar
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")

        btn(tb, "+ New Patient", self._new_patient, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_patient).pack(side="left", padx=2)
        btn(tb, "Deactivate", self._deactivate).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete, "Danger.TButton").pack(side="left", padx=2)
        btn(tb, "View Sessions", self._view_sessions).pack(side="left", padx=2)
        btn(tb, "Billing Ledger", self._view_billing).pack(side="left", padx=2)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)

        ttk.Label(tb, text="Show:").pack(side="left")
        ttk.Combobox(tb, textvariable=self._status_filter,
                     values=["Active", "Inactive", "All"], width=10, state="readonly"
                     ).pack(side="left", padx=4)
        self._status_filter.trace_add("write", lambda *a: self.refresh())

        ttk.Label(tb, text="Search:").pack(side="left", padx=(8, 2))
        self._sv = tk.StringVar()
        self._sv.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(tb, textvariable=self._sv, width=24).pack(side="left")
        btn(tb, "Clear", lambda: self._sv.set("")).pack(side="left", padx=2)

        self._lbl_count = ttk.Label(tb, text="", foreground=MUTED)
        self._lbl_count.pack(side="right", padx=8)

        # Treeview
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=4)

        cols = ("id","last_name","first_name","dob","phone_home","insurance","dx1","status")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        hdrs = [("ID",40),("Last Name",130),("First Name",110),("DOB",90),
                ("Phone",110),("Insurance",160),("Dx1",90),("Status",80)]
        for (hdr, w), col in zip(hdrs, cols):
            self.tv.heading(col, text=hdr, anchor="w")
            self.tv.column(col, width=w, stretch=col in ("last_name","first_name","insurance"))

        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tv.bind("<Double-1>", lambda e: self._edit_patient())
        self.tv.tag_configure("even", background=ROW_EVEN)

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        status = self._status_filter.get()
        term = self._sv.get().strip()
        if term:
            rows = db.search_patients(term, "Active") + (
                db.search_patients(term, "Inactive") if status in ("Inactive","All") else [])
        else:
            rows = []
            if status in ("Active", "All"):
                rows += db.get_all_patients("Active")
            if status in ("Inactive", "All"):
                rows += db.get_all_patients("Inactive")
            rows.sort(key=lambda r: (r["last_name"] or "").lower())

        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            self.tv.insert("", "end", iid=str(r["id"]), tags=(tag,),
                           values=(r["id"], r["last_name"], r["first_name"],
                                   fmt_date(r["dob"]), r["phone_home"] or r["phone_cell"],
                                   r["ins_name"], r["dx1"], r["status"]))
        self._lbl_count.config(text=f"{len(rows)} patient(s)")

    def _selected_pid(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _new_patient(self):
        PatientDialog(self, on_save=lambda _: self.refresh())

    def _edit_patient(self):
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Select", "Please select a patient first.")
            return
        PatientDialog(self, pid=pid, on_save=lambda _: self.refresh())

    def _deactivate(self):
        pid = self._selected_pid()
        if not pid:
            return
        pt = db.get_patient(pid)
        new_status = "Active" if pt["status"] == "Inactive" else "Inactive"
        if messagebox.askyesno("Confirm", f"Set status to {new_status}?"):
            db.set_patient_status(pid, new_status)
            self.refresh()

    def _delete(self):
        pid = self._selected_pid()
        if not pid:
            return
        if messagebox.askyesno("Delete Patient",
                                "Permanently delete this patient and ALL associated records?\n"
                                "This cannot be undone.", icon="warning"):
            db.delete_patient(pid)
            self.refresh()

    def _view_sessions(self):
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Select", "Please select a patient first.")
            return
        # Switch to Sessions tab and filter by patient
        nb = self.master
        for i in range(nb.index("end")):
            if "Session" in nb.tab(i, "text"):
                nb.select(i)
                if hasattr(nb.nametowidget(nb.tabs()[i]), "filter_patient"):
                    nb.nametowidget(nb.tabs()[i]).filter_patient(pid)
                break

    def _view_billing(self):
        pid = self._selected_pid()
        if not pid:
            messagebox.showinfo("Select", "Please select a patient first.")
            return
        nb = self.master
        for i in range(nb.index("end")):
            if "Billing" in nb.tab(i, "text"):
                nb.select(i)
                if hasattr(nb.nametowidget(nb.tabs()[i]), "filter_patient"):
                    nb.nametowidget(nb.tabs()[i]).filter_patient(pid)
                break


# ─── Session Notes Tab ─────────────────────────────────────────────────────────

class SessionNotesTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._pid_filter = None
        self._build()
        self.refresh()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        btn(tb, "+ New Session", self._new_session, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_session).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete_session, "Danger.TButton").pack(side="left", padx=2)
        btn(tb, "Generate CMS-1500", self._to_cms).pack(side="left", padx=2)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Label(tb, text="Date Filter:").pack(side="left")
        self._date_sv = tk.StringVar()
        ttk.Entry(tb, textvariable=self._date_sv, width=12).pack(side="left", padx=4)
        ttk.Label(tb, text="(YYYY-MM-DD)").pack(side="left")
        btn(tb, "Filter", self.refresh).pack(side="left", padx=2)
        btn(tb, "All Sessions", self._show_all).pack(side="left", padx=2)

        self._pt_label = ttk.Label(tb, text="", foreground=ACCENT, font=("Calibri",10,"bold"))
        self._pt_label.pack(side="right", padx=8)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        cols = ("id","patient_name","session_date","session_type","cpt_code","fee","signed")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        hdrs = [("ID",40),("Patient",180),("Date",90),("Type",120),("CPT",70),("Fee",80),("Signed",60)]
        for (h, w), c in zip(hdrs, cols):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=w, stretch=c in ("patient_name",))
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", lambda e: self._edit_session())
        self.tv.tag_configure("even", background=ROW_EVEN)
        self.tv.tag_configure("signed", foreground=SUCCESS)

        # Note preview pane
        prev_frame = lframe(self, "Session Note Preview")
        prev_frame.pack(fill="x", padx=8, pady=(0, 8))
        self._preview = tk.Text(prev_frame, height=6, font=FONT_UI, state="disabled",
                                wrap="word", relief="flat", background=BG)
        self._preview.pack(fill="x")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)

    def filter_patient(self, pid):
        self._pid_filter = pid
        pt = db.get_patient(pid)
        if pt:
            self._pt_label.config(text=f"Showing: {pt['last_name']}, {pt['first_name']}")
        self.refresh()

    def _show_all(self):
        self._pid_filter = None
        self._pt_label.config(text="")
        self._date_sv.set("")
        self.refresh()

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        date_flt = self._date_sv.get().strip()
        if self._pid_filter:
            rows = db.get_sessions_for_patient(self._pid_filter)
            for r in rows:
                self._insert_row(r, dict(r), r["id"])
        elif date_flt:
            rows = db.get_sessions_by_date(date_flt)
            for i, r in enumerate(rows):
                self._insert_row(r, dict(r), r["id"], even=i % 2 == 0)
        else:
            rows = db.get_recent_sessions(200)
            for i, r in enumerate(rows):
                self._insert_row(r, dict(r), r["id"], even=i % 2 == 0)

    def _insert_row(self, r, rd, iid, even=False):
        name = rd.get("patient_name", "")
        if not name:
            pt = db.get_patient(rd.get("patient_id"))
            name = f"{pt['last_name']}, {pt['first_name']}" if pt else "—"
        tags = []
        if even:
            tags.append("even")
        if rd.get("signed"):
            tags.append("signed")
        self.tv.insert("", "end", iid=str(iid), tags=tags,
                       values=(iid, name, fmt_date(rd.get("session_date","")),
                               rd.get("session_type",""), rd.get("cpt_code",""),
                               fmt_money(rd.get("fee",0)),
                               "✓" if rd.get("signed") else ""))

    def _on_select(self, event=None):
        sel = self.tv.selection()
        if not sel:
            return
        sid = int(sel[0])
        s = db.get_session(sid)
        if s:
            note = s["note_text"] or ""
            self._preview.config(state="normal")
            self._preview.delete("1.0", "end")
            self._preview.insert("1.0", note[:600] + ("…" if len(note) > 600 else ""))
            self._preview.config(state="disabled")

    def _sel_sid(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _new_session(self):
        SessionDialog(self, pid=self._pid_filter, on_save=lambda _: self.refresh())

    def _edit_session(self):
        sid = self._sel_sid()
        if not sid:
            messagebox.showinfo("Select", "Please select a session first.")
            return
        SessionDialog(self, sid=sid, on_save=lambda _: self.refresh())

    def _delete_session(self):
        sid = self._sel_sid()
        if not sid:
            return
        if messagebox.askyesno("Delete", "Delete this session note?"):
            db.delete_session(sid)
            self.refresh()

    def _to_cms(self):
        sid = self._sel_sid()
        if not sid:
            messagebox.showinfo("Select", "Select a session to generate a CMS-1500 claim.")
            return
        s = db.get_session(sid)
        nb = self.master
        for i in range(nb.index("end")):
            if "CMS" in nb.tab(i, "text"):
                nb.select(i)
                tab = nb.nametowidget(nb.tabs()[i])
                if hasattr(tab, "load_from_session"):
                    tab.load_from_session(s["patient_id"], [dict(s)])
                break


# ─── Billing Tab ───────────────────────────────────────────────────────────────

class BillingTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._pid_filter = None
        self._build()
        self.refresh()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        btn(tb, "+ Add Record", self._new_record, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Edit", self._edit_record).pack(side="left", padx=2)
        btn(tb, "Delete", self._delete_record, "Danger.TButton").pack(side="left", padx=2)
        btn(tb, "All Records", self._show_all).pack(side="left", padx=2)

        self._pt_label = ttk.Label(tb, text="", foreground=ACCENT, font=("Calibri",10,"bold"))
        self._pt_label.pack(side="right", padx=8)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        cols = ("id","patient_name","record_date","description","charge","payment",
                "ins_payment","adjustment","balance","payment_type")
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        hdrs = [("ID",40),("Patient",160),("Date",90),("Description",160),
                ("Charge",80),("Pt Paid",75),("Ins Paid",75),("Adj",70),
                ("Balance",80),("Method",100)]
        for (h, w), c in zip(hdrs, cols):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=w, stretch=c in ("patient_name","description"))
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", lambda e: self._edit_record())
        self.tv.tag_configure("even", background=ROW_EVEN)
        self.tv.tag_configure("credit", foreground=SUCCESS)
        self.tv.tag_configure("overdue", foreground=DANGER)

        # Summary bar
        sumbar = ttk.Frame(self, padding=(8, 4))
        sumbar.pack(fill="x", side="bottom")
        self._lbl_charges = ttk.Label(sumbar, text="Total Charges: $0.00", font=FONT_UI)
        self._lbl_charges.pack(side="left", padx=16)
        self._lbl_paid = ttk.Label(sumbar, text="Total Paid: $0.00", font=FONT_UI, foreground=SUCCESS)
        self._lbl_paid.pack(side="left", padx=16)
        self._lbl_balance = ttk.Label(sumbar, text="Balance: $0.00", font=FONT_LG, foreground=DANGER)
        self._lbl_balance.pack(side="left", padx=16)

    def filter_patient(self, pid):
        self._pid_filter = pid
        pt = db.get_patient(pid)
        if pt:
            self._pt_label.config(text=f"Showing: {pt['last_name']}, {pt['first_name']}")
        self.refresh()

    def _show_all(self):
        self._pid_filter = None
        self._pt_label.config(text="")
        self.refresh()

    def refresh(self):
        self.tv.delete(*self.tv.get_children())
        if self._pid_filter:
            rows = db.get_billing_for_patient(self._pid_filter)
        else:
            conn = db.get_connection()
            rows = conn.execute(
                """SELECT b.*, p.first_name||' '||p.last_name AS patient_name
                   FROM billing_records b
                   JOIN patients p ON b.patient_id=p.id
                   ORDER BY b.record_date DESC, b.id DESC LIMIT 500"""
            ).fetchall()
            conn.close()

        total_c = total_p = total_b = 0.0
        for i, r in enumerate(rows):
            tag = "even" if i % 2 == 0 else "odd"
            bal = float(r["balance"] or 0)
            if bal < 0:
                tag = "credit"
            name = r["patient_name"] if "patient_name" in r.keys() else ""
            if not name:
                pt = db.get_patient(r["patient_id"])
                name = f"{pt['last_name']}, {pt['first_name']}" if pt else ""
            self.tv.insert("", "end", iid=str(r["id"]), tags=(tag,),
                           values=(r["id"], name, fmt_date(r["record_date"]),
                                   r["description"], fmt_money(r["charge"]),
                                   fmt_money(r["payment"]), fmt_money(r["ins_payment"]),
                                   fmt_money(r["adjustment"]), fmt_money(r["balance"]),
                                   r["payment_type"]))
            total_c += float(r["charge"] or 0)
            total_p += float(r["payment"] or 0) + float(r["ins_payment"] or 0)
            total_b += bal

        self._lbl_charges.config(text=f"Total Charges: {fmt_money(total_c)}")
        self._lbl_paid.config(text=f"Total Paid: {fmt_money(total_p)}")
        self._lbl_balance.config(text=f"Balance: {fmt_money(total_b)}",
                                 foreground=(DANGER if total_b > 0 else SUCCESS))

    def _sel_rid(self):
        sel = self.tv.selection()
        return int(sel[0]) if sel else None

    def _new_record(self):
        BillingDialog(self, pid=self._pid_filter, on_save=self.refresh)

    def _edit_record(self):
        rid = self._sel_rid()
        if not rid:
            messagebox.showinfo("Select", "Please select a record.")
            return
        BillingDialog(self, rid=rid, pid=self._pid_filter, on_save=self.refresh)

    def _delete_record(self):
        rid = self._sel_rid()
        if not rid:
            return
        if messagebox.askyesno("Delete", "Delete this billing record?"):
            db.delete_billing_record(rid)
            self.refresh()


# ─── CMS-1500 Tab ──────────────────────────────────────────────────────────────

class CMS1500Tab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._overlay_offsets = {
            "top": [1, 3],
            "mid": [1, 3],
            "dx": [1, 2],
            "line": [1, 2],
            "bot": [1, 2],
        }
        self._overlay_field_offsets = {
            "ins_type_medicare": [-383, 128],
            "patient_name": [11, 74],
            "patient_address": [15, 72],
            "ins_type_medicaid": [-339, 127],
            "ins_type_tricare": [-298, 126],
            "ins_type_champva": [-225, 127],
            "patient_dob": [-12, 76],
            "ins_relation_self": [24, 73],
            "ins_relation_spouse": [48, 72],
            "ins_relation_child": [59, 74],
            "ins_relation_other": [85, 71],
            "patient_sex": [-25, 75],
            "patient_sex_f": [24, 74],
            "ins_type_group": [-182, 127],
            "ins_type_feca": [-121, 126],
            "ins_type_other": [-87, 127],
            "patient_city": [15, 65],
            "billing_date": [719, 174],
            "billing_other_id": [-16, 86],
            "billing_npi": [-12, 86],
            "facility_npi": [-118, 85],
            "facility_other_id": [-120, 86],
            "facility_city_state_zip": [-14, 68],
            "facility_address": [-14, 76],
            "facility_name": [-14, 88],
            "provider_sig": [13, 151],
            "provider_sig_date": [-26, 151],
            "billing_qualifier": [-185, 179],
            "billing_city_state_zip": [-20, 69],
            "billing_address": [-19, 78],
            "billing_name": [-19, 89],
            "billing_phone": [-3, 126],
            "amount_paid": [24, 101],
            "total_charge": [22, 100],
            "sl6_npi": [9, 84],
            "sl6_id_qual": [-11, 58],
            "sl6_family_plan": [-8, 82],
            "sl6_epsdt": [-7, 366],
            "sl6_units": [8, 82],
            "sl6_charge": [-12, 82],
            "sl5_npi": [8, 94],
            "sl5_id_qual": [-12, 68],
            "sl5_family_plan": [-9, 93],
            "sl4_npi": [-12, 415],
            "sl4_id_qual": [-12, 76],
            "sl3_npi": [9, 108],
            "sl3_id_qual": [-12, 87],
            "sl5_charge": [-12, 93],
            "sl5_units": [8, 93],
            "sl5_epsdt": [-31, 425],
            "sl4_charge": [-11, 103],
            "sl4_units": [8, 102],
            "sl4_epsdt": [-55, 481],
            "sl4_family_plan": [-11, 102],
            "sl3_charge": [-12, 112],
            "sl3_units": [8, 112],
            "sl3_family_plan": [-9, 112],
            "sl3_epsdt": [-4, 514],
            "sl2_npi": [11, 117],
            "sl2_id_qual": [-12, 94],
            "sl2_family_plan": [-7, 120],
            "sl2_epsdt": [-31, 571],
            "sl2_charge": [-11, 120],
            "sl2_units": [8, 120],
            "sl1_npi": [11, 128],
            "sl1_id_qual": [-11, 104],
            "sl1_units": [9, 127],
            "sl1_family_plan": [-8, 127],
            "sl1_charge": [-8, 128],
            "sl1_epsdt": [-56, 628],
            "accept_assign": [-21, 101],
            "accept_assign_yes": [-21, 101],
            "accept_assign_no": [10, 101],
            "patient_acct": [-16, 101],
            "tax_id_ein": [88, 103],
            "tax_id": [13, 104],
            "sl6_dx_ptr": [32, 82],
            "sl5_dx_ptr": [32, 93],
            "sl4_dx_ptr": [33, 105],
            "sl3_dx_ptr": [33, 112],
            "sl2_dx_ptr": [32, 120],
            "sl1_dx_ptr": [33, 129],
            "sl6_modifier": [39, 82],
            "sl6_cpt": [32, 84],
            "sl5_modifier": [36, 93],
            "sl5_cpt": [33, 93],
            "sl4_modifier": [36, 104],
            "sl4_cpt": [31, 104],
            "sl3_modifier": [38, 112],
            "sl3_cpt": [29, 112],
            "sl2_modifier": [40, 120],
            "sl2_cpt": [28, 121],
            "sl1_modifier": [39, 129],
            "sl1_cpt": [29, 129],
            "sl6_pos": [24, 84],
            "sl5_pos": [22, 93],
            "sl4_pos": [22, 102],
            "sl3_pos": [22, 111],
            "sl2_pos": [24, 120],
            "sl1_pos": [22, 127],
            "sl6_to_date": [16, 84],
            "sl5_to_date": [16, 94],
            "sl4_to_date": [16, 104],
            "sl3_to_date": [16, 112],
            "sl2_to_date": [16, 121],
            "sl1_to_date": [16, 129],
            "sl6_from_date": [4, 84],
            "sl5_from_date": [5, 95],
            "sl4_from_date": [5, 105],
            "sl3_from_date": [5, 112],
            "sl2_from_date": [5, 121],
            "sl1_from_date": [4, 129],
            "dx9": [-15, 45],
            "dx5": [-15, 50],
            "dx1": [-15, 56],
            "dx10": [-20, 45],
            "dx6": [-20, 53],
            "dx2": [-20, 59],
            "dx11": [-22, 47],
            "dx7": [-23, 51],
            "dx3": [-22, 56],
            "dx12": [-28, 47],
            "dx8": [-28, 54],
            "dx4": [-28, 59],
            "auth_number": [-7, 81],
            "resubmission_code": [-62, 61],
            "original_ref_no": [-16, 61],
            "outside_lab": [-31, 46],
            "outside_lab_charge": [4, 47],
            "hospital_from": [-1, 56],
            "hospital_to": [15, 55],
            "unable_from": [-4, 70],
            "unable_to": [13, 70],
            "ins_sig": [49, 92],
            "add_info": [15, 47],
            "ref_provider": [28, 55],
            "illness_date": [15, 67],
            "illness_qual": [59, 66],
            "ref_npi": [40, 57],
            "ref_qual": [48, 34],
            "other_date": [97, 67],
            "other_date_qual": [-122, 67],
            "patient_sig_date": [53, 94],
            "patient_sig": [15, 94],
            "patient_auth_no": [394, 3],
            "patient_auth_yes": [348, 2],
            "other_plan": [13, 71],
            "reserved_nucc_c": [11, -27],
            "reserved_nucc_b": [13, 81],
            "other_ins_policy": [13, 40],
            "other_ins_name": [12, 52],
            "other_ins_employer": [19, -448],
            "other_ins_dob": [69, -361],
            "other_ins_sex_f": [-48, -328],
            "other_ins_sex": [-65, -330],
            "patient_phone": [49, 59],
            "patient_zip": [15, 59],
            "patient_state": [26, 61],
            "other_plan_yes": [-102, -418],
            "patient_status_employed": [-178, -327],
            "other_claim_id": [-8, 32],
            "ins_plan": [-7, 76],
            "reserved_local_use": [-298, -139],
            "related_other_yes": [-220, 135],
            "other_plan_no": [-118, -418],
            "related_other_no": [-166, 134],
            "related_auto_yes": [-222, 115],
            "related_auto_no": [-167, 115],
            "related_auto_state": [-146, 119],
            "related_emp_yes": [-221, 100],
            "related_emp_no": [-167, 99],
            "ins_sex_f": [61, 41],
            "ins_sex": [-20, 40],
            "ins_dob": [-61, 44],
            "patient_status": [19, -324],
            "patient_status_single": [-153, -339],
            "patient_status_married": [-171, -339],
            "patient_status_other": [-188, -339],
            "patient_status_full_time": [-195, -326],
            "patient_status_part_time": [-209, -326],
            "ins_zip2": [-5, 58],
            "ins_group": [-8, 49],
            "ins_phone": [51, 58],
            "ins_state2": [10, 65],
            "ins_city2": [-6, 65],
            "ins_address2": [-8, 72],
            "ins_name": [-5, 75],
            "ins_id": [-5, 102],
            "ins_type": [-122, 14],
            "tax_id_ssn": [-191, -34],
        }
        self._overlay_field_size_offsets = {
            "ins_type_medicare": [-2, 4],
            "ins_type_medicaid": [-6, 5],
            "ins_type_tricare": [-4, 4],
            "ins_type_champva": [-4, 2],
            "patient_sex": [5, 0],
            "patient_sex_f": [6, 1],
            "ins_type_group": [-6, 4],
            "ins_type_feca": [-6, 5],
            "ins_type_other": [-7, 5],
            "ins_relation_self": [-4, 4],
            "ins_relation_spouse": [-5, 7],
            "ins_relation_child": [-4, 5],
            "ins_relation_other": [-2, 5],
            "billing_other_id": [32, 0],
            "provider_sig": [-34, 0],
            "provider_sig_date": [28, 0],
            "billing_phone": [42, 0],
            "sl6_npi": [54, 0],
            "sl6_id_qual": [8, 0],
            "sl6_units": [19, 1],
            "sl6_epsdt": [9, 1],
            "sl5_npi": [58, -1],
            "sl5_id_qual": [9, 1],
            "sl4_npi": [53, 1],
            "sl4_id_qual": [11, 2],
            "sl3_npi": [53, 4],
            "sl3_id_qual": [11, 0],
            "sl6_charge": [45, 1],
            "sl5_charge": [41, 0],
            "sl5_units": [15, 0],
            "sl6_family_plan": [0, 1],
            "sl4_charge": [40, 0],
            "sl4_units": [14, 0],
            "sl4_family_plan": [2, 0],
            "sl3_charge": [39, -1],
            "sl3_units": [14, 0],
            "sl2_npi": [55, 3],
            "sl2_id_qual": [8, 0],
            "sl2_charge": [36, 0],
            "sl2_units": [18, 0],
            "sl1_npi": [52, 0],
            "sl1_id_qual": [8, 2],
            "sl1_units": [12, 2],
            "sl1_family_plan": [0, 2],
            "sl1_charge": [30, 0],
            "accept_assign": [-60, 0],
            "accept_assign_yes": [-60, 0],
            "accept_assign_no": [-60, 0],
            "patient_acct": [44, 0],
            "sl6_modifier": [66, 0],
            "sl5_modifier": [66, 1],
            "sl4_modifier": [65, 1],
            "sl3_modifier": [64, 0],
            "sl2_modifier": [61, 1],
            "sl1_modifier": [62, 0],
            "sl6_to_date": [15, 1],
            "sl5_to_date": [16, 0],
            "sl4_to_date": [16, 1],
            "sl3_to_date": [16, 0],
            "sl2_to_date": [16, 0],
            "sl1_to_date": [17, 0],
            "tax_id": [89, -1],
            "sl6_from_date": [16, 1],
            "sl5_from_date": [14, 0],
            "sl4_from_date": [14, 0],
            "sl3_from_date": [14, 0],
            "sl2_from_date": [14, 0],
            "sl1_from_date": [14, 0],
            "dx9": [-8, 0],
            "dx5": [-8, -2],
            "dx1": [-10, 0],
            "dx10": [-8, 0],
            "dx6": [-10, -2],
            "dx2": [-10, 0],
            "dx11": [-8, 0],
            "dx7": [-8, -2],
            "dx3": [-8, 0],
            "dx12": [-6, -2],
            "dx8": [-6, -2],
            "dx4": [-6, 0],
            "auth_number": [-4, 7],
            "resubmission_code": [55, -1],
            "original_ref_no": [78, -1],
            "outside_lab": [-93, -2],
            "unable_from": [0, -4],
            "unable_to": [0, -4],
            "ref_npi": [195, 0],
            "ref_qual": [-6, 0],
            "other_date_qual": [-14, 0],
            "other_date": [75, 0],
            "patient_sig_date": [79, -1],
            "patient_auth_yes": [-2, 4],
            "patient_auth_no": [-2, 4],
            "patient_status_employed": [-6, 4],
            "related_other_yes": [-8, 2],
            "related_other_no": [-6, 4],
            "related_auto_yes": [-4, 4],
            "related_auto_no": [-6, 4],
            "related_emp_yes": [-6, 2],
            "related_emp_no": [-6, 4],
            "ins_sex_f": [6, 0],
            "ins_sex": [6, 0],
            "ins_dob": [58, 0],
            "ins_phone": [8, 0],
            "reserved_local_use": [-80, 38],
            "tax_id_ein": [-2, 4],
            "tax_id_ssn": [0, 4],
            "patient_phone": [-13, 2],
        }
        self._selected_overlay_field = ""
        self._drag_state = None
        self._resize_drag_state = None
        self._form_scale = 1.0
        self._build()

    def _build(self):
        # Left: claim list
        left = ttk.Frame(self, width=260)
        left.pack(side="left", fill="y", padx=(8, 0), pady=8)
        left.pack_propagate(False)

        ttk.Label(left, text="Saved Claims", font=FONT_LG).pack(anchor="w", padx=4, pady=4)
        btn(left, "+ New Claim", self._new_claim, "Accent.TButton").pack(fill="x", padx=4, pady=2)
        btn(left, "Open Claim", self._open_claim).pack(fill="x", padx=4, pady=2)

        cl_frm = ttk.Frame(left)
        cl_frm.pack(fill="both", expand=True)
        self.claim_tv = ttk.Treeview(cl_frm, columns=("id","patient","date","status"),
                                      show="headings", height=20)
        for c, h, w in [("id","ID",40),("patient","Patient",120),
                         ("date","Date",80),("status","Status",70)]:
            self.claim_tv.heading(c, text=h, anchor="w")
            self.claim_tv.column(c, width=w)
        sb2 = ttk.Scrollbar(cl_frm, orient="vertical", command=self.claim_tv.yview)
        self.claim_tv.configure(yscrollcommand=sb2.set)
        self.claim_tv.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        self.claim_tv.bind("<Double-1>", self._open_claim)

        # Right: claim form
        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        self._form_title = ttk.Label(right, text="CMS-1500 Claim Form", font=FONT_H1)
        self._form_title.pack(anchor="w", pady=(0, 6))

        self._form_canvas = tk.Canvas(right, background=BG, highlightthickness=0)
        vscr = ttk.Scrollbar(right, orient="vertical", command=self._form_canvas.yview)
        self._form_canvas.configure(yscrollcommand=vscr.set)
        self._form_canvas.pack(side="left", fill="both", expand=True)
        vscr.pack(side="right", fill="y")
        self._bind_form_mousewheel()

        self._form_frame = ttk.Frame(self._form_canvas)
        self._form_frame_id = self._form_canvas.create_window((0, 0), window=self._form_frame, anchor="nw")
        self._form_frame.bind("<Configure>", lambda e: self._form_canvas.configure(
            scrollregion=self._form_canvas.bbox("all")))

        self._build_form(self._form_frame)

        # Action buttons
        act = ttk.Frame(right, padding=4)
        act.pack(fill="x", before=self._form_canvas)
        btn(act, "Auto-Populate from Patient",  self._auto_populate).pack(side="left", padx=4)
        btn(act, "Save Claim",                  self._save_claim).pack(side="left", padx=4)
        btn(act, "Print Preview",               self._preview_print).pack(side="left", padx=4)
        btn(act, "Export PDF",                  self._export_pdf, "Accent.TButton").pack(side="left", padx=4)
        btn(act, "Save Alignment JSON",         self._export_alignment_offsets).pack(side="left", padx=4)

        # Live alignment controls for interactive box placement.
        align = ttk.Frame(right, padding=(4, 0, 4, 4))
        align.pack(fill="x", before=self._form_canvas)
        ttk.Label(align, text="Mode:").pack(side="left", padx=(0, 4))
        self._align_mode = tk.StringVar(value="section")
        ttk.Combobox(
            align,
            textvariable=self._align_mode,
            values=["section", "field"],
            state="readonly",
            width=8,
        ).pack(side="left", padx=(0, 8))
        ttk.Label(align, text="Align Section:").pack(side="left", padx=(0, 4))
        self._align_section = tk.StringVar(value="top")
        ttk.Combobox(
            align,
            textvariable=self._align_section,
            values=["top", "mid", "dx", "line", "bot"],
            state="readonly",
            width=8,
        ).pack(side="left")
        ttk.Label(align, text="Nudge:").pack(side="left", padx=(10, 4))
        btn(align, "←", lambda: self._nudge_overlay(-1, 0)).pack(side="left", padx=1)
        btn(align, "↑", lambda: self._nudge_overlay(0, -1)).pack(side="left", padx=1)
        btn(align, "↓", lambda: self._nudge_overlay(0, 1)).pack(side="left", padx=1)
        btn(align, "→", lambda: self._nudge_overlay(1, 0)).pack(side="left", padx=1)
        ttk.Label(align, text="Size:").pack(side="left", padx=(10, 4))
        btn(align, "W-", lambda: self._resize_overlay_field(-2, 0)).pack(side="left", padx=1)
        btn(align, "W+", lambda: self._resize_overlay_field(2, 0)).pack(side="left", padx=1)
        btn(align, "H-", lambda: self._resize_overlay_field(0, -2)).pack(side="left", padx=1)
        btn(align, "H+", lambda: self._resize_overlay_field(0, 2)).pack(side="left", padx=1)
        btn(align, "Reset Section", self._reset_overlay_section).pack(side="left", padx=(10, 2))
        btn(align, "Reset Field", self._reset_overlay_field).pack(side="left", padx=(2, 2))
        btn(align, "Export Alignment", self._export_alignment_offsets).pack(side="left", padx=(8, 2))

        status_row = ttk.Frame(right, padding=(4, 0, 4, 4))
        status_row.pack(fill="x", before=self._form_canvas)
        self._align_status = ttk.Label(status_row, text="", anchor="w")
        self._align_status.pack(side="left", fill="x", expand=True)
        self._align_section.trace_add("write", lambda *a: self._update_align_status())
        self._align_mode.trace_add("write", lambda *a: self._update_align_status())
        self._update_align_status()

        self._refresh_claims()

    def _bind_form_mousewheel(self):
        self._form_canvas.bind("<Enter>", self._activate_form_mousewheel)
        self._form_canvas.bind("<Leave>", self._deactivate_form_mousewheel)

    def _activate_form_mousewheel(self, event=None):
        self._form_canvas.bind_all("<MouseWheel>", self._on_form_mousewheel)
        self._form_canvas.bind_all("<Shift-MouseWheel>", self._on_form_shift_mousewheel)
        self._form_canvas.bind_all("<Button-4>", self._on_form_wheel_up)
        self._form_canvas.bind_all("<Button-5>", self._on_form_wheel_down)

    def _deactivate_form_mousewheel(self, event=None):
        self._form_canvas.unbind_all("<MouseWheel>")
        self._form_canvas.unbind_all("<Shift-MouseWheel>")
        self._form_canvas.unbind_all("<Button-4>")
        self._form_canvas.unbind_all("<Button-5>")

    def _on_form_mousewheel(self, event):
        delta = event.delta if hasattr(event, "delta") else 0
        if delta == 0:
            return "break"
        units = -1 if delta > 0 else 1
        self._form_canvas.yview_scroll(units, "units")
        return "break"

    def _on_form_shift_mousewheel(self, event):
        delta = event.delta if hasattr(event, "delta") else 0
        if delta == 0:
            return "break"
        units = -1 if delta > 0 else 1
        self._form_canvas.xview_scroll(units, "units")
        return "break"

    def _on_form_wheel_up(self, event):
        self._form_canvas.yview_scroll(-1, "units")
        return "break"

    def _on_form_wheel_down(self, event):
        self._form_canvas.yview_scroll(1, "units")
        return "break"

    def _build_form(self, parent):
        """Build the CMS-1500 form directly on top of the provided sample image."""
        self._cv = {}
        self._sl_vars = []
        self._field_window_ids = {}
        self._field_window_meta = {}

        def fld(name, default=""):
            v = tk.StringVar(value=default)
            self._cv[name] = v
            return v

        sample_image = ASSETS_DIR / "cms1500_sample.png"
        if not sample_image.exists() or Image is None or ImageTk is None:
            ttk.Label(
                parent,
                text="CMS-1500 sample form image is unavailable.",
                foreground=DANGER,
            ).grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        original = Image.open(sample_image)
        max_width = 1040
        scale = min(1.0, max_width / float(original.width))
        if scale < 1.0:
            display = original.resize(
                (int(original.width * scale), int(original.height * scale)),
                Image.Resampling.LANCZOS,
            )
        else:
            display = original.copy()
        self._form_scale = max(scale, 0.01)

        self._cms_form_pil = display
        self._cms_form_img = ImageTk.PhotoImage(display)

        parent.columnconfigure(0, weight=1)

        surface = tk.Canvas(
            parent,
            width=display.width,
            height=display.height + 44,
            bg=BG,
            highlightthickness=0,
        )
        surface.grid(row=0, column=0, sticky="nw", padx=4, pady=4)
        surface.create_image(0, 0, image=self._cms_form_img, anchor="nw")
        self._cms_surface = surface

        def sx(value):
            return int(round(value * scale))

        def sy(value):
            return int(round(value * scale))

        field_font = ("Arial", 12)
        line_font = ("Arial", 12)
        field_height = max(18, sy(24))
        mini_height = max(14, sy(18))
        entry_border = "#1f2937"
        # Section-specific nudges tuned against the current sample form scan.
        top_x_nudge, top_y_nudge = self._overlay_offsets.get("top", [1, 3])
        mid_x_nudge, mid_y_nudge = self._overlay_offsets.get("mid", [1, 3])
        dx_x_nudge, dx_y_nudge = self._overlay_offsets.get("dx", [1, 2])
        line_x_nudge, line_y_nudge = self._overlay_offsets.get("line", [1, 2])
        bot_x_nudge, bot_y_nudge = self._overlay_offsets.get("bot", [1, 2])

        def bind_field_selection(widget, field_key):
            widget.bind("<Button-1>", lambda e, k=field_key: self._select_overlay_field(k), add="+")
            widget.bind("<FocusIn>", lambda e, k=field_key: self._select_overlay_field(k), add="+")
            widget.bind("<ButtonPress-1>", lambda e, k=field_key: self._start_field_drag(e, k), add="+")
            widget.bind("<B1-Motion>", lambda e, k=field_key: self._drag_field_motion(e, k), add="+")
            widget.bind("<ButtonRelease-1>", lambda e, k=field_key: self._end_field_drag(e, k), add="+")
            widget.bind("<Shift-ButtonPress-1>", lambda e, k=field_key: self._start_field_resize_drag(e, k), add="+")
            widget.bind("<Shift-B1-Motion>", lambda e, k=field_key: self._drag_field_resize_motion(e, k), add="+")
            widget.bind("<Shift-ButtonRelease-1>", lambda e, k=field_key: self._end_field_resize_drag(e, k), add="+")

        def add_entry(name, x, y, width, *, height=None, justify="left", x_nudge=0, y_nudge=0):
            field_dx, field_dy = self._overlay_field_offsets.get(name, [0, 0])
            size_dw, size_dh = self._overlay_field_size_offsets.get(name, [0, 0])
            widget = tk.Entry(
                surface,
                textvariable=fld(name),
                font=field_font,
                bd=1,
                relief="solid",
                highlightthickness=1,
                highlightbackground=entry_border,
                highlightcolor=entry_border,
                bg="white",
                fg="black",
                insertbackground="black",
                justify=justify,
            )
            bind_field_selection(widget, name)
            base_w = sx(width)
            base_h = height or field_height
            item_id = surface.create_window(
                sx(x + x_nudge + field_dx),
                sy(y + y_nudge + field_dy),
                window=widget,
                anchor="nw",
                width=max(12, base_w + sx(size_dw)),
                height=max(12, base_h + sy(size_dh)),
            )
            self._field_window_ids[name] = item_id
            self._field_window_meta[name] = {"item_id": item_id, "base_w": base_w, "base_h": base_h}
            return widget

        def add_service_entry(var_map, name, x, y, width, *, justify="left", x_nudge=0, y_nudge=0, field_key=None):
            var = tk.StringVar()
            var_map[name] = var
            field_id = field_key or name
            field_dx, field_dy = self._overlay_field_offsets.get(field_id, [0, 0])
            size_dw, size_dh = self._overlay_field_size_offsets.get(field_id, [0, 0])
            widget = tk.Entry(
                surface,
                textvariable=var,
                font=line_font,
                bd=1,
                relief="solid",
                highlightthickness=1,
                highlightbackground=entry_border,
                highlightcolor=entry_border,
                bg="white",
                fg="black",
                insertbackground="black",
                justify=justify,
            )
            bind_field_selection(widget, field_id)
            base_w = sx(width)
            base_h = max(16, sy(22))
            item_id = surface.create_window(
                sx(x + x_nudge + field_dx),
                sy(y + y_nudge + field_dy),
                window=widget,
                anchor="nw",
                width=max(12, base_w + sx(size_dw)),
                height=max(12, base_h + sy(size_dh)),
            )
            self._field_window_ids[field_id] = item_id
            self._field_window_meta[field_id] = {"item_id": item_id, "base_w": base_w, "base_h": base_h}

        def add_top_entry(name, x, y, width, **kwargs):
            return add_entry(name, x, y, width, x_nudge=top_x_nudge, y_nudge=top_y_nudge, **kwargs)

        def add_mid_entry(name, x, y, width, **kwargs):
            return add_entry(name, x, y, width, x_nudge=mid_x_nudge, y_nudge=mid_y_nudge, **kwargs)

        def add_dx_entry(name, x, y, width, **kwargs):
            return add_entry(name, x, y, width, x_nudge=dx_x_nudge, y_nudge=dx_y_nudge, **kwargs)

        def add_bottom_entry(name, x, y, width, **kwargs):
            return add_entry(name, x, y, width, x_nudge=bot_x_nudge, y_nudge=bot_y_nudge, **kwargs)

        def add_line_entry(var_map, name, x, y, width, field_key, **kwargs):
            return add_service_entry(
                var_map,
                name,
                x,
                y,
                width,
                x_nudge=line_x_nudge,
                y_nudge=line_y_nudge,
                field_key=field_key,
                **kwargs,
            )

        # Top / patient / insured area
        add_top_entry("ins_type_medicare", 434, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type_medicaid", 489, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type_tricare", 548, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type_champva", 604, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type_group", 663, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type_feca", 718, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type_other", 771, 183, 28, height=mini_height, justify="center")
        add_top_entry("ins_type", 808, 183, 110)
        add_top_entry("ins_id", 760, 208, 360)
        add_top_entry("patient_name", 44, 279, 372)
        add_top_entry("patient_dob", 492, 281, 110, justify="center")
        add_top_entry("patient_sex", 665, 281, 18, justify="center")
        add_top_entry("patient_sex_f", 688, 281, 18, justify="center")
        add_top_entry("ins_name", 760, 279, 368)
        add_top_entry("patient_address", 40, 333, 386)
        add_top_entry("ins_relation_self", 486, 333, 28, height=mini_height, justify="center")
        add_top_entry("ins_relation_spouse", 533, 333, 28, height=mini_height, justify="center")
        add_top_entry("ins_relation_child", 580, 333, 28, height=mini_height, justify="center")
        add_top_entry("ins_relation_other", 627, 333, 28, height=mini_height, justify="center")
        add_top_entry("ins_address2", 760, 333, 368)
        add_top_entry("patient_city", 40, 386, 335)
        add_top_entry("patient_state", 392, 386, 36, justify="center")
        add_top_entry("patient_zip", 40, 444, 158)
        add_top_entry("ins_city2", 760, 386, 318)
        add_top_entry("ins_state2", 1088, 386, 38, justify="center")
        add_top_entry("patient_phone", 216, 444, 210, justify="center")
        add_top_entry("ins_zip2", 760, 444, 150)
        add_top_entry("ins_group", 760, 499, 368)
        add_top_entry("ins_plan", 760, 617, 368)
        add_top_entry("ins_phone", 934, 444, 192, justify="center")
        add_top_entry("patient_status", 486, 444, 193)
        add_top_entry("patient_status_single", 488, 472, 28, height=mini_height, justify="center")
        add_top_entry("patient_status_married", 535, 472, 28, height=mini_height, justify="center")
        add_top_entry("patient_status_other", 582, 472, 28, height=mini_height, justify="center")
        add_top_entry("patient_status_employed", 488, 500, 28, height=mini_height, justify="center")
        add_top_entry("patient_status_full_time", 535, 500, 28, height=mini_height, justify="center")
        add_top_entry("patient_status_part_time", 582, 500, 28, height=mini_height, justify="center")
        add_top_entry("other_ins_name", 40, 500, 386)
        add_top_entry("other_ins_policy", 40, 556, 386)
        add_top_entry("reserved_nucc_b", 40, 614, 386)
        add_top_entry("reserved_nucc_c", 40, 672, 386)
        add_top_entry("other_ins_dob", 434, 558, 144, justify="center")
        add_top_entry("other_ins_sex", 604, 558, 22, justify="center")
        add_top_entry("other_ins_sex_f", 632, 558, 22, justify="center")
        add_top_entry("other_ins_employer", 434, 615, 242)
        add_top_entry("patient_sig", 110, 738, 338)
        add_top_entry("ins_dob", 816, 555, 178, justify="center")
        add_top_entry("ins_sex", 1032, 555, 16, justify="center")
        add_top_entry("ins_sex_f", 1054, 555, 16, justify="center")
        add_top_entry("other_claim_id", 760, 613, 368)
        add_top_entry("ins_sig", 787, 738, 300)
        add_top_entry("other_plan", 40, 672, 386)
        add_top_entry("other_plan_yes", 434, 675, 28, height=mini_height, justify="center")
        add_top_entry("other_plan_no", 482, 675, 28, height=mini_height, justify="center")
        add_top_entry("patient_auth_yes", 433, 739, 26, height=mini_height, justify="center")
        add_top_entry("patient_auth_no", 461, 739, 26, height=mini_height, justify="center")

        add_top_entry("patient_sig_date", 502, 738, 120, justify="center")
        # Mid form
        add_mid_entry("illness_date", 38, 819, 148)
        add_mid_entry("ref_provider", 38, 876, 370)
        add_mid_entry("ref_npi", 459, 876, 58)
        add_mid_entry("illness_qual", 206, 819, 72, justify="center")
        add_mid_entry("other_date", 432, 819, 149, justify="center")
        add_mid_entry("other_date_qual", 600, 819, 63, justify="center")
        add_mid_entry("unable_from", 816, 819, 127, justify="center")
        add_mid_entry("unable_to", 997, 819, 128, justify="center")
        add_mid_entry("add_info", 38, 935, 640)
        add_mid_entry("ref_qual", 421, 876, 38, justify="center")
        add_mid_entry("auth_number", 760, 990, 368)
        add_mid_entry("hospital_from", 817, 876, 128, justify="center")
        add_mid_entry("hospital_to", 998, 876, 128, justify="center")

        add_mid_entry("outside_lab", 816, 935, 114, justify="center")
        add_mid_entry("outside_lab_charge", 972, 935, 152, justify="right")
        add_mid_entry("related_emp_yes", 760, 500, 28, height=mini_height, justify="center")
        add_mid_entry("related_emp_no", 792, 500, 28, height=mini_height, justify="center")
        add_mid_entry("related_auto_yes", 760, 530, 28, height=mini_height, justify="center")
        add_mid_entry("related_auto_no", 792, 530, 28, height=mini_height, justify="center")
        add_mid_entry("related_auto_state", 826, 530, 42, height=mini_height, justify="center")
        add_mid_entry("related_other_yes", 760, 560, 28, height=mini_height, justify="center")
        add_mid_entry("related_other_no", 792, 560, 28, height=mini_height, justify="center")
        add_mid_entry("reserved_local_use", 760, 588, 368)
        # Diagnosis box
        add_dx_entry("dx1", 95, 973, 110)
        add_dx_entry("dx2", 286, 973, 110)
        add_dx_entry("dx3", 477, 973, 110)
        add_dx_entry("dx4", 669, 973, 110)
        add_dx_entry("dx5", 95, 1003, 110)
        add_dx_entry("dx6", 286, 1003, 110)
        add_dx_entry("dx7", 477, 1003, 110)
        add_dx_entry("dx8", 669, 1003, 110)
        add_dx_entry("dx9", 95, 1033, 110)
        add_dx_entry("dx10", 286, 1033, 110)
        add_dx_entry("dx11", 477, 1033, 110)
        add_dx_entry("dx12", 669, 1033, 110)

        add_dx_entry("resubmission_code", 816, 970, 108, justify="center")
        add_dx_entry("original_ref_no", 936, 970, 188)
        # Service lines
        line_y = [1046, 1103, 1160, 1217, 1274, 1331]
        for line_idx, y in enumerate(line_y, start=1):
            sl_row = {}
            add_line_entry(sl_row, "from_date", 47, y, 108, f"sl{line_idx}_from_date")
            add_line_entry(sl_row, "to_date", 162, y, 108, f"sl{line_idx}_to_date")
            add_line_entry(sl_row, "pos", 285, y, 40, f"sl{line_idx}_pos", justify="center")
            add_line_entry(sl_row, "cpt", 369, y, 96, f"sl{line_idx}_cpt", justify="center")
            add_line_entry(sl_row, "modifier", 468, y, 110, f"sl{line_idx}_modifier", justify="center")
            add_line_entry(sl_row, "dx_ptr", 648, y, 60, f"sl{line_idx}_dx_ptr", justify="center")
            add_line_entry(sl_row, "charge", 769, y, 84, f"sl{line_idx}_charge", justify="right")
            add_line_entry(sl_row, "units", 872, y, 42, f"sl{line_idx}_units", justify="center")
            add_line_entry(sl_row, "epsdt", 919, y, 24, f"sl{line_idx}_epsdt", justify="center")
            add_line_entry(sl_row, "family_plan", 946, y, 30, f"sl{line_idx}_family_plan", justify="center")
            add_line_entry(sl_row, "id_qual", 979, y, 34, f"sl{line_idx}_id_qual", justify="center")
            add_line_entry(sl_row, "npi", 1000, y, 124, f"sl{line_idx}_npi", justify="center")
            self._sl_vars.append(sl_row)

        # Bottom / provider area
        add_bottom_entry("tax_id", 38, 1361, 116)
        add_bottom_entry("tax_id_ein", 223, 1361, 24, height=mini_height, justify="center")
        add_bottom_entry("tax_id_ssn", 472, 1497, 24, height=mini_height, justify="center")
        add_bottom_entry("patient_acct", 381, 1361, 160)
        add_bottom_entry("accept_assign_yes", 605, 1361, 24, height=mini_height, justify="center")
        add_bottom_entry("accept_assign_no", 636, 1361, 24, height=mini_height, justify="center")
        add_bottom_entry("total_charge", 774, 1361, 116, justify="center")
        add_bottom_entry("amount_paid", 928, 1361, 98, justify="center")
        add_bottom_entry("provider_sig", 38, 1421, 250)
        add_bottom_entry("provider_sig_date", 294, 1421, 66, justify="center")
        add_bottom_entry("billing_date", 271, 1497, 88, justify="center")
        add_bottom_entry("facility_name", 378, 1421, 268)
        add_bottom_entry("facility_address", 378, 1456, 268)
        add_bottom_entry("facility_city_state_zip", 378, 1488, 268)
        add_bottom_entry("facility_npi", 496, 1497, 148, justify="center")
        add_bottom_entry("facility_other_id", 661, 1497, 148, justify="center")
        add_bottom_entry("billing_name", 771, 1421, 270)
        add_bottom_entry("billing_address", 771, 1456, 270)
        add_bottom_entry("billing_city_state_zip", 771, 1488, 270)
        add_bottom_entry("billing_phone", 1000, 1361, 130, justify="center")
        add_bottom_entry("billing_qualifier", 756, 1497, 24, justify="center")
        add_bottom_entry("billing_npi", 780, 1497, 148, justify="center")
        add_bottom_entry("billing_other_id", 947, 1497, 178, justify="center")

        lookup_btn = ttk.Button(
            parent,
            text="Lookup Diagnosis Code",
            command=lambda: DSMPicker(self, lambda c: self._dx_insert(c)),
        )
        lookup_btn.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))

    def _dx_insert(self, code):
        for key in ["dx1","dx2","dx3","dx4","dx5","dx6","dx7","dx8","dx9","dx10","dx11","dx12"]:
            if not self._cv[key].get():
                self._cv[key].set(code)
                return
        self._cv["dx12"].set(code)

    def _nudge_overlay(self, dx, dy):
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode == "field":
            if not self._selected_overlay_field:
                return
            field_offset = self._overlay_field_offsets.setdefault(self._selected_overlay_field, [0, 0])
            field_offset[0] += dx
            field_offset[1] += dy
            self._update_align_status()
            self._rebuild_form_preserve_values()
            return

        section = self._align_section.get().strip() if hasattr(self, "_align_section") else "top"
        if section not in self._overlay_offsets:
            section = "top"
        self._overlay_offsets[section][0] += dx
        self._overlay_offsets[section][1] += dy
        self._update_align_status()
        self._rebuild_form_preserve_values()

    def _select_overlay_field(self, field_key):
        self._selected_overlay_field = field_key
        self._update_align_status()

    def _start_field_drag(self, event, field_key):
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode != "field":
            self._drag_state = None
            return
        if event.state & 0x0001:
            # Shift-drag is reserved for resize.
            self._drag_state = None
            return
        self._select_overlay_field(field_key)
        self._drag_state = {
            "field": field_key,
            "x_root": event.x_root,
            "y_root": event.y_root,
        }

    def _drag_field_motion(self, event, field_key):
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode != "field":
            return
        if not self._drag_state or self._drag_state.get("field") != field_key:
            return
        item_id = self._field_window_ids.get(field_key)
        if item_id is None or not hasattr(self, "_cms_surface"):
            return

        dx_px = event.x_root - self._drag_state["x_root"]
        dy_px = event.y_root - self._drag_state["y_root"]
        if dx_px == 0 and dy_px == 0:
            return

        self._cms_surface.move(item_id, dx_px, dy_px)
        self._drag_state["x_root"] = event.x_root
        self._drag_state["y_root"] = event.y_root

        off = self._overlay_field_offsets.setdefault(field_key, [0.0, 0.0])
        off[0] += dx_px / self._form_scale
        off[1] += dy_px / self._form_scale
        self._update_align_status()

    def _end_field_drag(self, event, field_key):
        if self._drag_state and self._drag_state.get("field") == field_key:
            self._drag_state = None
            self._rebuild_form_preserve_values()

    def _start_field_resize_drag(self, event, field_key):
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode != "field":
            self._resize_drag_state = None
            return
        self._select_overlay_field(field_key)
        self._resize_drag_state = {
            "field": field_key,
            "x_root": event.x_root,
            "y_root": event.y_root,
        }

    def _drag_field_resize_motion(self, event, field_key):
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode != "field":
            return
        if not self._resize_drag_state or self._resize_drag_state.get("field") != field_key:
            return
        meta = self._field_window_meta.get(field_key)
        if not meta or not hasattr(self, "_cms_surface"):
            return

        dx_px = event.x_root - self._resize_drag_state["x_root"]
        dy_px = event.y_root - self._resize_drag_state["y_root"]
        if dx_px == 0 and dy_px == 0:
            return

        size_off = self._overlay_field_size_offsets.setdefault(field_key, [0.0, 0.0])
        size_off[0] += dx_px / self._form_scale
        size_off[1] += dy_px / self._form_scale

        new_w = max(12, meta["base_w"] + int(round(size_off[0] * self._form_scale)))
        new_h = max(12, meta["base_h"] + int(round(size_off[1] * self._form_scale)))
        self._cms_surface.itemconfigure(meta["item_id"], width=new_w, height=new_h)

        self._resize_drag_state["x_root"] = event.x_root
        self._resize_drag_state["y_root"] = event.y_root
        self._update_align_status()

    def _end_field_resize_drag(self, event, field_key):
        if self._resize_drag_state and self._resize_drag_state.get("field") == field_key:
            self._resize_drag_state = None
            self._rebuild_form_preserve_values()

    def _reset_overlay_field(self):
        if not self._selected_overlay_field:
            return
        self._overlay_field_offsets[self._selected_overlay_field] = [0, 0]
        self._overlay_field_size_offsets[self._selected_overlay_field] = [0, 0]
        self._update_align_status()
        self._rebuild_form_preserve_values()

    def _resize_overlay_field(self, dw, dh):
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode != "field" or not self._selected_overlay_field:
            return
        size_offset = self._overlay_field_size_offsets.setdefault(self._selected_overlay_field, [0, 0])
        size_offset[0] += dw
        size_offset[1] += dh
        self._update_align_status()
        self._rebuild_form_preserve_values()

    def _reset_overlay_section(self):
        section = self._align_section.get().strip() if hasattr(self, "_align_section") else "top"
        defaults = {
            "top": [1, 3],
            "mid": [1, 3],
            "dx": [1, 2],
            "line": [1, 2],
            "bot": [1, 2],
        }
        self._overlay_offsets[section] = defaults.get(section, [1, 3]).copy()
        self._update_align_status()
        self._rebuild_form_preserve_values()

    def _export_alignment_offsets(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="cms1500_alignment_offsets.json",
            title="Export CMS Alignment Offsets",
        )
        if not path:
            return

        payload = {
            "section_offsets": {
                key: [int(round(vals[0])), int(round(vals[1]))]
                for key, vals in self._overlay_offsets.items()
            },
            "field_offsets": {
                key: [int(round(vals[0])), int(round(vals[1]))]
                for key, vals in self._overlay_field_offsets.items()
            },
            "field_size_offsets": {
                key: [int(round(vals[0])), int(round(vals[1]))]
                for key, vals in self._overlay_field_size_offsets.items()
            },
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            messagebox.showinfo("Export Alignment", f"Alignment offsets exported to:\n{path}")
        except OSError as ex:
            messagebox.showerror("Export Alignment", f"Could not export alignment offsets:\n{ex}")

    def _update_align_status(self):
        if not hasattr(self, "_align_status"):
            return
        mode = self._align_mode.get().strip() if hasattr(self, "_align_mode") else "section"
        if mode == "field":
            field = self._selected_overlay_field or "none"
            x_off, y_off = self._overlay_field_offsets.get(field, [0, 0]) if field != "none" else (0, 0)
            w_off, h_off = self._overlay_field_size_offsets.get(field, [0, 0]) if field != "none" else (0, 0)
            self._align_status.config(
                text=f"field {field}: x={int(round(x_off))}, y={int(round(y_off))}, w={int(round(w_off))}, h={int(round(h_off))}"
            )
            return
        section = self._align_section.get().strip() if hasattr(self, "_align_section") else "top"
        if section not in self._overlay_offsets:
            section = "top"
        x_off, y_off = self._overlay_offsets[section]
        self._align_status.config(text=f"{section}: x={x_off}, y={y_off}")

    def _rebuild_form_preserve_values(self):
        existing = self._collect_form_data() if hasattr(self, "_cv") else {}
        for child in self._form_frame.winfo_children():
            child.destroy()
        self._build_form(self._form_frame)
        if not existing:
            return
        for key, var in self._cv.items():
            if key in existing:
                var.set(str(existing[key]) if existing[key] is not None else "")
        sls = existing.get("service_lines", [])
        for i, sl_vars in enumerate(self._sl_vars):
            sl = sls[i] if i < len(sls) else {}
            for key, var in sl_vars.items():
                var.set(str(sl.get(key, "")) if sl.get(key) is not None else "")

    def load_from_session(self, pid, sessions):
        """Pre-populate form from patient + sessions."""
        from cms_pdf import cms_form_data_from_patient
        pt  = db.get_patient(pid)
        prov = db.get_provider()
        fd = cms_form_data_from_patient(pt, sessions, prov)
        self._apply_relation_checkboxes(fd)
        for fld, var in self._cv.items():
            if fld in fd:
                var.set(str(fd[fld]) if fd[fld] is not None else "")
        # Service lines
        sls = fd.get("service_lines", [])
        for i, sl_vars in enumerate(self._sl_vars):
            sl = sls[i] if i < len(sls) else {}
            for key, var in sl_vars.items():
                var.set(str(sl.get(key, "")) if sl.get(key) is not None else "")
        self._current_pid = pid
        self._current_sessions = sessions

    def _apply_relation_checkboxes(self, fd):
        relation = str(fd.get("ins_relation", "") or "").strip().lower()
        rel_map = {
            "self": "ins_relation_self",
            "spouse": "ins_relation_spouse",
            "child": "ins_relation_child",
            "other": "ins_relation_other",
        }
        for key in rel_map.values():
            fd.setdefault(key, "")
        target = rel_map.get(relation)
        if target and not str(fd.get(target, "")).strip():
            fd[target] = "X"

    def _auto_populate(self):
        # Ask user to pick a patient
        picker = tk.Toplevel(self)
        picker.title("Select Patient for CMS-1500")
        picker.geometry("480x340")
        picker.grab_set()

        ttk.Label(picker, text="Select Patient:").pack(anchor="w", padx=10, pady=6)
        sv = tk.StringVar()
        pts = db.get_all_patients("Active")
        names = [f"{p['last_name']}, {p['first_name']}  (ID:{p['id']})" for p in pts]
        cb = ttk.Combobox(picker, textvariable=sv, values=names, width=44, state="readonly")
        cb.pack(padx=10, pady=4)

        ttk.Label(picker, text="Select Sessions (hold Ctrl for multi-select):").pack(anchor="w", padx=10, pady=4)
        sess_lv = tk.Listbox(picker, selectmode="multiple", height=10, font=FONT_UI)
        sess_lv.pack(fill="both", expand=True, padx=10)

        def on_pt_select(*a):
            idx = cb.current()
            if idx < 0:
                return
            pid = pts[idx]["id"]
            sess_lv.delete(0, "end")
            for s in db.get_sessions_for_patient(pid):
                sess_lv.insert("end", f"{fmt_date(s['session_date'])}  {s['cpt_code']}  {fmt_money(s['fee'])}")
        cb.bind("<<ComboboxSelected>>", on_pt_select)

        def do_populate():
            idx = cb.current()
            if idx < 0:
                messagebox.showwarning("Select", "Please choose a patient.", parent=picker)
                return
            pid = pts[idx]["id"]
            sel_indices = sess_lv.curselection()
            sessions = db.get_sessions_for_patient(pid)
            chosen = [sessions[i] for i in sel_indices] if sel_indices else sessions[:1]
            self.load_from_session(pid, [dict(s) for s in chosen])
            picker.destroy()

        ttk.Button(picker, text="Populate Form", command=do_populate).pack(pady=8)

    def _collect_form_data(self):
        fd = {k: v.get().strip() for k, v in self._cv.items()}
        fd["service_lines"] = []
        for sl in self._sl_vars:
            entry = {k: v.get().strip() for k, v in sl.items()}
            if any(entry.values()):
                fd["service_lines"].append(entry)
        fd["alignment_offsets"] = {
            "section_offsets": {
                key: [int(round(vals[0])), int(round(vals[1]))]
                for key, vals in self._overlay_offsets.items()
            },
            "field_offsets": {
                key: [int(round(vals[0])), int(round(vals[1]))]
                for key, vals in self._overlay_field_offsets.items()
            },
            "field_size_offsets": {
                key: [int(round(vals[0])), int(round(vals[1]))]
                for key, vals in self._overlay_field_size_offsets.items()
            },
        }
        return fd

    def _alignment_section_for_field(self, field_name):
        if field_name.startswith("sl"):
            return "line"
        if field_name.startswith("dx") or field_name in {"resubmission_code", "original_ref_no"}:
            return "dx"
        if field_name in {
            "illness_date", "ref_provider", "ref_npi", "illness_qual", "other_date",
            "other_date_qual", "unable_from", "unable_to", "add_info", "ref_qual",
            "auth_number", "hospital_from", "hospital_to", "outside_lab",
            "outside_lab_charge", "related_emp_yes", "related_emp_no", "related_auto_yes",
            "related_auto_no", "related_auto_state", "related_other_yes",
            "related_other_no", "reserved_local_use",
        }:
            return "mid"
        if field_name in {
            "tax_id", "tax_id_ein", "tax_id_ssn", "patient_acct", "accept_assign", "accept_assign_yes", "accept_assign_no", "total_charge",
            "amount_paid", "provider_sig", "provider_sig_date", "billing_date",
            "facility_name", "facility_address", "facility_city_state_zip", "facility_qualifier",
            "facility_npi", "facility_other_id", "billing_name", "billing_address",
            "billing_city_state_zip", "billing_phone", "billing_qualifier", "billing_npi",
            "billing_other_id",
        }:
            return "bot"
        return "top"

    def _preview_aligned_xy(self, field_name, x, y, section_offsets, field_offsets):
        section = self._alignment_section_for_field(field_name)
        sec_x, sec_y = section_offsets.get(section, [0, 0])
        fld_x, fld_y = field_offsets.get(field_name, [0, 0])
        return x + sec_x + fld_x, y + sec_y + fld_y

    def _save_claim(self):
        fd = self._collect_form_data()
        pid = getattr(self, "_current_pid", None)
        if pid is None:
            messagebox.showinfo("Info", "Use 'Auto-Populate from Patient' before saving.")
            return
        try:
            total = sum(float(sl.get("charge", 0) or 0) for sl in fd["service_lines"])
        except (ValueError, TypeError):
            total = 0.0
        data = {
            "patient_id":   pid,
            "billing_date": fd.get("billing_date") or current_date_str(),
            "form_data":    json.dumps(fd),
            "total_charge": total,
            "claim_status": "Draft",
        }
        db.save_claim(data)
        self._refresh_claims()
        messagebox.showinfo("Saved", "Claim saved as Draft.")

    def _export_pdf(self):
        from cms_pdf import build_cms1500_pdf
        fd = self._collect_form_data()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"CMS1500_{fd.get('patient_name','claim').replace(', ','_')}.pdf",
        )
        if not path:
            return
        ok = build_cms1500_pdf(path, fd)
        if ok:
            messagebox.showinfo("Exported", f"PDF saved to:\n{path}")
        else:
            messagebox.showerror("Error",
                "Could not generate PDF.\n"
                "Make sure 'reportlab' is installed:\n"
                "  pip install reportlab")

    def _preview_print(self):
        fd = self._collect_form_data()
        sample_image = ASSETS_DIR / "cms1500_sample.png"
        if not sample_image.exists() or Image is None or ImageTk is None:
            messagebox.showerror(
                "Print Preview",
                "The CMS-1500 form background is not available for preview.",
            )
            return

        original = Image.open(sample_image)
        max_width = 1180
        scale = min(1.0, max_width / float(original.width))
        if scale < 1.0:
            display = original.resize(
                (int(original.width * scale), int(original.height * scale)),
                Image.Resampling.LANCZOS,
            )
        else:
            display = original.copy()

        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("CMS-1500 Print Preview")
        win.geometry("1240x900")

        frm = ttk.Frame(win)
        frm.pack(fill="both", expand=True)

        cv = tk.Canvas(frm, bg="#f5f5f5", highlightthickness=0)
        vsb = ttk.Scrollbar(frm, orient="vertical", command=cv.yview)
        hsb = ttk.Scrollbar(frm, orient="horizontal", command=cv.xview)
        cv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        cv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        preview_img = ImageTk.PhotoImage(display)
        cv.create_image(0, 0, image=preview_img, anchor="nw")
        cv.config(scrollregion=(0, 0, display.width, display.height))
        win._preview_img = preview_img

        def sx(v):
            return int(round(v * scale))

        def sy(v):
            return int(round(v * scale))

        font_size = 12
        line_size = 12

        alignment = fd.get("alignment_offsets", {})
        section_offsets = alignment.get("section_offsets", self._overlay_offsets)
        field_offsets = alignment.get("field_offsets", self._overlay_field_offsets)

        def draw_field(name, x, y, *, size=None, anchor="nw"):
            val = fd.get(name, "")
            if val is None:
                return
            text = str(val).strip()
            if not text:
                return
            ax, ay = self._preview_aligned_xy(name, x, y, section_offsets, field_offsets)
            cv.create_text(
                sx(ax),
                sy(ay),
                text=text,
                anchor=anchor,
                fill="black",
                font=("Arial", size or font_size),
            )

        for name, x, y in [
            ("ins_id", 760, 212),
            ("patient_name", 44, 283),
            ("patient_dob", 492, 285),
            ("patient_sex", 665, 285),
            ("patient_sex_f", 688, 285),
            ("ins_name", 760, 283),
            ("patient_address", 40, 337),
            ("ins_relation_self", 486, 337),
            ("ins_relation_spouse", 533, 337),
            ("ins_relation_child", 580, 337),
            ("ins_relation_other", 627, 337),
            ("ins_address2", 760, 337),
            ("patient_city", 40, 390),
            ("patient_state", 392, 390),
            ("patient_zip", 40, 448),
            ("patient_phone", 216, 448),
            ("ins_city2", 760, 390),
            ("ins_state2", 1088, 390),
            ("ins_zip2", 760, 448),
            ("ins_phone", 934, 448),
            ("other_ins_name", 40, 504),
            ("other_ins_policy", 40, 560),
            ("other_ins_sex", 604, 559),
            ("other_ins_sex_f", 632, 559),
            ("ins_group", 760, 503),
            ("ins_dob", 816, 559),
            ("ins_sex", 1032, 559),
            ("ins_sex_f", 1054, 559),
            ("other_claim_id", 760, 617),
            ("ins_plan", 760, 621),
            ("other_plan", 40, 676),
            ("patient_sig", 110, 742),
            ("patient_sig_date", 502, 742),
            ("ins_sig", 787, 742),
            ("illness_date", 38, 823),
            ("illness_qual", 206, 823),
            ("other_date", 432, 823),
            ("other_date_qual", 600, 823),
            ("unable_from", 816, 823),
            ("unable_to", 997, 823),
            ("ref_provider", 38, 880),
            ("ref_qual", 421, 880),
            ("ref_npi", 459, 880),
            ("hospital_from", 817, 880),
            ("hospital_to", 998, 880),
            ("add_info", 38, 939),
            ("outside_lab", 816, 939),
            ("outside_lab_charge", 972, 939),
            ("dx1", 95, 977),
            ("dx2", 286, 977),
            ("dx3", 477, 977),
            ("dx4", 669, 977),
            ("dx5", 95, 1007),
            ("dx6", 286, 1007),
            ("dx7", 477, 1007),
            ("dx8", 669, 1007),
            ("dx9", 95, 1037),
            ("dx10", 286, 1037),
            ("dx11", 477, 1037),
            ("dx12", 669, 1037),
            ("resubmission_code", 816, 974),
            ("original_ref_no", 936, 974),
            ("auth_number", 760, 994),
            ("tax_id", 38, 1365),
            ("tax_id_ein", 223, 1365),
            ("patient_acct", 381, 1365),
            ("accept_assign_yes", 605, 1365),
            ("accept_assign_no", 636, 1365),
            ("total_charge", 774, 1365),
            ("amount_paid", 928, 1365),
            ("provider_sig", 38, 1425),
            ("provider_sig_date", 294, 1425),
            ("billing_date", 271, 1501),
            ("facility_name", 378, 1425),
            ("facility_address", 378, 1460),
            ("facility_city_state_zip", 378, 1492),
            ("tax_id_ssn", 472, 1501),
            ("facility_npi", 496, 1501),
            ("facility_other_id", 661, 1501),
            ("billing_name", 771, 1425),
            ("billing_address", 771, 1460),
            ("billing_city_state_zip", 771, 1492),
            ("billing_phone", 1000, 1365),
            ("billing_qualifier", 756, 1501),
            ("billing_npi", 780, 1501),
            ("billing_other_id", 947, 1501),
        ]:
            draw_field(name, x, y)

        line_y = [1048, 1105, 1162, 1219, 1276, 1333]
        service_lines = fd.get("service_lines", [])
        for i, y in enumerate(line_y):
            sl = service_lines[i] if i < len(service_lines) else {}
            if not sl:
                continue

            def draw_sl(key, x):
                txt = str(sl.get(key, "") or "").strip()
                if txt:
                    sl_field = f"sl{i+1}_{key}"
                    ax, ay = self._preview_aligned_xy(sl_field, x, y, section_offsets, field_offsets)
                    cv.create_text(sx(ax), sy(ay), text=txt, anchor="nw", fill="black", font=("Arial", line_size))

            draw_sl("from_date", 47)
            draw_sl("to_date", 162)
            draw_sl("pos", 285)
            draw_sl("cpt", 369)
            draw_sl("modifier", 468)
            draw_sl("dx_ptr", 648)
            draw_sl("charge", 769)
            draw_sl("units", 872)
            draw_sl("epsdt", 919)
            draw_sl("family_plan", 946)
            draw_sl("id_qual", 979)
            draw_sl("npi", 1000)

    def _refresh_claims(self):
        self.claim_tv.delete(*self.claim_tv.get_children())
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT c.id, p.last_name||', '||p.first_name AS nm, c.billing_date, c.claim_status
               FROM cms_claims c JOIN patients p ON c.patient_id=p.id
               ORDER BY c.billing_date DESC LIMIT 200"""
        ).fetchall()
        conn.close()
        for r in rows:
            self.claim_tv.insert("", "end", iid=str(r["id"]),
                                 values=(r["id"], r["nm"], fmt_date(r["billing_date"]), r["claim_status"]))

    def _new_claim(self):
        for v in self._cv.values():
            v.set("")
        for sl in self._sl_vars:
            for v in sl.values():
                v.set("")
        self._current_pid = None
        self._current_sessions = []
        prov = db.get_provider()
        self._cv["tax_id"].set(prov.get("tax_id",""))
        self._cv["billing_npi"].set(prov.get("npi",""))
        self._cv["billing_name"].set(prov.get("practice_name",""))
        self._cv["billing_address"].set(prov.get("address",""))
        self._cv["billing_date"].set(date.today().strftime("%m/%d/%Y"))
        if int(prov.get("accept_assign", 1) or 0):
            self._cv["accept_assign_yes"].set("X")
            self._cv["accept_assign_no"].set("")
        else:
            self._cv["accept_assign_yes"].set("")
            self._cv["accept_assign_no"].set("X")

    def _open_claim(self, event=None):
        sel = self.claim_tv.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a claim to open.")
            return
        cid = int(sel[0])
        conn = db.get_connection()
        claim = conn.execute("SELECT * FROM cms_claims WHERE id=?", (cid,)).fetchone()
        conn.close()
        if not claim:
            return
        try:
            fd = json.loads(claim["form_data"])
        except (json.JSONDecodeError, TypeError):
            fd = {}
        # Backward compatibility for saved claims that used a single accept_assign value.
        if "accept_assign_yes" not in fd and "accept_assign_no" not in fd and "accept_assign" in fd:
            if str(fd.get("accept_assign", "")).strip().lower() in {"1", "true", "yes", "y", "x"}:
                fd["accept_assign_yes"] = "X"
                fd["accept_assign_no"] = ""
            else:
                fd["accept_assign_yes"] = ""
                fd["accept_assign_no"] = "X"
        self._apply_relation_checkboxes(fd)
        self._current_pid = claim["patient_id"]
        for key, var in self._cv.items():
            if key in fd:
                var.set(str(fd[key]) if fd[key] is not None else "")
        sls = fd.get("service_lines", [])
        for i, sl_vars in enumerate(self._sl_vars):
            sl = sls[i] if i < len(sls) else {}
            for key, var in sl_vars.items():
                var.set(str(sl.get(key, "")) if sl.get(key) is not None else "")


# ─── Reports Tab ───────────────────────────────────────────────────────────────

class ReportsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._build()

    def _build(self):
        ttk.Label(self, text="Reports", font=FONT_H1).pack(anchor="w", padx=14, pady=(12, 6))

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        def report_btn(txt, cmd):
            btn(frm, txt, cmd, "Accent.TButton").pack(fill="x", padx=4, pady=4)

        report_btn("Patient Roster (Active)",    self._rpt_active_patients)
        report_btn("Patient Roster (Inactive)",  self._rpt_inactive_patients)
        report_btn("Sessions This Month",        self._rpt_sessions_month)
        report_btn("Sessions by Patient",        self._rpt_sessions_patient)
        report_btn("Billing Summary",            self._rpt_billing_summary)
        report_btn("Outstanding Balances",       self._rpt_outstanding)
        report_btn("Export All Patients (CSV)",  self._export_patients_csv)
        report_btn("Export Sessions (CSV)",      self._export_sessions_csv)
        report_btn("Export Billing (CSV)",       self._export_billing_csv)

        self._output = tk.Text(frm, font=FONT_MONO, wrap="none", height=22,
                               relief="solid", borderwidth=1, background="#fafafa")
        sb_v = ttk.Scrollbar(frm, orient="vertical",   command=self._output.yview)
        sb_h = ttk.Scrollbar(frm, orient="horizontal", command=self._output.xview)
        self._output.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)
        self._output.pack(side="top", fill="both", expand=True, pady=(10, 0))
        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")

    def _show(self, text):
        self._output.config(state="normal")
        self._output.delete("1.0", "end")
        self._output.insert("1.0", text)
        self._output.config(state="disabled")

    def _rpt_active_patients(self):
        rows = db.get_all_patients("Active")
        lines = [f"{'ID':>4}  {'Last Name':<18}  {'First':<14}  {'DOB':<12}  "
                 f"{'Phone':<14}  {'Insurance':<22}  Dx1"]
        lines.append("-" * 100)
        for r in rows:
            lines.append(f"{r['id']:>4}  {r['last_name']:<18}  {r['first_name']:<14}  "
                         f"{fmt_date(r['dob']):<12}  {r['phone_home'] or r['phone_cell']:<14}  "
                         f"{r['ins_name']:<22}  {r['dx1']}")
        lines.append(f"\nTotal: {len(rows)} active patients")
        self._show("\n".join(lines))

    def _rpt_inactive_patients(self):
        rows = db.get_all_patients("Inactive")
        lines = [f"{'ID':>4}  {'Last Name':<18}  {'First':<14}  Intake Date"]
        lines.append("-" * 70)
        for r in rows:
            lines.append(f"{r['id']:>4}  {r['last_name']:<18}  {r['first_name']:<14}  {fmt_date(r['intake_date'])}")
        lines.append(f"\nTotal: {len(rows)} inactive patients")
        self._show("\n".join(lines))

    def _rpt_sessions_month(self):
        today = date.today()
        month_prefix = today.strftime("%Y-%m")
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT s.session_date, p.last_name, p.first_name, s.session_type, s.cpt_code, s.fee, s.signed
               FROM session_notes s JOIN patients p ON s.patient_id=p.id
               WHERE s.session_date LIKE ?
               ORDER BY s.session_date""",
            (f"{month_prefix}%",)
        ).fetchall()
        conn.close()
        lines = [f"Sessions for {today.strftime('%B %Y')}", ""]
        lines.append(f"{'Date':<12}  {'Patient':<24}  {'Type':<14}  {'CPT':<8}  {'Fee':>8}  Signed")
        lines.append("-" * 88)
        total_fee = 0.0
        for r in rows:
            total_fee += float(r["fee"] or 0)
            lines.append(f"{fmt_date(r['session_date']):<12}  "
                         f"{r['last_name']+', '+r['first_name']:<24}  "
                         f"{r['session_type']:<14}  {r['cpt_code']:<8}  "
                         f"{fmt_money(r['fee']):>8}  {'✓' if r['signed'] else ''}")
        lines.append(f"\nTotal sessions: {len(rows)}   Total fees: {fmt_money(total_fee)}")
        self._show("\n".join(lines))

    def _rpt_sessions_patient(self):
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT p.id, p.last_name, p.first_name, COUNT(s.id) AS cnt,
                      SUM(s.fee) AS total_fee
               FROM patients p
               LEFT JOIN session_notes s ON s.patient_id=p.id
               WHERE p.status='Active'
               GROUP BY p.id ORDER BY p.last_name""").fetchall()
        conn.close()
        lines = [f"{'Patient':<26}  {'Sessions':>9}  {'Total Fees':>12}"]
        lines.append("-" * 56)
        for r in rows:
            lines.append(f"{r['last_name']+', '+r['first_name']:<26}  "
                         f"{r['cnt']:>9}  {fmt_money(r['total_fee'] or 0):>12}")
        self._show("\n".join(lines))

    def _rpt_billing_summary(self):
        tc, tp, tb = db.get_billing_summary()
        lines = ["Billing Summary – All Patients", "=" * 40,
                 f"Total Charges:  {fmt_money(tc):>12}",
                 f"Total Paid:     {fmt_money(tp):>12}",
                 f"Total Balance:  {fmt_money(tb):>12}"]
        # Per-patient breakdown
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT p.last_name, p.first_name,
                      SUM(b.charge) AS tc, SUM(b.payment)+SUM(b.ins_payment) AS tp,
                      SUM(b.charge)-SUM(b.payment)-SUM(b.ins_payment)-SUM(b.adjustment) AS tb
               FROM billing_records b JOIN patients p ON b.patient_id=p.id
               GROUP BY p.id ORDER BY tb DESC LIMIT 50"""
        ).fetchall()
        conn.close()
        lines += ["", f"\n{'Patient':<26}  {'Charges':>10}  {'Paid':>10}  {'Balance':>10}"]
        lines.append("-" * 62)
        for r in rows:
            lines.append(f"{r['last_name']+', '+r['first_name']:<26}  "
                         f"{fmt_money(r['tc'] or 0):>10}  {fmt_money(r['tp'] or 0):>10}  "
                         f"{fmt_money(r['tb'] or 0):>10}")
        self._show("\n".join(lines))

    def _rpt_outstanding(self):
        conn = db.get_connection()
        rows = conn.execute(
            """SELECT p.last_name, p.first_name, p.phone_home, p.phone_cell,
                      SUM(b.charge)-SUM(b.payment)-SUM(b.ins_payment)-SUM(b.adjustment) AS bal
               FROM billing_records b JOIN patients p ON b.patient_id=p.id
               GROUP BY p.id HAVING bal > 0.005
               ORDER BY bal DESC"""
        ).fetchall()
        conn.close()
        lines = ["Outstanding Balances", "=" * 56,
                 f"{'Patient':<26}  {'Phone':<14}  {'Balance':>10}"]
        lines.append("-" * 56)
        for r in rows:
            phone = r["phone_home"] or r["phone_cell"] or ""
            lines.append(f"{r['last_name']+', '+r['first_name']:<26}  {phone:<14}  {fmt_money(r['bal']):>10}")
        self._show("\n".join(lines))

    def _export_patients_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="patients_export.csv")
        if not path:
            return
        import csv as _csv
        rows = db.get_all_patients("Active") + db.get_all_patients("Inactive")
        keys = rows[0].keys() if rows else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        messagebox.showinfo("Exported", f"Patients exported to:\n{path}")

    def _export_sessions_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="sessions_export.csv")
        if not path:
            return
        import csv as _csv
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT s.*, p.last_name, p.first_name FROM session_notes s JOIN patients p ON s.patient_id=p.id"
        ).fetchall()
        conn.close()
        keys = rows[0].keys() if rows else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        messagebox.showinfo("Exported", f"Sessions exported to:\n{path}")

    def _export_billing_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile="billing_export.csv")
        if not path:
            return
        import csv as _csv
        conn = db.get_connection()
        rows = conn.execute(
            "SELECT b.*, p.last_name, p.first_name FROM billing_records b JOIN patients p ON b.patient_id=p.id"
        ).fetchall()
        conn.close()
        keys = rows[0].keys() if rows else []
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = _csv.writer(f)
            w.writerow(keys)
            for r in rows:
                w.writerow([r[k] for k in keys])
        messagebox.showinfo("Exported", f"Billing exported to:\n{path}")


# ─── Settings Tab ──────────────────────────────────────────────────────────────

class SettingsTab(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._vars = {}
        self._build()
        self._load()

    def _refresh_app_views(self, *, patients=False, sessions=False, billing=False, select_tab=None):
        app = self.winfo_toplevel()
        if patients and hasattr(app, "tab_patients"):
            app.tab_patients.refresh()
        if sessions and hasattr(app, "tab_sessions"):
            app.tab_sessions.refresh()
        if billing and hasattr(app, "tab_billing"):
            app.tab_billing.refresh()
        if hasattr(app, "_update_stats"):
            app._update_stats()
        if select_tab is not None and hasattr(app, "nb"):
            app.nb.select(select_tab)

    def _fld(self, name, default=""):
        v = tk.StringVar(value=default)
        self._vars[name] = v
        return v

    def _build(self):
        nb = ttk.Notebook(self)
        self._nb = nb
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Provider / Practice ───────────────────────────────────────────────
        f1 = ttk.Frame(nb, padding=14)
        nb.add(f1, text=" Provider / Practice ")
        for c in range(4): f1.columnconfigure(c, weight=1)

        fields = [
            ("Practice Name",         "practice_name",  0, 0),
            ("Provider Last Name",     "provider_last",  1, 0),
            ("Provider First Name",    "provider_first", 1, 2),
            ("Provider Suffix",        "provider_suffix",2, 0),
            ("Credentials (LCSW etc.)","credentials",    2, 2),
            ("NPI",                    "npi",            3, 0),
            ("Tax ID",                 "tax_id",         3, 2),
            ("Tax ID Type (EIN/SSN)",  "tax_id_type",    4, 0),
            ("ID Qualifier",           "id_qualifier",   4, 2),
            ("Taxonomy Codes",         "license_num",    5, 0),
            ("UPIN (legacy)",          "upin",           5, 2),
            ("Address",                "address",        6, 0),
            ("City",                   "city",           7, 0),
            ("State",                  "state",          7, 2),
            ("Zip",                    "zip",            8, 0),
            ("Phone",                  "phone",          8, 2),
            ("Fax",                    "fax",            9, 0),
            ("Email",                  "email",          9, 2),
            ("Default POS",            "default_pos",   10, 0),
        ]
        for lbl, key, r, c in fields:
            ttk.Label(f1, text=lbl).grid(row=r, column=c, sticky="e", padx=4, pady=3)
            ttk.Entry(f1, textvariable=self._fld(key), width=26).grid(
                row=r, column=c+1, sticky="ew", padx=(0,12))

        self.accept_var = tk.IntVar(value=1)
        assign_frm = ttk.Frame(f1)
        assign_frm.grid(row=11, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Label(assign_frm, text="Assignment:").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(assign_frm, text="Accept Assignment", variable=self.accept_var, value=1).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(assign_frm, text="Do Not Accept Assignment", variable=self.accept_var, value=0).pack(side="left")

        btn(f1, "Save Provider Settings", self._save_provider, "Accent.TButton"
            ).grid(row=12, column=0, columnspan=2, pady=10, padx=4, sticky="w")

        # ── Data Import ───────────────────────────────────────────────────────
        f2 = ttk.Frame(nb, padding=14)
        nb.add(f2, text=" Data Import ")

        ttk.Label(f2, text="Import Data from Any Medical Software",
                  font=FONT_LG).pack(anchor="w", pady=(0, 6))

        info_txt = (
            "TheraTrak Pro accepts CSV files exported from any medical practice management\n"
            "or EHR system (SimplePractice, Kareo, TherapyNotes, Practice Fusion, etc.).\n\n"
            "HOW TO EXPORT FROM YOUR CURRENT SOFTWARE:\n"
            "  1. Open your current software and go to its export / reports section.\n"
            "  2. Choose CSV or Excel format, then save the file.\n"
            "  3. Use the Import buttons below to bring data into TheraTrak Pro.\n\n"
            "TheraTrak Pro automatically maps common column names — exact header names\n"
            "are not required.  For best results, download a CSV template to see the\n"
            "expected structure and rename your exported columns accordingly."
        )
        ttk.Label(f2, text=info_txt, justify="left", wraplength=680).pack(anchor="w")

        ttk.Separator(f2).pack(fill="x", pady=10)

        # ── Import buttons ────────────────────────────────────────────────────
        ttk.Label(f2, text="Import Records", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(0, 4))
        import_frm = ttk.Frame(f2)
        import_frm.pack(anchor="w")
        btn(import_frm, "⬆  Import Patients (CSV)",
            self._import_patients_csv, "Accent.TButton").grid(row=0, column=0, padx=4, pady=4)
        btn(import_frm, "⬆  Import Sessions (CSV)",
            self._import_sessions_csv, "Accent.TButton").grid(row=0, column=1, padx=4, pady=4)
        btn(import_frm, "⬆  Import Billing (CSV)",
            self._import_billing_csv,  "Accent.TButton").grid(row=0, column=2, padx=4, pady=4)

        ttk.Separator(f2).pack(fill="x", pady=10)

        # ── CSV Templates ─────────────────────────────────────────────────────
        ttk.Label(f2, text="Download CSV Templates", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(0, 4))
        ttk.Label(f2,
                  text="Download a blank template to see the required columns and format for each record type.",
                  foreground=MUTED).pack(anchor="w", pady=(0, 6))
        tpl_frm = ttk.Frame(f2)
        tpl_frm.pack(anchor="w")
        btn(tpl_frm, "⬇  Patients Template",
            self._download_patients_template, "TButton").grid(row=0, column=0, padx=4, pady=4)
        btn(tpl_frm, "⬇  Sessions Template",
            self._download_sessions_template, "TButton").grid(row=0, column=1, padx=4, pady=4)
        btn(tpl_frm, "⬇  Billing Template",
            self._download_billing_template,  "TButton").grid(row=0, column=2, padx=4, pady=4)

        ttk.Separator(f2).pack(fill="x", pady=10)

        ttk.Label(f2, text="Import Log", font=("Calibri", 10, "bold")).pack(anchor="w", pady=(0, 2))
        self._import_log = tk.Text(f2, height=10, font=FONT_MONO, state="disabled",
                                   relief="solid", borderwidth=1, background="#fafafa")
        self._import_log.pack(fill="both", expand=True)

    def show_provider_profile(self):
        if hasattr(self, "_nb"):
            self._nb.select(0)

    def _load(self):
        prov = db.get_provider()
        for key, var in self._vars.items():
            var.set(str(prov.get(key, "") or ""))
        self.accept_var.set(prov.get("accept_assign", 1))

    def _save_provider(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        data["accept_assign"] = self.accept_var.get()
        db.save_provider(data)
        messagebox.showinfo("Saved", "Provider settings saved.")

    def _log(self, text):
        self._import_log.config(state="normal")
        self._import_log.insert("end", text + "\n")
        self._import_log.see("end")
        self._import_log.config(state="disabled")

    def _import_patients_csv(self):
        path = filedialog.askopenfilename(
            title="Select Patients CSV",
            filetypes=[("CSV Files","*.csv"),("Text Files","*.txt"),("All","*.*")])
        if not path:
            return
        import migration
        count, warns = migration.import_patients_csv(path)
        self._log(f"Patients imported: {count}")
        for w in warns[:20]:
            self._log(f"  WARN: {w}")
        self._refresh_app_views(patients=True, select_tab=0)
        messagebox.showinfo("Import Complete", f"Imported {count} patients.\n{len(warns)} warnings.")

    def _import_sessions_csv(self):
        path = filedialog.askopenfilename(
            title="Select Sessions CSV",
            filetypes=[("CSV Files","*.csv"),("Text Files","*.txt"),("All","*.*")])
        if not path:
            return
        import migration
        count, warns = migration.import_sessions_csv(path)
        self._log(f"Sessions imported: {count}")
        for w in warns[:20]:
            self._log(f"  WARN: {w}")
        self._refresh_app_views(sessions=True)
        messagebox.showinfo("Import Complete", f"Imported {count} sessions.\n{len(warns)} warnings.")

    def _import_billing_csv(self):
        path = filedialog.askopenfilename(
            title="Select Billing CSV",
            filetypes=[("CSV Files","*.csv"),("Text Files","*.txt"),("All","*.*")])
        if not path:
            return
        import migration
        count, warns = migration.import_billing_csv(path)
        self._log(f"Billing records imported: {count}")
        for w in warns[:20]:
            self._log(f"  WARN: {w}")
        self._refresh_app_views(billing=True)
        messagebox.showinfo("Import Complete", f"Imported {count} billing records.\n{len(warns)} warnings.")

    def _download_patients_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Patients CSV Template",
            initialfile="patients_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_patients_template(path)
        self._log(f"Patients template saved: {path}")
        messagebox.showinfo("Template Saved", f"Patients CSV template saved to:\n{path}")

    def _download_sessions_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Sessions CSV Template",
            initialfile="sessions_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_sessions_template(path)
        self._log(f"Sessions template saved: {path}")
        messagebox.showinfo("Template Saved", f"Sessions CSV template saved to:\n{path}")

    def _download_billing_template(self):
        path = filedialog.asksaveasfilename(
            title="Save Billing CSV Template",
            initialfile="billing_template.csv",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All", "*.*")])
        if not path:
            return
        import migration
        migration.write_billing_template(path)
        self._log(f"Billing template saved: {path}")
        messagebox.showinfo("Template Saved", f"Billing CSV template saved to:\n{path}")


class VersionManagerDialog(tk.Toplevel):
    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self.title("Version Manager")
        self.geometry("420x280")
        self.resizable(False, False)
        self._build()
        self._refresh()
        self.grab_set()

    def _build(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Current Version", font=FONT_LG).pack(anchor="w")
        self.lbl_ver = ttk.Label(main, text="", font=("Calibri", 14, "bold"), foreground=ACCENT)
        self.lbl_ver.pack(anchor="w", pady=(2, 10))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=4)
        btn(btn_frame, "+ Build", self._bump_build, "Accent.TButton").pack(side="left", padx=3)
        btn(btn_frame, "+ Patch", self._bump_patch, "Accent.TButton").pack(side="left", padx=3)
        btn(btn_frame, "+ Minor", self._bump_minor, "Accent.TButton").pack(side="left", padx=3)
        btn(btn_frame, "+ Major", self._bump_major, "Accent.TButton").pack(side="left", padx=3)

        set_frame = lframe(main, "Set Exact Version")
        set_frame.pack(fill="x", pady=8)

        self.var_major = tk.StringVar()
        self.var_minor = tk.StringVar()
        self.var_patch = tk.StringVar()
        self.var_build = tk.StringVar()

        ttk.Label(set_frame, text="Major").grid(row=0, column=0, padx=4, pady=3)
        ttk.Entry(set_frame, textvariable=self.var_major, width=6).grid(row=0, column=1, padx=4)
        ttk.Label(set_frame, text="Minor").grid(row=0, column=2, padx=4)
        ttk.Entry(set_frame, textvariable=self.var_minor, width=6).grid(row=0, column=3, padx=4)
        ttk.Label(set_frame, text="Patch").grid(row=0, column=4, padx=4)
        ttk.Entry(set_frame, textvariable=self.var_patch, width=6).grid(row=0, column=5, padx=4)
        ttk.Label(set_frame, text="Build").grid(row=0, column=6, padx=4)
        ttk.Entry(set_frame, textvariable=self.var_build, width=6).grid(row=0, column=7, padx=4)

        btn(set_frame, "Apply Version", self._set_version).grid(row=1, column=0, columnspan=8, pady=6)

        self.lbl_status = ttk.Label(main, text="", foreground=MUTED)
        self.lbl_status.pack(anchor="w", pady=(4, 0))

        bottom = ttk.Frame(main)
        bottom.pack(fill="x", side="bottom", pady=(10, 0))
        btn(bottom, "Close", self.destroy).pack(side="right")

    def _refresh(self):
        data = vm.get_version_data()
        self.lbl_ver.config(text=vm.get_version_string())
        self.var_major.set(str(data["major"]))
        self.var_minor.set(str(data["minor"]))
        self.var_patch.set(str(data["patch"]))
        self.var_build.set(str(data["build"]))

    def _notify_change(self):
        self._refresh()
        if self.on_change:
            self.on_change(vm.get_version_string())

    def _bump_build(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_build()}")
        self._notify_change()

    def _bump_patch(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_patch()}")
        self._notify_change()

    def _bump_minor(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_minor()}")
        self._notify_change()

    def _bump_major(self):
        self.lbl_status.config(text=f"Updated: {vm.bump_major()}")
        self._notify_change()

    def _set_version(self):
        try:
            major = int(self.var_major.get().strip())
            minor = int(self.var_minor.get().strip())
            patch = int(self.var_patch.get().strip())
            build = int(self.var_build.get().strip())
        except ValueError:
            messagebox.showerror("Invalid", "Version numbers must be integers.", parent=self)
            return
        version_text = vm.set_version(major, minor, patch, build)
        self.lbl_status.config(text=f"Updated: {version_text}")
        self._notify_change()


# ─── Main Application Window ───────────────────────────────────────────────────

class TheraTrakApp(tk.Tk):
    def __init__(self, current_user=None):
        super().__init__()
        apply_window_icon(self)
        self.current_user = current_user
        self._version = vm.get_version_string()
        self.title(f"TheraTrak Pro - {self._version}")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        win_w = min(1280, screen_w - 40)
        win_h = min(820, screen_h - 60)
        self.geometry(f"{win_w}x{win_h}+{(screen_w-win_w)//2}+{(screen_h-win_h)//2}")
        self.minsize(900, 600)

        # Configure style before building widgets
        self._style = ttk_style()

        # Init database
        db.initialize_db()

        self._build_header()
        self._build_notebook()
        self._build_statusbar()
        self._build_menu()
        self._update_stats()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_header(self):
        hdr = tk.Frame(self, bg=HDR_BG, height=56)
        hdr.pack(fill="x", side="top")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="TheraTrak Pro", bg=HDR_BG, fg=HDR_FG,
                 font=("Calibri", 20, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text="Combined Therapy & Billing", bg=HDR_BG, fg="#93c5fd",
                 font=("Calibri", 10)).pack(side="left", padx=2)
        self._lbl_version = tk.Label(hdr, text=self._version, bg=HDR_BG, fg="#bfdbfe",
                         font=("Calibri", 9, "bold"))
        self._lbl_version.pack(side="left", padx=10)

        stats = tk.Frame(hdr, bg=HDR_BG)
        stats.pack(side="right", padx=14)
        self._lbl_date  = tk.Label(stats, text="", bg=HDR_BG, fg="#93c5fd", font=FONT_SM)
        self._lbl_pts   = tk.Label(stats, text="", bg=HDR_BG, fg="#93c5fd", font=FONT_SM)
        self._lbl_user  = tk.Label(stats, text="", bg=HDR_BG, fg="#bfdbfe", font=FONT_SM)
        self._lbl_date.pack(side="bottom", anchor="e")
        self._lbl_pts.pack(side="bottom", anchor="e")
        self._lbl_user.pack(side="bottom", anchor="e")

    def _build_notebook(self):
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True)

        self.tab_patients = PatientsTab(self.nb)
        self.tab_sessions = SessionNotesTab(self.nb)
        self.tab_billing  = BillingTab(self.nb)
        self.tab_cms      = CMS1500Tab(self.nb)
        self.tab_reports  = ReportsTab(self.nb)
        self.tab_settings = SettingsTab(self.nb)

        self.nb.add(self.tab_patients, text="  Patients  ")
        self.nb.add(self.tab_sessions, text="  Session Notes  ")
        self.nb.add(self.tab_billing,  text="  Billing  ")
        self.nb.add(self.tab_cms,      text="  CMS-1500  ")
        self.nb.add(self.tab_reports,  text="  Reports  ")
        self.nb.add(self.tab_settings, text="  Settings / Import  ")

    def _build_statusbar(self):
        sb = tk.Frame(self, bg="#e2e8f0", height=24)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._status_lbl = tk.Label(sb, text="Ready", bg="#e2e8f0", fg=MUTED, font=FONT_SM)
        self._status_lbl.pack(side="left", padx=8)
        db_path = str(db.DB_PATH)
        tk.Label(sb, text=f"Database: {db_path}", bg="#e2e8f0", fg=MUTED, font=FONT_SM).pack(side="right", padx=8)

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Patient",    command=lambda: PatientDialog(self, on_save=lambda _: self.tab_patients.refresh()))
        file_menu.add_command(label="New Session",    command=lambda: SessionDialog(self, on_save=lambda _: self.tab_sessions.refresh()))
        file_menu.add_separator()
        file_menu.add_command(label="User Directory", command=self._open_user_directory)
        file_menu.add_command(label="Provider Profile", command=self._open_provider_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database", command=self._backup_db)
        file_menu.add_separator()
        file_menu.add_command(label="Logout", command=self._logout)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        nav_menu = tk.Menu(menubar, tearoff=0)
        nav_menu.add_command(label="Patients",        command=lambda: self.nb.select(0))
        nav_menu.add_command(label="Session Notes",   command=lambda: self.nb.select(1))
        nav_menu.add_command(label="Billing",         command=lambda: self.nb.select(2))
        nav_menu.add_command(label="CMS-1500",        command=lambda: self.nb.select(3))
        nav_menu.add_command(label="Reports",         command=lambda: self.nb.select(4))
        nav_menu.add_command(label="Settings/Import", command=lambda: self.nb.select(5))
        nav_menu.add_command(label="Provider Profile", command=self._open_provider_profile)
        menubar.add_cascade(label="Navigate", menu=nav_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates)
        help_menu.add_command(label="User Guide", command=self._open_user_guide)
        help_menu.add_command(label="About TheraTrak Pro", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _update_stats(self):
        self._version = vm.get_version_string()
        self.title(f"TheraTrak Pro - {self._version}")
        self._lbl_version.config(text=self._version)
        n = db.count_patients("Active")
        self._lbl_pts.config(text=f"Active Patients: {n}")
        self._lbl_date.config(text=date.today().strftime("%A, %B %d, %Y"))
        if self.current_user:
            who = f"{self.current_user['first_name']} {self.current_user['last_name']} ({self.current_user['username']})"
            self._lbl_user.config(text=f"Logged In: {who}")
        else:
            self._lbl_user.config(text="Logged In: —")

    def set_logged_in_user(self, user):
        self.current_user = user
        self._update_stats()

    def _open_user_directory(self):
        UserDirectoryDialog(self)

    def _open_provider_profile(self):
        self.nb.select(5)
        if hasattr(self, "tab_settings"):
            self.tab_settings.show_provider_profile()

    def _logout(self):
        if not messagebox.askyesno("Logout", "Are you sure you want to log out?", parent=self):
            return
        self.current_user = None
        self._update_stats()
        self.withdraw()
        login = LoginDialog(self)
        self.wait_window(login)
        if login.user:
            self.set_logged_in_user(login.user)
            self.deiconify()
        else:
            self.destroy()

    def _backup_db(self):
        from shutil import copy2
        dest = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database","*.db"),("All","*.*")],
            initialfile=f"theratrak_backup_{date.today().strftime('%Y%m%d')}.db")
        if dest:
            copy2(db.DB_PATH, dest)
            messagebox.showinfo("Backup", f"Database backed up to:\n{dest}")

    def _open_user_guide(self):
        guide_candidates = [
            APP_ROOT / "USER_GUIDE.md",
            ASSETS_DIR / "USER_GUIDE.md",
        ]
        guide_path = next((p for p in guide_candidates if p.exists()), None)
        if not guide_path:
            looked_in = "\n".join(str(p) for p in guide_candidates)
            messagebox.showerror("User Guide", f"User guide file not found.\n\nLooked in:\n{looked_in}")
            return
        try:
            content = guide_path.read_text(encoding="utf-8")
        except OSError as ex:
            messagebox.showerror("User Guide", f"Could not read user guide:\n{ex}")
            return

        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("TheraTrak Pro User Guide")
        win.geometry("980x760")
        win.minsize(760, 560)

        frm = ttk.Frame(win, padding=10)
        frm.pack(fill="both", expand=True)
        txt = tk.Text(frm, wrap="word", font=FONT_UI, relief="solid", borderwidth=1)
        sb = ttk.Scrollbar(frm, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        txt.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        txt.insert("1.0", content)
        txt.configure(state="disabled")

    def _about(self):
        user_line = ""
        if self.current_user:
            user_line = f"Logged In User: {self.current_user['username']} ({self.current_user['role']})\n"
        messagebox.showinfo(
            "About TheraTrak Pro",
            "TheraTrak Pro\n"
            f"Version: {self._version}\n"
            f"{user_line}"
            "Combined Therapy Practice Management & CMS-1500 Billing\n\n"
            "Features:\n"
            "  • Patient management & demographics\n"
            "  • Session notes with DSM-5 / ICD-10 lookup\n"
            "  • Billing ledger & payment tracking\n"
            "  • CMS-1500 claim form + PDF export\n"
            "  • Reports & CSV data export\n"
            "  • Data migration from Notes 444 files\n\n"
            f"Database: {db.DB_PATH}"
        )

    def _parse_version_tuple(self, text):
        nums = [int(n) for n in re.findall(r"\d+", text or "")]
        if not nums:
            return (0, 0, 0, 0)
        while len(nums) < 4:
            nums.append(0)
        return tuple(nums[:4])

    def _format_tag_version(self, tag: str) -> str:
        """Convert a raw GitHub tag like 'v1.0.4-build5' to '1.0.4 Build 5'."""
        nums = [int(n) for n in re.findall(r"\d+", tag or "")]
        while len(nums) < 4:
            nums.append(0)
        major, minor, patch, build = nums[:4]
        return f"{major}.{minor}.{patch} Build {build}"

    def _pick_installer_asset(self, payload):
        assets = payload.get("assets") or []
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe") and "installer" in name:
                return asset
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe"):
                return asset
        return None

    def _backup_database_for_update(self):
        db_path = Path(db.DB_PATH)
        if not db_path.exists():
            return None
        backup_dir = UPDATE_TEMP_DIR / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"theratrak_preupdate_{ts}.db"
        shutil.copy2(db_path, backup_path)
        return backup_path

    def _download_file_with_progress(self, url, destination):
        progress_win = tk.Toplevel(self)
        apply_window_icon(progress_win)
        progress_win.title("Downloading Update")
        progress_win.resizable(False, False)
        progress_win.transient(self)
        progress_win.grab_set()
        progress_win.protocol("WM_DELETE_WINDOW", lambda: None)

        frame = ttk.Frame(progress_win, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Downloading latest installer...").pack(anchor="w")
        status_var = tk.StringVar(value="Starting download...")
        ttk.Label(frame, textvariable=status_var).pack(anchor="w", pady=(6, 8))

        bar = ttk.Progressbar(frame, orient="horizontal", length=380, mode="indeterminate")
        bar.pack(fill="x")

        progress_win.update_idletasks()
        width = max(420, progress_win.winfo_reqwidth())
        height = max(120, progress_win.winfo_reqheight())
        x = max(0, (progress_win.winfo_screenwidth() - width) // 2)
        y = max(0, (progress_win.winfo_screenheight() - height) // 2)
        progress_win.geometry(f"{width}x{height}+{x}+{y}")
        progress_win.update()

        downloaded = 0
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TheraTrak-Pro"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total_raw = resp.headers.get("Content-Length")
                total = int(total_raw) if total_raw and total_raw.isdigit() else int(getattr(resp, "length", 0) or 0)

                if total > 0:
                    bar.configure(mode="determinate", maximum=total, value=0)
                else:
                    bar.start(12)
                    progress_win.update()

                with destination.open("wb") as out_f:
                    while True:
                        chunk = resp.read(1024 * 128)
                        if not chunk:
                            break
                        out_f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            bar["value"] = downloaded
                            pct = min(100.0, (downloaded / total) * 100.0)
                            status_var.set(f"Downloaded {pct:.1f}% ({downloaded // 1024} KB of {total // 1024} KB)")
                            progress_win.title(f"Downloading Update - {pct:.1f}%")
                        else:
                            status_var.set(f"Downloaded {downloaded // 1024} KB")
                            progress_win.title(f"Downloading Update - {downloaded // 1024} KB")

                        progress_win.update()
        finally:
            if bar.cget("mode") == "indeterminate":
                bar.stop()
            progress_win.destroy()

    def _launch_installer_after_exit(self, installer_path):
        install_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "TheraTrak Pro"
        app_exe = install_dir / "TheraTrak Pro.exe"
        if not app_exe.exists() and getattr(sys, "frozen", False):
            app_exe = Path(sys.executable)
        updater_bat = UPDATE_TEMP_DIR / "run_theratrak_update.bat"
        log_file = Path(os.environ.get("TEMP", str(Path.home()))) / "theratrak_update.log"
        app_pid = os.getpid()

        lines = [
            "@echo off",
            "setlocal",
            f'set "INSTALLER={installer_path}"',
            f'set "APP_PID={app_pid}"',
            f'set "APP_EXE={app_exe}"',
            f'set "LOG={log_file}"',
            'echo [%date% %time%] Updater started > "%LOG%"',
            ':wait_close',
            'tasklist /FI "PID eq %APP_PID%" 2>nul | find "%APP_PID%" >nul',
            'if not errorlevel 1 (',
            '  ping 127.0.0.1 -n 2 >nul',
            '  goto wait_close',
            ')',
            'echo [%date% %time%] App exited, launching installer >> "%LOG%"',
            'start "" /wait "%INSTALLER%"',
            'echo [%date% %time%] Installer finished, errorlevel=%ERRORLEVEL% >> "%LOG%"',
            'if not "%APP_EXE%"=="" if exist "%APP_EXE%" (',
            '  echo [%date% %time%] Relaunching app: %APP_EXE% >> "%LOG%"',
            '  start "" "%APP_EXE%"',
            ')',
            'echo [%date% %time%] Update complete >> "%LOG%"',
            "endlocal",
            "exit /b 0",
        ]

        updater_bat.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        _append_startup_log(f"Prepared updater script: {updater_bat}")
        _append_startup_log(f"Update log will be written to: {log_file}")

        comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
        subprocess.Popen(
            [comspec, "/d", "/c", str(updater_bat)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

    def _check_for_updates(self):
        current_ver = self._version
        current_tuple = self._parse_version_tuple(current_ver)

        req = urllib.request.Request(
            GITHUB_LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "TheraTrak-Pro"
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception:
            messagebox.showwarning(
                "Check for Updates",
                "Could not contact the update server right now.\n\n"
                f"Current Version: {current_ver}\n\n"
                "You can still download the latest installer from:\n"
                f"{GITHUB_RELEASES_PAGE}"
            )
            return

        latest_tag = payload.get("tag_name") or payload.get("name") or ""
        latest_tuple = self._parse_version_tuple(latest_tag)
        latest_display = self._format_tag_version(latest_tag) if latest_tag else "Unknown"
        release_url = payload.get("html_url") or GITHUB_RELEASES_PAGE
        installer_asset = self._pick_installer_asset(payload)

        if latest_tuple > current_tuple:
            do_update = messagebox.askyesno(
                "Update Available",
                "A newer version of TheraTrak Pro is available.\n\n"
                f"Current Version: {current_ver}\n"
                f"Latest Version: {latest_display}\n\n"
                "Download and install it now?"
            )
            if not do_update:
                return

            if not installer_asset:
                messagebox.showwarning(
                    "Update Available",
                    "No installer asset was found on the latest release.\n\n"
                    "Opening releases page instead."
                )
                webbrowser.open(release_url)
                return

            asset_url = installer_asset.get("browser_download_url")
            asset_name = installer_asset.get("name") or "TheraTrak-Pro-Installer.exe"
            if not asset_url:
                webbrowser.open(release_url)
                return

            UPDATE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
            installer_path = UPDATE_TEMP_DIR / asset_name

            try:
                self._download_file_with_progress(asset_url, installer_path)
                backup_path = self._backup_database_for_update()
            except Exception as ex:
                messagebox.showerror(
                    "Update Failed",
                    "Could not download the installer automatically.\n\n"
                    f"Error: {ex}\n\n"
                    "Opening releases page instead."
                )
                webbrowser.open(release_url)
                return

            backup_msg = f"\nDatabase backup created at:\n{backup_path}" if backup_path else ""
            proceed = messagebox.askyesno(
                "Ready to Install Update",
                "The installer has been downloaded.\n\n"
                "TheraTrak Pro will now close, install the update, and reopen automatically.\n"
                "Your user profiles, patient records, and billing data will be preserved."
                f"{backup_msg}\n\n"
                "Continue?"
            )
            if not proceed:
                return

            try:
                self._launch_installer_after_exit(installer_path)
            except Exception as ex:
                messagebox.showerror(
                    "Update Failed",
                    f"Could not start the installer: {ex}"
                )
                return

            self.after(150, self._on_close)
            return

        if latest_tuple == current_tuple:
            messagebox.showinfo(
                "Check for Updates",
                "TheraTrak Pro is up to date.\n\n"
                f"Current Version: {current_ver}\n"
                f"Latest Version: {latest_display}"
            )
            return

        messagebox.showinfo(
            "Check for Updates",
            "You are running a newer build than the latest public release.\n\n"
            f"Current Version: {current_ver}\n"
            f"Latest Release: {latest_display}"
        )

    def _migration_help(self):
        messagebox.showinfo(
            "Data Migration Help",
            "To migrate your existing data from Notes 444:\n\n"
            "1. Open  H:\\Important Files\\Notes 444.EXE\n"
            "2. Go to File → Export Records\n"
            "3. Export each file as CSV:\n"
            "   • Patient records → patients.csv\n"
            "   • Session notes   → sessions.csv\n"
            "   • Payments        → billing.csv\n"
            "4. Go to Settings/Import tab in TheraTrak Pro\n"
            "5. Use the 'Import Patients/Sessions/Billing (CSV)' buttons\n\n"
            "The importer is flexible with column names and will\n"
            "attempt to map fields automatically.\n\n"
            "For billing (CMS-1500), your settings are entered once\n"
            "in Settings → Provider/Practice."
        )

    def _on_close(self):
        self.destroy()


# ─── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _install_crash_logger()
    _startup_self_check()
    try:
        db.initialize_db()
        app = TheraTrakApp()
        app.withdraw()

        login = LoginDialog(app)
        app.wait_window(login)

        if login.user:
            app.set_logged_in_user(login.user)
            if login.winfo_exists():
                login.destroy()
            app.deiconify()
            app.update_idletasks()
            try:
                app.state("zoomed")
            except tk.TclError:
                screen_w = app.winfo_screenwidth()
                screen_h = app.winfo_screenheight()
                app.geometry(f"{screen_w}x{screen_h}+0+0")
            app.mainloop()
        else:
            app.destroy()
    except Exception:
        _append_startup_log("Fatal startup failure:")
        _append_startup_log(traceback.format_exc().rstrip())
        raise
