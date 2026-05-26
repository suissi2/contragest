# CONTRAGEST MASTER PROMPT v6: Cyberpunk-meets-Corporate OLED Dashboard

## 1. Identity & Visual Concept
**Product Name:** Contragest
**Core Identity:** 'Cyberpunk-meets-Corporate' — A high-fidelity, data-dense enterprise dashboard designed for the Vincci Hoteles ecosystem.
**Visual Style:**
- **OLED Dark Mode:** Deepest blacks (#020617) to maximize contrast and power efficiency.
- **Glassmorphism:** Frosted glass panels (semi-transparent frames) with subtle glows (text-shadow: 0 0 10px).
- **Industrial Precision:** Tech-noir aesthetic with neon-green (#22C55E) positive indicators and sharp, high-readability typography.
- **WCAG Compliance:** Aim for AAA contrast in the OLED theme.

## 2. Technical Architecture (Python Stack)
- **Framework:** Python + `ttkbootstrap` (Superhero base theme).
- **Layout:**
    - **Ribbon Menu:** Top-docked `ttk.Notebook` (Style: 'Ribbon.TNotebook') with custom tab padding [20, 5] and Helvetica 10 bold font.
    - **Dashboard Hero:** Centered 300x300 corporate logo (`assets/company_logo.png`) on a spacious home frame.
    - **Status Bar:** Bottom-docked multi-section bar displaying PC Info (Hostname/IP), Env Data (Location/Weather via `BackgroundScheduler`), and a persistent real-time clock.
- **Data & Logic:**
    - **ORM:** SQLAlchemy with SQLite (`contragest.db`).
    - **Imaging:** `Pillow` for dynamic logo resizing and image caching to optimize performance.
    - **Reporting:** Tabbed interface with `Tableview` supporting global search, role/status filtering, and PDF/CSV exports via `fpdf2`.

## 3. Design Tokens
- **OLED Palette:**
    - **Background:** #020617 (Midnight Black)
    - **Surface/Panels:** #0F172A (Deep Navy)
    - **Secondary:** #1E293B (Slate)
    - **Primary Accent:** #22C55E (Neon Green)
    - **Text:** #F8FAFC (White-Smoke)
    - **Alerts:** Flash/Static pairs - Danger (#ff4444/#d9534f), Warning (#ffbb33/#f0ad4e).
- **Typography:**
    - **Headings/Code:** Fira Code (Technical precision).
    - **Body Text:** Fira Sans (High readability).
    - **Fallback:** Lexend (Primary headers) / Playfair Display SC (Branding accents).

## 4. Key Functional Modules
- **Security:** Integrated `auth_core` featuring MFA (OTP via email), Role-Based Access Control (RBAC), and a "Mouchard" (Audit Log) for tracking all sensitive actions.
- **Alert System:** Background scheduler monitors contract expirations and triggers automated SMTP notifications using HTML templates.
- **User Interface Features:**
    - Smooth transitions (150-300ms).
    - Visual flashing for critical status rows (800ms intervals).
    - RTL support for global deployments.

## 5. Developer Instructions
- Use `ttkbootstrap.widgets.tableview` instead of the deprecated standard module.
- Implement `image_cache` in the MainWindow to minimize disk I/O.
- Ensure all clickable cards use `cursor="hand2"`.
- Maintain repository hygiene: exclude `__pycache__`, `.db`, and `.log` files from commits.
- All GUI scripts must handle headless environments gracefully or document Tkinter requirements.
