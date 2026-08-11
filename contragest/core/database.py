import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Boolean, Time, Float, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Database File Path
DB_NAME = "contragest.db"
# contragest/core/database.py -> up to core -> up to contragest (package)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# CONTRAGEST_DB_PATH lets the Windows service point at the bootstrap database
# that holds the real network DB path (db_custom_path) when the app is frozen
# (PyInstaller) and __file__ resolves to _MEIPASS/_internal.
DB_PATH = os.environ.get("CONTRAGEST_DB_PATH") or os.path.join(BASE_DIR, DB_NAME)
# On Windows, absolute paths need an extra slash (sqlite:////C:/...)
if os.name == 'nt' and os.path.isabs(DB_PATH):
    DATABASE_URL = f"sqlite:///{DB_PATH.replace(os.sep, '/')}"
else:
    DATABASE_URL = f"sqlite:///{DB_PATH}"

Base = declarative_base()

class AppConfig(Base):
    __tablename__ = 'app_config'

    id = Column(Integer, primary_key=True)
    alert_threshold_days = Column(Integer, default=30)
    smtp_server = Column(String, default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String, nullable=True)
    smtp_password = Column(String, nullable=True)  # In real app, consider encryption
    smtp_ssl_verify = Column(Boolean, default=True)
    notification_email = Column(String, nullable=True)
    automatic_alerts_enabled = Column(Boolean, default=True)
    alert_time = Column(String, default="09:00")
    last_alert_date = Column(Date, nullable=True)
    last_audit_date = Column(Date, nullable=True)        # Last day a daily audit was completed
    last_correction_date = Column(Date, nullable=True)   # Last day an auto-correction was completed
    language = Column(String, default="en")
    company_logo_path = Column(String, nullable=True)

    # SQLite database configuration
    db_custom_path = Column(String, nullable=True)        # Override DB file location (requires restart)
    db_journal_mode = Column(String, default="WAL")       # PRAGMA journal_mode
    db_cache_size_kb = Column(Integer, default=2000)      # PRAGMA cache_size (in KB)
    db_auto_vacuum = Column(Boolean, default=False)       # PRAGMA auto_vacuum

class Department(Base):
    __tablename__ = 'departments'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    
    parent = relationship("Department", remote_side=[id], backref="children")
    employees = relationship("Employee", back_populates="dept_obj")

    def __repr__(self):
        return f"Department({self.name})"

class DayStatus(Base):
    """Types of reference points for schedule and attendance calendar calculation."""
    __tablename__ = 'day_statuses'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # e.g. Normal, Repos, Férié, Congé
    code = Column(String(10), nullable=False)   # e.g. N, R, F, C
    color_hex = Column(String(10), default="#ffffff")
    is_worked_day = Column(Boolean, default=True)
    coefficient = Column(Float, default=1.0)
    
    def __repr__(self):
        return f"<DayStatus(name='{self.name}', code='{self.code}')>"

class PredefinedNote(Base):
    """Predefined annotations/notes available for manual assignment."""
    __tablename__ = 'predefined_notes'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    color_hex = Column(String(10), default="#ffffff")

    def __repr__(self):
        return f"<PredefinedNote(name='{self.name}')>"

class Employee(Base):
    __tablename__ = 'employees'

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    department = Column(String, nullable=True) # Legacy string field
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=True)
    role_title = Column(String, nullable=True)
    
    # New fields for enhanced Employee Manager
    civility = Column(String, nullable=True)
    registration_number = Column(String, nullable=True)
    office_phone = Column(String, nullable=True)
    mobile_phone = Column(String, nullable=True)
    function = Column(String, nullable=True)
    privilege = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    hire_date = Column(Date, nullable=True)
    id_card_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    photo_path = Column(String, nullable=True)
    is_auto_punch = Column(Boolean, default=False)
    weekly_day_off = Column(String, nullable=True)
    exit_date = Column(Date, nullable=True)

    
    # Newly requested modernization fields
    matrimonial_status = Column(String, nullable=True)
    children_count = Column(Integer, default=0)
    cnss = Column(String, nullable=True)
    passport = Column(String, nullable=True)
    nationality = Column(String, nullable=True)
    gross_salary = Column(String, nullable=True)
    net_salary = Column(String, nullable=True)
    
    # Archive fields (soft-delete)
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(Date, nullable=True)
    archive_reason = Column(String, nullable=True)
    
    dept_obj = relationship("Department", back_populates="employees")
    contracts = relationship("Contract", back_populates="employee", cascade="all, delete-orphan")
    assignments = relationship("EmployeeSchedule", back_populates="employee", cascade="all, delete-orphan")

    def __repr__(self):
        return f"{self.first_name} {self.last_name}"

class Contract(Base):
    __tablename__ = 'contracts'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    contract_type = Column(String, nullable=False)  # CDI, CDD, Stage, etc.
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # Nullable for CDI? Usually CDI has no end date, but for alerts we focus on CDD/End dates.
    document_path = Column(String, nullable=True)
    version = Column(Integer, default=1)
    updated_at = Column(Date, default=datetime.now, onupdate=datetime.now)
    
    employee = relationship("Employee", back_populates="contracts")
    history = relationship("ContractHistory", back_populates="contract", cascade="all, delete-orphan")

    def __repr__(self):
        return f"Contract({self.contract_type} - {self.employee.last_name})"

class ContractHistory(Base):
    __tablename__ = 'contract_history'
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey('contracts.id'), nullable=False)
    version_number = Column(Integer, nullable=False)
    change_date = Column(Date, default=datetime.now)
    change_reason = Column(String, nullable=True)
    
    # Snapshot fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    contract_type = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    contract = relationship("Contract", back_populates="history")


