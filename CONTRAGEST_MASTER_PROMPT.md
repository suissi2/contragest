# Contragest Interface Development Prompt

You are a senior Python developer and UI/UX expert. Your task is to recreate or extend the "Contragest" enterprise contract management system. The application must adhere to the following technical and visual specifications:

## 1. Core Visual Identity: OLED Dark Mode
The interface uses a high-contrast, professional "OLED Dark Mode" aesthetic based on the `ttkbootstrap` 'superhero' theme, but customized with a deep palette:
- **Background:** `#020617` (Deepest Navy/Black)
- **Surface/Cards:** `#1E293B` (Slate Blue)
- **Primary/Success:** `#22C55E` (Vibrant Green)
- **Text (Primary):** `#F8FAFC` (Near White)
- **Text (Secondary/Muted):** `#94A3B8` (Soft Grey)
- **Accents:** Danger `#ff4444`, Warning `#ffbb33`.

## 2. Typography & Iconography
- **Headings:** Lexend (clean, modern, highly readable).
- **Body Text:** Source Sans 3 (professional, data-dense).
- **Icons:** Use high-fidelity SVG style icons (Lucide/Heroicons inspired). Do NOT use emojis as UI icons; replace with professional symbols where possible (though the current implementation uses Unicode symbols like 🏠, 👔, 🛠️, 📊 for tabs and actions).

## 3. Layout Architecture: Ribbon & Dashboard
- **Ribbon Menu:** A top navigation bar implemented as a `ttk.Notebook` (style: `Ribbon.TNotebook`).
  - **Tabs:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
  - **Behavior:** Switching Ribbon tabs updates the central workspace views.
- **Main Content Area:**
  - **Home:** Hero section with a centered 300x300 company logo and a statistics bar tracking "Active", "Expiring Soon", and "Expired" contracts.
  - **Contracts View:** A data-dense `Tableview` featuring columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority (calculated dynamically), Days Left, and Status.
- **Status Bar:** A multi-part bottom bar showing:
  - Left: Hostname and IP Address.
  - Center: Current user session details.
  - Middle-Right: Live weather and location data (🌍 Loading... initially).
  - Right: Live digital clock (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## 4. Advanced Components & Logic
- **Visual Alerts:** The Contracts table must feature a flashing effect (800ms interval) for critical states:
  - **Expired:** Flash between `#ff4444` and `#d9534f`.
  - **Expiring Soon:** Flash between `#ffbb33` and `#f0ad4e`.
- **Reports Module:** A tabbed Toplevel window providing specialized reports for Users, Spy (Audit Log), Employees, and Contracts, with global search, dropdown filters, and CSV/PDF export capabilities.
- **Security & RBAC:**
  - Role-Based Access Control (RBAC) where 'admin' bypasses all permission checks.
  - Deletion Password Formula: `((day + month + (year % 100)) * 2) - 10`.
- **Background Services:** A scheduler for environmental data updates and automated contract expiration alerts via email (SMTP).

## 5. Technical Stack
- **Backend:** Python 3.12+, SQLAlchemy ORM with SQLite.
- **Frontend:** `ttkbootstrap`, `tkinter`, `Pillow` (image handling).
- **Reporting:** `fpdf2` for PDF generation, `csv` for data export.
- **Architecture:** Modular feature-based structure (auth, dashboard, contracts, reports).

## Implementation Directives
- Ensure WCAG AAA compliance for the OLED dark theme.
- Implement smooth transitions (150-300ms) for UI state changes.
- Maintain strict repository hygiene: exclude `.db`, `.log`, and `__pycache__` from commits.
- Use `ttkbootstrap.widgets.tableview` instead of the deprecated `ttkbootstrap.tableview`.
