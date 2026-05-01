# CONTRAGEST MASTER PROMPT: High-Fidelity Interface Recreation

## 1. IDENTITY & VISION
Recreate the **Contragest** interface, an "Enterprise Gateway" and "Data-Dense Dashboard" designed for professional contract management. The interface must embody a sophisticated **OLED Dark Mode** aesthetic, ensuring high contrast, WCAG AAA compliance, and an elite "Cyberpunk-meets-Corporate" feel.

## 2. VISUAL TOKENS (OLED DARK MODE)
Apply the following hexadecimal palette and typography to all components:
- **Background:** `#020617` (Deep Slate Black)
- **Surface/Cards:** `#1E293B` (Slate Grey)
- **Primary/Success:** `#22C55E` (Emerald Green)
- **Primary Text:** `#F8FAFC` (Ghost White)
- **Muted Text:** `#94A3B8` (Slate Muted)
- **Danger/Alert:** `#ff4444` (Vivid Red)
- **Warning:** `#ffbb33` (Amber)

### Typography
- **Headings:** `Lexend` (Clean, geometric, high readability)
- **Sub-headers:** `Playfair Display SC` (Small caps, elegant, authoritative)
- **Body/Data:** `Source Sans 3` (Functional, professional)

## 3. LAYOUT ARCHITECTURE
### A. Ribbon Navigation System
Implement a top-mounted `ttk.Notebook` styled as a **Ribbon Menu** with the following tabs:
1. **🏠 Home:** Dashboard navigation, application settings, company profile, and session controls (Logout/Exit).
2. **👔 HR:** Employee management and contract workspace access.
3. **🛠️ Tools:** Administrative utilities (User Management, Audit Log/Mouchard), visible only to 'admin' roles.
4. **📊 Reports:** Analytics hub for Users, Spy/Audit, Employees, and Contracts.

### B. Dashboard Hero Section
- A centered **Hero Area** featuring a high-resolution `300x300` company logo.
- Main title "Contragest" in `Lexend` 24pt Bold.
- Subtitle "Professional Contract Management System" in `Source Sans 3` 14pt.

### C. Multi-Part Status Bar (Bottom)
A sophisticated `DARK` bootstyle status bar containing:
- **Left:** PC Info (💻 Hostname & Local IP).
- **Center-Left:** Session Info (Logged in as: Username).
- **Center-Right:** Environmental Data (🌍 Location & 🌡️ Real-time Weather).
- **Right:** Live Digital Clock (📅 DD/MM/YYYY  🕒 HH:M:S).

## 4. COMPONENT LOGIC & UX
### A. Intelligent Tableview (Contracts)
- **Columns:** Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
- **Dynamic Alerts:** Implement a **flashing animation** (800ms interval) for critical rows.
    - **Expired:** Flash between `#ff4444` and `#d9534f`.
    - **Expiring Soon:** Flash between `#ffbb33` and `#f0ad4e`.
- **Seniority Calculation:** Real-time logic computing total months and days since `start_date`.

### B. Security & RBAC
- Role-Based Access Control (RBAC) with an **Admin Bypass**.
- Sensitive actions (Deletion/Recovery) require a **Dynamic Security Password** calculated via formula: `((day + month + year_short) * 2) - 10`.

### C. Advanced Reports
- Tabbed interface with global search and multi-criteria filters (Dropdowns for Role/Status/Department).
- Export capabilities for **CSV** and **High-Fidelity PDF** (utilizing `fpdf2` with logo headers).

## 5. TECHNICAL STACK (PYTHON)
- **GUI:** `ttkbootstrap` (Theme: `superhero` with OLED overrides).
- **Database:** `SQLAlchemy` ORM with SQLite.
- **Imaging:** `Pillow` (PIL) for image resizing and caching.
- **Automation:** `BackgroundScheduler` for real-time weather updates and automated email alerts.
