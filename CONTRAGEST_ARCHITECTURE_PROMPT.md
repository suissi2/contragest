# Meta-Prompt: Contragest Interface Recreation

## Objective
Act as an expert Python UI/UX Developer specializing in desktop applications. Your goal is to recreate or extend a high-end, professional contract management system (codenamed **Contragest**) using a modern, data-dense, and security-focused architectural pattern.

## 1. Technical Stack
- **Framework:** Python with `ttkbootstrap` (primary theme: "superhero").
- **Database:** SQLAlchemy ORM with a local SQLite backend (`contragest.db`).
- **Icons:** Use professional SVG-style icons (via Lucide/Heroicons logic) or high-quality unicode symbols for Ribbon/Table actions.
- **Reporting:** `fpdf2` for professional PDF generation and `csv` for data exports.
- **Image Handling:** `Pillow` (PIL) for logo processing and UI assets.

## 2. Visual Identity: OLED Dark Mode
Achieve WCAG AAA compliance using the following "OLED-optimized" slate palette:
- **Background:** `#020617` (Deepest Navy/Black)
- **Surface/Panels:** `#1E293B` (Slate Grey-Blue)
- **Primary Actions:** `#22C55E` (Vibrant Success Green)
- **Primary Text:** `#F8FAFC` (Cloud White)
- **Secondary Text/Borders:** `#94A3B8` (Muted Slate)
- **Alerts (Danger):** `#EF4444` (Flash Red)
- **Alerts (Warning):** `#F59E0B` (Amber)

## 3. Layout Architecture
- **Navigation:** Top-mounted **Ribbon Menu** using a styled `ttk.Notebook` (Tab style: `Ribbon.TNotebook`).
  - **Tabs:** `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
- **Main Workspace:** A central area with hidden notebook tabs, synchronized with the Ribbon selection.
- **Status Bar:** Multi-part bottom bar containing:
  - **Left:** System Info (PC Name, Local IP).
  - **Center:** User Session (Username, Role).
  - **Middle-Right:** Environmental Data (Location, Real-time Weather).
  - **Right:** Live Digital Clock (`📅 DD/MM/YYYY  🕒 HH:MM:SS`).

## 4. Advanced UI Components
- **Flashing Tableview:**
  - A central `Tableview` displaying contract data.
  - **Columns:** Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
  - **Visual Alerts:** Critical rows (Expired/Expiring) must flash every 800ms using a dual-state tag configuration:
    - *State A (Active):* Vivid red/amber background.
    - *State B (Static):* Standard theme danger/warning background.
- **Ribbon Buttons:** Large, padded buttons (10px padding) with specific bootstyles (`INFO`, `LIGHT`, `SECONDARY`, `DANGER`, `outline-warning`).

## 5. Core Logic & Security
- **Seniority Calculation:** Dynamically compute months and days since `start_date` relative to `today`.
- **RBAC (Role-Based Access Control):** Implement a decorator-based permission system (`@AuthService.require_permission`). Admins bypass all checks.
- **Security Password for Deletion:** Sensitive actions (like contract deletion) require a daily rotating password calculated as:
  - `((day + month + (year % 100)) * 2) - 10`
- **Background Tasks:** Use a `BackgroundScheduler` to handle real-time environmental updates and automated expiration alerts without freezing the GUI.

## 6. Interaction Pattern
- **Enterprise Gateway:** Focus on high integrity, trust signals, and data density.
- **Modals:** Use `ttk.Toplevel` for forms (Contract Entry, Settings, User Management) with grouped `Labelframe` sections and specialized widgets like `DateEntry`.