class ContractArchive(Base):
    __tablename__ = 'contract_archive'

    id = Column(Integer, primary_key=True)
    original_contract_id = Column(Integer)
    first_name = Column(String)  # Snapshot of first name
    last_name = Column(String)   # Snapshot of last name
    contract_type = Column(String)
    start_date = Column(Date)
    end_date = Column(Date, nullable=True)
    version = Column(Integer)
    deleted_at = Column(Date, default=datetime.now)
    reason = Column(String, nullable=True)


class CompanyProfile(Base):
    __tablename__ = 'company_profiles'

    id = Column(Integer, primary_key=True)
    code = Column(String(50), nullable=False, unique=True)
    raison_sociale = Column(String(200), nullable=False)
    responsable = Column(String(150), nullable=True)
    contact = Column(String(150), nullable=True)
    site_web = Column(String(200), nullable=True)
    email = Column(String(150), nullable=True)
    adresse = Column(String(500), nullable=True)
    code_postal = Column(String(20), nullable=True)
    ville = Column(String(100), nullable=True)
    telephone = Column(String(50), nullable=True)
    fax = Column(String(50), nullable=True)
    telex = Column(String(50), nullable=True)
    
    # Options Tab Booleans
    utilisation_fdcst = Column(Boolean, default=False)
    facturation_coffre = Column(Boolean, default=False)
    controle_nom_pax = Column(Boolean, default=False)
    devise = Column(String(50), nullable=True)
    nationalite = Column(String(100), nullable=True)
    
    # Options Tab (Taxe Sejour)
    taxe_sejour = Column(Boolean, default=False)
    transaction_taxe = Column(String(100), nullable=True)
    
    # Options Tab (Gestion bebes/enfants/adultes)
    bebe_gratuit = Column(Boolean, default=False)
    bebe_gestion = Column(Boolean, default=False)
    bebe_max = Column(Integer, default=0)
    
    enfant_gestion = Column(Boolean, default=False)
    enfant_max = Column(Integer, default=0)
    
    adulte_max = Column(Integer, default=0)
    logo_path = Column(String(500), nullable=True)

    # General / Other
    forme_juridique = Column(String(50), nullable=True)
    categories = Column(String(50), nullable=True)
    pays = Column(String(50), nullable=True)
    lbl_code_pays = Column(String(10), nullable=True)
    secteur_geographique = Column(String(100), nullable=True)
    activite = Column(String(100), nullable=True)
    date_creation = Column(Date, nullable=True)
    representant_juridique = Column(String(150), nullable=True)
    qualite = Column(String(100), nullable=True)

    # Administratif Tab
    code_tva = Column(String(50), nullable=True)
    police_assurance = Column(String(100), nullable=True)
    code_securite_sociale = Column(String(100), nullable=True)
    capital_social = Column(String(100), nullable=True)  # Using String due to 0.000 format requested
    
    # Applications Tab
    dossier_hotix = Column(String(200), nullable=True)
    
    # lblServeurs Tab
    ftp_url = Column(String(200), nullable=True)
    ftp_utilisateur = Column(String(100), nullable=True)
    ftp_mot_de_passe = Column(String(100), nullable=True)
    
    # Stamp Tab
    stamp_path = Column(String(500), nullable=True)
    
    email_configs = relationship("CompanyEmailConfig", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CompanyProfile(code='{self.code}', raison_sociale='{self.raison_sociale}')>"

# ─── Master Data Tables for Company Profile ─────────────────────────────────

class CompanyCategory(Base):
    """Governed list of company categories (e.g. Hotel, Agency, etc.)"""
    __tablename__ = 'company_categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    
    def __repr__(self):
        return f"Category({self.name})"

class LegalForm(Base):
    """Juridical structures (e.g. SARL, SA, SUARL)"""
    __tablename__ = 'legal_forms'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"LegalForm({self.name})"

class Activity(Base):
    """Industry sectors or activities"""
    __tablename__ = 'company_activities'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"Activity({self.name})"

class GeoSector(Base):
    """Geographical zones or sectors"""
    __tablename__ = 'geo_sectors'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)

    def __repr__(self):
        return f"GeoSector({self.name})"

class Country(Base):
    """Country master list"""
    __tablename__ = 'countries'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(10), nullable=True)

    def __repr__(self):
        return f"Country({self.name})"

class CompanyEmailConfig(Base):
    __tablename__ = 'company_email_configs'
    
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey('company_profiles.id'), nullable=False)
    type = Column(String(100), nullable=False)  # e.g., 'Mail Reservation', 'Mail Satisfaction'
    email = Column(String(150), nullable=True)
    login = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    smtp = Column(String(100), nullable=True)
    port = Column(Integer, default=0)
    ssl = Column(Boolean, default=False)
    authentifier = Column(Boolean, default=True)

    company = relationship("CompanyProfile", back_populates="email_configs")


class BiometricTemplate(Base):
    """
    Stores raw hardware bitmasks (biometric templates) for faces and fingers.
    Allows for identity backup and restoration to different physical machines.
    """
    __tablename__ = 'biometric_templates'

    id = Column(Integer, primary_key=True)
    registration_number = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)  # 'finger' or 'face'
    template_index = Column(Integer, default=0) # Finger index (0-9) or face index
    template_data = Column(String, nullable=False) # The raw bitmask (hex or base64)
    version = Column(Integer, default=10) # Template version (e.g., 9, 10, 11)
    synced_at = Column(Date, default=datetime.now)

    __table_args__ = (
        UniqueConstraint('registration_number', 'type', 'template_index', name='_reg_type_idx_uc'),
    )

    def __repr__(self):
        return f"<BiometricTemplate(reg={self.registration_number}, type={self.type}, idx={self.template_index})>"


