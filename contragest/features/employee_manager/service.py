from sqlalchemy.orm import Session
from contragest.core.database import Department, Employee
from typing import List, Optional

class EmployeeService:
    def __init__(self, session: Session):
        self.session = session

    def get_department_hierarchy(self) -> List[Department]:
        """Returns top-level departments with their children loaded."""
        return self.session.query(Department).filter(Department.parent_id == None).all()

    def get_employee(self, emp_id: int) -> Optional[Employee]:
        return self.session.query(Employee).get(emp_id)

    def create_department(self, name: str, parent_id: Optional[int] = None) -> Department:
        dept = Department(name=name.strip(), parent_id=parent_id)
        self.session.add(dept)
        self.session.commit()
        return dept

    def update_department(self, dept_id: int, name: str, parent_id: Optional[int] = None):
        dept = self.session.query(Department).get(dept_id)
        if dept:
            dept.name = name.strip()
            dept.parent_id = parent_id
            self.session.commit()
        return dept

    def delete_department(self, dept_id: int):
        dept = self.session.query(Department).get(dept_id)
        if dept:
            # Reassign employees to parent department or make them unassigned?
            # For now, we'll prevent deletion if it has children or employees
            if dept.children or dept.employees:
                raise ValueError("Cannot delete department that has sub-departments or employees.")
            self.session.delete(dept)
            self.session.commit()

    def get_employees_by_department(self, dept_id: Optional[int]) -> List[Employee]:
        query = self.session.query(Employee).filter(Employee.is_archived == False)
        if dept_id:
            query = query.filter(Employee.department_id == dept_id)
        else:
            query = query.filter(Employee.department_id == None)
        return query.all()

    def get_all_active_employees(self) -> List[Employee]:
        """Returns all non-archived employees with their department info pre-loaded."""
        from sqlalchemy.orm import joinedload
        return (
            self.session.query(Employee)
            .options(joinedload(Employee.dept_obj))
            .filter(Employee.is_archived == False)
            .order_by(Employee.last_name, Employee.first_name)
            .all()
        )

    def get_all_archived_employees(self) -> List[Employee]:
        """Returns all archived employees."""
        return (
            self.session.query(Employee)
            .filter(Employee.is_archived == True)
            .order_by(Employee.archived_at.desc())
            .all()
        )

    def archive_employee(self, emp_id: int, reason: str) -> bool:
        """Soft-delete an employee by setting is_archived=True."""
        from datetime import date
        emp = self.session.query(Employee).get(emp_id)
        if not emp:
            return False
        emp.is_archived = True
        emp.archived_at = date.today()
        emp.archive_reason = reason.strip() if reason else "No reason provided"
        self.session.commit()
        return True

    def reinstate_employee(self, emp_id: int) -> bool:
        """Reverse an archive by clearing archive fields."""
        emp = self.session.query(Employee).get(emp_id)
        if not emp:
            return False
        emp.is_archived = False
        emp.archived_at = None
        emp.archive_reason = None
        self.session.commit()
        return True

    def bulk_archive_employees(self, emp_ids: List[int], reason: str) -> bool:
        """Archive multiple employees in a single transaction."""
        from datetime import date
        try:
            employees = self.session.query(Employee).filter(Employee.id.in_(emp_ids)).all()
            for emp in employees:
                emp.is_archived = True
                emp.archived_at = date.today()
                emp.archive_reason = reason.strip() if reason else "Bulk archive"
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def bulk_reinstate_employees(self, emp_ids: List[int]) -> bool:
        """Reinstate multiple employees in a single transaction."""
        try:
            employees = self.session.query(Employee).filter(Employee.id.in_(emp_ids)).all()
            for emp in employees:
                emp.is_archived = False
                emp.archived_at = None
                emp.archive_reason = None
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            return False

    def add_employee(self, first_name: str, last_name: str, email: str, role_title: str, department_id: Optional[int], registry_num: Optional[str] = None, **kwargs):
        if registry_num:
            existing = self.session.query(Employee).filter(
                Employee.registration_number == registry_num,
                Employee.is_archived == False
            ).first()
            if existing:
                raise ValueError(f"Registration number {registry_num} is already used by an active employee.")
                
        emp = Employee(
            first_name=first_name,
            last_name=last_name,
            email=email,
            role_title=role_title,
            department_id=department_id,
            registration_number=registry_num,
            **kwargs
        )
        self.session.add(emp)
        self.session.commit()
        self._relink_attendance_records(emp)
        return emp

    def update_employee(self, emp_id: int, **kwargs):
        emp = self.session.query(Employee).get(emp_id)
        if emp:
            if "registration_number" in kwargs and kwargs["registration_number"]:
                reg_num = kwargs["registration_number"]
                existing = self.session.query(Employee).filter(
                    Employee.registration_number == reg_num,
                    Employee.is_archived == False,
                    Employee.id != emp_id
                ).first()
                if existing:
                    raise ValueError(f"Registration number {reg_num} is already used by another active employee.")

            for key, value in kwargs.items():
                if hasattr(emp, key):
                    setattr(emp, key, value)
            self.session.commit()
            self._relink_attendance_records(emp)
        return emp

    def _relink_attendance_records(self, emp: Employee):
        """
        Links all existing attendance records (punches) that were made using this 
        employee's registration number (REG) before the employee profile was properly 
        configured or after a REG number correction.
        """
        if not emp.registration_number:
            return
            
        from contragest.core.database import AttendanceRecord
        # Find records with the matching machine user_id but unlinked or incorrectly linked
        records = self.session.query(AttendanceRecord).filter(
            AttendanceRecord.zk_user_id == emp.registration_number,
            (AttendanceRecord.employee_id.is_(None)) | (AttendanceRecord.employee_id != emp.id)
        ).all()
        
        if records:
            for r in records:
                r.employee_id = emp.id
            self.session.commit()

    def delete_employee(self, emp_id: int):
        from contragest.core.database import AttendanceRecord, AttendanceCorrectionLog, EmployeeRotation, BiometricTemplate
        emp = self.session.query(Employee).get(emp_id)
        if emp:
            # Delete associated records to satisfy foreign key integrity
            if emp.registration_number:
                self.session.query(AttendanceRecord).filter(
                    (AttendanceRecord.employee_id == emp.id) | (AttendanceRecord.zk_user_id == emp.registration_number)
                ).delete(synchronize_session=False)
                
                self.session.query(AttendanceCorrectionLog).filter(
                    (AttendanceCorrectionLog.employee_id == emp.id) | (AttendanceCorrectionLog.reg_number == emp.registration_number)
                ).delete(synchronize_session=False)
                
                self.session.query(BiometricTemplate).filter(
                    BiometricTemplate.registration_number == emp.registration_number
                ).delete(synchronize_session=False)
            else:
                self.session.query(AttendanceRecord).filter(AttendanceRecord.employee_id == emp.id).delete(synchronize_session=False)
                self.session.query(AttendanceCorrectionLog).filter(AttendanceCorrectionLog.employee_id == emp.id).delete(synchronize_session=False)

            self.session.query(EmployeeRotation).filter(EmployeeRotation.employee_id == emp.id).delete(synchronize_session=False)

            self.session.delete(emp)
            self.session.commit()

    # ------------------------------------------------------------------ #
    #  Extended methods for Data Entry Interface
    # ------------------------------------------------------------------ #

    def get_all_departments(self) -> List[Department]:
        """Return a flat list of all departments for Combobox population."""
        return self.session.query(Department).order_by(Department.name).all()

    def search_departments(self, query: str) -> List[Department]:
        """Filter departments by name (case-insensitive) for autocomplete."""
        return (
            self.session.query(Department)
            .filter(Department.name.ilike(f"%{query}%"))
            .order_by(Department.name)
            .all()
        )

    def get_employee_full(self, emp_id: int) -> Optional[Employee]:
        """Load an employee with eagerly-loaded department relationship."""
        from sqlalchemy.orm import joinedload
        return (
            self.session.query(Employee)
            .options(joinedload(Employee.dept_obj))
            .filter(Employee.id == emp_id)
            .first()
        )

    def bulk_import_employees(self, records: list) -> tuple:
        """
        Bulk import a list of employee record dicts.

        Args:
            records: List of dicts with DB field names as keys.

        Returns:
            Tuple of (success_count, error_messages_list).
        """
        from datetime import datetime
        from contragest.features.pointage.sync_bus import sync_bus

        success = 0
        errors = []
        new_emp_ids = []

        for idx, record in enumerate(records, start=1):
            try:
                # Validate required fields
                first_name = record.get("first_name", "").strip()
                last_name = record.get("last_name", "").strip()
                if not first_name or not last_name:
                    errors.append(f"Row {idx}: Missing first_name or last_name")
                    continue

                # Resolve department name to ID if provided
                dept_id = None
                dept_name = record.pop("department", None)
                if dept_name:
                    # Robust lookup: strip both sides and use case-insensitive match
                    search_name = dept_name.strip()
                    dept = self.session.query(Department).all()
                    for d in dept:
                        if d.name.strip().lower() == search_name.lower():
                            dept_id = d.id
                            break

                # Parse date fields
                for date_field in ["dob", "hire_date", "exit_date"]:
                    val = record.get(date_field)
                    if val and isinstance(val, str):
                        try:
                            record[date_field] = datetime.strptime(val.strip(), "%Y-%m-%d").date()
                        except ValueError:
                            try:
                                record[date_field] = datetime.strptime(val.strip(), "%d/%m/%Y").date()
                            except ValueError:
                                record[date_field] = None

                # Parse integer fields
                for int_field in ["children_count"]:
                    val = record.get(int_field)
                    if val and isinstance(val, str):
                        try:
                            record[int_field] = int(val)
                        except ValueError:
                            record[int_field] = 0

                emp = Employee(
                    first_name=first_name,
                    last_name=last_name,
                    email=record.get("email"),
                    department_id=dept_id,
                    role_title=record.get("role_title"),
                    civility=record.get("civility"),
                    registration_number=record.get("registration_number"),
                    function=record.get("function"),
                    privilege=record.get("privilege"),
                    dob=record.get("dob"),
                    hire_date=record.get("hire_date"),
                    exit_date=record.get("exit_date"),
                    nationality=record.get("nationality"),
                    matrimonial_status=record.get("matrimonial_status"),
                    children_count=record.get("children_count", 0),
                    mobile_phone=record.get("mobile_phone"),
                    office_phone=record.get("office_phone"),
                    address=record.get("address"),
                    id_card_number=record.get("id_card_number"),
                    passport=record.get("passport"),
                    cnss=record.get("cnss"),
                    gross_salary=record.get("gross_salary"),
                    net_salary=record.get("net_salary"),
                )
                self.session.add(emp)
                self.session.flush() # Ensure ID is generated
                new_emp_ids.append(emp.id)
                success += 1

            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")

        if success > 0:
            self.session.commit()
            # Trigger background sync for all successfully imported employees
            for eid in new_emp_ids:
                sync_bus.publish_employee_update(eid)

        return success, errors
