import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from contragest.core.database import (
    SessionLocal, CompanyProfile, CompanyEmailConfig, AppConfig,
    CompanyCategory, LegalForm, Activity, GeoSector, Country
)
from contragest.core.i18n import tr
from ttkbootstrap.widgets import DateEntry
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import os
import shutil
import smtplib
import ssl
from contragest.core.status_bar import StatusLabel
from contragest.core.gui_utils import DesignTokens, apply_premium_style, center_window

class MasterDataManagementWindow(ttk.Toplevel):
    """Generic window to manage simple master data lists (Category, LegalForm, etc.)"""
    def __init__(self, parent, model_class, title, callback=None):
        super().__init__(parent)
        self.title(f"Manage {title}")
        self.geometry("500x600")
        self.center_window()
        self.model_class = model_class
        self.callback = callback
        self.session = SessionLocal()
        
        container = ttk.Frame(self, padding=12)
        container.pack(fill=BOTH, expand=YES)
        
        ttk.Label(container, text=f"List of {title}", font=("Space Mono", 10, "bold")).pack(pady=(1, 6))
        
        # Grid
        self.tree = ttk.Treeview(container, columns=("name"), show="headings", height=10)
        self.tree.heading("name", text="Name")
        self.tree.column("name", width=300)
        self.tree.pack(fill=BOTH, expand=YES)
        
        # Form
        form_frame = ttk.Frame(container, padding=6)
        form_frame.pack(fill=X)
        ttk.Label(form_frame, text="Name:").pack(side=LEFT, padx=3)
        self.v_name = ttk.StringVar()
        self.ent_name = ttk.Entry(form_frame, textvariable=self.v_name)
        self.ent_name.pack(side=LEFT, fill=X, expand=YES, padx=3)
        
        # Actions
        btn_frame = ttk.Frame(container, padding=6)
        btn_frame.pack(fill=X)
        
        ttk.Button(btn_frame, text=" ➕ Add ", bootstyle="success", command=self.add_item).pack(side=LEFT, padx=3)
        ttk.Button(btn_frame, text=" 📝 Edit ", bootstyle="info", command=self.edit_item).pack(side=LEFT, padx=3)
        ttk.Button(btn_frame, text=" ➖ Delete ", bootstyle="danger", command=self.delete_item).pack(side=LEFT, padx=3)
        
        self.load_data()
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def center_window(self):
        center_window(self)

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        items = self.session.query(self.model_class).all()
        for i in items:
            self.tree.insert("", END, iid=i.id, values=(i.name,))

    def on_select(self, event):
        sel = self.tree.selection()
        if sel:
            self.v_name.set(self.tree.item(sel[0])['values'][0])

    def add_item(self):
        name = self.v_name.get().strip()
        if not name: return
        
        # Check for duplicates first
        existing = self.session.query(self.model_class).filter_by(name=name).first()
        if existing:
            Messagebox.show_warning(f"'{name}' already exists in the list.", "Duplicate Entry")
            return

        try:
            new_item = self.model_class(name=name)
            self.session.add(new_item)
            self.session.commit()
            self.load_data()
            self.v_name.set("")
            if self.callback: self.callback()
        except Exception as e:
            self.session.rollback()
            Messagebox.show_error(f"Error: {e}", "Database Error")

    def edit_item(self):
        sel = self.tree.selection()
        if not sel: return
        item_id = sel[0]
        name = self.v_name.get().strip()
        if not name: return
        try:
            # Check for duplicates if name changed
            existing = self.session.query(self.model_class).filter(self.model_class.name == name, self.model_class.id != item_id).first()
            if existing:
                Messagebox.show_warning(f"'{name}' already exists.", "Duplicate Entry")
                return

            item = self.session.query(self.model_class).get(item_id)
            if item:
                item.name = name
                self.session.commit()
                self.load_data()
                if self.callback: self.callback()
        except Exception as e:
            self.session.rollback()
            Messagebox.show_error(f"Error: {e}", "Database Error")

    def delete_item(self):
        sel = self.tree.selection()
        if not sel: return
        item_id = sel[0]
        if Messagebox.yesno("Delete this item?", "Confirm"):
            try:
                item = self.session.query(self.model_class).get(item_id)
                if item:
                    self.session.delete(item)
                    self.session.commit()
                    self.load_data()
                    self.v_name.set("")
                    if self.callback: self.callback()
            except Exception as e:
                self.session.rollback()
                Messagebox.show_error(f"Error: {e}", "Database Error")

