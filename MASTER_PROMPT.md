# Contragest Master Prompt: Cyberpunk Corporate Interface

Develop a high-fidelity Python desktop application interface using `ttkbootstrap` (Superhero theme) that embodies a 'Cyberpunk-meets-Corporate' (Tech Noir) visual identity.

## 🎨 Visual Identity & Design Tokens
*   **Color Palette:**
    *   **Background:** Deep OLED Black (`#020617`)
    *   **Surface/Cards:** Slate Blue (`#1E293B`)
    *   **Primary/Success:** Neon Emerald (`#22C55E`)
    *   **Muted Text:** Cool Gray (`#94A3B8`)
    *   **Alerts (Danger):** Flash/Static pair (`#ff4444` / `#d9534f`)
    *   **Alerts (Warning):** Flash/Static pair (`#ffbb33` / `#f0ad4e`)
*   **Typography:**
    *   **Headers:** `Lexend` (for maximum readability and modern feel)
    *   **Body Text:** `Source Sans 3` (professional enterprise standard)
    *   **Data/Technical:** `Fira Code` (for monospaced data precision)
    *   **Branding:** `Playfair Display SC` (for serif elegance in logos)
*   **Effects:** 150-300ms smooth transitions, 800ms pulsing animations for critical alerts, and WCAG AAA compliance.

## 🏗️ UI Architecture & Layout
*   **Navigation (Ribbon Menu):**
    *   Top-aligned `ttk.Notebook` styled as a Ribbon.
    *   Tabs: **Home** (Dashboard), **HR** (Staff Management), **Contracts** (Core Business), **Reports** (Analytics), and **Tools** (Admin).
    *   Custom padding `[20, 5]` and bold `Helvetica 10` for tab labels.
*   **Dashboard Hero:**
    *   Centered `300x300` company logo.
    *   Upper statistics bar tracking high-level metrics (e.g., Active vs. Expired status).
*   **Data Presentation:**
    *   Advanced `Tableview` widgets with integrated global search.
    *   Multi-level filtering: Dropdown selectors for Role, Status, and Department.
    *   Date range pickers for chronological reporting.
*   **System Status Bar:**
    *   Bottom-docked toolbar displaying:
        *   Host PC Name and Local IP.
        *   Dynamic Environmental Data (Location and Weather).
        *   Persistent real-time Clock (`📅 dd/mm/yyyy   🕒 HH:MM:SS`).

## ⚙️ Technical Requirements
*   **Backend:** SQLAlchemy ORM with SQLite database.
*   **Imaging:** PIL/Pillow for high-performance logo caching and UI asset scaling.
*   **Reporting:** Integrated CSV and PDF export functionality via `fpdf2`, featuring branded headers and alternating row highlights.
*   **Security:** Role-Based Access Control (RBAC) with specific 'admin' bypass logic and audit logging (Mouchard).