# ─── Pointage (Time & Attendance) Models ────────────────────────────────────

class AttendanceMachine(Base):
    """Stores ZK attendance machine connection parameters."""
    __tablename__ = 'attendance_machines'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, default="Machine 1")
    ip_address = Column(String(45), nullable=False)
    port = Column(Integer, nullable=False, default=4370)
    
    # New identification fields
    machine_number = Column(Integer, default=1)
    comm_type = Column(String(50), default="Ethernet")
    baud_rate = Column(Integer, default=115200)
    product_name = Column(String(100), nullable=True)
    serial_number = Column(String(100), nullable=True)
    
    # Stats fields for the overview table
    user_count = Column(Integer, default=0)
    admin_count = Column(Integer, default=0)
    fingerprint_count = Column(Integer, default=0)
    password_count = Column(Integer, default=0)
    face_count = Column(Integer, default=0)
    face_cap = Column(Integer, default=0)
    punch_count = Column(Integer, default=0)

    username = Column(String(100), nullable=True)
    password = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    last_sync = Column(Date, nullable=True)

    # Auto reboot settings
    auto_reboot_enabled = Column(Boolean, default=False)
    auto_reboot_time = Column(String(5), default="03:00")  # HH:MM format

    records = relationship("AttendanceRecord", back_populates="machine", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<AttendanceMachine(name='{self.name}', ip='{self.ip_address}')>"


class AttendanceRecord(Base):
    """Logs individual attendance punches synced from the machine."""
    __tablename__ = 'attendance_records'

    id = Column(Integer, primary_key=True)
    # employee_id is nullable: ZK records arriving before an employee is registered
    # (or whose REG number is not yet set) are stored with employee_id=None.
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=True)
    machine_id = Column(Integer, ForeignKey('attendance_machines.id'), nullable=True)
    punch_time = Column(String, nullable=False)  # ISO timestamp string
    punch_type = Column(String(20), default="check_in")  # check_in / check_out
    synced_at = Column(Date, default=datetime.now)
    # Raw ZK user_id (= employee registration_number) stored for traceability
    zk_user_id = Column(String(50), nullable=True)

    employee = relationship("Employee")
    machine = relationship("AttendanceMachine", back_populates="records")

    def __repr__(self):
        return f"<AttendanceRecord(emp={self.employee_id}, zk={self.zk_user_id}, time='{self.punch_time}')>"


class WorkSchedule(Base):
    """Defines a named shift / work-schedule template."""
    __tablename__ = 'work_schedules'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # e.g. "Morning Shift"
    start_time = Column(String(5), nullable=False, default="08:00")
    end_time = Column(String(5), nullable=False, default="17:00")
    break_start = Column(String(5), nullable=True, default="12:00")
    break_end = Column(String(5), nullable=True, default="13:00")
    days_of_week = Column(String(50), default="Mon,Tue,Wed,Thu,Fri")  # CSV
    total_hours = Column(Float, default=8.0)
    
    # Advanced Segment Fields
    retard_tolere_mn = Column(Integer, default=0)
    depart_avance_tolere_mn = Column(Integer, default=0)
    debut_pointage_entree = Column(String(5), default="00:00")
    fin_pointage_entree = Column(String(5), default="23:59")
    debut_pointage_sortie = Column(String(5), default="00:00")
    fin_pointage_sortie = Column(String(5), default="23:59")
    compte_journee = Column(Float, default=1.0)
    compte_minute = Column(Integer, default=480)
    pointe_entree_obligatoire = Column(Boolean, default=True)
    pointe_sortie_obligatoire = Column(Boolean, default=True)
    color_hex = Column(String(10), default="#0055ff")

    assignments = relationship("EmployeeSchedule", back_populates="schedule", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<WorkSchedule(name='{self.name}')>"


class EmployeeSchedule(Base):
    """Links an employee to their assigned work schedule."""
    __tablename__ = 'employee_schedules'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    schedule_id = Column(Integer, ForeignKey('work_schedules.id'), nullable=False)
    effective_date = Column(Date, nullable=False)

    employee = relationship("Employee", back_populates="assignments")
    schedule = relationship("WorkSchedule", back_populates="assignments")

    def __repr__(self):
        return f"<EmployeeSchedule(emp={self.employee_id}, sched={self.schedule_id})>"


class ShiftRotation(Base):
    """Named rotating shift pattern (e.g. '3×8 Reception' = 21-day cycle)."""
    __tablename__ = 'shift_rotations'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    cycle_days = Column(Integer, nullable=False, default=21)
    description = Column(String(500), nullable=True)

    slots = relationship(
        "ShiftRotationSlot", back_populates="rotation",
        cascade="all, delete-orphan",
        order_by="ShiftRotationSlot.day_offset"
    )

    def __repr__(self):
        return f"<ShiftRotation(name='{self.name}', cycle={self.cycle_days}d)>"


class ShiftRotationSlot(Base):
    """Maps each day offset in the rotation cycle to a WorkSchedule."""
    __tablename__ = 'shift_rotation_slots'

    id = Column(Integer, primary_key=True)
    rotation_id = Column(Integer, ForeignKey('shift_rotations.id'), nullable=False)
    day_offset = Column(Integer, nullable=False)  # 0-based offset within cycle
    schedule_id = Column(Integer, ForeignKey('work_schedules.id'), nullable=False)

    rotation = relationship("ShiftRotation", back_populates="slots")
    schedule = relationship("WorkSchedule")

    def __repr__(self):
        return f"<ShiftRotationSlot(rotation={self.rotation_id}, day={self.day_offset})>"


class EmployeeRotation(Base):
    """Assigns an employee to a shift rotation pattern with an anchor date."""
    __tablename__ = 'employee_rotations'

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey('employees.id'), nullable=False)
    rotation_id = Column(Integer, ForeignKey('shift_rotations.id'), nullable=False)
    cycle_start_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True)

    employee = relationship("Employee")
    rotation = relationship("ShiftRotation")

    def __repr__(self):
        return f"<EmployeeRotation(emp={self.employee_id}, rot={self.rotation_id})>"


