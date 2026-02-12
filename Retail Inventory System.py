"""
Retail POS - Single-file app (extended)
Features added on top of user's base:
- User authentication & roles (admin/cashier)
- Barcode field for products + quick-add by barcode (or product id)
- Optional barcode generation (python-barcode)
- Per-item and order-level discounts
- Multiple payment methods (cash, card, upi, split)
- Inventory low-stock notifications on startup and after operations
- Customer management with loyalty points (1 point per ₹100)
- Supplier quick view/edit (kept in product model)
- More robust backups & import/export
- Role-based access to Settings/Admin actions
- Graceful optional dependencies: fpdf, python-barcode, matplotlib

Notes:
- This single-file app persists to inventory.json, orders.json, users.json (created automatically), and customers.json
- Optional libs: fpdf (PDF invoices), python-barcode (barcode generation), matplotlib (sales chart)

Run: python retail_pos_full_featured.py
"""

import os
import json
import csv
from datetime import datetime
from collections import Counter, defaultdict
from typing import List, Dict, Optional
import tkinter as tk
import webbrowser
from tkinter import messagebox, filedialog, simpledialog

# UI libs: prefer ttkbootstrap, fallback to tkinter.ttk
try:
    import ttkbootstrap as tb
    from ttkbootstrap import ttk
    from ttkbootstrap.constants import *
    TB_AVAILABLE = True
    STYLE = tb.Style()
except Exception:
    from tkinter import ttk
    TB_AVAILABLE = False
    STYLE = None
    tb = None

# optional PDF
try:
    from fpdf import FPDF
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

# optional barcode generation (python-barcode)
try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except Exception:
    BARCODE_AVAILABLE = False

# optional plotting
try:
    import matplotlib.pyplot as plt
    from PIL import Image, ImageTk
    MATPLOTLIB_AVAILABLE = True
except Exception:
    MATPLOTLIB_AVAILABLE = False

# App files
APP_DIR = os.getcwd()
INVENTORY_FILE = os.path.join(APP_DIR, "inventory.json")
ORDERS_FILE = os.path.join(APP_DIR, "orders.json")
USERS_FILE = os.path.join(APP_DIR, "users.json")
CUSTOMERS_FILE = os.path.join(APP_DIR, "customers.json")
BACKUP_FILE = os.path.join(APP_DIR, "data_backup.json")

LOW_STOCK_THRESHOLD_DEFAULT = 5
LOYALTY_POINTS_PER_RS = 100  # 1 point per 100 Rs


# --- JSON helpers ---
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# --- Data models ---
class Product:
    def __init__(self, product_id: int, name: str, category: str, quantity: int, price: float, supplier: str, barcode_value: str = ""):
        self.product_id = int(product_id)
        self.name = name
        self.category = category
        self.quantity = int(quantity)
        self.price = float(price)
        self.supplier = supplier
        self.barcode = barcode_value or str(product_id)  # fallback to id if not provided

    def to_dict(self):
        return {
            "product_id": self.product_id,
            "name": self.name,
            "category": self.category,
            "quantity": self.quantity,
            "price": self.price,
            "supplier": self.supplier,
            "barcode": self.barcode,
        }

    @staticmethod
    def from_dict(d):
        return Product(d["product_id"], d.get("name", ""), d.get("category", ""), d.get("quantity", 0), d.get("price", 0.0), d.get("supplier", ""), d.get("barcode", ""))


class OrderRecord:
    def __init__(self, order_id: int, customer: str, items: List[Dict], total: float, created_at: str, payment: Dict[str, any] = None, discount: float = 0.0):
        self.order_id = order_id
        self.customer = customer
        self.items = items
        self.total = total
        self.created_at = created_at
        self.payment = payment or {"method": "unknown", "details": {}}
        self.discount = discount

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "customer": self.customer,
            "items": self.items,
            "total": self.total,
            "created_at": self.created_at,
            "payment": self.payment,
            "discount": self.discount,
        }

    @staticmethod
    def from_dict(d):
        return OrderRecord(d["order_id"], d["customer"], d.get("items", []), d.get("total", 0.0), d.get("created_at", ""), d.get("payment", {}), d.get("discount", 0.0))


