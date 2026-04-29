# REFINED INTERFACE PROMPT: Contragest Enterprise Gateway (OLED Dark Mode)

You are a senior Python developer and UI/UX expert. Your task is to recreate or extend the **Contragest** interface, a professional contract management system. The design must strictly adhere to the **"Enterprise Gateway"** pattern with an **OLED Dark Mode** aesthetic.

## 1. Visual Identity & Palette
- **Theme Name:** Contragest OLED Dark (High Contrast)
- **Background:** `#020617` (Deepest Black/Slate)
- **Surface/Cards:** `#1E293B` (Slate Dark)
- **Primary Action / Success:** `#22C55E` (Emerald Green)
- **Primary Text:** `#F8FAFC` (Slate White)
- **Muted Text:** `#94A3B8` (Slate 400)
- **Secondary Actions:** `#1E293B` (Outline or Solid)
- **Critical Alerts:** `#FF4444` (Flash Active) / `#D9534F` (Static)

## 2. Typography
- **Headings/Display:** `Playfair Display SC` (Small Caps) for a premium, authoritative feel.
- **Navigation/UI Elements:** `Lexend` (for maximum readability and accessibility).
- **Body/Data:** `Source Sans 3` (for clean, dense information display).

## 3. Layout Architecture (The "Ribbon" System)
- **Header:** A Microsoft-style Ribbon Menu using `ttk.Notebook` (Style: `Ribbon.TNotebook`).
  - **Tabs:** `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
  - **Interaction:** Tab switching should instantly swap the main content area (Notebook without tabs).
- **Hero Section (Home):**
  - Centered 300x300 logo (`assets/company_logo.png`).
  - Large display text ("Contragest") in `Lexend` 24pt Bold.
  - Subtitle: "Professional Contract Management System".
- **Main View (Contracts):**
  - A dense `Tableview` (from `ttkbootstrap.widgets.tableview`).
  - Columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
  - **Visual Feedback:** Rows for "Expired" or "Expiring Soon" contracts must flash every 800ms using alternating colors.
- **Footer (Status Bar):**
  - Multi-part dark status bar (`#020617` background).
  - Left: PC Info (Hostname/IP).
  - Center: Session User Info.
  - Middle-Right: Environmental Info (Location/Weather).
  - Right: Live Digital Clock (Date + HH:MM:SS).

## 4. Technical Stack
- **Framework:** `Python 3.x` with `ttkbootstrap` (Superhero theme as base, customized).
- **Database:** `SQLAlchemy` ORM with `SQLite`.
- **Imaging:** `Pillow` (PIL) for high-quality logo resizing and caching.
- **Reporting:** `fpdf2` for PDF exports with custom font embedding.
- **Security:** Role-Based Access Control (RBAC). Admin users bypass all permission checks.

## 5. UI/UX Directives
- **SVG Icons:** Replace all Unicode emojis with Lucide-style SVG icons for a modern look.
- **Transitions:** All interactive elements must have a 150-300ms transition on hover/active states.
- **RTL Support:** Implement layout logic that dynamically flips sides (pack_start/pack_end) based on the active language (English/French/Arabic).
- **Compliance:** Aim for WCAG AAA compliance through high-contrast OLED palette.
