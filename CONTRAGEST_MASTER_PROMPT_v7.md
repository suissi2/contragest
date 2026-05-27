# Contragest Master Prompt v7: Cyberpunk-meets-Corporate Enterprise Interface

## 1. Conceptual Identity
**"The Enterprise Noir Gateway"**
A high-fidelity dashboard that blends high-stakes corporate management with a Cyberpunk/OLED aesthetic. The interface must feel like a "Mission Control" for corporate contracts—clean, data-dense, authoritative, yet visually striking.

## 2. Visual Tokens & Design System
### A. OLED Dark Mode Palette
- **Deep Background:** `#020617` (True Black/Near Black for OLED)
- **Surface/Card:** `#1E293B` (Slate Navy)
- **Primary/Action:** `#22C55E` (Vivid Emerald Green)
- **Danger (Flash/Static):** `#ff4444` / `#d9534f` (For Expired status)
- **Warning (Flash/Static):** `#ffbb33` / `#f0ad4e` (For Expiring Soon status)
- **Muted Text:** `#94A3B8` (Cool Grey)

### B. Typography Hierarchy
- **Primary Headers:** `Lexend` (Modern, geometric, high readability)
- **Branding/Accents:** `Playfair Display SC` (For elegant, authoritative enterprise feel)
- **Body Text:** `Source Sans 3` (Optimized for data-dense environments)
- **Technical/Code:** `Fira Code` (For system info and status bars)

## 3. UI Architecture (The "Ribbon-Hero" Framework)
### A. The Ribbon Navigation
- **Style:** A modern "Office-inspired" Ribbon Menu using a custom Notebook tab system.
- **Tabs:**
    - `🏠 Home`: Dashboard navigation, App/Company settings, Session controls (Logout/Exit).
    - `👔 HR`: Employee directory and Contract management shortcuts.
    - `🛠️ Tools`: Administrative utilities (User management, Audit logs/Mouchard).
    - `📊 Reports`: Advanced analytics with global search and multi-format export (CSV/PDF).

### B. The Dashboard Hero & Stats
- **Hero Section:** A centered, high-contrast company logo (300x300) set against a minimal dark backdrop.
- **KPI Bar:** A top-aligned statistics bar tracking:
    - `✅ Active Contracts`
    - `⚠️ Expiring Soon`
    - `🚫 Expired`

### C. System Status Bar (The HUD)
- **Persistent Bottom Bar:**
    - Left: PC Info (Hostname/IP) + Session User.
    - Center: Dynamic Environment Data (Location + Weather/Temp).
    - Right: High-precision Digital Clock (`📅 DD/MM/YYYY  🕒 HH:MM:SS`).

## 4. Technical Component Specifications
- **Data Tables:** Multi-column layout with `Edit` and `Delete` action icons. Implementation of smooth row-flashing (800ms interval) for critical status alerts.
- **Glassmorphism:** Subtle background blurs on modal dialogs and overlays.
- **Responsiveness:** Desktop-first "Zoomed" state by default, optimized for 1200x700+ resolution.

## 5. Execution Logic (Python/ttkbootstrap)
- **Theme Base:** `superhero` (customized to OLED tokens).
- **Core Libraries:** `SQLAlchemy` (ORM), `Pillow` (Icon/Logo processing), `ttkbootstrap.tableview`, `fpdf2` (Report generation).
- **Automation:** Background `scheduler` for real-time environmental updates and automated expiration alerts.
