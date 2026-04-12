# Contragest Application Specification

## 1. Visual Identity & Theme
- **Framework**: Python with `ttkbootstrap`.
- **Primary Theme**: `superhero` (establishes an "OLED Dark Mode" aesthetic with slate blue and grey palette).
- **Core Aesthetic**: Professional, data-dense enterprise dashboard.
- **Typography**:
  - Main Heading: Helvetica 24 Bold ("Hero" style).
  - Stats/Subheaders: Helvetica 11 (bootstyle: `inverse-secondary`).
  - Status Bar: Helvetica 9 (bootstyle: `inverse-dark`).
  - Ribbon Tabs: Helvetica 10 Bold.
- **Color Palette**:
  - Danger (Expired): `#ff4444` (active) / `#d9534f` (static).
  - Warning (Expiring Soon): `#ffbb33` (active) / `#f0ad4e` (static).
  - Success (Active): `#5cb85c`.
  - Background: Standard Superhero slate dark.

## 2. Layout Architecture
- **Navigation**: Ribbon Menu (`Ribbon.TNotebook`) with categorized tabs:
  - `🏠 Home`: Dashboard stats, company logo, app configuration, session logout.
  - `👔 HR`: Employee and contract management shortcuts.
  - `🛠️ Tools`: User management, Audit Log (Mouchard), recovery tools (Admin only).
  - `📊 Reports`: Advanced analytics and reporting hub.
- **Main Workspace**: `Main.TNotebook` with tabs hidden (tabs layout cleared) to create a seamless view-switching experience controlled by the Ribbon.
- **Status Bar**: Multi-part dark toolbar at the bottom:
  - Left: System info (Host/IP).
  - Center: Session details (Username/Role).
  - Mid-Right: Environmental data (Location/Weather) updated via background thread.
  - Right: Live digital clock (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## 3. Core Features & Components
- **Dashboard Home**:
  - Stats bar showing Active vs. Expiring vs. Expired counts.
  - Hero area with large company logo and professional greeting.
- **Contracts Management**:
  - Tableview with columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
  - **Animated Alerts**: Table rows flash between vivid and standard colors for danger/warning states every 800ms.
  - Seniority Calculation: Dynamic computation of months and days since start date.
- **Reports Module**:
  - Tabbed interface (Users, Spy, Employees, Contracts).
  - Advanced filtering: Global search + dropdowns for Role/Status/Department.
  - Exporting: CSV and PDF (via `fpdf2`) with company logo and stylized headers.
- **Security & RBAC**:
  - AuthService managing Role-Based Access Control.
  - Sensitive actions (deletion, recovery) protected by a calculated dynamic password: `((day + month + (year % 100)) * 2) - 10`.
  - Mouchard (Spy) window for detailed audit logging of system actions.

## 4. Backend & Logic
- **ORM**: SQLAlchemy with SQLite (`contragest.db`).
- **Services**:
  - `EmailManager`: Thread-safe singleton with background workers and retry logic.
  - `BackgroundScheduler`: Manages periodic environmental updates and scheduled expiration alerts.
  - `LanguageManager`: Supports i18n (EN, FR, AR) via JSON locale files.

## 5. Implementation Prompt for LLM
> "Create a professional contract management dashboard using Python, `ttkbootstrap` (superhero theme), and SQLAlchemy. Implement a Ribbon-style navigation menu and a multi-part status bar with live system info and a clock. The main interface should feature a data-dense Tableview with conditional row coloring and a flashing animation effect (800ms interval) for expiring/expired items. Include a tabbed Reports window with CSV/PDF export capabilities. Ensure the architecture uses a service-oriented pattern for Authentication (RBAC), Audit Logging (Mouchard), and Background Tasks (Scheduler). Support internationalization (i18n) and use specialized widgets like DateEntry and Spinbox for data input forms."
