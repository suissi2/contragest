import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.tableview import Tableview
from contragest.core.i18n import tr
from contragest.logic.report_service import ReportService
from contragest.core.database import SessionLocal, AppConfig
import csv
import os
from tkinter import filedialog
from ttkbootstrap.dialogs import Messagebox
from datetime import datetime
from fpdf import FPDF
class ReportsView(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.db = SessionLocal()
        self.service = ReportService(self.db)
        self.tables = {}
        self.tab_info = {}
        
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = ttk.Frame(self, bootstyle=SECONDARY, padding=10)
        header.pack(fill=X)
        ttk.Label(header, text="📊 " + tr("reports") if hasattr(self, "tr") else "📊 Reports", 
                  font=("Helvetica", 16, "bold"), bootstyle="inverse-secondary").pack(side=LEFT, padx=10)

        # Tab Control
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=YES, padx=10, pady=10)

        # Tabs
        self.tab_users = self.create_report_tab("Users", self.service.get_users_report, [
            ("id", "ID", 50), ("username", "Username", 150), ("email", "Email", 200),
            ("role", "Role", 100), ("status", "Status", 100), ("created_at", "Created At", 180)
        ], filters_config={'role': ['All', 'admin', 'user'], 'status': ['All', 'Active', 'Inactive']})
        
        self.tab_spy = self.create_report_tab("Spy", self.service.get_spy_report, [
            ("id", "ID", 50), ("timestamp", "Timestamp", 160), ("username", "User", 120),
            ("action", "Action", 150), ("entity", "Entity", 100), ("details", "Summary", 300)
        ], filters_config={'action': ['All', 'SESSION_START', 'AUTH_ERROR', 'CREATE_CONTRACT', 'EDIT_CONTRACT', 'DELETE_CONTRACT', 'API_ACCESS']},
           date_filters=['timestamp'])
        
        self.tab_employees = self.create_report_tab("Employees", self.service.get_employees_report, [
            ("id", "ID", 50), ("first_name", "First Name", 150), ("last_name", "Last Name", 150),
            ("email", "Email", 200), ("department", "Department", 150), ("contract_count", "Contracts", 80)
        ], filters_config={'department': ['All', 'IT', 'HR', 'Finance', 'Engineering', 'Marketing', 'Sales', 'Operations']})
        
        self.tab_contracts = self.create_report_tab("Contracts", self.service.get_contracts_report, [
            ("id", "ID", 50), ("employee", "Employee", 200), ("type", "Type", 100),
            ("start_date", "Start", 120), ("end_date", "End", 120), ("status", "Status", 120), ("days_left", "Left", 80)
        ], filters_config={'type': ['All', 'CDI', 'CDD', 'Internship', 'Freelance'], 'status': ['All', 'Active', 'Expiring Soon', 'Expired']},
           date_filters=['start_date', 'end_date'])

        self.notebook.add(self.tab_users, text="👥 Users")
        self.notebook.add(self.tab_spy, text="🕵️ Spy")
        self.notebook.add(self.tab_employees, text="👔 Employees")
        self.notebook.add(self.tab_contracts, text="📑 Contracts")

    def create_report_tab(self, name, data_func, columns, filters_config=None, date_filters=None):
        tab = ttk.Frame(self.notebook, padding=10)
        
        # Filter Bar
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="🔍").pack(side=LEFT, padx=(5, 2))
        search_var = ttk.StringVar()
        search_entry = ttk.Entry(filter_frame, textvariable=search_var, width=25)
        search_entry.pack(side=LEFT, padx=(0, 15))
        
        filter_vars = {}
        if filters_config:
            for col_key, options in filters_config.items():
                lbl_text = next((c[1] for c in columns if c[0] == col_key), col_key.capitalize())
                ttk.Label(filter_frame, text=lbl_text+":").pack(side=LEFT, padx=(5, 2))
                f_var = ttk.StringVar(value=options[0] if options else "All")
                cb = ttk.Combobox(filter_frame, textvariable=f_var, values=options, state="readonly", width=12)
                cb.pack(side=LEFT, padx=(0, 15))
                filter_vars[col_key] = f_var
        
        # 1.5 Date Filters
        date_filter_vars = {}
        if date_filters:
            date_filter_frame = ttk.Frame(tab)
            date_filter_frame.pack(fill=X, pady=(0, 10))
            
            ttk.Label(date_filter_frame, text="📅").pack(side=LEFT, padx=(5, 2))
            for col_key in date_filters:
                lbl_text = next((c[1] for c in columns if c[0] == col_key), col_key.capitalize())
                
                # Active Toggle
                active_var = ttk.BooleanVar(value=False)
                ttk.Checkbutton(date_filter_frame, text=lbl_text, variable=active_var, bootstyle="round-toggle").pack(side=LEFT, padx=(5, 5))
                
                ttk.Label(date_filter_frame, text="From:").pack(side=LEFT, padx=(5, 2))
                from_date = ttk.DateEntry(date_filter_frame, dateformat="%Y-%m-%d")
                from_date.pack(side=LEFT, padx=(0, 10))
                
                ttk.Label(date_filter_frame, text="To:").pack(side=LEFT, padx=(5, 2))
                to_date = ttk.DateEntry(date_filter_frame, dateformat="%Y-%m-%d")
                to_date.pack(side=LEFT, padx=(0, 20))
                
                date_filter_vars[col_key] = {
                    'active': active_var,
                    'from_entry': from_date,
                    'to_entry': to_date
                }
        
        ttk.Button(filter_frame, text="🔄 Refresh", bootstyle=INFO, 
                   command=lambda: self.refresh_tab(name, data_func, columns, table, search_var, filter_vars, date_filter_vars)).pack(side=LEFT, padx=5)
                   
        export_buttons_frame = ttk.Frame(filter_frame)
        export_buttons_frame.pack(side=RIGHT, padx=5)
        
        ttk.Button(export_buttons_frame, text="📤 Export CSV", bootstyle=SUCCESS,
                   command=lambda: self.export_csv(name, columns, table)).pack(side=LEFT, padx=2)
                   
        ttk.Button(export_buttons_frame, text="📥 Export PDF", bootstyle="danger",
                   command=lambda: self.export_pdf(name, columns, table)).pack(side=LEFT, padx=2)

        # Table
        table_container = ttk.Frame(tab)
        table_container.pack(fill=BOTH, expand=YES)
        
        table = self.load_table_data(table_container, data_func(), columns)
        self.tables[name.lower()] = table
        self.apply_table_styling(name.lower(), table)
        
        self.tab_info[name.lower()] = {
            'data_func': data_func,
            'columns': columns,
            'table': table,
            'search_var': search_var,
            'filter_vars': filter_vars,
            'date_filter_vars': date_filter_vars
        }
        
        # Search and Combobox Bindings
        def trigger_filter(*args):
             if not self.winfo_exists():
                 return
             self.apply_filter(name.lower(), self.tables[name.lower()], data_func(), search_var, filter_vars, date_filter_vars)
        
        search_var.trace_add("write", trigger_filter)
        for var in filter_vars.values():
             var.trace_add("write", trigger_filter)
        
        for filter_group in date_filter_vars.values():
             filter_group['active'].trace_add("write", trigger_filter)
             # Note: DateEntry vars might not trace beautifully depending on ttkbootstrap version, 
             # but we can rely on the trigger_filter bound to the toggle and refresh button.

        return tab

    def get_selected_contract_id(self):
        """Returns the ID of the selected contract in the Contracts tab."""
        if 'contracts' not in self.tables:
            return None
        
        table = self.tables['contracts']
        selected = table.view.selection()
        if not selected:
            return None
            
        item = table.view.item(selected[0])
        # In ReportsView, self.tab_contracts columns are: ID, Employee, Type, Start, End, Status, Left
        # So ID is index 0
        return int(item['values'][0])

    def load_table_data(self, container, data, columns):
        # Clear container
        for widget in container.winfo_children():
            widget.destroy()
            
        col_data = [{"text": c[1], "stretch": True} for c in columns]
        row_data = [[str(row.get(c[0], "")) for c in columns] for row in data]
        
        table = Tableview(
            master=container,
            coldata=col_data,
            rowdata=row_data,
            paginated=True,
            pagesize=20,
            searchable=False, # We use our own filter bar
            bootstyle=PRIMARY,
            autofit=True
        )
        table.pack(fill=BOTH, expand=YES)
        return table

    def refresh_tab(self, name, data_func, columns, table, search_var, filter_vars, date_filter_vars):
        if not self.winfo_exists():
            return
        # Reset all filters to defaults
        search_var.set("")
        for f_var in filter_vars.values():
            f_var.set("All")
        for f_group in date_filter_vars.values():
            f_group['active'].set(False)
        
        # Reload fresh data
        data = data_func()
        self.apply_filter(name.lower(), table, data, search_var, filter_vars, date_filter_vars)

    def refresh_all(self):
        if not self.winfo_exists() or not hasattr(self, 'tab_info'):
            return
        for name, info in self.tab_info.items():
            self.refresh_tab(
                name, 
                info['data_func'], 
                info['columns'], 
                info['table'], 
                info['search_var'],
                info['filter_vars'],
                info.get('date_filter_vars', {})
            )

    def apply_filter(self, name, table, data, search_var, filter_vars, date_filter_vars):
        if not self.winfo_exists() or not table.winfo_exists():
            return
        search_term = search_var.get().lower()
        
        filtered_data = []
        for row in data:
            # 1. Evaluate General Search
            matches_search = True
            if search_term:
                 matches_search = any(search_term in str(val).lower() for val in row.values())
            
            # 2. Evaluate Combobox Filters
            matches_dropdowns = True
            for col_key, f_var in filter_vars.items():
                 selected_val = f_var.get()
                 if selected_val and selected_val != "All":
                      # The data dict has values, we need to match it based on col_key
                      row_val = str(row.get(col_key, ""))
                      if selected_val.lower() != row_val.strip().lower():
                           matches_dropdowns = False
                           break
            
            # 3. Evaluate Date Filters
            matches_dates = True
            for col_key, f_group in date_filter_vars.items():
                 if f_group['active'].get():
                      # Date filter is activated
                      row_val_str = str(row.get(col_key, ""))
                      if not row_val_str or row_val_str == "None":
                           matches_dates = False
                           break
                      try:
                           # Extract just the date part if it's a datetime string like '2023-10-15 14:30:00'
                           date_str = row_val_str.split(" ")[0]
                           row_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                           
                           from_date_str = f_group['from_entry'].entry.get()
                           from_date = datetime.strptime(from_date_str, "%Y-%m-%d").date()
                           
                           to_date_str = f_group['to_entry'].entry.get()
                           to_date = datetime.strptime(to_date_str, "%Y-%m-%d").date()
                           
                           if not (from_date <= row_date <= to_date):
                                matches_dates = False
                                break
                      except ValueError:
                           # If parsing fails, exclude it or handle defensively
                           matches_dates = False
                           break

            if matches_search and matches_dropdowns and matches_dates:
                 filtered_data.append(row)
        
        # Tableview in ttkbootstrap makes it hard to update rowdata directly without recreating
        # but let's try to access the underlying view if possible or just rebuild
        # Rebuilding is safer for consistency with the component
        self.update_table_rows(table, filtered_data)
        self.apply_table_styling(name, table)

    def update_table_rows(self, table, filtered_data):
        if not table.winfo_exists():
            return
        table.delete_rows()
        rows = [[str(val) for val in row.values()] for row in filtered_data]
        table.insert_rows(END, rows)
        table.load_table_data()

    def export_csv(self, name, columns, table):
        # Extract direct table rows which inherently represent the currently filtered data
        filtered_rows = table.get_rows()
        if not filtered_rows:
            Messagebox.show_info("No data available to export.", "Export")
            return
            
        col_headers = [c[1] for c in columns]
        # table.get_rows() returns TableRow objects. Access values via row.values
        data = [row.values for row in filtered_rows]
            
        df = pd.DataFrame(data, columns=col_headers)
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"report_{name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        if file_path:
            try:
                with open(file_path, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(col_headers)
                    writer.writerows(data)
                Messagebox.show_info(f"CSV Report exported to {file_path}", "Success")
            except Exception as e:
                Messagebox.show_error(f"Failed to export CSV: {e}", "Error")

    def export_pdf(self, name, columns, table):
        # Extract filtered data from the active Tableview
        filtered_rows = table.get_rows()
        if not filtered_rows:
            Messagebox.show_info("No data available to export.", "Export")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"report_{name.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        if not file_path:
            return
            
        try:
            col_headers = [c[1] for c in columns]
            data_rows = [row.values for row in filtered_rows]

            pdf = FPDF(orientation='L', unit='mm', format='A4')
            pdf.add_page()
            
            # Company Logo Header
            logo_path = self._get_company_logo_path()
            if logo_path:
                try:
                    pdf.image(logo_path, x=10, y=8, h=18)
                except Exception:
                    pass  # Skip logo if image format unsupported
            
            # Title (offset right if logo exists)
            title_x = 35 if logo_path else 10
            pdf.set_xy(title_x, 10)
            pdf.set_font("helvetica", "B", 16)
            pdf.cell(0, 8, f"Contragest - {name} Report", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", "I", 10)
            pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align="C", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(5)
            
            # Table logic: distribute column widths evenly for simplicity
            epw = pdf.w - 2 * pdf.l_margin
            col_width = epw / len(col_headers)
            
            # Header Row
            pdf.set_font("helvetica", "B", 11)
            pdf.set_fill_color(66, 139, 202) # Nice subtle blue header
            pdf.set_text_color(255, 255, 255)
            for header in col_headers:
                pdf.cell(col_width, 10, str(header), border=1, align='C', fill=True)
            pdf.ln()

            # Data Rows
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            fill = False
            for row in data_rows:
                if pdf.get_y() > 180: # Margin threshold, add new page
                     pdf.add_page()
                     # Redraw headers
                     pdf.set_font("helvetica", "B", 11)
                     pdf.set_fill_color(66, 139, 202)
                     pdf.set_text_color(255, 255, 255)
                     for header in col_headers:
                         pdf.cell(col_width, 10, str(header), border=1, align='C', fill=True)
                     pdf.ln()
                     pdf.set_font("helvetica", "", 10)
                     pdf.set_text_color(0, 0, 0)
                     
                if fill:
                     pdf.set_fill_color(240, 240, 240)
                else:
                     pdf.set_fill_color(255, 255, 255)
                
                # Print cells
                for item in row:
                    # Truncate strings to prevent cell overflow
                    val = str(item)[:30] + "..." if len(str(item)) > 30 else str(item)
                    pdf.cell(col_width, 8, val, border=1, align='L', fill=True)
                pdf.ln()
                fill = not fill

            pdf.output(file_path)
            Messagebox.show_info(f"PDF Report cleanly exported to {file_path}", "Success")
            
        except Exception as e:
            Messagebox.show_error(f"An error occurred during PDF generation:\n{e}", "Export Error")

    def apply_table_styling(self, name, table):
        """Applies dynamic row coloring based on the active tab and data values."""
        if not table or not hasattr(table, 'view'):
            return
            
        # Configure the standard visual tag palette for ttkbootstrap Treeview
        table.view.tag_configure('danger', background='#d9534f', foreground='white')
        table.view.tag_configure('warning', background='#f0ad4e', foreground='white')
        table.view.tag_configure('success', background='#5cb85c', foreground='white')
        
        for item_id in table.view.get_children():
            values = table.view.item(item_id, 'values')
            if not values: 
                continue
                
            if name == "contracts":
                # Contracts columns: ID[0], Employee[1], Type[2], Start[3], End[4], Status[5], Left[6]
                if len(values) > 5:
                    status_text = str(values[5]).strip()
                    if status_text == "Expired" or status_text == (tr("expired") if hasattr(self, "tr") else "Expired"):
                        table.view.item(item_id, tags=('danger',))
                    elif status_text == "Expiring Soon" or status_text == (tr("expiring_soon") if hasattr(self, "tr") else "Expiring Soon"):
                        table.view.item(item_id, tags=('warning',))
                    elif status_text == "Active" or status_text == (tr("active") if hasattr(self, "tr") else "Active"):
                        table.view.item(item_id, tags=('success',))
                        
            elif name == "users":
                # Users columns: ID[0], Username[1], Email[2], Role[3], Status[4], Created At[5]
                if len(values) > 4:
                    status_text = str(values[4]).strip()
                    if status_text == "Inactive":
                        table.view.item(item_id, tags=('danger',))
                    elif status_text == "Active":
                        table.view.item(item_id, tags=('success',))
                        
            elif name == "spy":
                # Spy columns: ID[0], Timestamp[1], User[2], Action[3], Entity[4], Summary[5]
                if len(values) > 3:
                    action_text = str(values[3]).strip()
                    if "ERROR" in action_text or "DELETE" in action_text:
                        table.view.item(item_id, tags=('danger',))
                    elif "CREATE" in action_text or "EDIT" in action_text:
                        table.view.item(item_id, tags=('success',))

    def _get_company_logo_path(self):
        """Get company logo path from AppConfig, return None if not found."""
        session = SessionLocal()
        try:
            config = session.query(AppConfig).first()
            if config and config.company_logo_path and os.path.exists(config.company_logo_path):
                return config.company_logo_path
        except Exception:
            pass
        finally:
            session.close()
        return None

    def __del__(self):
        if hasattr(self, "db"):
            self.db.close()
