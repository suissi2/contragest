import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.dialogs import Messagebox
from contragest.core.database import SessionLocal, CompanyProfile, CompanyEmailConfig, AppConfig
from contragest.core.i18n import tr
from ttkbootstrap.widgets import DateEntry
from tkinter import filedialog
from PIL import Image, ImageTk
from datetime import datetime
import os
import shutil

class CompanyManagerWindow(ttk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent  # Explicit reference to MainWindow
        self.title("Saisie et M.à.j Société")
        self.geometry("1150x850")
        self.center_window()
        self.resizable(True, True)
        
        self.session = SessionLocal()
        
        # Variables
        self.init_variables()
        
        self.main_container = ttk.Frame(self, padding=2, bootstyle="secondary")
        self.main_container.pack(fill=BOTH, expand=YES)
        
        self.tabs_dict = {}
        self.current_company_id = None
        
        # Build layout (from bottom up to pin the bottom area)
        self.build_bottom_tabs_container()  # Bottom-most
        self.build_middle_navigation()       # Above forms
        self.build_bottom_action_bar()      # Immediately below Treeview
        self.build_top_grid()               # Top, expandable
        
        self.load_grid_data()
        
    def center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
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

    def build_top_grid(self):
        grid_frame = ttk.Frame(self.main_container)
        grid_frame.pack(fill=BOTH, expand=YES, pady=(0, 2))
        
        columns = (
            "code", "raison_sociale", "responsable", "contacts", "site_web", 
            "email", "adresse", "code_postal", "ville", "telephone", "fax", 
            "telex", "bebe_gratuit", "utilisation_fi", "forme_juridique", 
            "code_tva", "categories", "pays", "lblcodepays", "secteur_geo", "devise"
        )
        self.tree = ttk.Treeview(grid_frame, columns=columns, show="headings", selectmode="browse")
        
        vsb = ttk.Scrollbar(grid_frame, orient=VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(grid_frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(column=0, row=0, sticky='nsew')
        vsb.grid(column=1, row=0, sticky='ns')
        hsb.grid(column=0, row=1, sticky='ew')
        
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_rowconfigure(0, weight=1)
        
        headings = [
            "Code", "Raison Sociale", "Responsable", "Contact(s)", "Site Web",
            "Email", "Adresse", "Code Postal", "Ville", "Téléphone", "Fax",
            "Téléx", "Bébé Gratuit", "Utilisation FI", "Forme Juridique",
            "Code TVA", "Catégories", "Pays", "lblCodePays", "Secteur Géographique", "Devise"
        ]
        
        for col, head in zip(columns, headings):
            self.tree.heading(col, text=head)
            self.tree.column(col, width=100, minwidth=80)
            
        self.tree.bind("<<TreeviewSelect>>", self.on_grid_select)

    def build_middle_navigation(self):
        nav_frame = ttk.Frame(self.main_container, bootstyle="secondary")
        nav_frame.pack(fill=X, side=BOTTOM, pady=2)
        
        left_actions = ttk.Frame(nav_frame)
        left_actions.pack(side=LEFT, padx=5)
        ttk.Button(left_actions, text="🔄", bootstyle="outline-primary", command=self.load_grid_data).pack(side=LEFT, padx=2)
        
        tabs_frame = ttk.Frame(nav_frame)
        tabs_frame.pack(side=LEFT, padx=5)
        
        tabs = [
            ("📝", "Général"), ("📱", "Contact(s)"), ("⚙️", "Option(s)"), 
            ("👔", "Administratif"), ("📧", "Messagerie"), ("☁️", "Applications"), 
            ("🖥️", "lblServeurs"), ("📜", "Stamp")
        ]
        
        for icon, tab_name in tabs:
            btn = ttk.Button(tabs_frame, text=f"{icon} {tab_name}", bootstyle="link", 
                             command=lambda t=tab_name: self.show_tab(t))
            btn.pack(side=LEFT, padx=2)

    def build_bottom_tabs_container(self):
        # We use a fixed height container for the forms area
        self.bottom_container = ttk.Frame(self.main_container, bootstyle="light", height=350)
        self.bottom_container.pack(fill=X, side=BOTTOM, expand=False)
        self.bottom_container.pack_propagate(False) # Keep fixed height regardless of content
        
        # Build individual tab frames
        self.tabs_dict["Général"] = self.build_general_tab()
        self.tabs_dict["Contact(s)"] = self.build_contact_tab()
        self.tabs_dict["Option(s)"] = self.build_option_tab()
        self.tabs_dict["Administratif"] = self.build_admin_tab()
        self.tabs_dict["Messagerie"] = self.build_messagerie_tab()
        self.tabs_dict["Applications"] = self.build_app_tab()
        self.tabs_dict["lblServeurs"] = self.build_serveurs_tab()
        self.tabs_dict["Stamp"] = self.build_stamp_tab()
        
        # Show default tab
        self.show_tab("Général")

    def show_tab(self, tab_name):
        for frame in self.tabs_dict.values():
            if frame:
                frame.pack_forget()
        
        if tab_name in self.tabs_dict and self.tabs_dict[tab_name]:
            self.tabs_dict[tab_name].pack(fill=BOTH, expand=YES)

    def build_bottom_action_bar(self):
        # The background should match the top navigation bar
        action_bar = ttk.Frame(self.main_container, bootstyle="secondary")
        action_bar.pack(fill=X, side=BOTTOM, pady=(0, 2))
        
        container = ttk.Frame(action_bar, bootstyle="secondary")
        container.pack(side=LEFT, fill=Y, padx=0, pady=0)
        
        # Style definition for flush square buttons
        # In ttkbootstrap, we can use 'toolbutton' or specific width/padding
        
        # Group 1: CRUD Actions (Green, Dark Gray, Red, Cyan)
        crud_frame = ttk.Frame(container, bootstyle="secondary")
        crud_frame.pack(side=LEFT, padx=(5, 10))
        
        btn_add = ttk.Button(crud_frame, text=" ➕ ", bootstyle="success", width=3, command=self.cmd_add)
        btn_add.pack(side=LEFT, padx=0, fill=Y)
        
        btn_edit = ttk.Button(crud_frame, text=" 📝 ", bootstyle="secondary", width=3, command=self.cmd_edit)
        btn_edit.pack(side=LEFT, padx=0, fill=Y)
        
        btn_del = ttk.Button(crud_frame, text=" ➖ ", bootstyle="danger", width=3, command=self.cmd_delete)
        btn_del.pack(side=LEFT, padx=0, fill=Y)
        
        btn_ref = ttk.Button(crud_frame, text=" 🔄 ", bootstyle="info", width=3, command=self.load_grid_data)
        btn_ref.pack(side=LEFT, padx=0, fill=Y)
        
        # Separator (A small vertical line or just empty space)
        ttk.Frame(container, bootstyle="secondary", width=10).pack(side=LEFT, fill=Y)
        
        # Group 2: Navigation (All Cyan)
        nav_frame = ttk.Frame(container, bootstyle="secondary")
        nav_frame.pack(side=LEFT, padx=0)
        
        btn_first = ttk.Button(nav_frame, text=" ⏪ ", bootstyle="info", width=3, command=self.nav_first)
        btn_first.pack(side=LEFT, padx=0, fill=Y)
        
        btn_prev = ttk.Button(nav_frame, text=" ◀ ", bootstyle="info", width=3, command=self.nav_prev)
        btn_prev.pack(side=LEFT, padx=0, fill=Y)
        
        btn_next = ttk.Button(nav_frame, text=" ▶ ", bootstyle="info", width=3, command=self.nav_next)
        btn_next.pack(side=LEFT, padx=0, fill=Y)
        
        btn_last = ttk.Button(nav_frame, text=" ⏩ ", bootstyle="info", width=3, command=self.nav_last)
        btn_last.pack(side=LEFT, padx=0, fill=Y)
        
        # Main form actions on Right side
        right_actions = ttk.Frame(action_bar, bootstyle="secondary")
        right_actions.pack(side=RIGHT, padx=5, pady=2)
        ttk.Button(right_actions, text="💾 Enregistrer", bootstyle="success", command=self.save_company).pack(side=LEFT, padx=2)
        ttk.Button(right_actions, text="❌ Fermer", bootstyle="secondary", command=self.destroy).pack(side=LEFT, padx=2)

    def add_form_row(self, parent, label_text, variable, width=32):
        row = parent.grid_size()[1]
        ttk.Label(parent, text=label_text, width=15, anchor=W, bootstyle="light").grid(row=row, column=0, pady=2, sticky=W)
        ttk.Entry(parent, textvariable=variable, width=width).grid(row=row, column=1, pady=2, sticky=W)

    # --- TAB BUILDERS --- #
    def build_general_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        
        left_col = ttk.Frame(frame, bootstyle="light")
        left_col.pack(side=LEFT, fill=Y, padx=(10, 50))
        self.add_form_row(left_col, "Code", self.v_code)
        self.add_form_row(left_col, "Raison Sociale", self.v_raison_sociale)
        
        ttk.Label(left_col, text="Catégories", width=15, anchor=W, bootstyle="light").grid(column=0, row=2, pady=2, sticky=W)
        ttk.Combobox(left_col, textvariable=self.v_categories, width=30).grid(row=2, column=1, pady=2, sticky=W)
        ttk.Label(left_col, text="Forme Juridique", width=15, anchor=W, bootstyle="light").grid(column=0, row=3, pady=2, sticky=W)
        ttk.Combobox(left_col, textvariable=self.v_forme_juridique, width=30).grid(row=3, column=1, pady=2, sticky=W)
        self.add_form_row(left_col, "Activité", self.v_activite)

        right_col = ttk.Frame(frame, bootstyle="light")
        right_col.pack(side=RIGHT, fill=Y, padx=(50, 10))
        ttk.Label(right_col, text="Secteur Géographique", width=20, anchor=W, bootstyle="light").grid(column=0, row=0, pady=2, sticky=W)
        ttk.Combobox(right_col, textvariable=self.v_secteur_geo, width=30).grid(row=0, column=1, pady=2, sticky=W)
        
        ttk.Label(right_col, text="Date de Création", width=20, anchor=W, bootstyle="light").grid(column=0, row=1, pady=2, sticky=W)
        self.date_picker = DateEntry(right_col, width=28)
        self.date_picker.grid(row=1, column=1, pady=2, sticky=W)
        
        self.add_form_row(right_col, "Représentant Juridique", self.v_representant)
        self.add_form_row(right_col, "Qualité", self.v_qualite)
        return frame

    def build_contact_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        
        left_col = ttk.Frame(frame, bootstyle="light")
        left_col.pack(side=LEFT, fill=Y, padx=(10, 50))
        
        # Override add_form_row specifically for Adresse which needs to be larger
        ttk.Label(left_col, text="Adresse", width=12, anchor=NW, bootstyle="light").grid(column=0, row=0, pady=2, sticky=NW)
        ttk.Entry(left_col, textvariable=self.v_adresse, width=50).grid(row=0, column=1, pady=2, sticky=W)
        
        ttk.Label(left_col, text="Ville", width=12, anchor=W, bootstyle="light").grid(column=0, row=1, pady=2, sticky=W)
        ttk.Entry(left_col, textvariable=self.v_ville, width=40).grid(row=1, column=1, pady=2, sticky=W)
        
        ttk.Label(left_col, text="Code Postal", width=12, anchor=W, bootstyle="light").grid(column=0, row=2, pady=2, sticky=W)
        ttk.Spinbox(left_col, textvariable=self.v_code_postal, width=10, from_=0, to=99999).grid(row=2, column=1, pady=2, sticky=W)
        
        ttk.Label(left_col, text="Pays", width=12, anchor=W, bootstyle="light").grid(column=0, row=3, pady=2, sticky=W)
        ttk.Combobox(left_col, textvariable=self.v_pays, width=30).grid(row=3, column=1, pady=2, sticky=W)

        right_col = ttk.Frame(frame, bootstyle="light")
        right_col.pack(side=RIGHT, fill=Y, padx=(50, 10))
        
        ttk.Label(right_col, text="Téléphone", width=15, anchor=W, bootstyle="light").grid(column=0, row=0, pady=2, sticky=W)
        ttk.Entry(right_col, textvariable=self.v_telephone, width=30).grid(row=0, column=1, pady=2, sticky=W)
        ttk.Label(right_col, text="Fax", width=15, anchor=W, bootstyle="light").grid(column=0, row=1, pady=2, sticky=W)
        ttk.Entry(right_col, textvariable=self.v_fax, width=30).grid(row=1, column=1, pady=2, sticky=W)
        ttk.Label(right_col, text="Téléx", width=15, anchor=W, bootstyle="light").grid(column=0, row=2, pady=2, sticky=W)
        ttk.Entry(right_col, textvariable=self.v_telex, width=30).grid(row=2, column=1, pady=2, sticky=W)
        ttk.Label(right_col, text="Site Web", width=15, anchor=W, bootstyle="light").grid(column=0, row=3, pady=2, sticky=W)
        ttk.Entry(right_col, textvariable=self.v_site_web, width=30).grid(row=3, column=1, pady=2, sticky=W)

        return frame

    def build_option_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        
        # Left Panel Booleans
        left_col = ttk.Frame(frame, bootstyle="light")
        left_col.pack(side=LEFT, fill=Y, padx=(5, 20))
        
        ttk.Checkbutton(left_col, text="Utilisation FDCST", variable=self.v_utilisation_fdcst, bootstyle="round-toggle,light").pack(anchor=W, pady=2)
        ttk.Checkbutton(left_col, text="Facturation Coffre /Jour", variable=self.v_facturation_coffre, bootstyle="round-toggle,light").pack(anchor=W, pady=2)
        ttk.Checkbutton(left_col, text="Contrôle Nom PAX", variable=self.v_controle_nom_pax, bootstyle="round-toggle,light").pack(anchor=W, pady=2)
        
        ttk.Label(left_col, text="Devise", bootstyle="light").pack(anchor=W, pady=(10,0))
        ttk.Combobox(left_col, textvariable=self.v_devise, width=20, values=["Dinar Tunisien", "Euro", "USD"]).pack(anchor=W)
        
        ttk.Label(left_col, text="Nationalité", bootstyle="light").pack(anchor=W, pady=(5,0))
        ttk.Combobox(left_col, textvariable=self.v_nationalite, width=20, values=["Résidents Tunisiens"]).pack(anchor=W)

        # Middle Groups
        mid_col = ttk.Frame(frame, bootstyle="light")
        mid_col.pack(side=LEFT, fill=Y, padx=20)
        
        # Taxe Sejour Group
        taxe_frame = ttk.LabelFrame(mid_col, text="Taxe Séjour")
        taxe_frame.pack(fill=X, pady=5)
        ttk.Checkbutton(taxe_frame, text="Taxe Séjour", variable=self.v_taxe_sejour).grid(row=0, column=0, columnspan=2, pady=2, padx=5, sticky=W)
        ttk.Label(taxe_frame, text="Transaction", bootstyle="light").grid(row=1, column=0, pady=2, padx=5)
        ttk.Entry(taxe_frame, textvariable=self.v_transaction_taxe, width=25).grid(row=1, column=1, pady=2, padx=5)
        
        # Gestion Group Container
        gestion_container = ttk.Frame(mid_col, bootstyle="light")
        gestion_container.pack(fill=X, pady=5)
        
        # Bebes
        b_frame = ttk.LabelFrame(gestion_container, text="Gestion des bébés")
        b_frame.pack(side=LEFT, padx=2)
        ttk.Checkbutton(b_frame, text="Gratuit", variable=self.v_bebe_gratuit).pack(anchor=W, padx=5)
        ttk.Checkbutton(b_frame, text="Gestion", variable=self.v_bebe_gestion).pack(anchor=W, padx=5)
        hf = ttk.Frame(b_frame)
        hf.pack(anchor=W, padx=5, pady=2)
        ttk.Label(hf, text="Nbre.Maxim").pack(side=LEFT)
        ttk.Spinbox(hf, textvariable=self.v_bebe_max, width=4, from_=0, to=10).pack(side=LEFT)

        # Enfants
        e_frame = ttk.LabelFrame(gestion_container, text="Gestion des enfants")
        e_frame.pack(side=LEFT, padx=2, fill=Y)
        ttk.Checkbutton(e_frame, text="Gestion", variable=self.v_enfant_gestion).pack(anchor=W, padx=5)
        hf2 = ttk.Frame(e_frame)
        hf2.pack(anchor=W, padx=5, pady=2)
        ttk.Label(hf2, text="Nbre.Maxim").pack(side=LEFT)
        ttk.Spinbox(hf2, textvariable=self.v_enfant_max, width=4, from_=0, to=10).pack(side=LEFT)
        
        # Adultes
        a_frame = ttk.LabelFrame(gestion_container, text="Gestion des adultes")
        a_frame.pack(side=LEFT, padx=2, fill=Y)
        hf3 = ttk.Frame(a_frame)
        hf3.pack(anchor=W, padx=5, pady=2)
        ttk.Label(hf3, text="Nbre.Maxim").pack(side=LEFT)
        ttk.Spinbox(hf3, textvariable=self.v_adulte_max, width=4, from_=0, to=10).pack(side=LEFT)

        # Right Logo
        logo_frame = ttk.LabelFrame(frame, text="Logo")
        logo_frame.pack(side=RIGHT, fill=Y, padx=10)
        
        self.lbl_logo = ttk.Label(logo_frame, text="[No Logo Selected]", width=25, anchor=CENTER)
        self.lbl_logo.pack(side=LEFT, padx=10, fill=BOTH, expand=YES)
        
        btn_frame = ttk.Frame(logo_frame)
        btn_frame.pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="📁", command=self.upload_logo).pack(pady=5)
        ttk.Button(btn_frame, text="❌", bootstyle="danger", command=lambda: [self.v_logo_path.set(""), self.refresh_logo_display()]).pack(pady=5)

        return frame

    def build_admin_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        col = ttk.Frame(frame, bootstyle="light")
        col.pack(side=LEFT, fill=Y, padx=10)
        
        self.add_form_row(col, "Code TVA", self.v_code_tva, width=40)
        self.add_form_row(col, "Police Assurance", self.v_police_assurance, width=40)
        self.add_form_row(col, "Code Sécurité Sociale", self.v_code_securite_sociale, width=40)
        
        row = 3
        ttk.Label(col, text="Capital Social", width=15, anchor=W, bootstyle="light").grid(row=row, column=0, pady=2, sticky=W)
        ttk.Spinbox(col, textvariable=self.v_capital_social, width=15, format="%.3f").grid(row=row, column=1, pady=2, sticky=W)
        return frame

    def build_messagerie_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=2, bootstyle="light")
        
        cols = ("type", "email", "login", "password", "smtp", "port", "ssl", "auth")
        heads = ["Type", "Email", "lblEmailLogin", "Mot de Passe", "SMTP", "lblPORT", "SSL", "Authentifier"]
        
        self.mail_tree = ttk.Treeview(frame, columns=cols, show="headings", height=6)
        for c, h in zip(cols, heads):
            self.mail_tree.heading(c, text=h)
            self.mail_tree.column(c, width=120)

        self.mail_tree.pack(fill=BOTH, expand=YES)
        return frame

    def build_app_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        group = ttk.LabelFrame(frame, text="My Hotix Guest")
        group.pack(anchor=NW, fill=X, padx=10, pady=5)
        
        ttk.Label(group, text="Dossier", width=10).pack(side=LEFT, padx=5, pady=10)
        ttk.Entry(group, textvariable=self.v_dossier_hotix, width=40).pack(side=LEFT, padx=5, pady=10)
        ttk.Button(group, text="📁").pack(side=LEFT, padx=5, pady=10)
        return frame

    def build_serveurs_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        group = ttk.LabelFrame(frame, text="lblFtpServer")
        group.pack(anchor=NW, fill=X, padx=10, pady=5)
        
        inner = ttk.Frame(group)
        inner.pack(anchor=NW, padx=10, pady=5)
        self.add_form_row(inner, "URL", self.v_ftp_url, width=40)
        self.add_form_row(inner, "Utilisateur", self.v_ftp_user, width=40)
        self.add_form_row(inner, "Mot De Passe", self.v_ftp_pass, width=40)
        return frame

    def build_stamp_tab(self):
        frame = ttk.Frame(self.bottom_container, padding=10, bootstyle="light")
        
        # Right Stamp
        stamp_frame = ttk.LabelFrame(frame, text="Stamp")
        stamp_frame.pack(side=RIGHT, fill=Y, padx=10)
        
        self.lbl_stamp = ttk.Label(stamp_frame, text="[No Stamp Selected]", width=25, anchor=CENTER)
        self.lbl_stamp.pack(side=LEFT, padx=10, fill=BOTH, expand=YES)
        
        btn_frame = ttk.Frame(stamp_frame)
        btn_frame.pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="📁", command=self.upload_stamp).pack(pady=5)
        ttk.Button(btn_frame, text="❌", bootstyle="danger", command=lambda: [self.v_stamp_path.set(""), self.refresh_stamp_display()]).pack(pady=5)

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
            v = (c.type, c.email, c.login, c.password, c.smtp, c.port, "☑" if c.ssl else "☐", "☑" if c.authentifier else "☐")
            self.mail_tree.insert("", END, values=v)

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
