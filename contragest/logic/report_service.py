from datetime import datetime, date
from sqlalchemy.orm import Session
from contragest.core.database import Contract, Employee, AppConfig
from contragest.features.auth.service import AuthService, User
from typing import List, Dict, Any

class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.auth_service = AuthService()

    def get_users_report(self) -> List[Dict[str, Any]]:
        users = self.auth_service.get_all_users()
        report_data = []
        for u in users:
            report_data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
                "status": "Active" if u.is_active else "Inactive",
                "created_at": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else "N/A"
            })
        return report_data

    def get_spy_report(self, since: datetime = None) -> List[Dict[str, Any]]:
        # This reuses the logic from Mouchard logic if needed, but we can query directly
        query = self.db.query(self.auth_service.AuditLog)
        if since:
            query = query.filter(self.auth_service.AuditLog.timestamp >= since)
        
        logs = query.order_by(self.auth_service.AuditLog.timestamp.desc()).all()
        report_data = []
        for l in logs:
            report_data.append({
                "id": l.id,
                "timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "N/A",
                "username": l.username or f"ID:{l.user_id}",
                "action": l.action,
                "entity": l.affected_entity or "-",
                "entity_id": l.entity_id or "-",
                "details": l.details[:100] + "..." if l.details and len(l.details) > 100 else (l.details or "")
            })
        return report_data

    def get_employees_report(self) -> List[Dict[str, Any]]:
        employees = self.db.query(Employee).all()
        report_data = []
        for e in employees:
            report_data.append({
                "id": e.id,
                "first_name": e.first_name,
                "last_name": e.last_name,
                "email": e.email or "N/A",
                "department": e.department or "N/A",
                "contract_count": len(e.contracts)
            })
        return report_data

    def get_contracts_report(self) -> List[Dict[str, Any]]:
        contracts = self.db.query(Contract).all()
        config = self.db.query(AppConfig).first()
        threshold = config.alert_threshold_days if config else 30
        today = date.today()
        
        report_data = []
        for c in contracts:
            days_left = (c.end_date - today).days if c.end_date else None
            status = "Active"
            if days_left is not None:
                if days_left < 0:
                    status = "Expired"
                elif days_left <= threshold:
                    status = "Expiring Soon"
            
            report_data.append({
                "id": c.id,
                "employee": f"{c.employee.first_name} {c.employee.last_name}",
                "type": c.contract_type,
                "start_date": c.start_date.strftime("%Y-%m-%d"),
                "end_date": c.end_date.strftime("%Y-%m-%d") if c.end_date else "∞",
                "status": status,
                "days_left": str(days_left) if days_left is not None else "∞"
            })
        return report_data
