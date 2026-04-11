"""
TheraTrak Pro
Combined therapy practice management and CMS-1500 application.

Python 3.10+  ·  Tkinter + ttk  ·  SQLite backend
"""

import json
import io
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

import database as db
import version_manager as vm
from app_paths import APP_ROOT, ASSETS_DIR, DB_FILE, ICON_FILE, VERSION_FILE

try:
    import fitz  # type: ignore[import-not-found]
    from PIL import Image, ImageTk  # type: ignore[import-not-found]
    PDF_RENDER_AVAILABLE = True
except Exception:
    fitz = None
    Image = None
    ImageTk = None
    PDF_RENDER_AVAILABLE = False

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
PLACE_CODES    = [("11 - Office", "11"), ("02 - Telehealth", "02"), ("12 - Home", "12"),
                  ("21 - Inpatient Hospital", "21"), ("22 - Outpatient Hospital", "22"),
                  ("23 - Emergency Room", "23")]
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
CMS_TEMPLATE_FILE = APP_ROOT / "CMS1500_template.pdf"

# Build lookup mapping for place of service codes
_PLACE_CODE_MAP = {p[0]: p[1] for p in PLACE_CODES}
_PLACE_CODE_REVERSE = {p[1]: p[0] for p in PLACE_CODES}


# ─── Utilities ─────────────────────────────────────────────────────────────────

def _extract_place_code(place_value: str, default: str = "11") -> str:
    """Extract place of service code from display format or return code if already code."""
    if not place_value:
        return default
    if place_value in _PLACE_CODE_MAP:
        return _PLACE_CODE_MAP[place_value]
    return place_value


