# CONTRAGEST High-Fidelity Interface Concept Prompt

**Goal**: Recreate or extend the 'Contragest' Enterprise Contract Management System interface, a high-performance desktop application built with Python and `ttkbootstrap`, featuring an 'Enterprise Gateway' layout and 'OLED Dark Mode' aesthetic.

## 1. Visual Identity & Color Palette (OLED Dark Mode)
Implement a high-contrast, professional dark theme compliant with WCAG AAA standards.
- **Background**: `#020617` (Deepest Navy/Black)
- **Surface/Cards**: `#1E293B` (Slate Blue)
- **Primary/Action**: `#22C55E` (Emerald Green)
- **Primary Text**: `#F8FAFC` (Ghost White)
- **Muted/Secondary Text**: `#94A3B8` (Slate Grey)
- **Accents**:
  - Success: `#5cb85c`
  - Warning: `#f0ad4e` / `#ffbb33` (Active)
  - Danger: `#d9534f` / `#ff4444` (Active)

## 2. Typography & Iconography
- **Headings**: `Playfair Display SC` or `Lexend` for a modern, authoritative feel.
- **Interface/Body**: `Helvetica` or `Source Sans 3` for maximum legibility.
- **Icons**: Replace all Unicode emojis with high-fidelity SVG icons (Lucide or Heroicons). Standard size: 24x24px. Use consistent line weight.

## 3. Layout Architecture (Enterprise Gateway)
### A. Ribbon Navigation (`RibbonMenu`)
- **Structure**: A top-docked `ttk.Notebook` styled as a Ribbon Menu.
- **Tabs**:
  - `🏠 Home`: Dashboard navigation, settings, and session controls.
  - `👔 HR`: Employee and contract management shortcuts.
  - `🛠️ Tools`: Administrative utilities (User Management, Audit Log).
  - `📊 Reports`: Analytics and data export hub.
- **Styling**: `Ribbon.TNotebook` with 0 padding; tabs use `Ribbon.TNotebook.Tab` with `[20, 5]` padding and bold 10pt font.

### B. Dashboard Hero Section
- **Central Focus**: A centered 300x300px company logo.
- **Typography**: Large "Contragest" title in 24pt bold, followed by "Professional Contract Management System" in 14pt.
- **Stats Bar**: A top-aligned bar tracking contract counts: "Active | Expiring Soon | Expired".

### C. Multi-Part Status Bar
- **Left**: Hostname and Local IP.
- **Center**: Current Session User (Username/Role).
- **Middle-Right**: Real-time Weather and Location data.
- **Right**: Live Digital Clock (`📅 dd/mm/yyyy   🕒 HH:MM:SS`) and a window resize grip.

## 4. Advanced Components & UX
- **Flashing Tableview Alerts**:
  - Main contract table includes an "Edit" and "Delete" icon column.
  - Critical rows (Expired/Expiring) must flash every 800ms.
  - Danger Flash: `#ff4444` (Active) vs `#d9534f` (Static).
  - Warning Flash: `#ffbb33` (Active) vs `#f0ad4e` (Static).
- **Smooth Transitions**: All hover states and view transitions must have a 150-300ms duration.
- **Forms**: Use `ttk.Toplevel` with `Labelframe` grouping, `DateEntry` for calendar inputs, and `Spinbox` for numeric data.

## 5. Technical Stack & Integration
- **Framework**: Python 3.x with `ttkbootstrap` (Superhero theme as base).
- **Backend**: SQLAlchemy ORM with SQLite (`contragest.db`).
- **Assets**: PIL (Pillow) for image caching and dynamic logo resizing.
- **Security**: Role-Based Access Control (RBAC) with an 'admin' bypass. Deletion requires a dynamic daily password calculation.
