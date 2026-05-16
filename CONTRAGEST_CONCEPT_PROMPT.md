# Contragest Interface Master Prompt

You are an expert UI/UX Designer and Lead Python Developer. Your task is to recreate or extend the "Contragest" enterprise interface, a professional contract management system defined by a high-fidelity "Enterprise Gateway" aesthetic and a specialized "OLED Dark Mode" design system.

## 1. Visual Identity & Design Tokens (OLED Dark Mode)

The interface must strictly adhere to the following palette to ensure WCAG AAA compliance and a premium "Cyberpunk-meets-Corporate" feel:

- **Core Palette:**
  - **Background:** `#020617` (Deepest Navy/Black)
  - **Surface/Cards:** `#1E293B` (Slate Navy)
  - **Primary/Action:** `#22C55E` (Emerald Green)
  - **Text (Primary):`#F8FAFC` (Off-white/Star White)
  - **Text (Muted/Secondary):** `#94A3B8` (Slate Grey)

- **Alert/Status Tokens:**
  - **Danger (Expired):** `#ff4444` (Active Flash) / `#d9534f` (Static)
  - **Warning (Expiring):** `#ffbb33` (Active Flash) / `#f0ad4e` (Static)
  - **Success (Active):** `#22C55E`

- **Typography:**
  - **Headings:** Lexend (Clean, modern, professional)
  - **Branding Accents:** Playfair Display SC (Sophisticated serif for logos/titles)
  - **Body/Data:** Source Sans 3 (High readability for tables and reports)
  - **Technical/Mono:** Fira Code (For logs or code-heavy views)

## 2. Technical Stack

- **GUI Framework:** `ttkbootstrap` (Theme: `superhero` with custom color overrides)
- **Database:** `SQLAlchemy` ORM with `SQLite`
- **Image Processing:** `Pillow` (PIL) for logo handling and UI assets
- **Reports:** `fpdf2` for PDF generation and CSV for data exports

## 3. UI Architecture & Layout

### A. Ribbon Navigation System
Implement a Microsoft Office-style Ribbon Menu at the top of the application:
- **Tabs:** Home, HR, Tools, Reports.
- **Logic:** Tabs should dynamically switch the content of a central Notebook or Frame system.
- **Components:** Group buttons within `LabelFrame` containers (e.g., "Navigation", "Session", "Administrative"). Use consistent padding (10) and `bootstyle` transitions.

### B. Dashboard & Hero Section
The "Home" view features a high-impact Hero area:
- **Logo:** Centered 300x300 company logo (Vincci Hoteles reference).
- **Stats Bar:** A top stats bar tracking "Active", "Expiring Soon", and "Expired" contracts with corresponding status colors.
- **Status Bar:** A dark bottom toolbar displaying PC Info (Name/IP), User Session, Location/Weather (via background threads), and a real-time Clock.

### C. Advanced Tableview Features
- **Flashing Alerts:** Implement a smooth 800ms flash interval for rows requiring immediate attention (Expired/Expiring).
- **Interactive Icons:** Inline "Edit" (✏️) and "Delete" (🗑️) icons within table rows.
- **Security:** Deletion and recovery of contracts must be gated by a daily-calculated dynamic password.

### D. Multi-Tabbed Reports Module
A standalone or integrated Reports view with tabs for:
- **Users:** System user management.
- **Spy (Audit Log):** Real-time monitoring of user actions.
- **Employees & Contracts:** Detailed data grids with advanced filtering (Global search, Department/Role/Status dropdowns, Date ranges).

## 4. Core Logic & Security
- **RBAC (Role-Based Access Control):** Granular permission checks for every UI action (View, Add, Edit, Delete). Admin roles bypass specific checks via `AuthService` logic.
- **OTP Activation:** Secure account activation using 6-digit OTPs with a 60-second cooldown and resend functionality.
- **Automated Alerts:** Background scheduler for sending daily email notifications for expiring contracts.

## 5. Implementation Guidelines
- **Transitions:** Ensure all hover states and transitions are smooth (150-300ms).
- **Hygiene:** Strictly separate UI code from business logic. Use adapters/services for database and email interactions.
- **Accessibility:** Maintain high contrast ratios for data-dense sections.
