# Contragest Interface Master Prompt

This document serves as a high-fidelity technical and visual meta-prompt for recreating or extending the **Contragest** enterprise contract management interface.

## 1. Visual Identity & Design System
The interface follows a **"Cyberpunk-meets-Corporate"** aesthetic, optimized for OLED displays with high-contrast elements and space-efficient layouts.

### 🎨 OLED Dark Mode Palette
- **Background (Main):** `#020617` (Deepest Black)
- **Surface (Containers):** `#1E293B` (Slate Navy)
- **Primary / Success:** `#22C55E` (Vibrant Green)
- **Text (Primary):** `#F8FAFC` (Ghost White)
- **Text (Muted):** `#94A3B8` (Cool Grey)
- **Danger (Static/Flash):** `#d9534f` / `#ff4444`
- **Warning (Static/Flash):** `#f0ad4e` / `#ffbb33`

### 🏗️ Typography
- **Branding Accents:** *Playfair Display SC* (Serif, Professional)
- **Headings / UI Controls:** *Lexend* (Geometric Sans, High Readability)
- **Body / Data Tables:** *Source Sans 3* (Functional, Data-Dense)
- **Alternative (Technical):** *Fira Code* (Monospace for IDs/Logs)

## 2. Technical Stack
- **Language:** Python 3.10+
- **GUI Framework:** `ttkbootstrap` (using "superhero" base or custom OLED theme)
- **Database:** SQLAlchemy (ORM) with SQLite (`contragest.db`)
- **Graphics:** Pillow (PIL) for image processing and logo caching
- **Reporting:** `fpdf2` for PDF generation and `csv` for data exports

## 3. Layout Architecture

### 🎀 Ribbon Navigation
- **Top Ribbon:** Multi-tabbed `ttk.Notebook` (Home, HR, Tools, Reports).
- **Grouping:** Buttons grouped within `ttk.LabelFrame` (e.g., Navigation, Administrative, Session).
- **Styles:** Helvetica 10 Bold, [20, 5] padding.

### 🏠 Dashboard (Home)
- **Hero Section:** Centered 300x300 company logo (Vincci Hoteles reference).
- **Stats Bar:** Top-aligned horizontal bar tracking:
  - `Active` (Success Green)
  - `Expiring Soon` (Warning Gold)
  - `Expired` (Danger Red)

### 📊 Data Management (Contracts/Reports)
- **Tableview:** Advanced data grids with search and multi-dropdown filtering.
- **Flashing Alerts:** Rows with critical status (Expired/Expiring) flash every 800ms between static and vivid colors.
- **Action Icons:** ✏️ (Edit) and 🗑️ (Delete) integrated directly into the first columns of the grid.

### 🛠️ Sophisticated Status Bar
- **Left:** PC Info (💻 Hostname, IP) + Location/Weather (🌍 City, 🌡️ Temp).
- **Center:** Logged-in user role and session status.
- **Right:** Dynamic Clock (📅 DD/MM/YYYY 🕒 HH:MM:SS) + Sizegrip.

## 4. Security & Logic
- **RBAC:** Role-Based Access Control protecting sensitive tabs (Tools/Audit Log).
- **Admin Bypass:** Logic allowing super-user access for roles named 'admin'.
- **Security Check:** Deletion of records requires a calculated daily password: `((day + month + year_short) * 2) - 10`.
- **Audit Logging:** "Mouchard" (Spy) system logging all CRUD operations and session starts.

## 5. Implementation Directives
- Ensure **WCAG AAA** compliance for text contrast on dark backgrounds.
- Implement **smooth transitions** (150-300ms) for hover states.
- Prioritize **image caching** for UI assets to minimize disk I/O.
- Use **SVG/Lucide-style icons** instead of emojis for production-grade builds.
