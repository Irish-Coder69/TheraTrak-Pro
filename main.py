"""
TheraTrak Pro
Combined therapy practice management + CMS-1500 billing application.
Merges the functionality of Notes 444 (H: drive) and CMS1500v6 (E: drive).

Python 3.10+  ·  Tkinter + ttk  ·  SQLite backend
"""

import json
import os
import sys
import tkinter as tk
import tkinter.font as tkFont
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import database as db
import version_manager as vm
from app_paths import ICON_FILE

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


# ─── Utilities ─────────────────────────────────────────────────────────────────

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
        self.geometry("860x430")
        self.resizable(True, True)
        self._build()
        self._load_users()
        self.grab_set()

    def _build(self):
        container = ttk.Frame(self, padding=8)
        container.pack(fill="both", expand=True)

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
        self.tv.bind("<<TreeviewSelect>>", self._show_details)

        right = lframe(container, "Selected User Details")
        right.pack(side="left", fill="y", padx=(8, 0))
        self.details = tk.Text(right, width=34, height=20, font=FONT_MONO, state="disabled")
        self.details.pack(fill="both", expand=True)

        bottom = ttk.Frame(self, padding=8)
        bottom.pack(fill="x")
        btn(bottom, "Refresh", self._load_users).pack(side="left")
        btn(bottom, "Close", self.destroy).pack(side="right")

    def _load_users(self):
        self._rows = db.get_all_users()
        self.tv.delete(*self.tv.get_children())
        for r in self._rows:
            name = f"{r['first_name']} {r['last_name']}"
            self.tv.insert(
                "",
                "end",
                iid=str(r["id"]),
                values=(
                    r["id"],
                    r["username"],
                    name,
                    r["role"],
                    r["email"],
                    r["phone"],
                    "Yes" if r["is_active"] else "No",
                ),
            )

    def _show_details(self, event=None):
        sel = self.tv.selection()
        if not sel:
            return
        uid = int(sel[0])
        row = next((r for r in self._rows if r["id"] == uid), None)
        if not row:
            return
        lines = [
            f"ID: {row['id']}",
            f"Username: {row['username']}",
            f"Name: {row['first_name']} {row['last_name']}",
            f"Role: {row['role']}",
            f"Email: {row['email']}",
            f"Phone: {row['phone']}",
            f"Address: {row['address']}",
            f"City/State/Zip: {row['city']} {row['state']} {row['zip']}",
            f"Active: {'Yes' if row['is_active'] else 'No'}",
            f"Created: {row['created_at']}",
            f"Last Login: {row['last_login'] or 'Never'}",
        ]
        self.details.config(state="normal")
        self.details.delete("1.0", "end")
        self.details.insert("1.0", "\n".join(lines))
        self.details.config(state="disabled")


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

        # ── Row 4: Suffix | Show Password toggle ──────────────────
        _show_pw_var = tk.BooleanVar(value=False)
        def _toggle_show_pw():
            ch = "" if _show_pw_var.get() else "*"
            _e_password.config(show=ch)
            _e_confirm.config(show=ch)
        ttk.Label(frm, text="Suffix").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        _cb_suffix = ttk.Combobox(frm, textvariable=self._field("suffix"),
                     values=["", "PhD", "PsyD", "LCSW", "LMFT", "LPC", "LCPC", "MSW", "MA", "MS",
                             "MD", "DO", "NP", "PA", "RN", "EdD", "DSW", "DMin"],
                     width=12, state="readonly")
        _cb_suffix.grid(row=4, column=1, sticky="w")
        ttk.Checkbutton(
            frm, text="Show Password", variable=_show_pw_var,
            command=_toggle_show_pw
        ).grid(row=4, column=3, columnspan=2, sticky="w", padx=4, pady=4)

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

        # ── License / NPI ─────────────────────────────────────────
        ttk.Label(frm, text="License Number*").grid(row=13, column=0, sticky="e", padx=4, pady=4)
        _e_license = ttk.Entry(frm, textvariable=self._field("license_number"), width=24)
        _e_license.grid(row=13, column=1, sticky="w")

        ttk.Label(frm, text="NPI Number*").grid(row=14, column=0, sticky="e", padx=4, pady=4)
        _e_npi = ttk.Entry(frm, textvariable=self._field("npi_number"), width=24)
        _e_npi.grid(row=14, column=1, sticky="w")

        # ── Tab order: left column top→bottom, then right column ──
        self._set_tab_order([
            _e_first, _e_middle, _e_last, _cb_suffix, _e_phone, _e_email,
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
        ttk.Entry(f1, textvariable=self._fld("emr_relation"), width=12).grid(row=7, column=3, sticky="w")
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
        btn(act, "Export PDF",                  self._export_pdf, "Accent.TButton").pack(side="left", padx=4)

        self._refresh_claims()

    def _build_form(self, parent):
        """Build all CMS-1500 form fields."""
        self._cv = {}  # field_name -> StringVar

        def fld(name, default=""):
            v = tk.StringVar(value=default)
            self._cv[name] = v
            return v

        def row(frame, label, fname, r, c=0, w=20, combo=None):
            ttk.Label(frame, text=label).grid(row=r, column=c, sticky="ne", padx=(8,2), pady=2)
            if combo:
                wid = ttk.Combobox(frame, textvariable=fld(fname), values=combo, width=w)
                wid.grid(row=r, column=c+1, sticky="ew", padx=(0,12), pady=2)
            else:
                ttk.Entry(frame, textvariable=fld(fname), width=w).grid(
                    row=r, column=c+1, sticky="ew", padx=(0,12), pady=2)

        parent.columnconfigure(0, weight=0)
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=0)
        parent.columnconfigure(3, weight=1)

        sections = [
            ("Insurance / Patient", [
                ("Box 1 – Insurance Type",    "ins_type",       0, 0, 18,
                 ["Medicare","Medicaid","TRICARE","CHAMPVA","Group Health Plan","FECA","Other"]),
                ("Box 1a – Insured ID #",     "ins_id",         1, 0, 24, None),
                ("Box 2 – Patient Name",      "patient_name",   1, 2, 24, None),
                ("Box 3 – Patient DOB",       "patient_dob",    2, 0, 14, None),
                ("Box 3 – Patient Sex",       "patient_sex",    2, 2, 6,  ["M","F","U"]),
                ("Box 4 – Insured Name",      "ins_name",       3, 0, 24, None),
                ("Box 5 – Patient Address",   "patient_address",3, 2, 26, None),
                ("Box 5 – City",              "patient_city",   4, 0, 18, None),
                ("Box 5 – State",             "patient_state",  4, 2, 6,  STATES),
                ("Box 5 – Zip",               "patient_zip",    5, 0, 12, None),
                ("Box 6 – Relation to Insured","ins_relation",  5, 2, 14, ["Self","Spouse","Child","Other"]),
                ("Box 7 – Insured Address",   "ins_address2",   6, 0, 26, None),
                ("Box 7 – City",              "ins_city2",      6, 2, 18, None),
                ("Box 7 – State",             "ins_state2",     7, 0, 6,  STATES),
                ("Box 7 – Zip",               "ins_zip2",       7, 2, 12, None),
                ("Box 11 – Ins. Policy/Group","ins_group",      8, 0, 18, None),
                ("Box 11c – Insurance Plan",  "ins_plan",       8, 2, 20, None),
                ("Box 12 – Patient Signature","patient_sig",    9, 0, 22, None),
                ("Box 13 – Insured Signature","ins_sig",        9, 2, 22, None),
            ]),
            ("Condition / Dates", [
                ("Box 14 – Date of Illness",        "illness_date",   0, 0, 14, None),
                ("Box 17 – Referring Provider",     "ref_provider",   1, 0, 24, None),
                ("Box 17b – Referring NPI",         "ref_npi",        1, 2, 14, None),
                ("Box 23 – Prior Auth #",           "auth_number",    2, 0, 20, None),
                ("Box 19 – Additional Info",        "add_info",       2, 2, 28, None),
            ]),
            ("Diagnoses (Box 21)", [
                ("Dx A",  "dx1",  0, 0, 12, None), ("Dx B",  "dx2",  0, 2, 12, None),
                ("Dx C",  "dx3",  1, 0, 12, None), ("Dx D",  "dx4",  1, 2, 12, None),
                ("Dx E",  "dx5",  2, 0, 12, None), ("Dx F",  "dx6",  2, 2, 12, None),
                ("Dx G",  "dx7",  3, 0, 12, None), ("Dx H",  "dx8",  3, 2, 12, None),
            ]),
            ("Billing / Provider", [
                ("Box 25 – Federal Tax ID",         "tax_id",          0, 0, 16, None),
                ("Box 25 – Tax ID Type",            "tax_id_type",     0, 2, 8, ["EIN","SSN"]),
                ("Box 26 – Patient Acct #",         "patient_acct",    1, 0, 16, None),
                ("Box 27 – Accept Assignment?",     "accept_assign",   1, 2, 6, ["YES","NO"]),
                ("Box 28 – Total Charge",           "total_charge",    2, 0, 14, None),
                ("Box 29 – Amount Paid",            "amount_paid",     2, 2, 14, None),
                ("Box 31 – Provider Signature",     "provider_sig",    3, 0, 22, None),
                ("Box 31 – Billing Date",           "billing_date",    3, 2, 14, None),
                ("Box 32 – Facility Name",          "facility_name",   4, 0, 24, None),
                ("Box 32 – Facility Address",       "facility_address",4, 2, 24, None),
                ("Box 32a – Facility NPI",          "facility_npi",    5, 0, 14, None),
                ("Box 33 – Billing Provider Name",  "billing_name",    6, 0, 26, None),
                ("Box 33 – Billing Address",        "billing_address", 6, 2, 26, None),
                ("Box 33 – Billing Phone",          "billing_phone",   7, 0, 16, None),
                ("Box 33a – Billing NPI",           "billing_npi",     7, 2, 14, None),
            ]),
        ]

        # Service lines section
        self._sl_vars = []  # list of dicts per service line

        row_offset = 0
        for sec_title, fields in sections:
            lbl_sec = ttk.Label(parent, text=sec_title, font=FONT_LG,
                                background=HDR_BG, foreground="white")
            lbl_sec.grid(row=row_offset, column=0, columnspan=4, sticky="ew",
                         padx=4, pady=(10, 2))
            row_offset += 1
            for (label, fname, r, c, w, combo) in fields:
                row(parent, label, fname, row_offset + r, c, w, combo)
            max_r = max(f[2] for f in fields) + 1
            row_offset += max_r + 1

        # Service Lines (Box 24) section
        sl_lbl = ttk.Label(parent, text="Service Lines – Box 24", font=FONT_LG,
                           background=HDR_BG, foreground="white")
        sl_lbl.grid(row=row_offset, column=0, columnspan=4, sticky="ew", padx=4, pady=(10, 2))
        row_offset += 1

        sl_headers = ttk.Frame(parent)
        sl_headers.grid(row=row_offset, column=0, columnspan=4, sticky="ew", padx=4)
        for i, (ht, hw) in enumerate([("From Date",10),("To Date",10),("POS",5),
                                       ("CPT",8),("Mod",5),("Dx Ptr",6),("Charge",8),("Units",5),("NPI",12)]):
            ttk.Label(sl_headers, text=ht, font=("Calibri",9,"bold")).grid(row=0, column=i, padx=3)
        row_offset += 1

        for line_num in range(6):
            sl_row = {}
            sl_frame = ttk.Frame(parent)
            sl_frame.grid(row=row_offset, column=0, columnspan=4, sticky="ew", padx=4, pady=1)
            ttk.Label(sl_frame, text=f"{line_num+1}.", width=2).grid(row=0, column=0)
            for i, (fname, fw) in enumerate([("from_date",10),("to_date",10),("pos",5),
                                              ("cpt",8),("modifier",5),("dx_ptr",6),
                                              ("charge",8),("units",5),("npi",12)]):
                v = tk.StringVar()
                sl_row[fname] = v
                ttk.Entry(sl_frame, textvariable=v, width=fw).grid(row=0, column=i+1, padx=2)
            self._sl_vars.append(sl_row)
            row_offset += 1

        # Lookup button for diagnoses
        dx_btn_frame = ttk.Frame(parent)
        dx_btn_frame.grid(row=row_offset, column=0, columnspan=4, sticky="w", padx=4, pady=4)
        ttk.Button(dx_btn_frame, text="Lookup Diagnosis Code",
                   command=lambda: DSMPicker(self, lambda c: self._dx_insert(c))
                   ).pack(side="left", padx=4)

    def _dx_insert(self, code):
        for key in ["dx1","dx2","dx3","dx4","dx5","dx6","dx7","dx8"]:
            if not self._cv[key].get():
                self._cv[key].set(code)
                return
        self._cv["dx8"].set(code)

    def load_from_session(self, pid, sessions):
        """Pre-populate form from patient + sessions."""
        from cms_pdf import cms_form_data_from_patient
        pt  = db.get_patient(pid)
        prov = db.get_provider()
        fd = cms_form_data_from_patient(pt, sessions, prov)
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
        return fd

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
        self._cv["accept_assign"].set("YES")

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
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Provider / Practice ───────────────────────────────────────────────
        f1 = ttk.Frame(nb, padding=14)
        nb.add(f1, text=" Provider / Practice ")
        for c in range(4): f1.columnconfigure(c, weight=1)

        fields = [
            ("Practice Name",         "practice_name",  0, 0),
            ("Provider Last Name",     "provider_last",  1, 0),
            ("Provider First Name",    "provider_first", 1, 2),
            ("Credentials (LCSW etc.)","credentials",    2, 0),
            ("NPI",                    "npi",            2, 2),
            ("Tax ID",                 "tax_id",         3, 0),
            ("Tax ID Type (EIN/SSN)",  "tax_id_type",    3, 2),
            ("UPIN (legacy)",          "upin",           4, 0),
            ("License Number",         "license_num",    4, 2),
            ("Address",                "address",        5, 0),
            ("City",                   "city",           6, 0),
            ("State",                  "state",          6, 2),
            ("Zip",                    "zip",            7, 0),
            ("Phone",                  "phone",          7, 2),
            ("Fax",                    "fax",            8, 0),
            ("Email",                  "email",          8, 2),
            ("Default POS",            "default_pos",    9, 0),
        ]
        for lbl, key, r, c in fields:
            ttk.Label(f1, text=lbl).grid(row=r, column=c, sticky="e", padx=4, pady=3)
            ttk.Entry(f1, textvariable=self._fld(key), width=26).grid(
                row=r, column=c+1, sticky="ew", padx=(0,12))

        self.accept_var = tk.IntVar(value=1)
        ttk.Checkbutton(f1, text="Accept Assignment (Medicare/Medicaid)",
                        variable=self.accept_var).grid(row=10, column=0, columnspan=4,
                                                        sticky="w", padx=4, pady=4)

        btn(f1, "Save Provider Settings", self._save_provider, "Accent.TButton"
            ).grid(row=11, column=0, columnspan=2, pady=10, padx=4, sticky="w")

        # ── Data Import ───────────────────────────────────────────────────────
        f2 = ttk.Frame(nb, padding=14)
        nb.add(f2, text=" Data Import ")

        ttk.Label(f2, text="Import data from Notes 444 / CMS-1500v6",
                  font=FONT_LG).pack(anchor="w", pady=(0, 10))

        info_txt = (
            "Your existing data (H: drive) is stored in FileMaker Pro 5 binary format (.444 files).\n\n"
            "RECOMMENDED: Export records from Notes 444 as CSV/Tab-delimited files,\n"
            "then import them here for the most complete and accurate data transfer.\n\n"
            "To export from Notes 444:\n"
            "  1. Open H:\\Important Files\\Notes 444.EXE\n"
            "  2. Go to File → Export Records\n"
            "  3. Choose CSV or Tab-Delimited format\n"
            "  4. Save and then import below.\n\n"
            "ALTERNATIVE: Raw binary extraction (partial data only – names, dates, phones)\n"
            "  is available but will not capture all fields."
        )
        ttk.Label(f2, text=info_txt, justify="left", wraplength=640).pack(anchor="w")

        ttk.Separator(f2).pack(fill="x", pady=10)

        btn_frame = ttk.Frame(f2)
        btn_frame.pack(anchor="w")
        btn(btn_frame, "Import Patients (CSV)",
            self._import_patients_csv, "Accent.TButton").grid(row=0, column=0, padx=4, pady=4)
        btn(btn_frame, "Import Sessions (CSV)",
            self._import_sessions_csv, "Accent.TButton").grid(row=0, column=1, padx=4, pady=4)
        btn(btn_frame, "Import Billing (CSV)",
            self._import_billing_csv,  "Accent.TButton").grid(row=0, column=2, padx=4, pady=4)
        btn(btn_frame, "Raw Extract from PTInfo.444",
            self._raw_extract,          "TButton").grid(row=1, column=0, padx=4, pady=4)
        btn(btn_frame, "Check .444 File Status",
            self._check_status,         "TButton").grid(row=1, column=1, padx=4, pady=4)

        self._import_log = tk.Text(f2, height=10, font=FONT_MONO, state="disabled",
                                   relief="solid", borderwidth=1, background="#fafafa")
        self._import_log.pack(fill="both", expand=True, pady=(10, 0))

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

    def _raw_extract(self):
        path = filedialog.askopenfilename(
            title="Select PTInfo.444 from H: drive",
            initialdir=r"H:\Important Files",
            filetypes=[("444 Database","*.444"),("All","*.*")])
        if not path:
            return
        import migration
        count, warns = migration.extract_raw_patients(path)
        self._log(f"Raw extraction: {count} records")
        for w in warns[:20]:
            self._log(f"  {w}")
        self._refresh_app_views(patients=True, select_tab=0)
        messagebox.showinfo("Extraction Complete",
                            f"Extracted {count} records.\nCheck import log for details.")

    def _check_status(self):
        import migration
        statuses = migration.get_data_files_status()
        self._log("File Status on H: drive:")
        for f in statuses:
            exists = "✓" if f["exists"] else "✗"
            fm5    = "FileMaker Pro 5" if f["is_fm5"] else ("(not FM5)" if f["exists"] else "")
            self._log(f"  {exists} {f['file']:<35}  {f['size_kb']:>6} KB  {fm5}")
            self._log(f"    └─ {f['description']}")


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
        file_menu.add_separator()
        file_menu.add_command(label="Backup Database", command=self._backup_db)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        nav_menu = tk.Menu(menubar, tearoff=0)
        nav_menu.add_command(label="Patients",        command=lambda: self.nb.select(0))
        nav_menu.add_command(label="Session Notes",   command=lambda: self.nb.select(1))
        nav_menu.add_command(label="Billing",         command=lambda: self.nb.select(2))
        nav_menu.add_command(label="CMS-1500",        command=lambda: self.nb.select(3))
        nav_menu.add_command(label="Reports",         command=lambda: self.nb.select(4))
        nav_menu.add_command(label="Settings/Import", command=lambda: self.nb.select(5))
        menubar.add_cascade(label="Navigate", menu=nav_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About TheraTrak Pro", command=self._about)
        help_menu.add_command(label="Check for Updates", command=self._check_for_updates)
        help_menu.add_command(label="Data Migration Help",  command=self._migration_help)
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

    def _backup_db(self):
        from shutil import copy2
        dest = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database","*.db"),("All","*.*")],
            initialfile=f"theratrak_backup_{date.today().strftime('%Y%m%d')}.db")
        if dest:
            copy2(db.DB_PATH, dest)
            messagebox.showinfo("Backup", f"Database backed up to:\n{dest}")

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
            "Combines:\n"
            "  • Notes 444 (H: drive) – therapy session notes\n"
            "  • CMS1500v6 (E: drive) – medical billing claims\n\n"
            "Features:\n"
            "  • Patient management & demographics\n"
            "  • Session notes with DSM-5 / ICD-10 lookup\n"
            "  • Billing ledger & payment tracking\n"
            "  • CMS-1500 claim form + PDF export\n"
            "  • Reports & CSV data export\n"
            "  • Data migration from Notes 444 files\n\n"
            f"Database: {db.DB_PATH}"
        )

    def _check_for_updates(self):
        current_ver = self._version
        messagebox.showinfo(
            "Check for Updates",
            "TheraTrak Pro Update Check\n\n"
            f"Current Version: {current_ver}\n\n"
            "To get the latest version:\n\n"
            "1. Visit the project repository\n"
            "2. Download the latest installer\n"
            "3. Run TheraTrak-Pro-Installer.exe\n"
            "4. The new version will be installed\n\n"
            "Your database will be preserved during upgrade."
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