def _get_place_display(place_code: str) -> str:
    """Get display format for place of service code, or return code if not found."""
    if not place_code:
        return "11 - Office"
    if place_code in _PLACE_CODE_REVERSE:
        return _PLACE_CODE_REVERSE[place_code]
    return place_code


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
    style.master.option_add("*Font", ("Arial", 12))
    style.master.option_add("*Text.Font", ("Arial", 12))
    style.master.option_add("*Entry.Font", ("Arial", 12))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, font=FONT_UI)
    style.configure("TButton", font=FONT_UI, padding=4)
    style.configure("TEntry", font=FONT_UI, padding=3)
    style.configure("TCombobox", font=FONT_UI)
    style.configure("TNotebook", background=HDR_BG, tabmargins=[2, 4, 2, 0])
    style.configure("TNotebook.Tab", background=HDR_BG, foreground="white", font=("Arial", 12, "bold"), padding=[10, 5])
    style.map("TNotebook.Tab", background=[("selected", BG), ("active", ACCENT)], foreground=[("selected", HDR_BG), ("active", "white")])
    style.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Arial", 12, "bold"), padding=5)
    style.map("Accent.TButton", background=[("active", ACCENT2), ("pressed", ACCENT2)])
    style.configure("Danger.TButton", background=DANGER, foreground="white", font=("Arial", 12, "bold"), padding=5)
    style.configure("Treeview", font=FONT_UI, rowheight=24, background=ROW_ODD, fieldbackground=ROW_ODD)
    style.configure("Treeview.Heading", font=("Arial", 12, "bold"), background=HDR_BG, foreground="white")
    style.map("Treeview", background=[("selected", SEL_BG)], foreground=[("selected", "#1e3a5f")])
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
    e.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=2, columnspan=colspan)
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
    """YYYY-MM-DD -> MM/DD/YYYY display string."""
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
        self.state('zoomed')
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

        ttk.Label(f1, text="Sig on File Date").grid(row=2, column=4, sticky="e", padx=4)
        ttk.Entry(f1, textvariable=self._fld("sig_on_file_date"), width=14).grid(row=2, column=5, sticky="w")

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
        ttk.Label(f3, text="Referring Taxonomy (17a)").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(f3, textvariable=self._fld("referring_taxonomy"), width=20).grid(row=2, column=1, sticky="w")

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
        try:
            pid = db.save_patient(data)
        except Exception as ex:
            messagebox.showerror("Save Error", f"Could not save patient:\n{ex}", parent=self)
            return
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
            if key == "fee":
                var.set(f"{float(v or 0):.2f}")
            else:
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
            messagebox.showinfo("Select", "Select a session to generate a CMS-1500 form.")
            return
        session_row = db.get_session(sid)
        if not session_row:
            return
        nb = self.master
        for i in range(nb.index("end")):
            if "CMS-1500" in nb.tab(i, "text"):
                nb.select(i)
                tab = nb.nametowidget(nb.tabs()[i])
                if hasattr(tab, "load_from_session"):
                    tab.load_from_session(session_row["patient_id"], [dict(session_row)])
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

        self._pt_label = ttk.Label(tb, text="", foreground=ACCENT, font=("Calibri", 10, "bold"))
        self._pt_label.pack(side="right", padx=8)

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        cols = (
            "id", "patient_name", "record_date", "description", "charge", "payment",
            "ins_payment", "adjustment", "balance", "payment_type",
        )
        self.tv = ttk.Treeview(frm, columns=cols, show="headings", selectmode="browse")
        hdrs = [
            ("ID", 40), ("Patient", 160), ("Date", 90), ("Description", 160),
            ("Charge", 80), ("Pt Paid", 75), ("Ins Paid", 75), ("Adj", 70),
            ("Balance", 80), ("Method", 100),
        ]
        for (h, w), c in zip(hdrs, cols):
            self.tv.heading(c, text=h, anchor="w")
            self.tv.column(c, width=w, stretch=c in ("patient_name", "description"))
        vsb = ttk.Scrollbar(frm, orient="vertical", command=self.tv.yview)
        self.tv.configure(yscrollcommand=vsb.set)
        self.tv.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tv.bind("<Double-1>", lambda e: self._edit_record())
        self.tv.tag_configure("even", background=ROW_EVEN)
        self.tv.tag_configure("credit", foreground=SUCCESS)
        self.tv.tag_configure("overdue", foreground=DANGER)

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
            self.tv.insert(
                "",
                "end",
                iid=str(r["id"]),
                tags=(tag,),
                values=(
                    r["id"],
                    name,
                    fmt_date(r["record_date"]),
                    r["description"],
                    fmt_money(r["charge"]),
                    fmt_money(r["payment"]),
                    fmt_money(r["ins_payment"]),
                    fmt_money(r["adjustment"]),
                    fmt_money(r["balance"]),
                    r["payment_type"],
                ),
            )
            total_c += float(r["charge"] or 0)
            total_p += float(r["payment"] or 0) + float(r["ins_payment"] or 0)
            total_b += bal

        self._lbl_charges.config(text=f"Total Charges: {fmt_money(total_c)}")
        self._lbl_paid.config(text=f"Total Paid: {fmt_money(total_p)}")
        self._lbl_balance.config(
            text=f"Balance: {fmt_money(total_b)}",
            foreground=(DANGER if total_b > 0 else SUCCESS),
        )

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
        self._field_defs = [
            ("Patient Name", "patient_name"),
            ("Patient DOB", "patient_dob"),
            ("Patient Sex", "patient_sex"),
            ("Patient SSN", "patient_ssn"),
            ("Insured ID", "ins_id"),
            ("Insured Name", "insured_name"),
            ("Insured DOB", "insured_dob"),
            ("Insured Sex", "insured_sex"),
            ("Insured Relation", "insured_relation"),
            ("Insured Group", "insured_group"),
            ("Insured Plan Type", "insured_plan_type"),
            ("Insured Plan Name", "insured_plan_name"),
            ("Other Insured Name", "other_insured_name"),
            ("Other Insured ID", "other_insured_id"),
            ("Other Insured Group", "other_insured_group"),
            ("Other Insured Plan", "other_insured_plan"),
            ("Patient Address", "patient_address"),
            ("Patient City", "patient_city"),
            ("Patient State", "patient_state"),
            ("Patient ZIP", "patient_zip"),
            ("Diagnosis 1", "dx1"),
            ("Diagnosis 2", "dx2"),
            ("Diagnosis 3", "dx3"),
            ("Diagnosis 4", "dx4"),
            ("Service Date", "service_date"),
            ("Illness Date", "illness_date"),
            ("Other Date", "other_date"),
            ("Other Date Qual", "other_date_qual"),
            ("Unable To Work From", "unable_to_work_from"),
            ("Unable To Work To", "unable_to_work_to"),
            ("Hospitalized From", "hospitalized_from"),
            ("Hospitalized To", "hospitalized_to"),
            ("CPT Code", "cpt_code"),
            ("Modifier", "modifier"),
            ("Place of Service", "place_of_service"),
            ("Units", "units"),
            ("Employment Related (Y/N)", "employment_related"),
            ("Auto Accident (Y/N)", "auto_accident"),
            ("Auto Accident State", "auto_accident_state"),
            ("Other Accident (Y/N)", "other_accident"),
            ("Outside Lab (Y/N)", "outside_lab"),
            ("Outside Lab Charge", "outside_lab_charge"),
            ("Claim Codes (10d)", "claim_codes"),
            ("Patient Account #", "patient_account_no"),
            ("Claim Number", "claim_number"),
            ("Check Number", "check_number"),
            ("Prior Auth Number", "prior_auth_number"),
            ("Additional Claim Info", "additional_claim_info"),
            ("Total Charge", "total_charge"),
            ("Amount Paid", "amount_paid"),
            ("Accept Assignment (YES/NO)", "accept_assignment"),
            ("Federal Tax ID Type", "federal_tax_id_type"),
            ("Billing ID Qualifier", "billing_id_qualifier"),
            ("Referring Name", "referring_name"),
            ("Referring Taxonomy", "referring_taxonomy"),
            ("Referring NPI", "referring_npi"),
            ("Billing Name", "billing_name"),
            ("Billing Address", "billing_address"),
            ("Billing City", "billing_city"),
            ("Billing State", "billing_state"),
            ("Billing ZIP", "billing_zip"),
            ("Billing Phone", "billing_phone"),
            ("Billing NPI", "billing_npi"),
            ("Billing Taxonomy", "billing_taxonomy"),
            ("Tax ID", "tax_id"),
            ("Facility Name", "facility_name"),
            ("Facility Address", "facility_address"),
            ("Facility City", "facility_city"),
            ("Facility State", "facility_state"),
            ("Facility ZIP", "facility_zip"),
            ("Facility NPI", "facility_npi"),
            ("Facility Taxonomy", "facility_taxonomy"),
            ("Provider Signature", "provider_signature"),
            ("Provider Signature Date", "provider_signature_date"),
        ]
        self._vars = {}
        self._current_pid = None
        self._current_sessions = []
        self._current_data = {}
        self._last_preview_path = None
        self._paper_image = None
        self._build()

    def _build(self):
        tb = ttk.Frame(self, padding=(8, 6))
        tb.pack(fill="x")
        btn(tb, "Auto-Populate from Patient", self._auto_populate, "Accent.TButton").pack(side="left", padx=4)
        btn(tb, "Show Blank Form", self._open_blank_template).pack(side="left", padx=4)
        btn(tb, "Refresh Filled Form", self._refresh_paper_preview).pack(side="left", padx=4)
        btn(tb, "Edit Form Data", self._open_data_editor).pack(side="left", padx=4)
        btn(tb, "Print Preview", self._print_preview).pack(side="left", padx=4)
        btn(tb, "Print", self._print_form).pack(side="left", padx=4)
        btn(tb, "Export PDF", self._export_pdf).pack(side="left", padx=4)

        frm = lframe(self, "CMS-1500 Paper Form")
        frm.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        ttk.Label(
            frm,
            text="This is the actual CMS-1500 template rendered in-app. Use 'Edit Form Data' for manual overrides.",
            foreground=ACCENT,
            justify="left",
            font=("Arial", 12, "bold"),
        ).pack(anchor="w", padx=6, pady=(4, 6))

        for _, key in self._field_defs:
            self._vars[key] = tk.StringVar()

        view_wrap = ttk.Frame(frm)
        view_wrap.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        self._paper_canvas = tk.Canvas(view_wrap, background="#dddddd", highlightthickness=0)
        vbar = ttk.Scrollbar(view_wrap, orient="vertical", command=self._paper_canvas.yview)
        hbar = ttk.Scrollbar(view_wrap, orient="horizontal", command=self._paper_canvas.xview)
        self._paper_canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        self._paper_canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        view_wrap.rowconfigure(0, weight=1)
        view_wrap.columnconfigure(0, weight=1)
        self._paper_canvas.bind("<Enter>", self._bind_canvas_wheel)
        self._paper_canvas.bind("<Leave>", self._unbind_canvas_wheel)

        self._paper_status = ttk.Label(frm, text="Loading CMS-1500 template...", foreground=MUTED)
        self._paper_status.pack(anchor="w", padx=6, pady=(0, 4))

        self.after(120, self._open_blank_template)

    def _bind_canvas_wheel(self, _event=None):
        self._paper_canvas.bind_all("<MouseWheel>", self._on_canvas_mousewheel)
        self._paper_canvas.bind_all("<Shift-MouseWheel>", self._on_canvas_shift_mousewheel)
        self._paper_canvas.bind_all("<Button-4>", self._on_canvas_mousewheel)
        self._paper_canvas.bind_all("<Button-5>", self._on_canvas_mousewheel)

    def _unbind_canvas_wheel(self, _event=None):
        self._paper_canvas.unbind_all("<MouseWheel>")
        self._paper_canvas.unbind_all("<Shift-MouseWheel>")
        self._paper_canvas.unbind_all("<Button-4>")
        self._paper_canvas.unbind_all("<Button-5>")

    def _on_canvas_mousewheel(self, event):
        if getattr(event, "num", None) == 4:
            self._paper_canvas.yview_scroll(-1, "units")
            return "break"
        if getattr(event, "num", None) == 5:
            self._paper_canvas.yview_scroll(1, "units")
            return "break"
        delta = int(-event.delta / 120) if getattr(event, "delta", 0) else 0
        if delta:
            self._paper_canvas.yview_scroll(delta, "units")
        return "break"

    def _on_canvas_shift_mousewheel(self, event):
        delta = int(-event.delta / 120) if getattr(event, "delta", 0) else 0
        if delta:
            self._paper_canvas.xview_scroll(delta, "units")
        return "break"

    def _open_data_editor(self):
        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("CMS-1500 Data Editor")
        win.geometry("980x700")
        win.transient(self.winfo_toplevel())

        shell = ttk.Frame(win, padding=(10, 10, 10, 0))
        shell.pack(fill="both", expand=True)

        canvas = tk.Canvas(shell, highlightthickness=0)
        vbar = ttk.Scrollbar(shell, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        body = ttk.Frame(canvas, padding=4)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(3, weight=1)

        win_body = canvas.create_window((0, 0), window=body, anchor="nw")

        def _sync_editor_scroll(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfigure(win_body, width=canvas.winfo_width())

        body.bind("<Configure>", _sync_editor_scroll)
        canvas.bind("<Configure>", _sync_editor_scroll)

        for idx, (label, key) in enumerate(self._field_defs):
            row = idx // 2
            col_base = (idx % 2) * 2
            ttk.Label(body, text=label).grid(row=row, column=col_base, sticky="e", padx=(4, 2), pady=3)
            ttk.Entry(body, textvariable=self._vars[key]).grid(row=row, column=col_base + 1, sticky="ew", padx=(0, 8), pady=3)

        foot = ttk.Frame(win, padding=(10, 0, 10, 10))
        foot.pack(fill="x")

        def apply_and_refresh():
            # Keep any structured service lines while reflecting edited scalar values.
            self._current_data.update({k: v.get().strip() for k, v in self._vars.items()})
            self._refresh_paper_preview()
            win.destroy()

        btn(foot, "Apply + Refresh Form", apply_and_refresh, "Accent.TButton").pack(side="right", padx=4)
        btn(foot, "Cancel", win.destroy).pack(side="right", padx=4)

    def _render_pdf_in_canvas(self, pdf_path: Path) -> bool:
        if not PDF_RENDER_AVAILABLE:
            self._paper_status.config(
                text=(
                    "In-app PDF rendering components are unavailable in this build. "
                    "Please install the latest update."
                ),
                foreground=DANGER,
            )
            return False

        try:
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            self._paper_image = ImageTk.PhotoImage(img)
            self._paper_canvas.delete("all")
            self._paper_canvas.create_image(0, 0, image=self._paper_image, anchor="nw")
            self._paper_canvas.configure(scrollregion=(0, 0, img.width, img.height))
            self._paper_status.config(text=f"Showing form: {pdf_path.name}", foreground=MUTED)
            doc.close()
            return True
        except Exception as ex:
            self._paper_status.config(text=f"Could not render CMS form in app: {ex}", foreground=DANGER)
            return False

    def _open_blank_template(self):
        if not self._ensure_template():
            return
        self._render_pdf_in_canvas(CMS_TEMPLATE_FILE)

    def _refresh_paper_preview(self):
        preview_path = APP_ROOT / "temp" / "CMS1500_live_paper_preview.pdf"
        saved = self._fill_to_path(preview_path)
        if not saved:
            return None
        self._last_preview_path = saved
        self._render_pdf_in_canvas(saved)
        return saved

    def _ensure_template(self) -> bool:
        if CMS_TEMPLATE_FILE.exists():
            return True
        messagebox.showerror(
            "Template Missing",
            f"Could not find template:\n{CMS_TEMPLATE_FILE}\n\nAdd CMS1500_template.pdf to the app root.",
        )
        return False

    def _collect_form_data(self):
        # Start with field-by-field UI values
        form = {k: v.get().strip() for k, v in self._vars.items()}
        # Merge in the full data dict (which carries service_lines list)
        # UI scalars take precedence for editable fields; list stays from _current_data.
        if hasattr(self, "_current_data") and self._current_data:
            for k, v in self._current_data.items():
                if k not in form:
                    form[k] = v
                elif k == "service_lines":
                    form[k] = v  # always use the structured list
        return form

    def _fill_to_path(self, output_path: Path) -> Path | None:
        if not self._ensure_template():
            return None
        try:
            from cms_pdf import fill_cms1500_pdf
        except ImportError:
            messagebox.showerror("Missing Dependency", "Install dependency: pip install pypdf")
            return None

        data = self._collect_form_data()
        try:
            fill_cms1500_pdf(CMS_TEMPLATE_FILE, output_path, data)
            return output_path
        except Exception as ex:
            messagebox.showerror("CMS-1500", f"Could not generate PDF:\n{ex}")
            return None

    def _auto_populate(self):
        picker = tk.Toplevel(self)
        apply_window_icon(picker)
        picker.title("Select Patient for CMS-1500")
        picker.geometry("520x360")
        picker.grab_set()

        ttk.Label(picker, text="Select Patient:").pack(anchor="w", padx=10, pady=6)
        sv = tk.StringVar()
        patients = db.get_all_patients("Active")
        names = [f"{p['last_name']}, {p['first_name']} (ID:{p['id']})" for p in patients]
        cb = ttk.Combobox(picker, textvariable=sv, values=names, width=48, state="readonly")
        cb.pack(padx=10, pady=4)

        ttk.Label(picker, text="Select Sessions (Ctrl for multi-select):").pack(anchor="w", padx=10, pady=4)
        sess_lv = tk.Listbox(picker, selectmode="extended", exportselection=False, height=10, font=FONT_UI)
        sess_lv.pack(fill="both", expand=True, padx=10)

        def on_patient_select(*_args):
            idx = cb.current()
            if idx < 0:
                return
            pid = patients[idx]["id"]
            sess_lv.delete(0, "end")
            for s in db.get_sessions_for_patient(pid):
                sess_lv.insert("end", f"{fmt_date(s['session_date'])}  {s['cpt_code']}  {fmt_money(s['fee'])}")

        cb.bind("<<ComboboxSelected>>", on_patient_select)

        def do_populate():
            idx = cb.current()
            if idx < 0:
                messagebox.showwarning("Select", "Please choose a patient.", parent=picker)
                return
            pid = patients[idx]["id"]
            sessions = db.get_sessions_for_patient(pid)
            chosen_idx = sess_lv.curselection()
            chosen = [dict(sessions[i]) for i in chosen_idx] if chosen_idx else [dict(sessions[0])] if sessions else []
            self.load_from_session(pid, chosen)
            picker.destroy()

        btn(picker, "Populate Form", do_populate, "Accent.TButton").pack(pady=8)

    def load_from_session(self, pid, sessions):
        patient = db.get_patient(pid)
        provider = db.get_provider()
        billing_rows = db.get_billing_for_patient(pid)
        latest_billing = billing_rows[0] if billing_rows else {}

        def g(row, key, default=""):
            try:
                return row[key] or default
            except Exception:
                return default

        first = sessions[0] if sessions else {}
        # Clamp to 6 service lines (CMS-1500 maximum)
        selected = list(sessions[:6])

        total_charge = 0.0
        for s in selected:
            try:
                total_charge += float(s.get("fee", 0) or 0)
            except Exception:
                pass

        total_paid = 0.0
        for r in billing_rows:
            try:
                total_paid += float(r["payment"] or 0) + float(r["ins_payment"] or 0)
            except Exception:
                pass

        patient_sex = g(patient, "sex").strip().upper()
        if patient_sex.startswith("MALE"):
            patient_sex = "M"
        elif patient_sex.startswith("FEMALE"):
            patient_sex = "F"

        provider_name = g(provider, "practice_name") or f"{g(provider, 'provider_first')} {g(provider, 'provider_last')}".strip()
        rendering_provider_name = f"{g(provider, 'provider_first')} {g(provider, 'provider_last')}".strip()
        billing_npi = g(provider, "npi")
        provider_taxonomy = g(provider, "license_num")
        insured_name = g(patient, "ins_holder") or f"{g(patient, 'last_name')}, {g(patient, 'first_name')}".strip(", ")
        insured_sex = g(patient, "ins_holder_sex") or patient_sex
        insured_relation = g(patient, "ins_relation", "Self")
        insured_dob = g(patient, "ins_holder_dob") or g(patient, "dob")
        insured_address = g(patient, "ins_address") or g(patient, "address")
        insured_city = g(patient, "ins_city") or g(patient, "city")
        insured_state = g(patient, "ins_state") or g(patient, "state")
        insured_zip = g(patient, "ins_zip") or g(patient, "zip")
        insured_phone = g(patient, "ins_phone") or g(patient, "phone_home") or g(patient, "phone_cell")
        patient_phone = g(patient, "phone_home") or g(patient, "phone_cell") or g(patient, "phone_work")

        # Build per-row diagnosis pointer: use "A" if only dx1 is set, or all
        # applicable pointers based on which of dx1-dx4 this session carry.
        def dx_pointer_for(sess) -> str:
            letters = "ABCD"
            dx_keys = ["dx1", "dx2", "dx3", "dx4"]
            ptrs = [letters[i] for i, k in enumerate(dx_keys) if g(sess, k) or g(first, k)]
            return " ".join(ptrs) if ptrs else "A"

        service_lines = [
            {
                "service_date": g(s, "session_date"),
                "cpt_code":     g(s, "cpt_code"),
                "modifier":     g(s, "cpt_modifier"),
                "pos":          _extract_place_code(g(s, "place_of_service", "11")),
                "units":        "1",
                "charge":       f"{float(s.get('fee', 0) or 0):.2f}",
                "dx_pointer":   dx_pointer_for(s),
                "id_qualifier": g(provider, "id_qualifier", "ZZ"),
                "taxonomy_code": provider_taxonomy,
                "npi":          billing_npi,
            }
            for s in selected
        ]

        data = {
            "patient_name": f"{g(patient, 'last_name')}, {g(patient, 'first_name')}",
            "patient_dob": g(patient, "dob"),
            "patient_sex": patient_sex,
            "patient_ssn": g(patient, "ssn"),
            "ins_id": g(patient, "ins_id"),
            "insured_name": insured_name,
            "insured_dob": insured_dob,
            "insured_sex": insured_sex,
            "insured_relation": insured_relation,
            "insured_group": g(patient, "ins_group"),
            "insured_plan_name": g(patient, "ins_name") or g(patient, "ins_plan"),
            "insured_plan_type": g(patient, "ins_plan"),
            "insured_address": insured_address,
            "insured_city": insured_city,
            "insured_state": insured_state,
            "insured_zip": insured_zip,
            "insured_phone": insured_phone,
            "other_insured_name": g(patient, "ins2_holder") or g(patient, "ins2_name"),
            "other_insured_id": g(patient, "ins2_id"),
            "other_insured_group": g(patient, "ins2_group"),
            "other_insured_plan": g(patient, "ins2_plan"),
            "other_insured_relation": g(patient, "ins2_relation"),
            "patient_address": g(patient, "address"),
            "patient_city": g(patient, "city"),
            "patient_state": g(patient, "state"),
            "patient_zip": g(patient, "zip"),
            "patient_phone": patient_phone,
            "dx1": g(first, "dx1") or g(patient, "dx1"),
            "dx2": g(first, "dx2") or g(patient, "dx2"),
            "dx3": g(first, "dx3") or g(patient, "dx3"),
            "dx4": g(first, "dx4") or g(patient, "dx4"),
            # Row-1 scalar fallbacks (used when service_lines is ignored)
            "service_date": g(first, "session_date"),
            "illness_date": "",
            "other_date": "",
            "other_date_qual": "",
            "unable_to_work_from": g(first, "unable_to_work_from") or g(patient, "unable_to_work_from"),
            "unable_to_work_to": g(first, "unable_to_work_to") or g(patient, "unable_to_work_to"),
            "hospitalized_from": g(first, "hospitalized_from") or g(patient, "hospitalized_from"),
            "hospitalized_to": g(first, "hospitalized_to") or g(patient, "hospitalized_to"),
            "cpt_code": g(first, "cpt_code"),
            "modifier": g(first, "cpt_modifier"),
            "place_of_service": _extract_place_code(g(first, "place_of_service", "11")),
            "units": "1",
            "employment_related": g(first, "employment_related") or g(patient, "employment_related"),
            "auto_accident": g(first, "auto_accident") or g(patient, "auto_accident"),
            "auto_accident_state": g(first, "auto_accident_state") or g(patient, "auto_accident_state"),
            "other_accident": g(first, "other_accident") or g(patient, "other_accident"),
            "outside_lab": g(first, "outside_lab") or g(patient, "outside_lab"),
            "outside_lab_charge": "",
            "patient_account_no": str(pid),
            "claim_codes": g(latest_billing, "claim_codes"),
            "claim_number": g(latest_billing, "claim_number"),
            "check_number": g(latest_billing, "check_number"),
            "prior_auth_number": g(latest_billing, "claim_number"),
            "additional_claim_info": g(patient, "notes") or g(first, "note_text"),
            "total_charge": f"{total_charge:.2f}",
            "amount_paid": f"{total_paid:.2f}",
            "provider_signature": g(provider, "sig_on_file", "Signature On File"),
            "provider_name": rendering_provider_name or provider_name,
            "provider_signature_date": g(patient, "sig_on_file_date") or g(first, "session_date") or g(latest_billing, "record_date"),
            "accept_assignment": "YES" if str(g(provider, "accept_assign", "1")) in {"1", "true", "True", "YES", "yes"} else "NO",
            "federal_tax_id_type": g(provider, "tax_id_type", "EIN"),
            "billing_id_qualifier": "",
            "referring_name": g(patient, "referring_name"),
            # 17a should only populate from explicit referral data.
            "referring_taxonomy": g(patient, "referring_taxonomy"),
            "referring_npi": g(patient, "referring_npi"),
            "billing_name": provider_name,
            "billing_address": g(provider, "address"),
            "billing_city": g(provider, "city"),
            "billing_state": g(provider, "state"),
            "billing_zip": g(provider, "zip"),
            "billing_phone": g(provider, "phone"),
            "billing_npi": billing_npi,
            "billing_taxonomy": provider_taxonomy,
            "tax_id": g(provider, "tax_id"),
            "facility_name": provider_name,
            "facility_address": g(provider, "address"),
            "facility_city": g(provider, "city"),
            "facility_state": g(provider, "state"),
            "facility_zip": g(provider, "zip"),
            "facility_npi": billing_npi,
            "facility_taxonomy": provider_taxonomy,
            "taxonomy_code": provider_taxonomy,
            # Multi-line list consumed by cms_pdf mapper
            "service_lines": service_lines,
        }

        for key, var in self._vars.items():
            var.set(str(data.get(key, "")))
        # Update row-count hint for the user
        n = len(service_lines)
        if n > 1:
            self._vars.get("units", tk.StringVar()).set(
                f"({n} sessions — see service lines)"
            )

        self._current_pid = pid
        self._current_sessions = sessions
        self._current_data = data  # retained for PDF fill
        self._refresh_paper_preview()

    def _show_template_fields(self):
        if not self._ensure_template():
            return
        try:
            from cms_pdf import get_template_fields_with_positions
            fields = get_template_fields_with_positions(CMS_TEMPLATE_FILE)
        except Exception as ex:
            messagebox.showerror("Template Fields", f"Could not read template fields:\n{ex}")
            return

        win = tk.Toplevel(self)
        apply_window_icon(win)
        win.title("CMS-1500 Template Fields")
        win.geometry("980x620")
        txt = tk.Text(win, wrap="none", font=FONT_MONO)
        txt.pack(fill="both", expand=True)

        if not fields:
            txt.insert("1.0", "No fillable fields found.")
        else:
            lines = []
            lines.append("Field | Page | Type | Rect(x1,y1,x2,y2) | Current Value")
            lines.append("-" * 120)
            for f in fields:
                rect = f.get("rect") or (0, 0, 0, 0)
                rect_str = f"({rect[0]:.1f},{rect[1]:.1f},{rect[2]:.1f},{rect[3]:.1f})"
                line = (
                    f"{f.get('name','')} | "
                    f"{f.get('page','')} | "
                    f"{f.get('field_type','')} | "
                    f"{rect_str} | "
                    f"{f.get('value','')}"
                )
                lines.append(line)
            txt.insert("1.0", "\n".join(lines))

        txt.config(state="disabled")

    def _export_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"CMS1500_{self._vars['patient_name'].get().replace(', ', '_') or 'claim'}.pdf",
        )
        if not path:
            return
        saved = self._fill_to_path(Path(path))
        if saved:
            messagebox.showinfo("Exported", f"PDF saved to:\n{saved}")

    def _print_preview(self):
        saved = self._refresh_paper_preview()
        if not saved:
            return
        webbrowser.open(saved.resolve().as_uri())

    def _print_form(self):
        print_path = APP_ROOT / "temp" / f"CMS1500_print_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        saved = self._fill_to_path(print_path)
        if not saved:
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(str(saved), "print")
                messagebox.showinfo("Print", "CMS-1500 sent to default printer.")
            else:
                webbrowser.open(saved.resolve().as_uri())
                messagebox.showinfo("Print", f"Opened PDF for printing:\n{saved}")
        except OSError as ex:
            messagebox.showerror("Print", f"Could not print PDF:\n{ex}")


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
            "Combined Therapy Practice Management + CMS-1500\n\n"
            "Features:\n"
            "  • Patient management & demographics\n"
            "  • Session notes with DSM-5 / ICD-10 lookup\n"
            "  • Billing ledger & payment tracking\n"
            "  • CMS-1500 fillable PDF (preview + print)\n"
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

        payload = None
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                messagebox.showinfo(
                    "Check for Updates",
                    "No public release has been found on the update server.\n\n"
                    f"Current Version: {current_ver}\n\n"
                    "You may already have the latest version.\n"
                    f"Check manually at:\n{GITHUB_RELEASES_PAGE}"
                )
            else:
                messagebox.showwarning(
                    "Check for Updates",
                    f"The update server returned an error (HTTP {ex.code}).\n\n"
                    f"Current Version: {current_ver}\n\n"
                    "You can check for updates manually at:\n"
                    f"{GITHUB_RELEASES_PAGE}"
                )
            return
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
            "For billing and CMS-1500, your settings are entered once\n"
            "in Settings -> Provider/Practice."
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