class MachineDepartment(Base):
    """Tracks which departments have been imported to an attendance machine."""
    __tablename__ = 'machine_departments'

    id = Column(Integer, primary_key=True)
    machine_id = Column(Integer, ForeignKey('attendance_machines.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    department_name = Column(String(150), nullable=False)
    synced_at = Column(Date, default=datetime.now)

    machine = relationship("AttendanceMachine")
    department = relationship("Department")

    def __repr__(self):
        return f"<MachineDepartment(dept='{self.department_name}', machine={self.machine_id})>"


class AttendanceCorrectionLog(Base):
    """
    Audit trail for every imputed or manually corrected attendance value.
    Raw machine records are NEVER modified - all corrections live here.
    """
    __tablename__ = 'attendance_correction_log'

    id           = Column(Integer, primary_key=True)
    employee_id  = Column(Integer, ForeignKey('employees.id'), nullable=True)
    reg_number   = Column(String(50), nullable=True)
    shift_date   = Column(String(10), nullable=False)    # YYYY-MM-DD of the shift start
    issue_type   = Column(String(50), nullable=False)    # 'MISSING_CHECK_IN' | 'MISSING_CHECK_OUT'
    original_val  = Column(String(30), nullable=True)    # None / raw timestamp
    imputed_val   = Column(String(50), nullable=True)    # e.g. '2026-03-07 23:00:00'
    strategy      = Column(String(30), nullable=True)    # 'SCHEDULE' | 'HISTORY' | 'MANUAL'
    corrected_by  = Column(String(100), default='SYSTEM')
    corrected_at  = Column(String(30))
    notes         = Column(String(500), nullable=True)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<CorrectionLog({self.shift_date} | {self.issue_type} | emp={self.employee_id})>"


class AttendanceRecordBackup(Base):
    """
    Point-in-time snapshot of attendance records.

    Produced by ``PointageService.backup_attendance_records()``.  Each backup
    run is tagged with a ``backup_label`` (e.g. '2026-03-04') so multiple
    independent backups can coexist in the same table.
    """
    __tablename__ = 'attendance_record_backups'

    id = Column(Integer, primary_key=True)
    # Original record id - not a FK, intentionally denormalised for backup safety
    source_record_id = Column(Integer, nullable=False)
    employee_id = Column(Integer, nullable=True)
    zk_user_id = Column(String(50), nullable=True)
    machine_id = Column(Integer, nullable=True)
    punch_time = Column(String, nullable=False)
    punch_type = Column(String(20), default="check_in")
    synced_at = Column(Date, nullable=True)
    backed_up_at = Column(Date, default=datetime.now)
    backup_label = Column(String(100), nullable=True)

    # Enhanced columns to match Treeview display
    employee_name = Column(String(200), nullable=True)
    department_name = Column(String(200), nullable=True)
    role_title = Column(String(200), nullable=True)
    machine_name = Column(String(100), nullable=True)
    check_in = Column(String(20), nullable=True)
    check_out = Column(String(20), nullable=True)
    punch_date = Column(String(20), nullable=True)
    out_record_id = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<AttendanceRecordBackup(src={self.source_record_id}, label='{self.backup_label}')>"


class DailyAttendance(Base):
    """
    Persisted, finalized daily summary for each employee.
    Used for historical reporting and dashboard speed.
    """
    __tablename__ = 'daily_attendance'

    id = Column(Integer, primary_key=True)
    date = Column(String(10), nullable=False) # YYYY-MM-DD
    reg_number = Column(String(50), nullable=False)
    employee_name = Column(String(200))
    department = Column(String(200))
    role = Column(String(200))
    schedule = Column(String(100))
    in1 = Column(String(20))
    out1 = Column(String(20))
    in2 = Column(String(20))
    out2 = Column(String(20))
    attendance_time = Column(String(20))
    work_time = Column(String(20))
    difference = Column(String(20))
    status = Column(String(50))
    note = Column(String(500))
    machine = Column(String(100))
    last_sync = Column(String(50))
    
    # Combined index for fast lookups
    # (date, reg_number) should be unique overall
    __table_args__ = (
        UniqueConstraint('date', 'reg_number', name='_date_reg_uc'),
    )

    def __repr__(self):
        return f"<DailyAttendance({self.date} | {self.reg_number} | {self.status})>"


class PublicHoliday(Base):
    """Stores public/national holidays for JF/JFB STAT computation."""
    __tablename__ = 'public_holidays'

    id          = Column(Integer, primary_key=True)
    date        = Column(String(10), nullable=False, unique=True)  # YYYY-MM-DD
    name        = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)

    def __repr__(self):
        return f"<PublicHoliday(date='{self.date}', name='{self.name}')>"


# Database Connection
# Read custom path from default local DB if it exists, before starting SQLAlchemy pool
import sqlite3
import os

_active_db_path = DB_PATH
if os.path.exists(DB_PATH):
    try:
        _temp_conn = sqlite3.connect(DB_PATH, timeout=10) # 10s timeout for network reliability
        _row = _temp_conn.execute("SELECT db_custom_path FROM app_config LIMIT 1").fetchone()
        _temp_conn.close()
        
        # If a custom path is set, verify we have permission to open or create it
        if _row and _row[0]:
            custom_db = _row[0]
            parent_dir = os.path.dirname(custom_db) or "."
            if os.path.isdir(parent_dir):
                try:
                    # Test we can write to the parent directory
                    test_file = os.path.join(parent_dir, ".db_write_test")
                    with open(test_file, "w") as f:
                        f.write("test")
                    os.remove(test_file)
                    
                    # Test we can open the database and read from it.
                    # Avoid DDL (CREATE/DROP TABLE) which requires an
                    # exclusive lock that may fail on network shares.
                    _test = sqlite3.connect(custom_db, timeout=10)
                    _test.execute("PRAGMA user_version;")
                    _test.execute("SELECT COUNT(*) FROM sqlite_master")
                    _test.close()
                    
                    _active_db_path = custom_db
                except Exception as e:
                    # Fallback to local DB if we can't open/read the custom one
                    print(f"Warning: Cannot access custom DB at {custom_db} ({e}). Falling back to default.")
            else:
                print(f"Warning: Directory for custom DB does not exist: {parent_dir}. Falling back to default.")
    except Exception:
        pass

# Determine SQLAlchemy URI based on the resolved active path
# On Windows and Linux, 3 slashes + absolute path is correct for local file paths
# (e.g., sqlite:///C:/users/... or sqlite:////var/lib/...)
if os.name == 'nt' and os.path.isabs(_active_db_path):
    ACTIVE_DATABASE_URL = f"sqlite:///{_active_db_path.replace(os.sep, '/')}"
else:
    ACTIVE_DATABASE_URL = f"sqlite:///{_active_db_path}"

# Optimized pool for network stability (SQLite on network drives prefers fewer concurrent writers)
engine = create_engine(
    ACTIVE_DATABASE_URL, 
    echo=False, 
    pool_size=10, 
    max_overflow=20,
    pool_timeout=60,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"timeout": 30} # sqlite3 busy_timeout (30 seconds)
)
SessionLocal = sessionmaker(bind=engine)

