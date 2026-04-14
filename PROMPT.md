# Contragest Application Specification & Reconstruction Prompt

## 1. Visual Identity & Theme
- **Framework**: Python with `ttkbootstrap`.
- **Primary Theme**: `superhero` (establishes a professional "OLED Dark Mode" aesthetic with a slate blue and grey palette).
- **Design Pattern**: **Enterprise Gateway** - focused on high-integrity data presentation, professional trust signals, and efficient navigation.
- **Core Aesthetic**: Professional, data-dense enterprise dashboard with high contrast and space-efficient layouts.
- **Typography**:
  - Main Heading: Helvetica 24 Bold ("Hero" style).
  - Stats/Subheaders: Helvetica 11 (bootstyle: `inverse-secondary`).
  - Status Bar: Helvetica 9 (bootstyle: `inverse-dark`).
  - Ribbon Tabs: Helvetica 10 Bold.
- **Color Palette**:
  - Primary Background: #0F172A (Slate Dark)
  - Danger (Expired): `#ff4444` (active) / `#d9534f` (static).
  - Warning (Expiring Soon): `#ffbb33` (active) / `#f0ad4e` (static).
  - Success (Active): `#5cb85c`.
- **Iconography**: Clean SVG-style icons or Unicode symbols used for actions like Edit (✏️), Delete (🗑️), and Navigation (🏠, 👔, 🛠️, 📊).

## 2. Layout Architecture
- **Navigation**: Ribbon Menu (`Ribbon.TNotebook`) categorized into:
  - `🏠 Home`: Dashboard overview, company logo, app settings, and session management.
  - `👔 HR`: Fast access to employee and contract management.
  - `🛠️ Tools`: Administrative utilities (User Management, Audit Logs, Recovery).
  - `📊 Reports`: Centralized hub for detailed analytics.
- **Main Workspace**: A `ttk.Notebook` with hidden tabs (layout cleared) that switches views based on Ribbon selection.
- **Status Bar**: A multi-segmented dark toolbar at the bottom providing:
  - **System Info**: Hostname and Local IP.
  - **Session Details**: Logged-in Username and Role.
  - **Environmental Data**: Real-time Location and Weather (updated via `BackgroundScheduler`).
  - **Live Clock**: Dynamic digital display (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## 3. Core Features & Components
- **Dashboard Home**:
  - Stats summary bar (Active vs. Expiring vs. Expired).
  - Hero section featuring a large company logo and professional greeting.
- **Contracts Tableview**:
  - Data-dense table showing ID, Employee Name, Type, Dates, Seniority, and Status.
  - **Animated Flash Alerts**: Rows for expiring or expired contracts pulse between vivid and standard colors every 800ms.
  - **Seniority Logic**: Dynamic calculation of months and days since the start date.
- **Reports Module**:
  - Tabbed interface (Users, Spy, Employees, Contracts).
  - Advanced filtering: Global search, role/status/department dropdowns, and date range pickers.
  - Export Support: Clean CSV and PDF generation (via `fpdf2`) including company branding and stylized headers.
- **Security & RBAC**:
  - Role-Based Access Control (RBAC) governing visibility of Ribbon tabs and action buttons.
  - **Daily Deletion Password**: Sensitive actions (like contract deletion or recovery) require a password calculated as: `((day + month + (year % 100)) * 2) - 10`.
  - **Mouchard (Spy)**: Detailed audit logging system for tracking all user actions.

## 4. Backend & Logic
- **ORM & Database**: SQLAlchemy with a local SQLite database (`contragest.db`).
- **Services**:
  - `EmailManager`: Thread-safe singleton for background notification delivery using a `PriorityQueue`.
  - `BackgroundScheduler`: Manages periodic tasks like environmental updates and automated expiration checks.
  - `I18n`: Support for Internationalization (English, French, Arabic) via JSON locale files and RTL layout support.

## 5. Master Implementation Prompt for LLM
> "As a seasoned Python developer and expert in GUI design, create an enterprise-grade contract management dashboard ('Contragest') using Python, `ttkbootstrap` (superhero theme), and SQLAlchemy.
>
> Implement a **Ribbon-style navigation menu** with tabs for Home, HR, Tools, and Reports. The main workspace must use a hidden Notebook for seamless view switching. Include a **multi-part status bar** showing system info, session state, real-time weather (mocked background service), and a live digital clock.
>
> The core feature is a **Tableview** for contracts with **conditional row coloring** and a **flashing animation effect** (800ms) for critical statuses (Expired/Expiring). Implement a **Reports window** with tabbed views, global search, multi-criteria filters, and PDF/CSV export functionality including company branding.
>
> Integrate a robust **RBAC security system** and a 'Mouchard' audit log. Sensitive actions must be protected by a dynamic daily password formula: `((day + month + (year % 100)) * 2) - 10`. Ensure the code is modular, follows a service-oriented pattern, and fully supports internationalization (EN/FR/AR) with RTL layout awareness."