class CompanyManagerWindow(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent  # Explicit reference to MainWindow
        self.title("🏢  Saisie et M.à.j Société - Premium Edition")
        self.geometry("1400x900")
        self.center_window()
        self.resizable(True, True)
        self.configure(background="#E7E5E4") # Deep AI Violet
        
        self.session = SessionLocal()
        self.current_company_id = None
        self.tabs_dict = {}

        # Design System Constants for Nebula Midnight
        self.COLORS = {
            "BG_MAIN": DesignTokens.BG_APP,
            "BG_CARD": DesignTokens.SURFACE,
            "BG_HOVER": DesignTokens.SECONDARY,
            "PRIMARY": DesignTokens.PRIMARY,
            "SUCCESS": DesignTokens.SUCCESS,
            "TEXT_MAIN": DesignTokens.TEXT,
            "TEXT_MUTED": DesignTokens.TEXT_MUTED
        }

        # Styles
        self._apply_styles()
        
        # Variables
        self.init_variables()
        
        # Add Persistent Status Bar (Bottom) - Reserve before main_container
        user = getattr(parent, 'current_user', None)
        self.status_bar = StatusLabel(self)
        self.status_bar.pack(side=BOTTOM, fill=X)
        self.status_bar.set_status("Managing Company Profile")

        # Build UI layout
        # 1. Top Section: Header & Stats Summary
        self.build_header()
        
        # 2. Middle Section: Searchable Grid (Company List)
        self.build_top_grid()
        
        # 3. Bottom Section: Tabbed Form Cards
        self.build_tabbed_form_area()
        
        # 4. Bottom Action Bar: Global CRUD actions
        self.build_bottom_action_bar()
        
        self.load_grid_data()
        self._load_logo()
        
    def _load_logo(self):
        """Loads company logo from database."""
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if config and config.company_logo_path and os.path.exists(config.company_logo_path):
                img = Image.open(config.company_logo_path)
                img.thumbnail((50, 50))
                self.logo_img = ImageTk.PhotoImage(img)
                if hasattr(self, 'logo_lbl'):
                    self.logo_lbl.config(image=self.logo_img)
        except: pass
        finally: session.close()
        
    def center_window(self):
        center_window(self)
        
    def init_variables(self):
        # General
        self.v_code = ttk.StringVar()
        self.v_raison_sociale = ttk.StringVar()
        self.v_categories = ttk.StringVar()
        self.v_forme_juridique = ttk.StringVar()
        self.v_activite = ttk.StringVar()
        self.v_secteur_geo = ttk.StringVar()
        self.v_representant = ttk.StringVar()
        self.v_qualite = ttk.StringVar()

        # Contact
        self.v_adresse = ttk.StringVar()
        self.v_ville = ttk.StringVar()
        self.v_code_postal = ttk.StringVar()
        self.v_pays = ttk.StringVar()
        self.v_telephone = ttk.StringVar()
        self.v_fax = ttk.StringVar()
        self.v_telex = ttk.StringVar()
        self.v_site_web = ttk.StringVar()

        # Options
        self.v_utilisation_fdcst = ttk.BooleanVar()
        self.v_facturation_coffre = ttk.BooleanVar()
        self.v_controle_nom_pax = ttk.BooleanVar()
        self.v_devise = ttk.StringVar(value="Dinar Tunisien")
        self.v_nationalite = ttk.StringVar(value="Résidents Tunisiens")
        
        self.v_taxe_sejour = ttk.BooleanVar()
        self.v_transaction_taxe = ttk.StringVar(value="Taxe de Séjour")
        
        self.v_bebe_gratuit = ttk.BooleanVar()
        self.v_bebe_gestion = ttk.BooleanVar()
        self.v_bebe_max = ttk.IntVar(value=0)
        
        self.v_enfant_gestion = ttk.BooleanVar()
        self.v_enfant_max = ttk.IntVar(value=0)
        
        self.v_adulte_max = ttk.IntVar(value=0)
        self.v_logo_path = ttk.StringVar()

        # Admin
        self.v_code_tva = ttk.StringVar()
        self.v_police_assurance = ttk.StringVar()
        self.v_code_securite_sociale = ttk.StringVar()
        self.v_capital_social = ttk.StringVar(value="0.000")

        # Configs
        self.v_dossier_hotix = ttk.StringVar()
        
        # lblServeurs
        self.v_ftp_url = ttk.StringVar()
        self.v_ftp_user = ttk.StringVar()
        self.v_ftp_pass = ttk.StringVar()
        
        # Stamp
        self.v_stamp_path = ttk.StringVar()

    def _apply_styles(self):
        s = ttk.Style()
        apply_premium_style(s)
        c = self.COLORS
        
        s.configure("TFrame", background=c["BG_MAIN"])
        s.configure("Company.TFrame", background=c["BG_MAIN"])
        s.configure("Card.TFrame", background=c["BG_CARD"], relief="flat")
        s.configure("Header.TFrame", background=c["BG_MAIN"])
        
        # Typography
        s.configure("Header.TLabel", font=("JetBrains Mono", 14, "bold"), foreground=c["TEXT_MAIN"], background=c["BG_MAIN"])
        s.configure("SubHeader.TLabel", font=("Fira Sans", 9), foreground=c["TEXT_MUTED"], background=c["BG_MAIN"])
        s.configure("FormLabel.TLabel", font=("Fira Sans", 9), foreground=c["TEXT_MUTED"], background=c["BG_CARD"])
        s.configure("CardTitle.TLabel", font=("Fira Sans", 10, "bold"), foreground=c["PRIMARY"], background=c["BG_CARD"])
        
        # Premium Treeview
        s.configure("Treeview", 
                    background=c["BG_MAIN"], 
                    foreground=c["TEXT_MAIN"], 
                    fieldbackground=c["BG_MAIN"], 
                    rowheight=28,
                    font=("Fira Sans", 9),
                    borderwidth=0)
        s.configure("Treeview.Heading", 
                    background=c["BG_CARD"], 
                    foreground=c["TEXT_MAIN"], 
                    font=("Fira Sans", 9, "bold"),
                    relief="flat")
        s.map("Treeview", 
              background=[("selected", c["BG_HOVER"])], 
              foreground=[("selected", c["PRIMARY"])])

        # Modern Custom Tab Button Style
        s.configure("Tab.TButton", 
                    font=("Fira Sans", 9, "bold"), 
                    padding=(9, 4),
                    background=c["BG_MAIN"],
                    foreground=c["TEXT_MUTED"])
        s.map("Tab.TButton",
              foreground=[("active", c["TEXT_MAIN"]), ("selected", c["PRIMARY"])],
              background=[("active", c["BG_HOVER"])])
              
        # Primary Action Button
        s.configure("Action.TButton", font=("Fira Sans", 9, "bold"), padding=(12, 6))

    def build_header(self):
        header = ttk.Frame(self, style="Header.TFrame", padding=(12, 9))
        header.pack(fill=X)
        
        title_frame = ttk.Frame(header, style="Header.TFrame")
        title_frame.pack(side=LEFT)
        
        self.logo_lbl = ttk.Label(title_frame, style="Header.TLabel")
        self.logo_lbl.pack(side=LEFT, padx=(1, 9))
        
        text_f = ttk.Frame(title_frame, style="Header.TFrame")
        text_f.pack(side=LEFT)
        
        ttk.Label(text_f, text="COMPANY PROFILE", style="Header.TLabel").pack(anchor=W)
        ttk.Label(title_frame, text="Modern Master Data Governance & Identity Management", style="SubHeader.TLabel").pack(anchor=W)
        
        # Quick stats/info on the right
        stats_frame = ttk.Frame(header, style="Header.TFrame")
        stats_frame.pack(side=RIGHT)
        self.lbl_count = ttk.Label(stats_frame, text="0 COMPANIES LOADED", font=("JetBrains Mono", 9), 
                                   foreground=self.COLORS["SUCCESS"], background=self.COLORS["BG_MAIN"])
        self.lbl_count.pack(side=RIGHT, padx=12)

    def build_top_grid(self):
        grid_container = ttk.Frame(self, padding=(6, 1))
        grid_container.pack(fill=BOTH, expand=YES)
        
        grid_inner = ttk.Frame(grid_container, bootstyle="secondary", padding=1)
        grid_inner.pack(fill=BOTH, expand=YES)
        
        columns = (
            "code", "raison_sociale", "responsable", "contacts", "site_web", 
            "email", "adresse", "code_postal", "ville", "telephone", "fax", 
            "telex", "bebe_gratuit", "utilisation_fi", "forme_juridique", 
            "code_tva", "categories", "pays", "lblcodepays", "secteur_geo", "devise"
        )
        self.tree = ttk.Treeview(grid_inner, columns=columns, show="headings", selectmode="browse")
        
        vsb = ttk.Scrollbar(grid_inner, orient=VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(grid_inner, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.pack(fill=BOTH, expand=YES)
        
        # Headings (Custom Widths)
        col_configs = {
            "code": (80, "Code"),
            "raison_sociale": (220, "Raison Sociale"),
            "responsable": (150, "Responsable"),
            "ville": (120, "Ville"),
            "telephone": (120, "Téléphone"),
            "email": (180, "Email"),
            "categories": (120, "Catégories"),
            "secteur_geo": (150, "Secteur")
        }
        
        for col in columns:
            name = col_configs.get(col, (100, col.replace("_", " ").title()))[1]
            width = col_configs.get(col, (100, ""))[0]
            self.tree.heading(col, text=name.upper())
            self.tree.column(col, width=width, anchor=W)
            
        self.tree.bind("<<TreeviewSelect>>", self.on_grid_select)
        
        # Hover effect on Treeview
        self.tree.bind("<Motion>", self._on_tree_hover)

    def _on_tree_hover(self, event):
        item = self.tree.identify_row(event.y)
        if hasattr(self, '_last_hovered_item') and self._last_hovered_item != item:
             # Tkinter Treeview doesn't have individual row hover tags by default easily
             # but we can simulate it or just use selection highlight. 
             # For now, we rely on standard selection visual.
             pass
        self._last_hovered_item = item

    def build_tabbed_form_area(self):
        # We create a container with a navigation sidebar and a content card
        self.form_area = ttk.Frame(self, padding=(6, 3))
        self.form_area.pack(fill=X, expand=False)
        
        # Horizontal Tab Navigation (Pills)
        nav_container = ttk.Frame(self.form_area, padding=(1, 1, 1, 6))
        nav_container.pack(fill=X)
        
        self.tab_buttons = {}
        tabs = [
            ("Général", "📋"), ("Contact(s)", "📞"), ("Option(s)", "⚙️"), 
            ("Administratif", "⚖️"), ("Messagerie", "📧"), ("Cloud App", "☁️"), 
            ("Serveurs", "🖥️"), ("Stamp", "🎨")
        ]
        
        for name, icon in tabs:
            btn = ttk.Button(nav_container, text=f"{icon}  {name.upper()}", style="Tab.TButton",
                             command=lambda n=name: self.show_tab(n))
            btn.pack(side=LEFT, padx=(1, 3))
            self.tab_buttons[name] = btn
            
            # Hover animations
            btn.bind("<Enter>", lambda e, b=btn: self._animate_tab_hover(b, True))
            btn.bind("<Leave>", lambda e, b=btn: self._animate_tab_hover(b, False))

        # Main Card Content
        self.content_card = ttk.Frame(self.form_area, style="Card.TFrame", padding=15)
        self.content_card.pack(fill=BOTH, expand=YES)
        
        self.tabs_dict = {
            "Général": self.build_general_tab(),
            "Contact(s)": self.build_contact_tab(),
            "Option(s)": self.build_option_tab(),
            "Administratif": self.build_admin_tab(),
            "Messagerie": self.build_messagerie_tab(),
            "Cloud App": self.build_app_tab(),
            "Serveurs": self.build_serveurs_tab(),
            "Stamp": self.build_stamp_tab(),
        }
        
        self.show_tab("Général")

    def _animate_tab_hover(self, button, entering):
        if entering:
            button.configure(style="Tab.TButton") # Transition mapping handles it
        else:
            button.configure(style="Tab.TButton")

    def show_tab(self, tab_name):
        for name, frame in self.tabs_dict.items():
            if frame:
                frame.pack_forget()
            btn = self.tab_buttons.get(name)
            if btn:
                # Highlight active button
                if name == tab_name:
                    btn.configure(bootstyle="primary")
                else:
                    btn.configure(bootstyle="link")
        
        if tab_name in self.tabs_dict:
            self.tabs_dict[tab_name].pack(fill=BOTH, expand=YES)

    def build_bottom_action_bar(self):
        action_bar = ttk.Frame(self, padding=(12, 6))
        action_bar.pack(fill=X, side=BOTTOM)
        
        # Left Side: CRUD Toolbar
        toolbar = ttk.Frame(action_bar)
        toolbar.pack(side=LEFT)
        
        # Stylish Action Group
        group = ttk.Frame(toolbar, bootstyle="secondary", padding=1)
        group.pack(side=LEFT)
        
        actions = [
            (" ➕ ADD ", "success", self.cmd_add),
            (" 📝 EDIT ", "info", self.cmd_edit),
            (" ➖ DELETE ", "danger", self.cmd_delete),
        ]
        
        for text, style, cmd in actions:
            ttk.Button(group, text=text, bootstyle=f"{style}-toolbutton", padding=(9, 4), command=cmd).pack(side=LEFT)
            
        ttk.Button(toolbar, text=" 🔄 SYNC ", bootstyle="secondary-outline", padding=(9, 4), command=self.load_grid_data).pack(side=LEFT, padx=6)
        
        # Right Side: Navigation & Save
        right_panel = ttk.Frame(action_bar)
        right_panel.pack(side=RIGHT)
        
        nav_group = ttk.Frame(right_panel, bootstyle="secondary", padding=1)
        nav_group.pack(side=LEFT, padx=12)
        
        navs = [("⏪", self.nav_first), ("◀", self.nav_prev), ("▶", self.nav_next), ("⏩", self.nav_last)]
        for icon, cmd in navs:
            ttk.Button(nav_group, text=f" {icon} ", bootstyle="secondary-toolbutton", command=cmd).pack(side=LEFT)
            
        ttk.Button(right_panel, text="💾 SAVE PROFILE", bootstyle="success", padding=(12, 6), command=self.save_company).pack(side=LEFT, padx=3)
        ttk.Button(right_panel, text="❌ CLOSE", bootstyle="secondary-outline", padding=(12, 6), command=self.destroy).pack(side=LEFT)

    def add_form_row(self, parent, label_text, variable, width=40):
        row_frame = ttk.Frame(parent, style="Card.TFrame", padding=(1, 3))
        row_frame.pack(fill=X)
        
        ttk.Label(row_frame, text=label_text.upper(), style="FormLabel.TLabel", width=22).pack(side=LEFT)
        ttk.Entry(row_frame, textvariable=variable, width=width).pack(side=LEFT, fill=X, expand=YES)

    def _add_combo_with_manager(self, parent, label_text, variable, model_class, values):
        row_frame = ttk.Frame(parent, style="Card.TFrame", padding=(1, 3))
        row_frame.pack(fill=X)
        
        ttk.Label(row_frame, text=label_text.upper(), style="FormLabel.TLabel", width=22).pack(side=LEFT)
        
        container = ttk.Frame(row_frame, style="Card.TFrame")
        container.pack(side=LEFT, fill=X, expand=YES)
        
        # Normalize key for attribute reference
        key = label_text.replace(" ", "_").replace("(", "").replace(")", "").replace("é", "e").lower()
        
        cb = ttk.Combobox(container, textvariable=variable, width=32, values=values)
        cb.pack(side=LEFT, fill=X, expand=YES, padx=(1, 3))
        setattr(self, f"cb_{key}", cb)
        
        btn = ttk.Button(container, text="➕", bootstyle="info-outline", width=3,
                         command=lambda: MasterDataManagementWindow(self, model_class, label_text, lambda: self._refresh_combo(key, model_class)))
        btn.pack(side=LEFT)

    def _refresh_combo(self, key, model_class):
        try:
            # Create a fresh session to get latest data
            session = SessionLocal()
            items = [i.name for i in session.query(model_class).all()]
            session.close()
            
            cb = getattr(self, f"cb_{key}", None)
            if cb:
                cb.config(values=items)
        except Exception as e:
            print(f"Error refreshing combo {key}: {e}")

    # --- TAB BUILDERS --- #
    def build_general_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        
        left_col = ttk.Frame(frame, style="Card.TFrame")
        left_col.pack(side=LEFT, fill=BOTH, expand=YES, padx=(1, 12))
        
        ttk.Label(left_col, text="PRIMARY IDENTITY", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        self.add_form_row(left_col, "Unique Entity Code", self.v_code)
        self.add_form_row(left_col, "Legal Business Name", self.v_raison_sociale)
        
        # Categorization Group
        cat_frame = ttk.Frame(left_col, style="Card.TFrame", padding=(1, 6))
        cat_frame.pack(fill=X)
        
        self._add_combo_with_manager(cat_frame, "Entity Category", self.v_categories, CompanyCategory, [])
        self._add_combo_with_manager(cat_frame, "Legal Policy Form", self.v_forme_juridique, LegalForm, [])
        self._add_combo_with_manager(cat_frame, "Primary Activity", self.v_activite, Activity, [])

        right_col = ttk.Frame(frame, style="Card.TFrame")
        right_col.pack(side=LEFT, fill=BOTH, expand=YES)
        
        ttk.Label(right_col, text="GOVERNANCE & CREATION", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        self._add_combo_with_manager(right_col, "Geographical Sector", self.v_secteur_geo, GeoSector, [])
        
        row_dt = ttk.Frame(right_col, style="Card.TFrame", padding=(1, 3))
        row_dt.pack(fill=X)
        ttk.Label(row_dt, text="CREATION DATE".upper(), style="FormLabel.TLabel", width=22).pack(side=LEFT)
        self.date_picker = DateEntry(row_dt, width=35)
        self.date_picker.pack(side=LEFT, fill=X, expand=YES)
        
        self.add_form_row(right_col, "Legal Representative", self.v_representant)
        self.add_form_row(right_col, "Official Quality", self.v_qualite)
        
        # Initial refresh of combos
        self._refresh_all_combos()
        return frame

    def _refresh_all_combos(self):
        # Batch refresh to avoid multiple session openings
        items_map = {
            "entity_category": CompanyCategory,
            "legal_policy_form": LegalForm,
            "primary_activity": Activity,
            "geographical_sector": GeoSector,
            "pays": Country
        }
        for key, model in items_map.items():
            self._refresh_combo(key, model)

    def build_contact_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        
        left_col = ttk.Frame(frame, style="Card.TFrame")
        left_col.pack(side=LEFT, fill=BOTH, expand=YES, padx=(1, 12))
        ttk.Label(left_col, text="LOCATION & ADDRESS", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        self.add_form_row(left_col, "Physical Address", self.v_adresse)
        self.add_form_row(left_col, "City / Urban Area", self.v_ville)
        
        row_cp = ttk.Frame(left_col, style="Card.TFrame", padding=(1, 3))
        row_cp.pack(fill=X)
        ttk.Label(row_cp, text="POSTAL CODE", style="FormLabel.TLabel", width=22).pack(side=LEFT)
        ttk.Spinbox(row_cp, textvariable=self.v_code_postal, width=15, from_=0, to=99999).pack(side=LEFT)
        
        self._add_combo_with_manager(left_col, "Country / Region", self.v_pays, Country, [])

        right_col = ttk.Frame(frame, style="Card.TFrame")
        right_col.pack(side=LEFT, fill=BOTH, expand=YES)
        ttk.Label(right_col, text="CONTACT CHANNELS", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        self.add_form_row(right_col, "Phone Number", self.v_telephone)
        self.add_form_row(right_col, "Fax Line", self.v_fax)
        self.add_form_row(right_col, "Telex ID", self.v_telex)
        self.add_form_row(right_col, "Official Website", self.v_site_web)

        return frame

    def build_option_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        
        left_col = ttk.Frame(frame, style="Card.TFrame")
        left_col.pack(side=LEFT, fill=BOTH, expand=YES, padx=(1, 12))
        ttk.Label(left_col, text="BILLING & REGULATORY", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        ttk.Checkbutton(left_col, text="Utilisation FDCST", variable=self.v_utilisation_fdcst, bootstyle="round-toggle").pack(anchor=W, pady=3)
        ttk.Checkbutton(left_col, text="Facturation Coffre /Jour", variable=self.v_facturation_coffre, bootstyle="round-toggle").pack(anchor=W, pady=3)
        ttk.Checkbutton(left_col, text="Contrôle Nom PAX", variable=self.v_controle_nom_pax, bootstyle="round-toggle").pack(anchor=W, pady=3)
        
        self.add_form_row(left_col, "Operational Currency", self.v_devise)
        self.add_form_row(left_col, "Default Nationality", self.v_nationalite)

        mid_col = ttk.Frame(frame, style="Card.TFrame")
        mid_col.pack(side=LEFT, fill=BOTH, expand=YES, padx=6)
        ttk.Label(mid_col, text="STAY TAX & FAMILY POLICY", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        taxe_frame = ttk.Frame(mid_col, style="Card.TFrame")
        taxe_frame.pack(fill=X, pady=3)
        ttk.Checkbutton(taxe_frame, text="Active Stay Tax", variable=self.v_taxe_sejour, bootstyle="success-square-toggle").pack(anchor=W)
        self.add_form_row(mid_col, "Tax Transaction ID", self.v_transaction_taxe)
        
        # Age-based Management group
        age_frame = ttk.Frame(mid_col, style="Card.TFrame", padding=(1, 6))
        age_frame.pack(fill=X)
        
        for label, bool_var, max_var in [("Infants (0-2)", self.v_bebe_gestion, self.v_bebe_max),
                                        ("Children (2-12)", self.v_enfant_gestion, self.v_enfant_max),
                                        ("Adults (12+)", None, self.v_adulte_max)]:
            row = ttk.Frame(age_frame, style="Card.TFrame", padding=1)
            row.pack(fill=X)
            if bool_var:
                 ttk.Checkbutton(row, text=label, variable=bool_var, width=15).pack(side=LEFT)
            else:
                 ttk.Label(row, text=label, style="FormLabel.TLabel", width=17).pack(side=LEFT)
            
            ttk.Label(row, text="Max Occupancy:", style="FormLabel.TLabel").pack(side=LEFT, padx=3)
            ttk.Spinbox(row, textvariable=max_var, width=5, from_=0, to=99).pack(side=LEFT)

        right_col = ttk.Frame(frame, style="Card.TFrame")
        right_col.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(12, 1))
        ttk.Label(right_col, text="CORPORATE ASSETS", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        self.lbl_logo = ttk.Label(right_col, text="[ NO LOGO ]", font=("JetBrains Mono", 9), anchor=CENTER, padding=12)
        self.lbl_logo.pack(fill=BOTH, expand=YES)
        
        btn_box = ttk.Frame(right_col, style="Card.TFrame")
        btn_box.pack(fill=X, pady=6)
        ttk.Button(btn_box, text=" 📁 UPLOAD ", bootstyle="secondary-outline", command=self.upload_logo).pack(side=LEFT, expand=YES, padx=3)
        ttk.Button(btn_box, text=" ❌ CLEAR ", bootstyle="danger-outline", command=lambda: [self.v_logo_path.set(""), self.refresh_logo_display()]).pack(side=LEFT, expand=YES, padx=3)

        return frame

    def build_admin_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        ttk.Label(frame, text="ADMINISTRATIVE & FINANCIALS", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        left_col = ttk.Frame(frame, style="Card.TFrame")
        left_col.pack(side=LEFT, fill=BOTH, expand=YES)
        
        self.add_form_row(left_col, "VAT ID Code (TVA)", self.v_code_tva)
        self.add_form_row(left_col, "Assurance Policy", self.v_police_assurance)
        
        right_col = ttk.Frame(frame, style="Card.TFrame")
        right_col.pack(side=LEFT, fill=BOTH, expand=YES)
        self.add_form_row(right_col, "Social Security ID", self.v_code_securite_sociale)
        
        row_cap = ttk.Frame(right_col, style="Card.TFrame", padding=(1, 3))
        row_cap.pack(fill=X)
        ttk.Label(row_cap, text="SOCIAL CAPITAL", style="FormLabel.TLabel", width=22).pack(side=LEFT)
        ttk.Spinbox(row_cap, textvariable=self.v_capital_social, width=20, format="%.3f").pack(side=LEFT)
        
        return frame

    def build_messagerie_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        
        ttk.Label(frame, text="EMAIL CHANNEL CONFIGURATION", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        cols = ("id", "type", "email", "login", "password", "smtp", "port", "ssl", "auth")
        heads = ["ID", "CHANNEL TYPE", "EMAIL ADDRESS", "USERNAME", "CREDENTIALS", "SMTP HOST", "PORT", "SECURE", "AUTH"]
        
        tree_container = ttk.Frame(frame, bootstyle="secondary", padding=1)
        tree_container.pack(fill=BOTH, expand=YES)
        
        self.mail_tree = ttk.Treeview(tree_container, columns=cols, show="headings", height=8)
        for c, h in zip(cols, heads):
            self.mail_tree.heading(c, text=h)
            if c == "id":
                self.mail_tree.column(c, width=0, stretch=NO)
            else:
                self.mail_tree.column(c, width=120, anchor=W)

        self.mail_tree.pack(fill=BOTH, expand=YES)
        self.mail_tree.bind("<Double-1>", self.on_mail_double_click)
        return frame

    def build_app_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        ttk.Label(frame, text="CORE APPLICATION SUITE", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        row = ttk.Frame(frame, style="Card.TFrame")
        row.pack(fill=X)
        ttk.Label(row, text="ERP ROOT DIRECTORY", style="FormLabel.TLabel", width=22).pack(side=LEFT)
        ttk.Entry(row, textvariable=self.v_dossier_hotix, width=50).pack(side=LEFT, fill=X, expand=YES)
        ttk.Button(row, text=" 📁 BROWSE ", bootstyle="secondary-outline").pack(side=LEFT, padx=6)
        return frame

    def build_serveurs_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        ttk.Label(frame, text="TELEMETRY & FTP CONNECTIVITY", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        left_col = ttk.Frame(frame, style="Card.TFrame")
        left_col.pack(side=LEFT, fill=BOTH, expand=YES)
        self.add_form_row(left_col, "Remote Server URL", self.v_ftp_url)
        self.add_form_row(left_col, "Service Username", self.v_ftp_user)
        
        right_col = ttk.Frame(frame, style="Card.TFrame")
        right_col.pack(side=LEFT, fill=BOTH, expand=YES)
        self.add_form_row(right_col, "Encrypted Access Token", self.v_ftp_pass)
        return frame

    def build_stamp_tab(self):
        frame = ttk.Frame(self.content_card, style="Card.TFrame")
        ttk.Label(frame, text="CORPORATE DIGITAL STAMP", style="CardTitle.TLabel").pack(anchor=W, pady=(1, 9))
        
        self.lbl_stamp = ttk.Label(frame, text="[ NO STAMP ]", font=("JetBrains Mono", 9), anchor=CENTER, padding=12)
        self.lbl_stamp.pack(fill=BOTH, expand=YES)
        
        btn_box = ttk.Frame(frame, style="Card.TFrame")
        btn_box.pack(fill=X, pady=6)
        ttk.Button(btn_box, text=" 📁 UPLOAD ", bootstyle="secondary-outline", command=self.upload_stamp).pack(side=LEFT, expand=YES, padx=3)
        ttk.Button(btn_box, text=" ❌ CLEAR ", bootstyle="danger-outline", command=lambda: [self.v_stamp_path.set(""), self.refresh_stamp_display()]).pack(side=LEFT, expand=YES, padx=3)

        return frame

    # --- BEHAVIOR --- #
    def upload_logo(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif")])
        if path:
            self.v_logo_path.set(path)
            self.refresh_logo_display()

    def refresh_logo_display(self):
        path = self.v_logo_path.get()
        if path:
            try:
                img = Image.open(path)
                img.thumbnail((150, 100))
                self.photo = ImageTk.PhotoImage(img)
                self.lbl_logo.config(image=self.photo, text="")
            except Exception as e:
                self.lbl_logo.config(text="[Error loading image]", image='')
        else:
             self.lbl_logo.config(text="[No Logo Selected]", image='')

    def upload_stamp(self):
        path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.gif")])
        if path:
            self.v_stamp_path.set(path)
            self.refresh_stamp_display()

    def refresh_stamp_display(self):
        path = self.v_stamp_path.get()
        if hasattr(self, 'lbl_stamp'):
            if path:
                try:
                    img = Image.open(path)
                    img.thumbnail((150, 100))
                    self.photo_stamp = ImageTk.PhotoImage(img)
                    self.lbl_stamp.config(image=self.photo_stamp, text="")
                except Exception as e:
                    self.lbl_stamp.config(text="[Error loading image]", image='')
            else:
                 self.lbl_stamp.config(text="[No Stamp Selected]", image='')

    def load_grid_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        self.session.expire_all()
        profiles = self.session.query(CompanyProfile).all()
        for p in profiles:
            values = (
                p.code, p.raison_sociale, p.responsable, p.contact, p.site_web,
                p.email, p.adresse, p.code_postal, p.ville, p.telephone, p.fax,
                p.telex, "✔️" if p.bebe_gratuit else "❌", "✔️" if p.utilisation_fdcst else "❌", 
                p.forme_juridique, p.code_tva, p.categories, p.pays, p.lbl_code_pays, 
                p.secteur_geographique, p.devise
            )
            self.tree.insert("", END, values=values)
            
        count = len(profiles)
        self.lbl_count.configure(text=f"{count} COMPANIES LOADED")
            
    def on_grid_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return
            
        item = self.tree.item(selected[0])
        code = str(item['values'][0])
        p = self.session.query(CompanyProfile).filter_by(code=code).first()
        if not p: return
        
        self.current_company_id = p.id
        
        # General & Others
        self.v_code.set(p.code)
        self.v_raison_sociale.set(p.raison_sociale)
        self.v_categories.set(p.categories or "")
        self.v_forme_juridique.set(p.forme_juridique or "")
        self.v_activite.set(p.activite or "")
        self.v_secteur_geo.set(p.secteur_geographique or "")
        self.v_representant.set(p.representant_juridique or "")
        self.v_qualite.set(p.qualite or "")

        if p.date_creation:
            self.date_picker.entry.delete(0, END)
            self.date_picker.entry.insert(0, p.date_creation.strftime("%Y-%m-%d"))

        # Contact
        self.v_adresse.set(p.adresse or "")
        self.v_ville.set(p.ville or "")
        self.v_code_postal.set(p.code_postal or "")
        self.v_pays.set(p.pays or "")
        self.v_telephone.set(p.telephone or "")
        self.v_fax.set(p.fax or "")
        self.v_telex.set(p.telex or "")
        self.v_site_web.set(p.site_web or "")

        # Option
        self.v_utilisation_fdcst.set(p.utilisation_fdcst or False)
        self.v_facturation_coffre.set(p.facturation_coffre or False)
        self.v_controle_nom_pax.set(p.controle_nom_pax or False)
        self.v_devise.set(p.devise or "Dinar Tunisien")
        self.v_nationalite.set(p.nationalite or "Résidents Tunisiens")
        
        self.v_taxe_sejour.set(p.taxe_sejour or False)
        self.v_transaction_taxe.set(p.transaction_taxe or "Taxe de Séjour")
        
        self.v_bebe_gratuit.set(p.bebe_gratuit or False)
        self.v_bebe_gestion.set(p.bebe_gestion or False)
        self.v_bebe_max.set(p.bebe_max or 0)
        
        self.v_enfant_gestion.set(p.enfant_gestion or False)
        self.v_enfant_max.set(p.enfant_max or 0)
        self.v_adulte_max.set(p.adulte_max or 0)
        
        self.v_logo_path.set(p.logo_path or "")
        self.refresh_logo_display()

        # Admin
        self.v_code_tva.set(p.code_tva or "")
        self.v_police_assurance.set(p.police_assurance or "")
        self.v_code_securite_sociale.set(p.code_securite_sociale or "")
        self.v_capital_social.set(p.capital_social or "0.000")

        # Configs
        self.v_dossier_hotix.set(p.dossier_hotix or "")
        
        # lblServeurs
        self.v_ftp_url.set(p.ftp_url or "")
        self.v_ftp_user.set(p.ftp_utilisateur or "")
        self.v_ftp_pass.set(p.ftp_mot_de_passe or "")
        
        # Stamp
        self.v_stamp_path.set(p.stamp_path or "")
        self.refresh_stamp_display()
        
        # Render Emails
        self.load_emails()

    def load_emails(self):
        for item in self.mail_tree.get_children():
            self.mail_tree.delete(item)
            
        if not self.current_company_id:
            return
            
        configs = self.session.query(CompanyEmailConfig).filter_by(company_id=self.current_company_id).all()
        # Seed dummy config if empty
        if not configs:
            dummy = CompanyEmailConfig(company_id=self.current_company_id, type="Mail Reservation", port=0)
            dummy2 = CompanyEmailConfig(company_id=self.current_company_id, type="Mail Satisfaction", port=0)
            self.session.add(dummy)
            self.session.add(dummy2)
            self.session.commit()
            configs = [dummy, dummy2]
            
        for c in configs:
            v = (c.id, c.type, c.email or "", c.login or "", c.password or "", c.smtp or "", c.port or 0, "☑" if c.ssl else "☐", "☑" if c.authentifier else "☐")
            self.mail_tree.insert("", END, values=v)

    def on_mail_double_click(self, event):
        item_id = self.mail_tree.identify_row(event.y)
        if not item_id: return
        
        values = self.mail_tree.item(item_id, 'values')
        # values: (id, type, email, login, password, smtp, port, ssl, auth)
        
        dlg = ttk.Toplevel(self)
        dlg.title(f"Edit {values[1]}")
        dlg.geometry("450x550")
        dlg.transient(self)
        dlg.grab_set()
        center_window(dlg)
        
        content = ttk.Frame(dlg, padding=20)
        content.pack(fill=BOTH, expand=YES)
        
        vars = {
            "email": ttk.StringVar(value=values[2]),
            "login": ttk.StringVar(value=values[3]),
            "password": ttk.StringVar(value=values[4]),
            "smtp": ttk.StringVar(value=values[5]),
            "port": ttk.IntVar(value=int(values[6])),
            "ssl": ttk.BooleanVar(value=(values[7] == "☑")),
            "auth": ttk.BooleanVar(value=(values[8] == "☑"))
        }
        
        def add_field(label, var):
            row = ttk.Frame(content)
            row.pack(fill=X, pady=6)
            ttk.Label(row, text=label, width=15).pack(side=LEFT)
            if isinstance(var, ttk.BooleanVar):
                ttk.Checkbutton(row, variable=var, bootstyle="round-toggle").pack(side=LEFT)
            else:
                ttk.Entry(row, textvariable=var).pack(side=LEFT, fill=X, expand=YES)

        add_field("Email Address", vars["email"])
        add_field("Username", vars["login"])
        add_field("Password", vars["password"])
        add_field("SMTP Host", vars["smtp"])
        add_field("Port", vars["port"])
        add_field("Use SSL/TLS", vars["ssl"])
        add_field("Require Auth", vars["auth"])
        
        def test_connection():
            host = vars["smtp"].get().strip()
            port = vars["port"].get()
            user = vars["login"].get().strip()
            pwd = vars["password"].get().strip()
            use_ssl = vars["ssl"].get()
            require_auth = vars["auth"].get()
            
            if not host:
                Messagebox.show_warning("Veuillez saisir un hôte SMTP.", "Données manquantes", parent=dlg)
                return
                
            try:
                # Show a temporary "checking..." state could be nice but let's keep it simple first
                if use_ssl:
                    context = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(host, port, context=context, timeout=15)
                else:
                    server = smtplib.SMTP(host, port, timeout=15)
                    try:
                        # Try STARTTLS if port is typical for it or if server suggests it
                        server.starttls()
                    except:
                        pass 
                
                if require_auth:
                    server.login(user, pwd)
                    
                server.quit()
                Messagebox.show_info("Connexion SMTP réussie !", "Succès", parent=dlg)
            except Exception as e:
                Messagebox.show_error(f"Échec de la connexion :\n{str(e)}", "Erreur de Vérification", parent=dlg)

        def save_dlg():
            try:
                self.mail_tree.item(item_id, values=(
                    values[0],
                    values[1],
                    vars["email"].get(),
                    vars["login"].get(),
                    vars["password"].get(),
                    vars["smtp"].get(),
                    vars["port"].get(),
                    "☑" if vars["ssl"].get() else "☐",
                    "☑" if vars["auth"].get() else "☐"
                ))
                dlg.destroy()
            except Exception as e:
                Messagebox.show_error(f"Error saving: {e}", "Error", parent=dlg)

        ttk.Button(content, text=" ⚡ TEST CONNECTION ", bootstyle="warning", command=test_connection).pack(fill=X, pady=(20, 0))
        ttk.Button(content, text=" APPLY CHANGES ", bootstyle="primary", command=save_dlg).pack(fill=X, pady=10)
        ttk.Button(content, text=" CANCEL ", bootstyle="secondary-link", command=dlg.destroy).pack(fill=X)

    def cmd_add(self):
        self.tree.selection_remove(self.tree.selection())
        self.current_company_id = None
        
        # General
        self.v_code.set("")
        self.v_raison_sociale.set("")
        self.v_categories.set("")
        self.v_forme_juridique.set("")
        self.v_activite.set("")
        self.v_secteur_geo.set("")
        self.v_representant.set("")
        self.v_qualite.set("")
        self.date_picker.entry.delete(0, END)
        
        # Contact
        self.v_adresse.set("")
        self.v_ville.set("")
        self.v_code_postal.set("")
        self.v_pays.set("")
        self.v_telephone.set("")
        self.v_fax.set("")
        self.v_telex.set("")
        self.v_site_web.set("")
        
        # Options
        self.v_utilisation_fdcst.set(False)
        self.v_facturation_coffre.set(False)
        self.v_controle_nom_pax.set(False)
        self.v_devise.set("Dinar Tunisien")
        self.v_nationalite.set("Résidents Tunisiens")
        self.v_taxe_sejour.set(False)
        self.v_transaction_taxe.set("Taxe de Séjour")
        self.v_bebe_gratuit.set(False)
        self.v_bebe_gestion.set(False)
        self.v_bebe_max.set(0)
        self.v_enfant_gestion.set(False)
        self.v_enfant_max.set(0)
        self.v_adulte_max.set(0)
        
        # Admin
        self.v_code_tva.set("")
        self.v_police_assurance.set("")
        self.v_code_securite_sociale.set("")
        self.v_capital_social.set("0.000")
        
        # App / Serveurs
        self.v_dossier_hotix.set("")
        self.v_ftp_url.set("")
        self.v_ftp_user.set("")
        self.v_ftp_pass.set("")
        
        # Images
        self.v_logo_path.set("")
        self.v_stamp_path.set("")
        self.refresh_logo_display()
        self.refresh_stamp_display()
        
        # Emails
        for item in self.mail_tree.get_children():
            self.mail_tree.delete(item)
        
        self.show_tab("Général")
    
    def cmd_edit(self):
        """Switch to edit mode for the current record."""
        if not self.current_company_id:
            Messagebox.show_warning("Veuillez sélectionner un enregistrement à modifier.", "Aucune sélection")
            return
        self.show_tab("Général")
        # Focus the Raison Sociale field for immediate editing
        for widget in self.winfo_children():
            self._focus_first_entry(widget)
            break
    
    def _focus_first_entry(self, parent):
        """Recursively find and focus the first Entry widget."""
        for child in parent.winfo_children():
            if isinstance(child, ttk.Entry):
                child.focus_set()
                child.select_range(0, END)
                return True
            if self._focus_first_entry(child):
                return True
        return False
            
    def cmd_delete(self):
        if not self.current_company_id:
            Messagebox.show_warning("Veuillez sélectionner un enregistrement à supprimer.", "Aucune sélection")
            return
        response = Messagebox.yesno("Êtes-vous sûr de vouloir supprimer ce profil ?", "Confirmer la suppression")
        if response == "Yes":
            p = self.session.get(CompanyProfile, self.current_company_id)
            if p:
                self.session.delete(p)
                self.session.commit()
                self.cmd_add()
                self.load_grid_data()
                
    def nav_first(self):
        items = self.tree.get_children()
        if items:
            self.tree.selection_set(items[0])
            self.tree.see(items[0])
        
    def nav_prev(self):
        sel = self.tree.selection()
        if sel:
            prev_item = self.tree.prev(sel[0])
            if prev_item:
                self.tree.selection_set(prev_item)
                self.tree.see(prev_item)
            
    def nav_next(self):
        sel = self.tree.selection()
        if sel:
            next_item = self.tree.next(sel[0])
            if next_item:
                self.tree.selection_set(next_item)
                self.tree.see(next_item)
            
    def nav_last(self):
        items = self.tree.get_children()
        if items:
            self.tree.selection_set(items[-1])
            self.tree.see(items[-1])

    def save_company(self):
        code = self.v_code.get().strip()
        rs = self.v_raison_sociale.get().strip()
        
        if not code or not rs:
            Messagebox.show_warning("Code et Raison Sociale sont obligatoires.", "Champs manquants")
            return
        
        # Use ID-based lookup for existing records (allows code changes)
        if self.current_company_id:
            p = self.session.get(CompanyProfile, self.current_company_id)
            if not p:
                Messagebox.show_warning("Enregistrement introuvable.", "Erreur")
                return
            p.code = code  # Allow code update
        else:
            # New record: check for duplicate code
            existing = self.session.query(CompanyProfile).filter_by(code=code).first()
            if existing:
                Messagebox.show_warning(f"Le code '{code}' existe déjà.", "Doublon")
                return
            p = CompanyProfile(code=code)
            self.session.add(p)
            
        # General
        p.raison_sociale = rs
        p.categories = self.v_categories.get()
        p.forme_juridique = self.v_forme_juridique.get()
        p.activite = self.v_activite.get()
        p.secteur_geographique = self.v_secteur_geo.get()
        p.representant_juridique = self.v_representant.get()
        p.qualite = self.v_qualite.get()
        dt_str = self.date_picker.entry.get().strip()
        if dt_str:
            for fmt in ("%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
                try:
                    p.date_creation = datetime.strptime(dt_str, fmt).date()
                    break
                except ValueError:
                    continue

        # Contact
        p.adresse = self.v_adresse.get()
        p.ville = self.v_ville.get()
        p.code_postal = self.v_code_postal.get()
        p.pays = self.v_pays.get()
        p.telephone = self.v_telephone.get()
        p.fax = self.v_fax.get()
        p.telex = self.v_telex.get()
        p.site_web = self.v_site_web.get()

        # Options
        p.utilisation_fdcst = self.v_utilisation_fdcst.get()
        p.facturation_coffre = self.v_facturation_coffre.get()
        p.controle_nom_pax = self.v_controle_nom_pax.get()
        p.devise = self.v_devise.get()
        p.nationalite = self.v_nationalite.get()
        p.taxe_sejour = self.v_taxe_sejour.get()
        p.transaction_taxe = self.v_transaction_taxe.get()
        p.bebe_gratuit = self.v_bebe_gratuit.get()
        p.bebe_gestion = self.v_bebe_gestion.get()
        p.bebe_max = self.v_bebe_max.get()
        p.enfant_gestion = self.v_enfant_gestion.get()
        p.enfant_max = self.v_enfant_max.get()
        p.adulte_max = self.v_adulte_max.get()
        
        # Logo Persistence
        new_logo_path = self.v_logo_path.get()
        if new_logo_path and os.path.exists(new_logo_path):
            # If it's not already in the assets folder, copy it
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            assets_dir = os.path.join(root_dir, "assets")
            if not os.path.exists(assets_dir):
                os.makedirs(assets_dir)
            
            # Use original filename or generic company_logo
            ext = os.path.splitext(new_logo_path)[1]
            target_path = os.path.join(assets_dir, f"company_logo{ext}")
            
            # Only copy if different path
            if os.path.normpath(new_logo_path) != os.path.normpath(target_path):
                try:
                    shutil.copy2(new_logo_path, target_path)
                    p.logo_path = target_path
                except Exception as e:
                    print(f"Error copying logo: {e}")
            else:
                p.logo_path = target_path
                
            # Sync with AppConfig
            config = self.session.query(AppConfig).first()
            if config:
                config.company_logo_path = p.logo_path
        else:
            p.logo_path = new_logo_path # Could be empty string if removed
            config = self.session.query(AppConfig).first()
            if config:
                config.company_logo_path = new_logo_path

        # Admin
        p.code_tva = self.v_code_tva.get()
        p.police_assurance = self.v_police_assurance.get()
        p.code_securite_sociale = self.v_code_securite_sociale.get()
        p.capital_social = self.v_capital_social.get()

        # App
        p.dossier_hotix = self.v_dossier_hotix.get()
        
        # lblServeurs
        p.ftp_url = self.v_ftp_url.get()
        p.ftp_utilisateur = self.v_ftp_user.get()
        p.ftp_mot_de_passe = self.v_ftp_pass.get()
        
        # Emails (Sync from mail_tree)
        for item in self.mail_tree.get_children():
            v = self.mail_tree.item(item, 'values')
            cfg_id = int(v[0])
            cfg = self.session.get(CompanyEmailConfig, cfg_id)
            if cfg:
                cfg.email = v[2]
                cfg.login = v[3]
                cfg.password = v[4]
                cfg.smtp = v[5]
                cfg.port = int(v[6])
                cfg.ssl = (v[7] == "☑")
                cfg.authentifier = (v[8] == "☑")
        
        # Stamp
        p.stamp_path = self.v_stamp_path.get()
        
        self.session.commit()
        self.current_company_id = p.id  # Ensure ID is set for new records
        saved_code = p.code
        
        # Refresh parent dashboard logos if applicable
        if hasattr(self, 'parent_window'):
            pw = self.parent_window
            if hasattr(pw, 'load_company_logo'):
                pw.load_company_logo() # Refresh top-left logo
                if hasattr(pw, 'hero_logo'):
                    pw.load_company_logo(label=pw.hero_logo, size=(300, 300)) # Refresh hero logo if exists
        
        self.load_grid_data()
        
        # Re-select the saved record in the grid
        for item in self.tree.get_children():
            if str(self.tree.item(item)['values'][0]) == str(saved_code):
                self.tree.selection_set(item)
                self.tree.see(item)
                break
        
        Messagebox.show_info("Profil société enregistré avec succès !", "Succès")
