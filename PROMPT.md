# Contragest Interface Meta-Prompt

## Role & Expertise
You are a seasoned Python developer and an expert in creating high-performance graphical interfaces (GUI) and manipulating complex data structures. Your goal is to implement a professional contract management system named **Contragest**, following the technical and visual specifications below.

## Visual Identity & Design System
- **Theme:** `superhero` from `ttkbootstrap` (OLED Dark Mode aesthetic).
- **Palette:** Slate blue, deep navy (#020617), and grey, with high-contrast accent colors (Success: Green, Warning: Amber, Danger: Red).
- **Typography:**
  - **Headings:** Helvetica/Fira Code 24pt Bold.
  - **Stats/Labels:** Helvetica 11pt (inverse-secondary).
  - **Status Bar:** Helvetica 9pt.
- **Icons:** SVG/Lucide-style icons (e.g., 🏠, 👔, 🛠️, 📊, ✏️, 🗑️). No standard emojis for primary UI actions.
- **Image Optimization:** Use an image cache for UI assets (logos, icons) to minimize disk I/O.

## Layout Architecture
- **Navigation (Ribbon Menu):**
  - Implement a Ribbon-style navigation using `ttk.Notebook` (Style: `Ribbon.TNotebook`).
  - Tabs: '🏠 Home', '👔 HR', '🛠️ Tools', '📊 Reports'.
  - Contextual buttons within tabs using `INFO`, `LIGHT`, `SECONDARY`, and `DANGER` bootstyles.
- **Main Workspace:**
  - A central `ttk.Notebook` with hidden tabs, synchronized with the Ribbon selection.
  - **Home View:** Hero area with large logo, application title, and real-time statistics (Active/Expiring/Expired counts).
  - **Contracts View:** Data-dense `Tableview` with search and action buttons.
- **Status Bar:**
  - Multi-part bottom bar:
    - Left: PC Info (Hostname/IP).
    - Center: Session details (Username/Role).
    - Mid-Right: Environmental data (Location/Weather via background task).
    - Right: Live Digital Clock (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## Advanced Components & Interaction
- **Dynamic Tableview:**
  - **Columns:** Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
  - **Visual Alerts:** Implement a "flash" effect (800ms interval) for rows in 'Danger' (#ff4444) or 'Warning' (#ffbb33) states.
  - **Seniority Logic:** Dynamically calculate months and days since the start date.
- **Reporting System:**
  - Tabbed interface (Users, Spy/Audit, Employees, Contracts).
  - Advanced filtering: Global search, specific dropdowns (Role/Status/Department), and date range pickers.
  - Export support for CSV and PDF (using `fpdf`).
- **Security & RBAC:**
  - Role-Based Access Control (RBAC) to conditionally enable/render Ribbon tabs and action buttons.
  - Sensitive actions (like deletion) require a password calculated via a date-based formula: `((day + month + (year % 100)) * 2) - 10`.
- **i18n & Layout:**
  - Support for Internationalization (en, fr, ar) using JSON locale files.
  - RTL (Right-to-Left) support for layout packing (pack_start/pack_end helpers).

## Technical Stack
- **Language:** Python 3.10+
- **GUI Framework:** `ttkbootstrap` (wrapper for Tkinter).
- **ORM:** `SQLAlchemy` with `SQLite` (contragest.db).
- **Imaging:** `Pillow` (PIL) for image processing and logo rendering.
- **Reporting:** `fpdf` for PDF generation.
- **Background Tasks:** `threading` or a `BackgroundScheduler` for alerts and environmental updates.
- **Auth Core:** Modular authentication system with OTP support and audit logging.