# Apply saved PRAGMAs from AppConfig on every new SQLite connection
from sqlalchemy import event as _sa_event

@_sa_event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, connection_record):
    """Apply PRAGMA settings from AppConfig on every new connection.
    
    IMPORTANT: Must NOT create a new SessionLocal() here - that would request
    another connection from the pool, firing this event again and causing
    infinite recursion. Instead, read config via the raw dbapi_conn cursor.
    
    Each PRAGMA is wrapped in its own try/except so that a failure on one
    (e.g. journal_mode on a read-only network share) does not kill the
    entire connection.
    """
    cursor = dbapi_conn.cursor()
    # Read current settings from AppConfig
    row = None
    try:
        row = cursor.execute(
            "SELECT db_journal_mode, db_cache_size_kb, db_auto_vacuum "
            "FROM app_config LIMIT 1"
        ).fetchone()
    except (sqlite3.OperationalError, Exception):
        pass

    # NETWORK RELIABILITY LOGIC:
    # SQLite WAL mode is NOT supported on network drives (UNC/SMB).
    # If the path looks like a network path, we force TRUNCATE mode.
    is_network = _active_db_path.startswith("//") or _active_db_path.startswith("\\\\")
    
    if row:
        journal_mode = row[0] or 'WAL'
        cache_size_kb = int(row[1]) if row[1] else 2000
        auto_vacuum = bool(row[2])
    else:
        journal_mode = 'WAL'
        cache_size_kb = 2000
        auto_vacuum = False

    if is_network:
        # Force switch to TRUNCATE for network safety
        if journal_mode == 'WAL':
            journal_mode = 'TRUNCATE'

    # Each PRAGMA is individually guarded so one failure doesn't
    # corrupt the connection for all subsequent queries.
    def _pragma(stmt):
        try:
            cursor.execute(stmt)
        except Exception:
            # Reset connection error state so subsequent queries work
            try:
                dbapi_conn.rollback()
            except Exception:
                pass

    if is_network:
        _pragma("PRAGMA synchronous=NORMAL")
        _pragma("PRAGMA mmap_size=0")

    _pragma(f"PRAGMA journal_mode={journal_mode}")
    _pragma(f"PRAGMA cache_size=-{cache_size_kb}")
    if auto_vacuum:
        _pragma("PRAGMA auto_vacuum=FULL")
    
    # Critical for network: Busy Timeout (60 seconds for higher latency)
    _pragma("PRAGMA busy_timeout=60000") 
    
    cursor.close()

    # Connection health check: verify the connection can execute a query.
    # If not, mark it for invalidation so SQLAlchemy discards it.
    try:
        check = dbapi_conn.cursor()
        check.execute("SELECT 1")
        check.close()
    except Exception:
        connection_record.invalidate()

