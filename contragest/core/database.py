import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Database File Path
DB_NAME = "contragest.db"
# contragest/core/database.py -> up to core -> up to contragest (package)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)
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
    language = Column(String, default="en")
    company_logo_path = Column(String, nullable=True)

class Employee(Base):
    __tablename__ = 'employees'

    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    department = Column(String, nullable=True)
    
    contracts = relationship("Contract", back_populates="employee", cascade="all, delete-orphan")

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

# Database Connection
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    """Creates tables if they don't exist and initializes default config."""
    Base.metadata.create_all(engine)
    
    # Migration: Check if users table needs role_id column
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'role_id' not in columns:
        print(f"Migrating database ({DB_PATH}): Adding role_id to users...")
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN role_id INTEGER REFERENCES auth_roles(id)")
            conn.commit()
            print("Migration successful: role_id column added.")
        except Exception as e:
            print(f"Migration error: {e}")
    else:
        print("Schema check: role_id column already exists.")
    conn.close()

    # Initialize default config if missing
    session = SessionLocal()
    config = session.query(AppConfig).first()
    if not config:
        default_config = AppConfig()
        session.add(default_config)
        session.commit()
    session.close()

def get_db():
    """Dependency for DB Session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
