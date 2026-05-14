# Contragest Interface Master Prompt

You are a specialized UI/UX Engineer and Python Developer. Your task is to recreate or extend the "Contragest" enterprise interface, a high-fidelity hospitality management dashboard inspired by the provided branding (Vincci Hoteles).

### 1. Visual Identity & Design Tokens
- **Theme Concept:** "Enterprise Gateway" / "Cyberpunk-meets-Corporate". A professional OLED Dark Mode designed for high contrast and WCAG AAA compliance.
- **Color Palette (OLED Slate):**
  - **Background:** `#020617` (Deep Black)
  - **Surface/Cards:** `#1E293B` (Slate Grey)
  - **Primary/Success:** `#22C55E` (Vivid Green)
  - **Text (Primary):** `#F8FAFC` (Anti-flash White)
  - **Text (Muted):** `#94A3B8` (Slate Muted)
  - **Alert (Danger):** `#ff4444` (Flash) / `#d9534f` (Static)
  - **Alert (Warning):** `#ffbb33` (Flash) / `#f0ad4e` (Static)
- **Typography Pairing:**
  - **Brand Accents:** Playfair Display SC (Elegant serif for headers/logos).
  - **UI Navigation:** Lexend (Highly readable sans-serif).
  - **Data/Body:** Source Sans 3 or Karla (Clean, professional body text).
  - **Technical/Code:** Fira Code (For audit logs/system info).

### 2. Technical Stack (Python-Centric)
- **Framework:** `ttkbootstrap` (Theme: `superhero` base, heavily customized with OLED overrides).
- **Core Engine:** Python 3.12+
- **Database:** SQLAlchemy ORM with SQLite (Local persistence for contracts, users, and audit logs).
- **Image Processing:** Pillow (PIL) for high-performance UI asset caching and logo resizing.
- **Reporting:** `fpdf2` for professional PDF generation; standard `csv` for data exports.

### 3. UI Architecture
- **Ribbon Navigation:** A multi-tabbed Ribbon Menu (Home, HR, Contracts, Tools, Reports) utilizing `ttk.Notebook` styled to appear integrated. Buttons use various bootstyles (INFO, LIGHT, SECONDARY, DANGER) with consistent 10px padding.
- **Dynamic Dashboard (Hero Section):**
  - Centered Branding: 300x300 high-fidelity company logo (Vincci Hoteles).
  - Stats Bar: Top-mounted horizontal stats tracking "Active", "Expiring", and "Expired" counts.
- **Data Density:**
  - `Tableview` widgets with `autofit` columns.
  - **Animated Alerts:** Critical rows (Expired/Expiring) must flash every 800ms, alternating between Vivid and Static alert colors.
- **Status Bar (HUD):**
  - Sophisticated bottom bar containing: PC hostname/IP, Logged-in User/Role, Real-time Local Weather/Location, and a high-precision live clock (DD/MM/YYYY HH:MM:SS).

### 4. Logic & Security
- **RBAC (Role-Based Access Control):** Permissions checked via an `AuthService`. Admin role has a hardcoded super-user bypass. Non-admin roles (Staff, Manager) have granular screen-level access (View, Add, Edit, Delete).
- **Audit System ("Mouchard"):** Comprehensive logging of all actions (logins, edits, deletions) with affected entity tracking.
- **Security Protocols:**
  - Dynamic deletion passwords calculated via date-based formulas (e.g., `((day + month + year_short) * 2) - 10`).
  - Activation OTPs with 60-second cooldowns and expiration logic.

### 5. Interaction Design
- **Transitions:** Smooth UI transitions (150-300ms) for all interactive states.
- **Cursors:** Explicit `cursor-pointer` on all clickable cards and buttons.
- **Visual Feedback:** High-contrast hover states (15% lighter than surface color).
- **Accessibility:** Resilient to RTL layouts and respecting `prefers-reduced-motion`.
