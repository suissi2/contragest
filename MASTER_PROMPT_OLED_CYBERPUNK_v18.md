# MASTER PROMPT: CONTRAGEST 'CYBERPUNK-MEETS-CORPORATE' OLED INTERFACE

## 1. VISION & IDENTITY
Create a professional Python-based desktop application named **"Contragest"** (Contract Management System). The interface must embody a **"Cyberpunk-meets-Corporate"** identity: a high-contrast, data-dense, OLED-optimized environment that balances the sleekness of sci-fi HUDs with the reliability of enterprise software.

## 2. TECHNICAL STACK
- **Language:** Python 3.12+
- **Primary Framework:** `tkinter` with `ttkbootstrap` (Superhero theme as base).
- **Widgets:** `ttkbootstrap.widgets.tableview`, `ttkbootstrap.DateEntry`.
- **Imaging:** `Pillow` (PIL) for high-fidelity logo rendering.
- **Backend:** `SQLAlchemy` (SQLite/PostgreSQL) with a strictly modular architecture.

## 3. DESIGN TOKENS (OLED DARK MODE)
- **Palette:**
  - **Background (OLED Black):** `#020617`
  - **Surface (Deep Navy):** `#1E293B`
  - **Corporate Navy (Accents):** `#0F172A`
  - **Primary (Neon Emerald):** `#22C55E` (Use for SUCCESS and PRIMARY bootstyles).
  - **Secondary (Muted Steel):** `#94A3B8`
  - **Alerts:** Static Danger `#d9534f` / Flash Danger `#ff4444`.
- **Typography:**
  - **Headers:** *Lexend* (Modern, clean).
  - **Branding Accents:** *Playfair Display SC* (Serif elegance).
  - **Body Text:** *Source Sans 3* (High readability).
  - **Data/Technical:** *Fira Code* (Monospace for tables/logs).

## 4. UI ARCHITECTURAL BLUEPRINT
### A. Ribbon Navigation System
- Implement a **Ribbon Menu** at the top using a custom `Ribbon.TNotebook` style.
- **Tab Config:** Padding `[20, 5]`, font `Helvetica 10 Bold`.
- **Tabs:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
- **Behavior:** Clicking a Ribbon tab programmatically switches a secondary, hidden-tab `Main.TNotebook`.

### B. Hidden-Tab Main Notebook
- The central content area uses a `ttk.Notebook` with **hidden tabs** (`style.layout('Main.TNotebook.Tab', [])`).
- This notebook hosts the primary views: Dashboard, Employee List, Contract Management, Audit Logs.

### C. Dashboard Hero Section
- **Branding:** Centered 300x300 company logo (Vincci Hoteles/Contragest).
- **Stats Bar:** Top-aligned horizontal frame showing real-time counters:
  - 🟢 Active Contracts
  - 🟡 Expiring Soon
  - 🔴 Expired

### D. Multi-Segment Status Bar (Bottom)
- **Segment 1 (PC Info):** Display 💻 PC Name and Local IP.
- **Segment 2 (Environment):** Real-time 🌍 Location and Weather status.
- **Segment 3 (Clock):** Persistent digital clock in bold.
- **Style:** `bootstyle=DARK`, font `Helvetica 9`.

## 5. COMPONENT SPECIFICATIONS
### Forms & Dialogs
- **Padding:** Main containers `padding=20`; internal LabelFrames `padding=15`.
- **Rows:** Standard `pady=5`. Labels `width=12`.
- **Buttons:** Emphasis using `ipady=5` and `width=15`.
- **Visual Feedback:** Urgent alerts must trigger an `animate_flash` loop between static and neon color states.

### Data Management
- Use `Tableview` for all lists.
- Columns: `Autofit=True`, `Searchable=True`.
- Bootstyle: `INFO` or `PRIMARY`.

## 6. CORE LOGIC & SECURITY
- **RBAC:** Multi-level permissions (Admin/User) controlling Ribbon tab visibility.
- **Audit Log ("Mouchard"):** Automated event tracking for every CRUD operation.
- **Secure Deletion:** Data removal requires a password calculated dynamically: `((day + month + year_short) * 2) - 10`.
- **I18n:** Full support for English, French, and Arabic (RTL support for Arabic).

## 7. PROMPT DIRECTIVE
"Generate a Python modular application using `ttkbootstrap` and `SQLAlchemy`. Implement a Ribbon-based UI with a hidden-tab content area. Use an OLED palette (#020617, #22C55E) and Lexend typography. Include a weather-integrated status bar, an automated audit log, and a statistics dashboard with logo-centric hero sections. Ensure all forms use high-density layouts with specific padding tokens [20, 15, 5]."
