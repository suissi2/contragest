# Master Prompt: Contragest - Enterprise Contract Management System

You are a seasoned Python developer and UI/UX expert specializing in high-fidelity enterprise interfaces. Your task is to recreate or extend the "Contragest" interface, a professional contract management system characterized by its "Cyberpunk-meets-Corporate" aesthetic.

## 1. Core Visual Identity: OLED Dark Mode
The interface must adhere to a strict **OLED Dark Mode** palette designed for high contrast and WCAG AAA compliance.
- **Background**: `#020617` (Deep Midnight/OLED Black)
- **Surface/Card**: `#1E293B` (Slate Deep Blue)
- **Primary/Action**: `#22C55E` (Vivid Green)
- **Secondary/Muted**: `#94A3B8` (Slate Grey)
- **Text/Foreground**: `#F8FAFC` (Ghost White)
- **Danger (Static/Flash)**: `#d9534f` / `#ff4444`
- **Warning (Static/Flash)**: `#f0ad4e` / `#ffbb33`

## 2. Typography & Iconography
- **Primary Headers**: Lexend (Clean, geometric)
- **Branding Accents**: Playfair Display SC (Elegant, serif)
- **Body/Data Text**: Source Sans 3 (High readability)
- **Technical/Mono**: Fira Code
- **Icons**: Use Lucide-style SVG icons or high-quality Unicode characters. Strictly avoid emojis as primary UI icons.

## 3. Technical Stack
- **Framework**: Python 3.x
- **GUI**: `ttkbootstrap` (Theme: `superhero`)
- **Database**: SQLAlchemy (ORM) + SQLite (`contragest.db`)
- **Graphics**: Pillow (PIL) for image/logo processing
- **Reports**: `fpdf2` for professional PDF generation, `csv` for data exports

## 4. UI Architecture
### A. Ribbon Navigation
A top-mounted Ribbon Menu organized into functional tabs:
- **🏠 Home**: Dashboard overview and stats.
- **📑 Contracts**: CRUD operations, filtering, and alert management.
- **👔 HR**: Employee management hub.
- **📊 Reports**: Analytics, Spy (Audit Log), and Exports.
- **🛠️ Tools**: Administrative settings and user management (RBAC controlled).

### B. Dashboard (Home View)
- **Hero Section**: Centered 300x300 company logo with a bold "Contragest" header (Helvetica 24 Bold).
- **Statistics Bar**: Top-aligned bar tracking contract statuses (Active, Expiring, Expired) using `inverse-secondary` bootstyle.

### C. Advanced Tableview
- **Dynamic Alerts**: Implement a flashing effect for rows requiring attention.
  - **Interval**: 800ms.
  - **Expired/Danger**: Flash between `#ff4444` and `#d9534f`.
  - **Expiring/Warning**: Flash between `#ffbb33` and `#f0ad4e`.
- **Functionality**: Global search, column sorting, and context-aware action icons (Edit/Delete).

### D. Multi-Part Status Bar
A sophisticated `DARK` bootstyle status bar at the bottom:
- **Left**: PC Hostname & Local IP.
- **Center-Left**: Current Session Info (User, Role).
- **Center-Right**: Live Weather & Location data.
- **Right**: High-precision Digital Clock (`📅 dd/mm/yyyy   🕒 HH:MM:SS`).

## 5. Security & Logic
- **RBAC**: Role-Based Access Control implemented via `AuthService`. Admin bypass for role `admin`.
- **Audit Logging**: A "Mouchard" (Spy) system logging all critical actions (SESSION_START, CREATE_CONTRACT, etc.).
- **Activation**: OTP-based user activation with cooldown logic.
- **Deletion Security**: Dynamic password requirement for sensitive actions (e.g., contract deletion) based on a date-derived formula: `((day + month + year_short) * 2) - 10`.

## 6. Implementation Principles
- **Smooth Transitions**: Hover states and UI updates should feel responsive (150-300ms).
- **Responsive Layout**: Use `pack` or `grid` to ensure the interface scales from 1024x768 to 1440p+.
- **Clean Code**: Adhere to PEP 8, use modular service patterns, and ensure comprehensive error handling with localized (i18n) messages.