# --- Landing Page ---
class LandingPage(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Welcome to SmartMart POS")
        self.geometry("800x500")
        self.configure(bg="white")
        self.resizable(False, False)

        # Load logo
        try:
            from PIL import Image, ImageTk
            logo_path = os.path.join("code", "logo.png")
            if os.path.exists(logo_path):
                img = Image.open(logo_path).resize((200, 200))
                self.logo_img = ImageTk.PhotoImage(img)
                tk.Label(self, image=self.logo_img, bg="white").pack(pady=20)
            else:
                tk.Label(self, text="SmartMart", font=("Segoe UI", 28, "bold"), fg="#2c3e50", bg="white").pack(pady=20)
        except:
            tk.Label(self, text="SmartMart", font=("Segoe UI", 28, "bold"), fg="#2c3e50", bg="white").pack(pady=20)

        tk.Label(self, text="Your Smart Retail POS Solution", font=("Segoe UI", 14), fg="#34495e", bg="white").pack()

        tk.Button(self, text="Proceed", font=("Segoe UI", 12, "bold"), bg="#27ae60", fg="white", padx=20, pady=10,
                  command=self.go_to_login).pack(pady=40)

    def go_to_login(self):
        self.destroy()
        LoginPage()


# --- Login Page ---
class LoginPage(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Login - SmartMart POS")
        self.geometry("400x300")
        self.configure(bg="white")
        self.resizable(False, False)

        self.user_store = UserStore()  # dynamic users

        tk.Label(self, text="Login", font=("Segoe UI", 18, "bold"), bg="white").pack(pady=20)

        tk.Label(self, text="Username:", bg="white").pack()
        self.username_entry = tk.Entry(self)
        self.username_entry.pack(pady=5)

        tk.Label(self, text="Password:", bg="white").pack()
        self.password_entry = tk.Entry(self, show="*")
        self.password_entry.pack(pady=5)

        tk.Button(
            self, text="Login",
            font=("Segoe UI", 12, "bold"),
            bg="#2980b9", fg="white", padx=15, pady=5,
            command=self.validate_login
        ).pack(pady=20)

    def validate_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if self.user_store.validate(username, password):
            role = self.user_store.role(username)
            messagebox.showinfo("Welcome", f"Logged in as {username} (role: {role})")
            self.destroy()
            run_pos_app(username, on_logout=self.back_to_login)  # ✅ pass username forward
        else:
            messagebox.showerror("Login Failed", "Invalid credentials.")

    def back_to_login(self):
        LoginPage().mainloop()

# --- Simple user store ---
class UserStore:
    def __init__(self, path=USERS_FILE):
        self.path = path
        self.users = {}  # username -> dict(pass, role)
        self.load()

    def load(self):
        data = load_json(self.path)
        if data and isinstance(data, dict):
            self.users = data
        else:
            # create default admin
            self.users = {"admin": {"password": "admin", "role": "admin"}, "cashier": {"password": "cash", "role": "cashier"}}
            self.save()

    def save(self):
        save_json(self.path, self.users)

    def validate(self, username, password):
        u = self.users.get(username)
        return u and u.get("password") == password

    def role(self, username):
        u = self.users.get(username)
        return u.get("role") if u else None


# --- Customer store (simple) ---
class CustomerStore:
    def __init__(self, path=CUSTOMERS_FILE):
        self.path = path
        self.customers = {}  # name -> {loyalty_points, email, phone}
        self.load()

    def load(self):
        data = load_json(self.path)
        if data and isinstance(data, dict):
            self.customers = data
        else:
            self.customers = {}
            self.save()

    def save(self):
        save_json(self.path, self.customers)

    def add_points(self, cust_name, points):
        if cust_name not in self.customers:
            self.customers[cust_name] = {"points": 0}
        self.customers[cust_name]["points"] = self.customers[cust_name].get("points", 0) + points
        self.save()

    def get_points(self, cust_name):
        return self.customers.get(cust_name, {}).get("points", 0)


# --- Main App ---
class RetailPOSApp(tb.Window if TB_AVAILABLE else tk.Tk):
    def __init__(self, username, on_logout=None):    # ✅ now accepts on_logout
        
        self.current_user = username
        self.on_logout = on_logout        # ✅ store callback
        self.user_store = UserStore()  # load users

        if TB_AVAILABLE:
            super().__init__(themename="flatly")
        else:
            super().__init__()

        role = self.user_store.role(username)
        self.title(f"Retail POS - Inventory & Billing (Extended) ({role.capitalize()}: {username})")

        self.geometry("1200x750")

          # Data stores
        self.products: List[Product] = []
        self.orders: List[OrderRecord] = []
        self.next_pid = 1
        self.next_oid = 1000

        # Cart
        self.cart_items: List[Dict] = []
        self.cart_total: float = 0.0
        self.order_level_discount: float = 0.0

        # config
        self.low_stock_threshold = LOW_STOCK_THRESHOLD_DEFAULT

        # users/customers
        self.customer_store = CustomerStore()

        # load data (or demo)
        self.load_data()

       
        # build UI
        self._build_ui()

        # after UI built, show any low-stock notifications
        self.after(500, self.check_low_stock_startup)

    def logout(self):
        if messagebox.askyesno("Logout", "Are you sure you want to logout?"):
            self.destroy()
            if self.on_logout:
                self.on_logout()

    # -------- Persistence --------
    def load_data(self):
        inv = load_json(INVENTORY_FILE)
        if inv:
            self.products = [Product.from_dict(d) for d in inv.get("products", [])]
            self.next_pid = inv.get("next_pid", max((p.product_id for p in self.products), default=0) + 1)
        else:
            # preload demo Indian products if no inventory.json
            if not self.products:
                demo = [
                    ("Basmati Rice (5kg)", "Grocery", 50, 1200.0, "Sharma Supplies"),
                    ("Masala Tea (250g)", "Beverage", 30, 250.0, "Tata Tea"),
                    ("Santoor Soap (4)", "Personal Care", 100, 25.0, "Wipro"),
                    ("Tata Salt (1kg)", "Grocery", 200, 22.0, "Tata Salt"),
                    ("Patanjali Honey (500g)", "Grocery", 40, 299.0, "Patanjali")
                ]
                for name, cat, qty, price, supp in demo:
                    self.products.append(Product(self.next_pid, name, cat, qty, price, supp))
                    self.next_pid += 1

        ords = load_json(ORDERS_FILE)
        if ords:
            self.orders = [OrderRecord.from_dict(d) for d in ords.get("orders", [])]
            self.next_oid = ords.get("next_oid", max((o.order_id for o in self.orders), default=999) + 1)

    def save_data(self):
        save_json(INVENTORY_FILE, {"products": [p.to_dict() for p in self.products], "next_pid": self.next_pid})
        save_json(ORDERS_FILE, {"orders": [o.to_dict() for o in self.orders], "next_oid": self.next_oid})
        # also lightweight backup
        save_json(BACKUP_FILE, {"products": [p.to_dict() for p in self.products], "orders": [o.to_dict() for o in self.orders], "next_pid": self.next_pid, "next_oid": self.next_oid})

    
    def current_role(self):
        return self.user_store.role(self.current_user)

    # -------- UI construction --------
    def _build_ui(self):

        menubar = tk.Menu(self)
        account_menu = tk.Menu(menubar, tearoff=0)
        account_menu.add_command(label="Logout", command=self.logout)
        menubar.add_cascade(label="Account", menu=account_menu)
        self.config(menu=menubar)
    
        nb = tb.Notebook(self, bootstyle="secondary") if TB_AVAILABLE else ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        inv_tab = ttk.Frame(nb)
        create_tab = ttk.Frame(nb)
        history_tab = ttk.Frame(nb)
        reports_tab = ttk.Frame(nb)

        nb.add(inv_tab, text="Inventory")
        nb.add(create_tab, text="Create Order")
        nb.add(history_tab, text="Orders History")
        nb.add(reports_tab, text="Reports")

        # ✅ Only add Settings tab if current user is admin
        if self.current_role() == "admin":
          settings_tab = ttk.Frame(nb)
          nb.add(settings_tab, text="Settings")
          self._build_settings_tab(settings_tab)

        # build tabs
        self._build_inventory_tab(inv_tab)
        self._build_create_order_tab(create_tab)
        self._build_history_tab(history_tab)
        self._build_reports_tab(reports_tab)

        # --- Status Bar ---
        self.status_var = tk.StringVar()
        role = self.user_store.role(self.current_user)
        self.status_var.set(f"User: {self.current_user} ({role}) | Cart Total: ₹{self.cart_total:.2f}")

        status_bar = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(side="bottom", fill="x")

        # keep updating clock + cart total
        self.update_status_bar()

   # -------- Inventory Tab --------
    def _build_inventory_tab(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Label(top, text="Name:").grid(row=0, column=0, sticky="w")
        self.inv_name = ttk.Entry(top, width=30); self.inv_name.grid(row=0, column=1, padx=4)

        ttk.Label(top, text="Category:").grid(row=0, column=2, sticky="w")
        self.inv_cat = ttk.Entry(top, width=20); self.inv_cat.grid(row=0, column=3, padx=4)

        ttk.Label(top, text="Qty:").grid(row=0, column=4, sticky="w")
        self.inv_qty = ttk.Entry(top, width=8); self.inv_qty.grid(row=0, column=5, padx=4)

        ttk.Label(top, text="Price:").grid(row=0, column=6, sticky="w")
        self.inv_price = ttk.Entry(top, width=10); self.inv_price.grid(row=0, column=7, padx=4)

        ttk.Label(top, text="Supplier:").grid(row=0, column=8, sticky="w")
        self.inv_supp = ttk.Entry(top, width=20); self.inv_supp.grid(row=0, column=9, padx=4)

        ttk.Label(top, text="Barcode:").grid(row=0, column=10, sticky="w")
        self.inv_barcode = ttk.Entry(top, width=18); self.inv_barcode.grid(row=0, column=11, padx=4)

        ttk.Button(top, text="Add", command=self.inv_add, width=10).grid(row=0, column=12, padx=6)
        ttk.Button(top, text="Update Selected", command=self.inv_update_selected, width=14).grid(row=0, column=13, padx=6)
        ttk.Button(top, text="Delete Selected", command=self.inv_delete_selected, width=14).grid(row=0, column=14, padx=6)

        mid = ttk.Frame(parent); mid.pack(fill="x", padx=6, pady=6)
        ttk.Label(mid, text="Search:").pack(side="left", padx=(0,6))
        self.inv_search_var = tk.StringVar()
        self.inv_search_var.trace_add("write", lambda *_: self.refresh_inventory_table())
        ttk.Entry(mid, textvariable=self.inv_search_var, width=40).pack(side="left")
        ttk.Button(mid, text="Import CSV", command=self.inv_import_csv).pack(side="right", padx=4)
        ttk.Button(mid, text="Export CSV", command=self.inv_export_csv).pack(side="right", padx=4)
        ttk.Button(mid, text="Gen Barcode Image", command=self.generate_barcode_for_selected).pack(side="right", padx=4)

        cols = ("ID", "Name", "Category", "Qty", "Price", "Supplier", "Barcode")
        self.inv_tree = ttk.Treeview(parent, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.inv_tree.heading(c, text=c)
            self.inv_tree.column(c, width=160 if c == "Name" else 100, anchor="w")
        self.inv_tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.inv_tree.bind("<Double-1>", self.on_inv_double_click)

        self.refresh_inventory_table()

    def inv_add(self):
        name = self.inv_name.get().strip()
        if not name:
            messagebox.showwarning("Input", "Name required")
            return
        try:
            qty = int(self.inv_qty.get().strip())
            price = float(self.inv_price.get().strip())
        except Exception:
            messagebox.showwarning("Invalid", "Quantity must be integer, price numeric")
            return
        cat = self.inv_cat.get().strip() or "General"
        supp = self.inv_supp.get().strip() or ""
        bc = self.inv_barcode.get().strip() or ""
        pid = self.next_pid; self.next_pid += 1
        p = Product(pid, name, cat, qty, price, supp, bc)
        if not p.barcode:
            p.barcode = str(pid)
        self.products.append(p)
        self.save_data()
        self.clear_inv_inputs()
        self.refresh_inventory_table()
        self.refresh_product_combobox()
    

    def inv_update_selected(self):
        sel = self.inv_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a product to update")
            return
        vals = self.inv_tree.item(sel[0], "values")
        pid = int(vals[0])
        prod = self.get_product(pid)
        if not prod: return
        name = self.inv_name.get().strip() or prod.name
        cat = self.inv_cat.get().strip() or prod.category
        supp = self.inv_supp.get().strip() or prod.supplier
        bc = self.inv_barcode.get().strip() or prod.barcode
        try:
            qty = int(self.inv_qty.get().strip()) if self.inv_qty.get().strip() else prod.quantity
            price = float(self.inv_price.get().strip()) if self.inv_price.get().strip() else prod.price
        except Exception:
            messagebox.showwarning("Invalid", "Quantity must be integer, price numeric")
            return
        prod.name, prod.category, prod.quantity, prod.price, prod.supplier, prod.barcode = name, cat, qty, price, supp, bc
        self.save_data()
        self.clear_inv_inputs()
        self.refresh_inventory_table()
        self.refresh_product_combobox()
        
        

    def inv_delete_selected(self):
        sel = self.inv_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a product to delete")
            return
        vals = self.inv_tree.item(sel[0], "values")
        pid = int(vals[0])
        if messagebox.askyesno("Confirm", f"Delete product ID {pid}?"):
            self.products = [p for p in self.products if p.product_id != pid]
            self.save_data()
            self.refresh_inventory_table()
            self.refresh_product_combobox()

    def inv_import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV","*.csv")])
        if not path: return
        try:
            with open(path, newline="", encoding="utf-8") as f:
                rdr = csv.DictReader(f)
                self.products = []
                for row in rdr:
                    p = Product(int(row["product_id"]), row["name"], row.get("category",""), int(row.get("quantity",0)), float(row.get("price",0.0)), row.get("supplier",""), row.get("barcode",""))
                    self.products.append(p)
                self.next_pid = max((p.product_id for p in self.products), default=0) + 1
            self.save_data()
            self.refresh_inventory_table()
            self.refresh_product_combobox()
            messagebox.showinfo("Import", "Inventory imported from CSV")
        except Exception as e:
            messagebox.showerror("Import failed", str(e))

    def inv_export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id","name","category","quantity","price","supplier","barcode"])
            for p in self.products:
                writer.writerow([p.product_id,p.name,p.category,p.quantity,p.price,p.supplier,p.barcode])
        messagebox.showinfo("Export", f"Inventory exported to {path}")

    def clear_inv_inputs(self):
        self.inv_name.delete(0, tk.END)
        self.inv_cat.delete(0, tk.END)
        self.inv_qty.delete(0, tk.END)
        self.inv_price.delete(0, tk.END)
        self.inv_supp.delete(0, tk.END)
        self.inv_barcode.delete(0, tk.END)

    def on_inv_double_click(self, _event):
        sel = self.inv_tree.selection()
        if not sel: return
        vals = self.inv_tree.item(sel[0], "values")
        pid = int(vals[0])
        prod = self.get_product(pid)
        if prod:
            self.inv_name.delete(0, tk.END); self.inv_name.insert(0, prod.name)
            self.inv_cat.delete(0, tk.END); self.inv_cat.insert(0, prod.category)
            self.inv_qty.delete(0, tk.END); self.inv_qty.insert(0, str(prod.quantity))
            self.inv_price.delete(0, tk.END); self.inv_price.insert(0, str(prod.price))
            self.inv_supp.delete(0, tk.END); self.inv_supp.insert(0, prod.supplier)
            self.inv_barcode.delete(0, tk.END); self.inv_barcode.insert(0, prod.barcode)

    def refresh_inventory_table(self):
        query = self.inv_search_var.get().strip().lower() if hasattr(self, "inv_search_var") else ""
        for r in self.inv_tree.get_children(): self.inv_tree.delete(r)
        for p in self.products:
            if query:
                if query not in p.name.lower() and query not in p.category.lower() and query not in p.supplier.lower() and query not in p.barcode.lower():
                    continue
            display_price = f"₹{p.price:.2f}"
            self.inv_tree.insert("", tk.END, values=(p.product_id, p.name, p.category, p.quantity, display_price, p.supplier, p.barcode))

    def get_product(self, pid) -> Optional[Product]:
        for p in self.products:
            if p.product_id == pid: return p
        return None

    def find_by_barcode(self, bc) -> Optional[Product]:
        for p in self.products:
            if p.barcode == bc or str(p.product_id) == str(bc):
                return p
        return None

    # -------- Create Order Tab --------
    def _build_create_order_tab(self, parent):
        top = ttk.Frame(parent); top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Customer name:").grid(row=0, column=0, sticky="w")
        self.cust_entry = ttk.Entry(top, width=30); self.cust_entry.grid(row=0, column=1, padx=6)
        ttk.Label(top, text="Customer city:").grid(row=0, column=2, sticky="w")
        self.city_entry = ttk.Entry(top, width=20); self.city_entry.grid(row=0, column=3, padx=6)
        ttk.Button(top, text="Lookup Loyalty", command=self.lookup_loyalty).grid(row=0, column=4, padx=6)

        mid = ttk.Frame(parent); mid.pack(fill="x", padx=6, pady=6)
        ttk.Label(mid, text="Scan/Barcode or Product ID:").pack(side="left")
        self.barcode_entry = ttk.Entry(mid, width=30)
        self.barcode_entry.pack(side="left", padx=6)
        ttk.Button(mid, text="Add by Barcode", command=self.add_by_barcode).pack(side="left", padx=6)

        ttk.Label(mid, text="Product:").pack(side="left", padx=(12,0))
        self.prod_var = tk.StringVar()
        self.prod_combo = ttk.Combobox(mid, textvariable=self.prod_var, state="readonly", width=60)
        self.prod_combo.pack(side="left", padx=6)
        ttk.Label(mid, text="Qty:").pack(side="left", padx=(6,0))
        self.qty_spin = ttk.Spinbox(mid, from_=1, to=999, width=6); self.qty_spin.set(1); self.qty_spin.pack(side="left", padx=6)
        ttk.Label(mid, text="Disc %:").pack(side="left")
        self.item_disc = ttk.Entry(mid, width=6); self.item_disc.insert(0, "0"); self.item_disc.pack(side="left", padx=4)
        ttk.Button(mid, text="Add to Cart", command=self.ui_add_to_cart).pack(side="left", padx=6)
        ttk.Button(mid, text="Remove Selected Item", command=self.ui_remove_cart_item).pack(side="left", padx=6)
        ttk.Button(mid, text="Clear Cart", command=self.ui_clear_cart).pack(side="left", padx=6)

        cart_cols = ("PID","Name","Qty","Disc%","Unit","Line")
        self.cart_tree = ttk.Treeview(parent, columns=cart_cols, show="headings", height=8)
        for c in cart_cols:
            self.cart_tree.heading(c, text=c); self.cart_tree.column(c, width=140, anchor="w")
        self.cart_tree.pack(fill="both", expand=False, padx=6, pady=6)

        bot = ttk.Frame(parent); bot.pack(fill="x", padx=6, pady=6)
        self.total_label_var = tk.StringVar(value="Total: ₹0.00")
        ttk.Label(bot, textvariable=self.total_label_var, font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(bot, text="Apply Order Discount", command=self.apply_order_discount).pack(side="left", padx=6)
        ttk.Button(bot, text="Finalize Order", command=self.ui_finalize_order).pack(side="right", padx=6)

        self.refresh_product_combobox()
        self.refresh_cart_tree()

    def lookup_loyalty(self):
        name = self.cust_entry.get().strip()
        if not name:
            messagebox.showinfo("Customer", "Enter customer name to lookup")
            return
        pts = self.customer_store.get_points(name)
        messagebox.showinfo("Loyalty", f"Customer {name} has {pts} points")

    def add_by_barcode(self):
        bc = self.barcode_entry.get().strip()
        if not bc:
            messagebox.showwarning("Scan", "Enter or scan a barcode/product id")
            return
        prod = self.find_by_barcode(bc)
        if not prod:
            messagebox.showerror("Not found", "Product not found for barcode")
            return
        # set combo and qty to 1 and add
        self.prod_combo.set(f"{prod.product_id} | {prod.name} (₹{prod.price:.2f}) [{prod.quantity}]")
        self.qty_spin.set(1)
        self.ui_add_to_cart()

    def refresh_product_combobox(self):
        if hasattr(self, "prod_combo"):
            vals = [f"{p.product_id} | {p.name} (₹{p.price:.2f}) [{p.quantity}]" for p in self.products]
            self.prod_combo['values'] = vals

    def update_status_bar(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        role = self.user_store.role(self.current_user)
        self.status_var.set(f"User: {self.current_user} ({role}) | Cart Total: ₹{self.cart_total:.2f} | {now}")
        self.after(1000, self.update_status_bar)  # update every second


    def update_cart_total(self):
        """Recalculate cart total (with discount) and refresh status bar."""
        subtotal = sum(item["line_total"] for item in self.cart_items)
        if self.order_level_discount:
            total = subtotal * (1 - self.order_level_discount / 100.0)
        else:
            total = subtotal
        self.cart_total = total
        self.update_status_bar()

    def ui_add_to_cart(self):
        sel = self.prod_combo.get()
        if not sel:
            messagebox.showwarning("Select", "Choose a product")
            return
        pid = int(sel.split("|")[0].strip())
        prod = self.get_product(pid)
        if not prod:
            messagebox.showerror("Error", "Product not found")
            return
        try:
            qty = int(self.qty_spin.get())
            if qty <= 0:
                raise ValueError()
        except Exception:
            messagebox.showwarning("Invalid", "Enter valid quantity")
            return
        try:
            disc_pct = float(self.item_disc.get().strip() or 0.0)
            disc_pct = max(0.0, min(100.0, disc_pct))
        except Exception:
            messagebox.showwarning("Invalid", "Invalid discount percentage")
            return
        if prod.quantity < qty:
            messagebox.showwarning("Stock", f"Only {prod.quantity} available")
            return
        prod.quantity -= qty
        unit = prod.price
        line = unit * qty
        if disc_pct:
            discount_amount = line * (disc_pct / 100.0)
            line -= discount_amount
        else:
            discount_amount = 0.0
        item = {"product_id": prod.product_id, "name": prod.name, "qty": qty, "unit_price": unit, "line_total": line, "disc_pct": disc_pct, "disc_amount": discount_amount}
        self.cart_items.append(item)
        self.cart_total += line
        self.save_data()
        self.refresh_cart_tree(); self.refresh_inventory_table(); self.refresh_product_combobox()
        self.update_cart_total()

    def ui_remove_cart_item(self):
        sel = self.cart_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select an item in cart")
            return
        vals = self.cart_tree.item(sel[0], "values")
        pid = int(vals[0]); qty = int(vals[2])
        for i, it in enumerate(self.cart_items):
            if it["product_id"] == pid and it["qty"] == qty:
                prod = self.get_product(pid)
                if prod:
                    prod.quantity += it["qty"]
                self.cart_total -= it["line_total"]
                del self.cart_items[i]
                break
        self.save_data()
        self.refresh_cart_tree(); self.refresh_inventory_table(); self.refresh_product_combobox()
        self.update_cart_total()

    def ui_clear_cart(self):
        for it in self.cart_items:
            prod = self.get_product(it["product_id"])
            if prod:
                prod.quantity += it["qty"]
        self.cart_items = []; self.cart_total = 0.0; self.order_level_discount = 0.0
        self.save_data(); self.refresh_cart_tree(); self.refresh_inventory_table(); self.refresh_product_combobox()
        self.update_cart_total()

    def refresh_cart_tree(self):
        for r in self.cart_tree.get_children(): self.cart_tree.delete(r)
        for it in self.cart_items:
            self.cart_tree.insert("", tk.END, values=(it["product_id"], it["name"], it["qty"], f"{it.get('disc_pct',0):.1f}", f"₹{it['unit_price']:.2f}", f"₹{it['line_total']:.2f}"))
        total_display = self.cart_total
        if self.order_level_discount:
            total_display = total_display * (1 - self.order_level_discount/100.0)
        self.total_label_var.set(f"Total: ₹{total_display:.2f}  (Disc {self.order_level_discount:.1f}%)")
        


    def apply_order_discount(self):
        val = simpledialog.askfloat("Order discount", "Enter order discount percent (0-100):", minvalue=0.0, maxvalue=100.0)
        if val is None: return
        self.order_level_discount = float(val)
        self.refresh_cart_tree()
        self.update_cart_total()

    def ui_finalize_order(self):
        if not self.cart_items:
            messagebox.showwarning("Empty", "Cart is empty"); return
        customer = self.cust_entry.get().strip(); city = self.city_entry.get().strip()
        if not customer:
            messagebox.showwarning("Customer", "Enter customer name"); return
        cust_str = f"{customer} ({city})" if city else customer
        oid = self.next_oid; self.next_oid += 1
        created_at = datetime.now().isoformat(timespec='seconds')

        # compute totals and apply order-level discount
        subtotal = sum(it['line_total'] for it in self.cart_items)
        discount_amount = subtotal * (self.order_level_discount/100.0)
        total = subtotal - discount_amount

        # payment dialog
        payment = self.ask_payment(total)
        if not payment:
            # user cancelled payment
            return

        rec = OrderRecord(oid, cust_str, list(self.cart_items), total, created_at, payment, self.order_level_discount)
        self.orders.append(rec)
        # loyalty points: 1 point per LOYALTY_POINTS_PER_RS rupees
        pts = int(total // LOYALTY_POINTS_PER_RS)
        if customer:
            self.customer_store.add_points(customer, pts)

        self.save_data(); self.write_invoice(rec)
        messagebox.showinfo("Order", f"Order {rec.order_id} saved. Invoices created. Loyalty points awarded: {pts}")
        self.cart_items = []; self.cart_total = 0.0; self.order_level_discount = 0.0
        self.refresh_cart_tree(); self.refresh_orders_table()
        self.cust_entry.delete(0, tk.END); self.city_entry.delete(0, tk.END)
        self.refresh_product_combobox(); self.refresh_inventory_table()
        self.update_cart_total()


    def ask_payment(self, amount) -> Optional[Dict]:
        dlg = PaymentDialog(self, amount)
        self.wait_window(dlg)
        return dlg.result

    def write_invoice(self, rec: OrderRecord):
        txt_name = f"invoice_{rec.order_id}.txt"
        lines = []
        lines.append(f"INVOICE - Order #{rec.order_id}")
        lines.append(f"Customer: {rec.customer}")
        lines.append(f"Date: {rec.created_at}")
        lines.append("")
        lines.append("{:<40} {:>5} {:>8} {:>12}".format("Item","Qty","Disc","Line"))
        lines.append("-"*80)
        for it in rec.items:
            lines.append("{:<40} {:>5} {:>8.2f} {:>12.2f}".format(it["name"][:40], it["qty"], it.get("disc_pct",0.0), it["line_total"]))
        lines.append("-"*80)
        lines.append(f"ORDER DISC %: {rec.discount:.2f}")
        lines.append(f"TOTAL (Rs.): {rec.total:.2f}")
        lines.append(f"Payment: {rec.payment.get('method')} {rec.payment.get('details')}")
        with open(txt_name, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if PDF_AVAILABLE:
            pdf_name = f"invoice_{rec.order_id}.pdf"
            pdf = FPDF()
            pdf.add_page(); pdf.set_auto_page_break(True, margin=15); pdf.set_font("Arial", size=11)
            pdf.cell(0,8, f"Invoice - Order #{rec.order_id}", ln=True)
            pdf.cell(0,6, f"Customer: {rec.customer}", ln=True); pdf.cell(0,6, f"Date: {rec.created_at}", ln=True); pdf.ln(4)
            pdf.set_font("Arial", style="B", size=11)
            pdf.cell(90,8,"Item", border=1); pdf.cell(25,8,"Qty", border=1, align="R"); pdf.cell(25,8,"Disc%", border=1, align="R"); pdf.cell(35,8,"Line (Rs.)", border=1, align="R"); pdf.ln()
            pdf.set_font("Arial", size=11)
            for it in rec.items:
                pdf.cell(90,8, it["name"][:40], border=1); pdf.cell(25,8, str(it["qty"]), border=1, align="R"); pdf.cell(25,8, f"{it.get('disc_pct',0):.2f}", border=1, align="R"); pdf.cell(35,8, f"{it['line_total']:.2f}", border=1, align="R"); pdf.ln()
            pdf.ln(4); pdf.set_font("Arial", style="B", size=12); pdf.cell(0,8, txt=f"ORDER DISC %: {rec.discount:.2f}", ln=True); pdf.cell(0,8, txt=f"TOTAL (Rs.): {rec.total:.2f}", ln=True); pdf.cell(0,8, txt=f"Payment: {rec.payment.get('method')}", ln=True)
            pdf.output(pdf_name)

    # -------- Orders History Tab --------
    def _build_history_tab(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="x", padx=6, pady=6)

        ttk.Button(top, text="Refresh", command=self.refresh_orders_table).pack(side="left", padx=6)
        ttk.Button(top, text="Export Orders CSV", command=self.export_orders_csv).pack(side="left", padx=6)

        cols = ("oid", "customer", "items", "total", "date")
        self.orders_tree = ttk.Treeview(parent, columns=cols, show="headings", height=15)
        for c, txt, w in [
            ("oid", "Order ID", 100),
            ("customer", "Customer", 200),
            ("items", "Items", 250),
            ("total", "Total", 120),
            ("date", "Date", 150)
        ]:
            self.orders_tree.heading(c, text=txt)
            self.orders_tree.column(c, width=w, anchor="center")
        self.orders_tree.pack(fill="both", expand=True, padx=6, pady=6)

        # ✅ Sales total label
        self.total_sales_label = ttk.Label(
            parent, text="Total Sales: ₹0.00",
            font=("Segoe UI", 10, "bold")
        )
        self.total_sales_label.pack(anchor="e", padx=10, pady=4)

        self.refresh_orders_table()   # load immediately
        self.orders_tree.bind("<Double-1>", self.on_order_double_click)



    def refresh_orders_table(self):
        if not hasattr(self, "orders_tree"):
            return

        # Clear old rows
        for r in self.orders_tree.get_children():
            self.orders_tree.delete(r)

        total_sales = 0.0

        # Refill with orders
        for o in self.orders:
            items_summary = "; ".join([f"{it['name']} x {it['qty']}" for it in o.items])
            self.orders_tree.insert(
                "", tk.END,
                values=(o.order_id, o.customer, items_summary, f"₹{o.total:.2f}", o.created_at)
            )
            total_sales += float(o.total)

        # ✅ Update total sales label
        if hasattr(self, "total_sales_label"):
            self.total_sales_label.config(text=f"Total Sales: ₹{total_sales:.2f}")


    def on_order_double_click(self, event):
        sel = self.orders_tree.selection()
        if not sel:
            return

        vals = self.orders_tree.item(sel[0], "values")
        oid = int(vals[0])
        txt_file = f"invoice_{oid}.txt"
        pdf_file = f"invoice_{oid}.pdf"

        if not os.path.exists(txt_file) and not os.path.exists(pdf_file):
            messagebox.showwarning("Invoice", f"No invoice found for Order {oid}")
            return

        # ✅ Custom dialog to choose format
        dialog = tk.Toplevel(self)
        dialog.title("Open Invoice As...")
        dialog.resizable(False, False)

        # --- center the dialog ---
        dialog.update_idletasks()
        w, h = 250, 120
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        dialog.geometry(f"{w}x{h}+{x}+{y}")

        ttk.Label(dialog, text=f"Open Invoice #{oid} as:").pack(pady=10)

        def open_txt():
            dialog.destroy()
            with open(txt_file, "r", encoding="utf-8") as f:
                txt = f.read()
            w = tk.Toplevel(self)
            w.title(f"Invoice #{oid} (TXT)")
            txtbox = tk.Text(w, wrap="none", width=100, height=30)
            txtbox.pack(fill="both", expand=True)
            txtbox.insert("1.0", txt)

        def open_pdf():
            dialog.destroy()
            if os.path.exists(pdf_file):
                try:
                    webbrowser.open_new(pdf_file)
                except Exception:
                    messagebox.showerror("Error", "Could not open PDF viewer.")
            else:
                messagebox.showwarning("Invoice", "PDF not found")

        ttk.Button(dialog, text="Open TXT", command=open_txt).pack(pady=5)
        ttk.Button(dialog, text="Open PDF", command=open_pdf).pack(pady=5)


    def export_orders_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["order_id","customer","items","total","created_at","payment","discount"])
            for o in self.orders:
                items_str = ";".join([f"{it['name']}|{it['qty']}" for it in o.items])
                w.writerow([o.order_id, o.customer, items_str, o.total, o.created_at, json.dumps(o.payment), o.discount])
        messagebox.showinfo("Export", f"Orders exported to {path}")

    # -------- Reports Tab --------
    def _build_reports_tab(self, parent):
        top = ttk.Frame(parent); top.pack(fill="x", padx=6, pady=6)
        role = self.current_role()

        if role == "admin":
          ttk.Button(top, text="Low-stock (<=threshold)", command=self.report_low_stock).pack(side="left", padx=6)

        ttk.Button(top, text="Top selling", command=self.report_top_selling).pack(side="left", padx=6)

        ttk.Button(top, text="Sales chart (matplotlib)", command=self.report_sales_chart).pack(side="left", padx=6)

        if role == "admin":
          ttk.Button(top, text="Top customers", command=self.report_top_customers).pack(side="left", padx=6)
        
        ttk.Button(top, text="Export Report (CSV)", command=self.export_report_csv).pack(side="right", padx=6)
        ttk.Button(top, text="Export Report (PDF)", command=self.export_report_pdf).pack(side="right", padx=6)


        self.report_text = tk.Text(parent, height=25); self.report_text.pack(fill="both", expand=True, padx=6, pady=6)
    
    def export_report_csv(self):
        text = self.report_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Export", "No report to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not path: return
        with open(path, "w", encoding="utf-8") as f:
            for line in text.splitlines():
                f.write(line.replace(":", ",") + "\n")
        messagebox.showinfo("Export", f"Report saved to {path}")

    def export_report_pdf(self):
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except ImportError:
            messagebox.showerror("PDF Export", "reportlab not installed. Install with: pip install reportlab")
            return

        text = self.report_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showinfo("Export", "No report to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not path: return

        c = canvas.Canvas(path, pagesize=letter)
        width, height = letter
        y = height - 50
        for line in text.splitlines():
            c.drawString(50, y, line)
            y -= 15
            if y < 50:
                c.showPage(); y = height - 50
        c.save()
        messagebox.showinfo("Export", f"Report saved to {path}")


    def report_low_stock(self):
        rows = [p for p in self.products if p.quantity <= self.low_stock_threshold]
        if not rows:
            self.report_text.delete("1.0", tk.END); self.report_text.insert("1.0", "No low-stock items."); return
        out = f"Low-stock items (<= {self.low_stock_threshold}):\n\n"
        for p in rows: out += f"ID {p.product_id}: {p.name} - Qty {p.quantity}\n"
        self.report_text.delete("1.0", tk.END); self.report_text.insert("1.0", out)

    def report_top_selling(self):
        cnt = Counter()
        for o in self.orders:
            for it in o.items: cnt[it["name"]] += it["qty"]
        if not cnt:
            self.report_text.delete("1.0", tk.END); self.report_text.insert("1.0", "No sales yet."); return
        out = "Top selling products:\n\n"
        for name, qty in cnt.most_common(20): out += f"{name}: {qty}\n"
        self.report_text.delete("1.0", tk.END); self.report_text.insert("1.0", out)

    def report_top_customers(self):
        cnt = Counter()
        for o in self.orders:
            cname = o.customer.split(" (")[0]
            cnt[cname] += o.total
        if not cnt:
            self.report_text.delete("1.0", tk.END); self.report_text.insert("1.0", "No orders yet."); return
        out = "Top customers by spend:\n\n"
        for name, val in cnt.most_common(20): out += f"{name}: ₹{val:.2f}\n"
        self.report_text.delete("1.0", tk.END); self.report_text.insert("1.0", out)

    def report_sales_chart(self):
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showinfo("Chart", "matplotlib not available. Install matplotlib and pillow to enable charts.")
            return
        # simple daily sales bar chart (by date)
        totals = defaultdict(float)
        for o in self.orders:
            date = o.created_at.split("T")[0]
            totals[date] += o.total
        if not totals:
            messagebox.showinfo("Chart", "No sales data to plot")
            return
        dates = sorted(totals.keys())
        vals = [totals[d] for d in dates]
        plt.figure(figsize=(8,4))
        plt.bar(dates, vals)
        plt.xticks(rotation=45, ha='right')
        plt.title('Daily sales')
        plt.tight_layout()
        img_path = os.path.join(APP_DIR, 'sales_chart.png')
        plt.savefig(img_path)
        plt.close()
        # show image in Toplevel
        win = tk.Toplevel(self); win.title('Sales chart')
        img = Image.open(img_path)
        tkimg = ImageTk.PhotoImage(img)
        lbl = ttk.Label(win, image=tkimg); lbl.image = tkimg; lbl.pack()

    # -------- Settings Tab --------
    def _build_settings_tab(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=6, pady=6)

        # Data management
        ttk.Button(frame, text="Save data now", command=self.save_data).pack(pady=6)
        ttk.Button(frame, text="Export all data JSON", command=self.export_all_data).pack(pady=6)
        ttk.Button(frame, text="Import all data JSON", command=self.import_all_data).pack(pady=6)
        ttk.Button(frame, text="Clear all data (reset)", command=self.clear_all_data).pack(pady=6)
        ttk.Button(frame, text="Backup now", command=self.backup_now).pack(pady=6)
        ttk.Button(frame, text="Logout", command=self.logout).pack(pady=10)

        # Stock settings
        ttk.Label(frame, text="Low stock threshold:").pack(pady=6)
        self.low_stock_var = tk.IntVar(value=self.low_stock_threshold)
        ttk.Spinbox(frame, from_=1, to=100, textvariable=self.low_stock_var, width=6).pack()
        ttk.Button(frame, text="Apply threshold", command=self.apply_threshold).pack(pady=6)

        # Theme (if ttkbootstrap available)
        if TB_AVAILABLE and STYLE is not None:
            ttk.Label(frame, text="Theme:").pack(pady=6)
            themes = STYLE.theme_names()
            self.theme_var = tk.StringVar(value=STYLE.theme_use())
            combo = ttk.Combobox(frame, values=themes, textvariable=self.theme_var, state="readonly")
            combo.pack()
            ttk.Button(frame, text="Apply Theme", command=self.apply_theme).pack(pady=6)

        # User management
        ttk.Separator(frame).pack(fill='x', pady=8)
        ttk.Label(frame, text='Manage users').pack()
        ttk.Button(frame, text='Add user', command=self.add_user_dialog).pack(pady=4)
        ttk.Button(frame, text='List users', command=self.list_users).pack(pady=4)

        # --- Theme Toggle ---
        ttk.Label(frame, text="Theme:").pack(pady=6)
        self.theme_var = tk.StringVar(value="light")
        theme_combo = ttk.Combobox(frame, values=["light", "dark"], textvariable=self.theme_var, state="readonly")
        theme_combo.pack()
        ttk.Button(frame, text="Apply Theme", command=self.apply_theme).pack(pady=6)


    def apply_theme(self):
        if not TB_AVAILABLE:
            messagebox.showinfo("Theme", "ttkbootstrap not available.")
            return
        mode = self.theme_var.get()
        if mode == "dark":
            STYLE.theme_use("darkly")   # bootstrap dark theme
        else:
            STYLE.theme_use("flatly")   # bootstrap light theme


    def export_all_data(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if not path: return
        data = {"products": [p.to_dict() for p in self.products], "orders": [o.to_dict() for o in self.orders], "next_pid": self.next_pid, "next_oid": self.next_oid}
        save_json(path, data); messagebox.showinfo("Export", f"Exported all data to {path}")

    def import_all_data(self):
        path = filedialog.askopenfilename(filetypes=[("JSON","*.json")])
        if not path: return
        data = load_json(path)
        if not data:
            messagebox.showerror("Import", "Invalid JSON"); return
        self.products = [Product.from_dict(d) for d in data.get("products", [])]
        self.orders = [OrderRecord.from_dict(d) for d in data.get("orders", [])]
        self.next_pid = data.get("next_pid", max((p.product_id for p in self.products), default=0)+1)
        self.next_oid = data.get("next_oid", max((o.order_id for o in self.orders), default=999)+1)
        self.save_data(); self.refresh_inventory_table(); self.refresh_orders_table(); self.refresh_product_combobox()
        messagebox.showinfo("Import", "All data imported")

    def clear_all_data(self):
        if not messagebox.askyesno("Confirm", "This will clear all products and orders. Continue?"): return
        self.products = []; self.orders = []; self.next_pid = 1; self.next_oid = 1000
        self.save_data(); self.refresh_inventory_table(); self.refresh_orders_table(); self.refresh_product_combobox()
        messagebox.showinfo("Reset", "Data cleared")

    def apply_theme(self):
        if TB_AVAILABLE and STYLE is not None:
            theme = self.theme_var.get()
            try:
                STYLE.theme_use(theme)
                messagebox.showinfo("Theme", f"Applied theme: {theme}")
            except Exception as e:
                messagebox.showerror("Theme", str(e))

    def backup_now(self):
        save_json(BACKUP_FILE, {"products": [p.to_dict() for p in self.products], "orders": [o.to_dict() for o in self.orders], "next_pid": self.next_pid, "next_oid": self.next_oid})
        messagebox.showinfo("Backup", f"Backup saved to {BACKUP_FILE}")

    def apply_threshold(self):
        try:
            self.low_stock_threshold = int(self.low_stock_var.get())
            messagebox.showinfo("Threshold", f"Applied low-stock threshold: {self.low_stock_threshold}")
        except Exception:
            messagebox.showwarning("Invalid", "Enter integer threshold")

    def add_user_dialog(self):
        dlg = AddUserDialog(self)
        self.wait_window(dlg)

        if dlg.result:
            username, password, role = dlg.result

            # ✅ Prevent duplicates
            if username in self.user_store.users:
                messagebox.showerror("Error", f"User '{username}' already exists!")
                return

            # Save to store
            self.user_store.users[username] = {"password": password, "role": role}
            self.user_store.save()

            messagebox.showinfo("Success", f"User '{username}' added as {role}")


    def list_users(self):
        dlg = tk.Toplevel(self)
        dlg.title("All Users")
        dlg.geometry("300x300")
        dlg.grab_set()

        cols = ("Username", "Role")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        tree.heading("Username", text="Username")
        tree.heading("Role", text="Role")
        tree.pack(fill="both", expand=True)

        for uname, info in self.user_store.users.items():
            tree.insert("", "end", values=(uname, info["role"]))


    # -------- Utilities --------
    def refresh_product_combobox(self):
        if hasattr(self, "prod_combo"):
            vals = [f"{p.product_id} | {p.name} (₹{p.price:.2f}) [{p.quantity}]" for p in self.products]
            self.prod_combo['values'] = vals

    def backup_and_notify(self):
        save_json(BACKUP_FILE, {"products": [p.to_dict() for p in self.products], "orders": [o.to_dict() for o in self.orders], "next_pid": self.next_pid, "next_oid": self.next_oid})

    def check_low_stock_startup(self):
        low = [p for p in self.products if p.quantity <= self.low_stock_threshold]
        if low:
            names = '\n'.join([f"{p.name}: {p.quantity}" for p in low])
            messagebox.showwarning("Low stock warning", f"The following items are low in stock (<= {self.low_stock_threshold}):\n{names}")

    def generate_barcode_for_selected(self):
        if not BARCODE_AVAILABLE:
            messagebox.showinfo("Barcode", "python-barcode not installed. Install 'python-barcode[images]' to enable this feature.")
            return
        sel = self.inv_tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Select a product to generate barcode")
            return
        pid = int(self.inv_tree.item(sel[0], 'values')[0])
        prod = self.get_product(pid)
        if not prod: return
        code = prod.barcode or str(prod.product_id)
        try:
            EAN = barcode.get_barcode_class('code128')
            e = EAN(code, writer=ImageWriter())
            out = os.path.join(APP_DIR, f'barcode_{prod.product_id}.png')
            e.save(out)
            messagebox.showinfo('Barcode', f'Barcode image saved: {out}')
        except Exception as e:
            messagebox.showerror('Barcode failed', str(e))


# --- Dialogs & small widgets ---
class LoginDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title('Login')
        self.resizable(False, False)
        self.result = None
        ttk.Label(self, text='Username:').grid(row=0, column=0, padx=6, pady=6)
        self.user_e = ttk.Entry(self); self.user_e.grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(self, text='Password:').grid(row=1, column=0, padx=6, pady=6)
        self.pass_e = ttk.Entry(self, show='*'); self.pass_e.grid(row=1, column=1, padx=6, pady=6)
        ttk.Button(self, text='Login', command=self.on_login).grid(row=2, column=0, columnspan=2, pady=6)
        self.user_e.focus()

    def on_login(self):
        u = self.user_e.get().strip(); p = self.pass_e.get().strip()
        if not u or not p:
            messagebox.showwarning('Login', 'enter credentials'); return
        self.result = (u, p)
        self.destroy()


class PaymentDialog(tk.Toplevel):
    def __init__(self, parent, amount):
        super().__init__(parent)
        self.title('Payment')
        self.resizable(False, False)
        self.amount = amount
        self.result = None
        ttk.Label(self, text=f'Total amount: ₹{amount:.2f}').grid(row=0, column=0, columnspan=2, padx=6, pady=6)
        ttk.Label(self, text='Method:').grid(row=1, column=0, padx=6, pady=6)
        self.method = tk.StringVar(value='Cash')
        cb = ttk.Combobox(self, values=['Cash','Card','UPI','Split'], textvariable=self.method, state='readonly'); cb.grid(row=1, column=1, padx=6, pady=6)
        ttk.Label(self, text='Details (optional):').grid(row=2, column=0, padx=6, pady=6)
        self.details = ttk.Entry(self); self.details.grid(row=2, column=1, padx=6, pady=6)
        ttk.Button(self, text='Pay', command=self.on_pay).grid(row=3, column=0, padx=6, pady=6)
        ttk.Button(self, text='Cancel', command=self.destroy).grid(row=3, column=1, padx=6, pady=6)

    def on_pay(self):
        m = self.method.get(); d = self.details.get().strip()
        if m == 'Split':
            # simple split: ask for two parts
            a1 = simpledialog.askfloat('Split', 'Amount for method 1', minvalue=0.0, maxvalue=self.amount)
            if a1 is None: return
            m1 = simpledialog.askstring('Split', 'Method 1 (Cash/Card/UPI)');
            a2 = self.amount - a1
            m2 = 'Remaining'
            self.result = {"method": 'Split', "details": {m1: a1, m2: a2}}
        else:
            self.result = {"method": m, "details": d}
        self.destroy()


class AddUserDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add User")
        self.resizable(False, False)
        self.result = None
        self.grab_set()   # make modal

        ttk.Label(self, text="Username:").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        self.u = ttk.Entry(self)
        self.u.grid(row=0, column=1, padx=6, pady=6)

        ttk.Label(self, text="Password:").grid(row=1, column=0, padx=6, pady=6, sticky="w")
        self.p = ttk.Entry(self, show="*")   # ✅ hides password
        self.p.grid(row=1, column=1, padx=6, pady=6)

        ttk.Label(self, text="Role:").grid(row=2, column=0, padx=6, pady=6, sticky="w")
        self.r = ttk.Combobox(self, values=["admin", "cashier"], state="readonly")
        self.r.grid(row=2, column=1, padx=6, pady=6)
        self.r.set("cashier")

        ttk.Button(self, text="Add", command=self.on_add).grid(row=3, column=0, columnspan=2, pady=10)

    def on_add(self):
        u = self.u.get().strip()
        p = self.p.get().strip()
        r = self.r.get().strip()

        if not u or not p or not r:
            messagebox.showwarning("Add User", "All fields are required")
            return

        self.result = (u, p, r)
        self.destroy()

# --- Run POS wrapper ---
def run_pos_app(username, on_logout=None):
    app = RetailPOSApp(username, on_logout=on_logout)
    app.mainloop()

# --- Start app ---
if __name__ == "__main__":
    LandingPage().mainloop()
