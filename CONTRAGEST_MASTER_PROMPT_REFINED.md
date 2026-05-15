# CONTRAGEST MASTER PROMPT: High-Fidelity Enterprise Interface

This master prompt is designed to guide the recreation or extension of the **Contragest** Contract Management System, focusing on its specific "Cyberpunk-meets-Corporate" visual identity and robust UI architecture.

---

## 1. Visual Identity & Design System
- **Theme Name:** Enterprise Gateway / OLED Dark Mode.
- **Core Aesthetic:** High-contrast, space-efficient, data-dense interface designed for OLED screens to minimize eye strain and energy consumption.
- **Color Palette:**
  - **Background:** `#020617` (True OLED Black)
  - **Surface/Cards:** `#1E293B` (Deep Slate)
  - **Primary Action:** `#22C55E` (Vibrant Green)
  - **Text (Primary):** `#F8FAFC` (Ghost White)
  - **Text (Muted):** `#94A3B8` (Slate Grey)
  - **Status - Danger:** Flash `#ff4444` / Static `#d9534f`
  - **Status - Warning:** Flash `#ffbb33` / Static `#f0ad4e`
- **Typography:**
  - **Headers:** *Lexend* (Geometric, high readability)
  - **Branding Accents:** *Playfair Display SC* (Serif elegance)
  - **Body/Data:** *Source Sans 3* (Professional sans-serif)
  - **Technical/Code:** *Fira Code* (Monospaced for data grids)

---

## 2. Technical Architecture (Python Stack)
- **UI Framework:** `ttkbootstrap` (utilizing a customized 'superhero' theme base).
- **Imaging:** `Pillow (PIL)` for dynamic logo resizing and weather icon rendering.
- **Database:** `SQLAlchemy` ORM with a `SQLite` backend (`contragest.db`).
- **Reporting:** `fpdf2` for professional PDF generation with integrated branding.
- **Security:** `AuthService` with Role-Based Access Control (RBAC) and OTP-based MFA.

---

## 3. UI Layout & Component Specifications

### A. Ribbon Navigation Menu
- **Tabs:** Home (Dashboard/Settings), HR (Employees/Contracts), Tools (User Management/Audit), Reports.
- **Structure:** `ttk.LabelFrame` groupings within `ttk.Frame` tabs. Large buttons with consistent padding (10) and semantic bootstyles (INFO, LIGHT, SECONDARY, DANGER).
- **Logic:** Conditional rendering based on user permissions via the `AuthService`.

### B. Dynamic Dashboard (Hero Section)
- **Top Stats Bar:** Horizontal strip tracking "Active", "Expiring", and "Expired" contracts with inverse-secondary styling.
- **Hero Area:** Centered `300x300` company logo (`assets/company_logo.jpg`) with professional typography overlay.
- **Alert Integration:** Real-time contract monitoring with automatic startup notification triggers.

### C. Advanced Tableview & Alerts
- **Component:** `ttkbootstrap.widgets.tableview`.
- **Alert Logic:** Conditional row formatting for contract status.
- **Visual Effects:** 800ms flash interval for critical items (Expired/Expiring) using the defined Danger/Warning palette.

### D. Multi-Tabbed Reports Module
- **Tabs:** Users, Spy (Audit Log), Employees, Contracts.
- **Features:**
  - Global real-time search filters.
  - Column-specific dropdown filters (Role, Status, Department, Type).
  - Date range filters with toggle switches.
  - Export functionality: CSV (standard) and PDF (branded with logo, page headers, and zebra-striped rows).

### E. Professional Status Bar (Footer)
- **System Info:** IP Address and PC Name display.
- **Environment:** Location-based weather status with dynamic SVG-style icons.
- **Time:** Real-time ticking clock (Helvetica 9, inverse-dark).

---

## 4. Functional Logic Patterns
- **RBAC:** Strictly enforced access levels. Role 'admin' provides a total system bypass.
- **Audit Logging (Mouchard):** Every state change (Create, Edit, Delete) is logged with a timestamp, user ID, and change justification.
- **Email Service:** SMTP integration with TLS/SSL support, including a "Test Connection" diagnostic tool and automated daily alerts for expiring contracts.
- **Form Patterns:** `ttk.Toplevel` modals with standardized layouts (`pack_start`/`pack_end` helpers), justification prompts for edits, and security re-authentication for non-admin users.

---

*Use this prompt to recreate the Contragest environment, ensuring adherence to the OLED palette and the modular Python-based architecture.*