def init_db():
    """Creates tables if they don't exist and initializes default config."""
    Base.metadata.create_all(engine)
    
    # Migration: Check if users table needs role_id column
    import sqlite3
    conn = sqlite3.connect(_active_db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'role_id' not in columns:
        print(f"Migrating database ({_active_db_path}): Adding role_id to users...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES auth_roles(id)")
            conn.commit()
            print("Migration successful: role_id column added.")
        except Exception as e:
            print(f"Migration error: {e}")
    else:
        print(f"Schema check: role_id column already exists in {_active_db_path}.")

    if 'auto_login' not in columns:
        print(f"Migrating database ({_active_db_path}): Adding auto_login to users...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN auto_login BOOLEAN DEFAULT 0")
            conn.commit()
            print("Migration successful: auto_login column added.")
        except Exception as e:
            print(f"Migration error: {e}")
    else:
        print(f"Schema check: auto_login column already exists in {_active_db_path}.")

    # Migration for Employees hierarchy and fields
    cursor.execute("PRAGMA table_info(employees)")
    emp_columns = [row[1] for row in cursor.fetchall()]
    
    new_cols = {
        'department_id': 'INTEGER REFERENCES departments(id)',
        'role_title': 'TEXT',
        'civility': 'TEXT',
        'registration_number': 'TEXT',
        'office_phone': 'TEXT',
        'mobile_phone': 'TEXT',
        'function': 'TEXT',
        'privilege': 'TEXT',
        'dob': 'DATE',
        'hire_date': 'DATE',
        'id_card_number': 'TEXT',
        'address': 'TEXT',
        'photo_path': 'TEXT',
        'matrimonial_status': 'TEXT',
        'children_count': 'INTEGER',
        'cnss': 'TEXT',
        'passport': 'TEXT',
        'nationality': 'TEXT',
        'gross_salary': 'TEXT',
        'net_salary': 'TEXT',
        'is_auto_punch': 'BOOLEAN DEFAULT 0',
        'weekly_day_off': 'TEXT',
        'exit_date': 'DATE',
        # Archive fields
        'is_archived': 'INTEGER NOT NULL DEFAULT 0',
        'archived_at': 'DATE',
        'archive_reason': 'TEXT',
    }

    added_any = False
    for col_name, col_type in new_cols.items():
        if col_name not in emp_columns:
            print(f"Migrating employees: Adding {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE employees ADD COLUMN {col_name} {col_type}")
                added_any = True
            except Exception as e:
                print(f"Migration error (employees, {col_name}): {e}")
    
    if added_any:
        conn.commit()
        print("Migration successful: employees table updated.")

    # Migration for attendance_machines biometric stats
    cursor.execute("PRAGMA table_info(attendance_machines)")
    mach_columns = [row[1] for row in cursor.fetchall()]
    
    mach_new_cols = {
        'face_count': 'INTEGER DEFAULT 0',
        'face_cap': 'INTEGER DEFAULT 0',
        'auto_reboot_enabled': 'BOOLEAN DEFAULT 0',
        'auto_reboot_time': 'TEXT DEFAULT "03:00"',
    }
    
    added_mach = False
    for col_name, col_type in mach_new_cols.items():
        if col_name not in mach_columns:
            print(f"Migrating attendance_machines: Adding {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE attendance_machines ADD COLUMN {col_name} {col_type}")
                added_mach = True
            except Exception as e:
                print(f"Migration error (attendance_machines, {col_name}): {e}")
    
    if added_mach:
        conn.commit()
        print("Migration successful: attendance_machines table updated.")
    else:
        print("Schema check: attendance_machines table is up to date.")

    # Migration for daily_attendance
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_attendance'")
    if not cursor.fetchone():
        print("Migrating: Creating daily_attendance table...")
        try:
            cursor.execute("""
                CREATE TABLE daily_attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    reg_number TEXT NOT NULL,
                    employee_name TEXT,
                    department TEXT,
                    role TEXT,
                    schedule TEXT,
                    in1 TEXT,
                    out1 TEXT,
                    in2 TEXT,
                    out2 TEXT,
                    attendance_time TEXT,
                    work_time TEXT,
                    difference TEXT,
                    status TEXT,
                    note TEXT,
                    machine TEXT,
                    last_sync TEXT,
                    UNIQUE(date, reg_number)
                )
            """)
            conn.commit()
            print("daily_attendance table created successfully.")
        except Exception as e:
            print(f"Migration error (daily_attendance): {e}")

    print("Schema check: employees table is up to date.")

    # Migration: ensure predefined_notes table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='predefined_notes'")
    if not cursor.fetchone():
        print("Migrating: Creating predefined_notes table...")
        try:
            cursor.execute("""
                CREATE TABLE predefined_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    color_hex TEXT DEFAULT '#ffffff'
                )
            """)
            conn.commit()
            print("predefined_notes table created successfully.")
        except Exception as e:
            print(f"Migration error (predefined_notes): {e}")
    else:
        print("Schema check: predefined_notes table already exists.")

    # Migration: ensure machine_departments table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='machine_departments'")
    if not cursor.fetchone():
        print("Migrating: Creating machine_departments table...")
        try:
            cursor.execute("""
                CREATE TABLE machine_departments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    machine_id INTEGER NOT NULL REFERENCES attendance_machines(id),
                    department_id INTEGER NOT NULL REFERENCES departments(id),
                    department_name TEXT NOT NULL,
                    synced_at DATE
                )
            """)
            conn.commit()
            print("Migration successful: machine_departments table created.")
        except Exception as e:
            print(f"Migration error (machine_departments): {e}")
    else:
        print("Schema check: machine_departments table already exists.")

    # Migration: attendance_records - add zk_user_id column if missing
    cursor.execute("PRAGMA table_info(attendance_records)")
    ar_columns = [row[1] for row in cursor.fetchall()]
    if 'zk_user_id' not in ar_columns:
        print("Migrating attendance_records: Adding zk_user_id column...")
        try:
            cursor.execute("ALTER TABLE attendance_records ADD COLUMN zk_user_id TEXT")
            conn.commit()
            print("Migration successful: zk_user_id column added to attendance_records.")
        except Exception as e:
            print(f"Migration error (attendance_records, zk_user_id): {e}")
    else:
        print("Schema check: attendance_records.zk_user_id already exists.")

    # Migration: attendance_records - drop NOT NULL constraint on employee_id if present
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='attendance_records'")
    row = cursor.fetchone()
    if row and row[0]:
        create_sql = row[0]
        if "employee_id INTEGER NOT NULL" in create_sql:
            print("Migrating attendance_records: dropping NOT NULL constraint on employee_id...")
            try:
                new_sql = create_sql.replace("employee_id INTEGER NOT NULL", "employee_id INTEGER")
                new_sql = new_sql.replace("CREATE TABLE attendance_records", "CREATE TABLE _attendance_records_new")
                
                cursor.execute("PRAGMA foreign_keys=off")
                cursor.execute(new_sql)
                cursor.execute("""
                    INSERT INTO _attendance_records_new (id, employee_id, machine_id, punch_time, punch_type, synced_at, zk_user_id)
                    SELECT id, employee_id, machine_id, punch_time, punch_type, synced_at, zk_user_id FROM attendance_records
                """)
                cursor.execute("DROP TABLE attendance_records")
                cursor.execute("ALTER TABLE _attendance_records_new RENAME TO attendance_records")
                conn.commit()
                cursor.execute("PRAGMA foreign_keys=on")
                print("Migration successful: employee_id is now nullable in attendance_records.")
            except Exception as e:
                print(f"Migration error (attendance_records NOT NULL drop): {e}")

    # Migration: create attendance_record_backups table if missing
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_record_backups'"
    )
    if not cursor.fetchone():
        print("Migrating: Creating attendance_record_backups table...")
        try:
            cursor.execute("""
                CREATE TABLE attendance_record_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_record_id INTEGER NOT NULL,
                    employee_id INTEGER,
                    zk_user_id TEXT,
                    machine_id INTEGER,
                    punch_time TEXT NOT NULL,
                    punch_type TEXT DEFAULT 'check_in',
                    synced_at DATE,
                    backed_up_at DATE,
                    backup_label TEXT
                )
            """)
            conn.commit()
            print("Migration successful: attendance_record_backups table created.")
        except Exception as e:
            print(f"Migration error (attendance_record_backups): {e}")
    else:
        print("Schema check: attendance_record_backups table already exists.")

    # Migration: create attendance_correction_log table if missing
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='attendance_correction_log'"
    )
    if not cursor.fetchone():
        print("Migrating: Creating attendance_correction_log table...")
        try:
            cursor.execute("""
                CREATE TABLE attendance_correction_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER REFERENCES employees(id),
                    reg_number TEXT,
                    shift_date TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    original_val TEXT,
                    imputed_val TEXT,
                    strategy TEXT,
                    corrected_by TEXT DEFAULT 'SYSTEM',
                    corrected_at TEXT,
                    notes TEXT
                )
            """)
            conn.commit()
            print("Migration successful: attendance_correction_log table created.")
        except Exception as e:
            print(f"Migration error (attendance_correction_log): {e}")
    else:
        print("Schema check: attendance_correction_log table already exists.")

    # Migration: attendance_record_backups - add metadata and pairing columns if missing
    cursor.execute("PRAGMA table_info(attendance_record_backups)")
    arb_columns = [row[1] for row in cursor.fetchall()]
    new_arb_cols = {
        'employee_name': 'TEXT',
        'department_name': 'TEXT',
        'role_title': 'TEXT',
        'machine_name': 'TEXT',
        'check_in': 'TEXT',
        'check_out': 'TEXT',
        'punch_date': 'TEXT',
        'out_record_id': 'INTEGER'
    }
    added_any_arb = False
    for col_name, col_type in new_arb_cols.items():
        if col_name not in arb_columns:
            print(f"Migrating attendance_record_backups: Adding {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE attendance_record_backups ADD COLUMN {col_name} {col_type}")
                added_any_arb = True
            except Exception as e:
                print(f"Migration error (attendance_record_backups, {col_name}): {e}")
    if added_any_arb:
        conn.commit()
        print("Migration successful: attendance_record_backups updated.")

    # Migration: work_schedules - add segment columns if missing
    cursor.execute("PRAGMA table_info(work_schedules)")
    ws_columns = [row[1] for row in cursor.fetchall()]
    new_ws_cols = {
        'retard_tolere_mn': 'INTEGER DEFAULT 0',
        'depart_avance_tolere_mn': 'INTEGER DEFAULT 0',
        'debut_pointage_entree': 'VARCHAR(5) DEFAULT "00:00"',
        'fin_pointage_entree': 'VARCHAR(5) DEFAULT "23:59"',
        'debut_pointage_sortie': 'VARCHAR(5) DEFAULT "00:00"',
        'fin_pointage_sortie': 'VARCHAR(5) DEFAULT "23:59"',
        'compte_journee': 'FLOAT DEFAULT 1.0',
        'compte_minute': 'INTEGER DEFAULT 480',
        'pointe_entree_obligatoire': 'BOOLEAN DEFAULT 1',
        'pointe_sortie_obligatoire': 'BOOLEAN DEFAULT 1',
        'color_hex': 'VARCHAR(10) DEFAULT "#0055ff"'
    }
    added_any_ws = False
    for col_name, col_type in new_ws_cols.items():
        if col_name not in ws_columns:
            print(f"Migrating work_schedules: Adding {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE work_schedules ADD COLUMN {col_name} {col_type}")
                added_any_ws = True
            except Exception as e:
                print(f"Migration error (work_schedules, {col_name}): {e}")
    if added_any_ws:
        conn.commit()
        print("Migration successful: work_schedules updated.")

    # Migration: attendance_machines - add new identification columns
    cursor.execute("PRAGMA table_info(attendance_machines)")
    am_columns = [row[1] for row in cursor.fetchall()]
    new_am_cols = {
        'machine_number': 'INTEGER DEFAULT 1',
        'comm_type': "TEXT DEFAULT 'Ethernet'",
        'baud_rate': 'INTEGER DEFAULT 115200',
        'product_name': 'TEXT',
        'serial_number': 'TEXT',
        'user_count': 'INTEGER DEFAULT 0',
        'admin_count': 'INTEGER DEFAULT 0',
        'fingerprint_count': 'INTEGER DEFAULT 0',
        'password_count': 'INTEGER DEFAULT 0',
        'punch_count': 'INTEGER DEFAULT 0'
    }
    added_any_am = False
    for col_name, col_type in new_am_cols.items():
        if col_name not in am_columns:
            print(f"Migrating attendance_machines: Adding {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE attendance_machines ADD COLUMN {col_name} {col_type}")
                added_any_am = True
            except Exception as e:
                print(f"Migration error (attendance_machines, {col_name}): {e}")
    if added_any_am:
        conn.commit()
        print("Migration successful: attendance_machines updated.")

    # Migration: app_config - add SQLite configuration columns if missing
    cursor.execute("PRAGMA table_info(app_config)")
    appconfig_columns = [row[1] for row in cursor.fetchall()]
    new_appconfig_cols = {
        'db_custom_path':   'TEXT',
        'db_journal_mode':  "TEXT DEFAULT 'WAL'",
        'db_cache_size_kb': 'INTEGER DEFAULT 2000',
        'db_auto_vacuum':   'BOOLEAN DEFAULT 0',
        'last_audit_date':  'DATE',
        'last_correction_date': 'DATE',
    }
    added_any_ac = False
    for col_name, col_type in new_appconfig_cols.items():
        if col_name not in appconfig_columns:
            print(f"Migrating app_config: Adding {col_name}...")
            try:
                cursor.execute(f"ALTER TABLE app_config ADD COLUMN {col_name} {col_type}")
                added_any_ac = True
            except Exception as e:
                print(f"Migration error (app_config, {col_name}): {e}")
    if added_any_ac:
        conn.commit()
        print("Migration successful: app_config updated.")

    # Migration: create day_statuses table if missing
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='day_statuses'"
    )
    if not cursor.fetchone():
        print("Migrating: Creating day_statuses table...")
        try:
            cursor.execute("""
                CREATE TABLE day_statuses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    code TEXT NOT NULL,
                    color_hex TEXT DEFAULT '#ffffff',
                    is_worked_day BOOLEAN DEFAULT 1,
                    coefficient FLOAT DEFAULT 1.0
                )
            """)
            conn.commit()
            print("Migration successful: day_statuses table created.")
        except Exception as e:
            print(f"Migration error (day_statuses): {e}")
    else:
        print("Schema check: day_statuses table already exists.")


    # Migration: create shift_rotations table if missing
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='shift_rotations'"
    )
    if not cursor.fetchone():
        print("Migrating: Creating shift_rotations table...")
        try:
            cursor.execute("""
                CREATE TABLE shift_rotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    cycle_days INTEGER NOT NULL DEFAULT 21,
                    description TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE shift_rotation_slots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rotation_id INTEGER NOT NULL REFERENCES shift_rotations(id),
                    day_offset INTEGER NOT NULL,
                    schedule_id INTEGER NOT NULL REFERENCES work_schedules(id)
                )
            """)
            cursor.execute("""
                CREATE TABLE employee_rotations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL REFERENCES employees(id),
                    rotation_id INTEGER NOT NULL REFERENCES shift_rotations(id),
                    cycle_start_date DATE NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            """)
            conn.commit()
            print("Migration successful: shift rotation tables created.")
        except Exception as e:
            print(f"Migration error (shift_rotations): {e}")
    else:
        print("Schema check: shift_rotations tables already exist.")

    # Migration: create public_holidays table if missing
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='public_holidays'"
    )
    if not cursor.fetchone():
        print("Migrating: Creating public_holidays table...")
        try:
            cursor.execute("""
                CREATE TABLE public_holidays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    description TEXT
                )
            """)
            conn.commit()
            print("Migration successful: public_holidays table created.")
        except Exception as e:
            print(f"Migration error (public_holidays): {e}")
    else:
        print("Schema check: public_holidays table already exists.")

    conn.close()

    # Make sure SQLAlchemy Base metadata creates any other missing items
    try:
        Base.metadata.create_all(engine)
    except Exception as e:
        print(f"Error in Base.metadata.create_all: {e}")

    # Register Audit Listeners (Currently disabled as file is missing)
    # try:
    #     from contragest.core.audit_listeners import register_audit_listeners
    #     from contragest.features.auth.service import User, Role
    #     register_audit_listeners([AppConfig, CompanyProfile, User, Role])
    #     print("Audit listeners registered successfully.")
    # except Exception as e:
    #     print(f"Error registering audit listeners: {e}")

    # Initialize default config if missing
    session = SessionLocal()
    config = session.query(AppConfig).first()
    if not config:
        default_config = AppConfig()
        session.add(default_config)
        session.commit()
    
    # Seed Company Master Data if missing
    if not session.query(CompanyCategory).first():
        cats = ["Hotel", "Agency", "Enterprise", "Other"]
        for c in cats: session.add(CompanyCategory(name=c))
    
    if not session.query(LegalForm).first():
        forms = ["SARL", "SUARL", "SA", "Personne Physique", "Other"]
        for f in forms: session.add(LegalForm(name=f))

    if not session.query(Activity).first():
        acts = ["Tourisme", "Industrie", "Commerce", "Services", "Other"]
        for a in acts: session.add(Activity(name=a))

    if not session.query(GeoSector).first():
        sects = ["Grand Tunis", "Sahel", "Nord", "Sud", "International"]
        for s in sects: session.add(GeoSector(name=s))

    if not session.query(Country).first():
        countries = [("Tunisie", "TN"), ("France", "FR"), ("Algérie", "DZ"), ("Libye", "LY")]
        for n, c in countries: session.add(Country(name=n, code=c))
    
    session.commit()
    session.close()

def get_db():
    """Dependency for DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
