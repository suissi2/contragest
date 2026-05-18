# CONTRAGEST INTERFACE MASTER PROMPT

Act as an expert Python UI/UX Developer specializing in data-dense enterprise applications. Your goal is to recreate the **Contragest** interface—a "Cyberpunk-meets-Corporate" Contract Management System optimized for OLED displays.

## 1. Visual Identity & Design Tokens

### Palette: OLED Dark Mode (WCAG AAA Compliant)
- **Background:** `#020617` (Deepest Black)
- **Surface:** `#1E293B` (Slate Grey)
- **Primary/Success:** `#22C55E` (Vibrant Green)
- **Text (Primary):** `#F8FAFC` (Ghost White)
- **Text (Muted):** `#94A3B8` (Slate Blue)
- **Alert (Danger):** Flash `#ff4444` / Static `#d9534f`
- **Alert (Warning):** Flash `#ffbb33` / Static `#f0ad4e`

### Typography
- **Branding/Accents:** *Playfair Display SC* (Elegant serif)
- **Primary Headers:** *Lexend* (Geometric sans-serif)
- **Body/Data:** *Source Sans 3* or *Fira Code* (High legibility)

## 2. Technical Stack
- **Framework:** Python with `ttkbootstrap` (Base theme: `superhero`)
- **Database:** SQLAlchemy ORM with SQLite
- **Imaging:** Pillow (PIL) for high-fidelity asset rendering
- **Reporting:** `fpdf2` for professional PDF generation with logo support

## 3. UI Architecture

### A. Ribbon Navigation (`RibbonMenu`)
- **Implementation:** A `ttk.Notebook` styled as a Ribbon (`Ribbon.TNotebook`).
- **Tabs:**
    - **Home:** Dashboard/Home actions, Application/Company settings, Session controls.
    - **HR:** Employee and Contract management shortcuts.
    - **Tools:** (Admin only) User Management and Audit Log (Mouchard).
    - **Reports:** (Admin only) Direct access to analytics.
- **Styling:** Tab padding `[20, 5]`, Bold Helvetica 10. Buttons use `INFO`, `LIGHT`, and `DANGER` bootstyles.

### B. Dashboard View (`MainWindow`)
- **Hero Section:** Centered 300x300 company logo with "Contragest" branding in Playfair Display SC.
- **Stats Bar:** A `SECONDARY` bootstyle frame showing counts of Active, Expiring, and Expired contracts.
- **Status Bar:** Bottom fixed frame (`DARK` bootstyle) containing:
    - Hostname and IP address.
    - User session details.
    - Real-time environment data (Weather/Location) via background scheduler.
    - Digital Clock (`%d/%m/%Y %H:%M:%S`).

### C. Advanced Tableview Features
- **Flashing Alerts:** Use a `1000ms` (or `800ms`) interval to toggle row tags (`danger`, `warning`) between vivid and static colors for contracts nearing expiration.
- **Inline Actions:** Icons for Edit (✏️) and Delete (🗑️) in the first two columns.
- **Filtering:** A dedicated filter bar with global search, status dropdowns, and date range pickers.

## 4. Core Logic & UX Patterns
- **RBAC:** Implement a `require_permission` decorator for UI methods.
- **Security:** "Deletion Password" formula: `((day + month + year_short) * 2) - 10`.
- **Transitions:** Smooth UI updates (150-300ms) and non-blocking background tasks for system checks.
- **I18n:** Multi-language support (English, French, Arabic) with RTL/LTR layout awareness.

## 5. Output Goal
Generate clean, modular Python code using `ttkbootstrap`. Structure the app with a `main.py` controller and feature-based directory structure (`core/`, `features/`, `logic/`). Ensure all UI assets are cached in an `image_cache` dictionary to prevent lag.
