import tkinter as tk
from tkinter import ttk
from ttkbootstrap.dialogs import Messagebox
import json
import csv
from datetime import datetime, timedelta
from typing import Any, List, Optional

class MouchardPanel(tk.Frame):
    """
    Advanced audit log viewer with filtering, searching, and detail inspection.
    """
    
    COLUMNS = [
        ("timestamp", "Timestamp", 160, "center"),
        ("username",  "User",      120, "w"),
        ("action",    "Action",    150, "center"),
        ("entity",    "Entity",    100, "center"),
        ("entity_id", "ID",        50,  "center"),
        ("details",   "Summary",   300, "w"),
    ]

    def __init__(self, master, audit_service: Any, current_user: Any = None):
        super().__init__(master)
        self.audit_service = audit_service
        self.current_user = current_user
        self._all_logs: List[Any] = []
        self._sort_col = "timestamp"
        self._sort_reverse = True
        
        self._create_widgets()
        self.load_logs()

    def _create_widgets(self):
        # ── Search & Filter Bar ────────────────────────────────
        control_frame = ttk.Frame(self)
        control_frame.pack(fill="x", padx=10, pady=10)

        # Search
        ttk.Label(control_frame, text="🔍").pack(side="left", padx=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._refresh_tree())
        search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side="left", padx=(0, 15))

        # Date Filter
        ttk.Label(control_frame, text="Period:").pack(side="left", padx=(0, 5))
        self.period_var = tk.StringVar(value="Today")
        period_combo = ttk.Combobox(
            control_frame, textvariable=self.period_var,
            values=["Today", "Last 3 Days", "This Week", "This Month", "All Time"],
            state="readonly", width=12
        )
        period_combo.pack(side="left", padx=(0, 15))
        period_combo.bind("<<ComboboxSelected>>", lambda e: self.load_logs())

        # Action Filter
        ttk.Label(control_frame, text="Action:").pack(side="left", padx=(0, 5))
        self.action_filter_var = tk.StringVar(value="All")
        self.action_combo = ttk.Combobox(
            control_frame, textvariable=self.action_filter_var,
            values=["All"], state="readonly", width=15
        )
        self.action_combo.pack(side="left", padx=(0, 15))
        self.action_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_tree())

        # ── Action Toolbar ─────────────────────────────────────
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(toolbar, text="👁 View Details", command=self._show_detail_dialog, bootstyle="info").pack(side="left", padx=2)
        ttk.Button(toolbar, text="📤 Export CSV", command=self._export_csv, bootstyle="success").pack(side="left", padx=2)
        ttk.Button(toolbar, text="↻ Refresh", command=self.load_logs, bootstyle="secondary").pack(side="left", padx=2)

        # ── Treeview ───────────────────────────────────────────
        tree_frame = ttk.Frame(self)
        tree_frame.pack(expand=True, fill="both", padx=10, pady=0)

        col_ids = [c[0] for c in self.COLUMNS]
        self.tree = ttk.Treeview(tree_frame, columns=col_ids, show="headings", selectmode="browse")

        for col_id, heading, width, anchor in self.COLUMNS:
            self.tree.heading(col_id, text=heading, command=lambda c=col_id: self._on_heading_click(c))
            self.tree.column(col_id, width=width, anchor=anchor)

        v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        h_scroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.pack(side="left", expand=True, fill="both")
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")

        # Tags
        self.tree.tag_configure("CREATE",  foreground="#2ecc71") # Green
        self.tree.tag_configure("DELETE",  foreground="#e74c3c") # Red
        self.tree.tag_configure("UPDATE",  foreground="#3498db") # Blue
        self.tree.tag_configure("AUTH",    foreground="#9b59b6") # Purple
        self.tree.tag_configure("SECURITY", foreground="#e67e22") # Orange

        self.tree.bind("<Double-1>", lambda e: self._show_detail_dialog())

    def load_logs(self):
        """Fetch logs from DB based on date period."""
        period = self.period_var.get()
        since = None
        if period == "Today":
            since = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "Last 3 Days":
            since = datetime.now() - timedelta(days=3)
        elif period == "This Week":
            since = datetime.now() - timedelta(days=7)
        elif period == "This Month":
            since = datetime.now() - timedelta(days=30)
            
        session = self.audit_service._get_session()
        try:
            query = session.query(self.audit_service.AuditLog)
            if since:
                query = query.filter(self.audit_service.AuditLog.timestamp >= since)
            
            self._all_logs = query.order_by(self.audit_service.AuditLog.timestamp.desc()).all()
            
            # Extract unique actions for filter
            actions = sorted(list(set(l.action for l in self._all_logs)))
            self.action_combo['values'] = ["All"] + actions
            
            # Expunge to avoid detached session errors
            for l in self._all_logs:
                session.expunge(l)
                
            self._refresh_tree()
        finally:
            session.close()

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().lower()
        action_filter = self.action_filter_var.get()

        logs = self._all_logs
        
        # Apply Filters
        if action_filter != "All":
            logs = [l for l in logs if l.action == action_filter]
            
        if search:
            logs = [l for l in logs if 
                    search in (l.username or "").lower() or 
                    search in (l.action or "").lower() or 
                    search in (l.details or "").lower() or
                    search in (l.affected_entity or "").lower()]

        # Apply Sort
        logs = self._apply_sort(logs)

        for l in logs:
            ts = l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "N/A"
            username = l.username or f"ID:{l.user_id}"
            
            # Picking Tag
            tag = "INFO"
            if any(x in l.action for x in ["CREATE", "REGISTER"]): tag = "CREATE"
            elif any(x in l.action for x in ["DELETE", "REMOVE"]): tag = "DELETE"
            elif any(x in l.action for x in ["UPDATE", "CHANGE", "EDIT"]): tag = "UPDATE"
            elif any(x in l.action for x in ["LOGIN", "ACTIVATION"]): tag = "AUTH"
            elif any(x in l.action for x in ["LOCKED", "FAILED", "RESET"]): tag = "SECURITY"

            # Summary processing (truncate JSON)
            summary = (l.details or "")
            if summary.startswith("{"):
                try:
                    data = json.loads(summary)
                    if "before" in data and "after" in data:
                        summary = "Modified record state"
                    else:
                        summary = ", ".join(f"{k}: {v}" for k, v in data.items() if k != "before")
                except:
                    pass
            
            if len(summary) > 60: summary = summary[:57] + "..."

            self.tree.insert("", "end", iid=str(l.id), values=(
                ts, username, l.action, l.affected_entity or "-", l.entity_id or "-", summary
            ), tags=(tag,))

    def _apply_sort(self, logs: list) -> list:
        key_map = {
            "timestamp": lambda l: l.timestamp or datetime.min,
            "username":  lambda l: (l.username or "").lower(),
            "action":    lambda l: (l.action or "").lower(),
            "entity":    lambda l: (l.affected_entity or "").lower(),
        }
        key = key_map.get(self._sort_col, lambda l: l.timestamp)
        return sorted(logs, key=key, reverse=self._sort_reverse)

    def _on_heading_click(self, col_id: str):
        if self._sort_col == col_id:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col_id
            self._sort_reverse = False
        self._refresh_tree()

    def _get_selected_log(self) -> Optional[Any]:
        sel = self.tree.selection()
        if not sel: return None
        log_id = int(sel[0])
        return next((l for l in self._all_logs if l.id == log_id), None)

    def _show_detail_dialog(self):
        log = self._get_selected_log()
        if not log: return

        dlg = tk.Toplevel(self)
        dlg.title(f"Log Detail - {log.action}")
        dlg.geometry("600x500")
        dlg.transient(self.winfo_toplevel())

        container = ttk.Frame(dlg, padding=20)
        container.pack(fill="both", expand=True)

        header_font = ("Helvetica", 11, "bold")
        
        # Info Grid
        info_frame = ttk.Frame(container)
        info_frame.pack(fill="x", pady=(0, 15))
        
        details = [
            ("Timestamp:", log.timestamp.strftime("%Y-%m-%d %H:%M:%S") if log.timestamp else "N/A"),
            ("User:",      f"{log.username} (ID: {log.user_id})"),
            ("Action:",    log.action),
            ("Target:",    f"{log.affected_entity or 'N/A'} (ID: {log.entity_id or 'N/A'})"),
        ]
        
        for i, (label, val) in enumerate(details):
            ttk.Label(info_frame, text=label, font=header_font).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(info_frame, text=val).grid(row=i, column=1, sticky="w", padx=5, pady=2)

        # Content Text Area
        ttk.Label(container, text="Details:", font=header_font).pack(anchor="w", pady=(0, 5))
        txt = tk.Text(container, wrap="word", padx=10, pady=10, font=("Consolas", 10))
        txt.pack(fill="both", expand=True)
        
        content = log.details or "No additional details."
        if content.startswith("{"):
            try:
                # Pretty print JSON
                data = json.loads(content)
                content = json.dumps(data, indent=2, ensure_ascii=False)
            except:
                pass
        
        txt.insert("1.0", content)
        txt.configure(state="disabled")

        ttk.Button(container, text="Close", command=dlg.destroy).pack(pady=(15, 0))

    def _export_csv(self):
        if not self._all_logs:
            Messagebox.show_info("No logs to export.", "Export")
            return
            
        filename = f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "User ID", "Username", "Action", "Entity", "Entity ID", "Details"])
                for l in self._all_logs:
                    writer.writerow([
                        l.timestamp, l.user_id, l.username, l.action, 
                        l.affected_entity, l.entity_id, l.details
                    ])
            Messagebox.show_info(f"Logs exported to {filename}", "Export Success")
        except Exception as e:
            Messagebox.show_error(f"Failed to export: {e}", "Export Error")
