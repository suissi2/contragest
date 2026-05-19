# CONTRAGEST MASTER PROMPT v3

## Vision
Create a "Cyberpunk-meets-Corporate" high-fidelity enterprise interface for a contract management system called **Contragest**. The design must balance the professional reliability of a corporate tool with the sleek, high-contrast aesthetic of tech noir/HUD interfaces.

## 🎨 Visual Identity & Design Tokens
- **Design System:** OLED Dark Mode (High Contrast, WCAG AAA compliant).
- **Color Palette:**
  - `Background`: #020617 (Deep Obsidian)
  - `Surface`: #1E293B (Midnight Slate)
  - `Primary`: #22C55E (Neon Emerald - for positive actions/active status)
  - `Secondary/Muted`: #94A3B8 (Cool Grey)
  - `Danger/Expired`: Flash #ff4444 / Static #d9534f
  - `Warning/Expiring`: Flash #ffbb33 / Static #f0ad4e
  - `Text`: #F8FAFC (Ghost White)
- **Typography Pairing:**
  - `Headers`: Lexend (Modern, readable, corporate)
  - `Branding Accents`: Playfair Display SC (Sophisticated serif)
  - `Body Text`: Source Sans 3 (High-fidelity readability)
  - `Data/Technical`: Fira Code (Monospaced, precise)
- **Animations:**
  - `Alert Flashing`: 800ms interval for critical rows in data tables.
  - `Transitions`: 150-300ms for hover states and tab switches.

## 🏗️ UI Architecture (Enterprise Gateway Pattern)
1. **Ribbon Navigation (`Ribbon.TNotebook`)**:
   - Tabbed interface at the top (Home, HR, Tools, Reports).
   - Icons: SVG/Lucide-style (No emojis as primary icons).
   - Padding: [20, 5] for tabs; Helvetica 10 Bold font.
2. **Dashboard (Hero Section)**:
   - Centered 300x300 brand logo.
   - Stats Bar: Tracking Active, Expiring, and Expired contracts.
3. **Data Management (Advanced Tableview)**:
   - Searchable, paginated tables using `ttkbootstrap.widgets.tableview`.
   - Global search + Column-specific filters (Role, Status, Department).
   - Date range filtering with `ttkbootstrap.DateEntry`.
4. **Standalone Reports Module**:
   - Multi-tabbed Toplevel window (Users, Spy, Employees, Contracts).
   - Export capabilities: CSV (standard) and PDF (via `fpdf2` with logo inclusion).
5. **Status Bar**:
   - Fixed at bottom: System info (PC/IP), Session status, Weather/Location, and a real-time Clock.

## 🛠️ Technical Stack (Python)
- **GUI Framework**: `ttkbootstrap` (Theme: `superhero` with custom OLED overrides).
- **ORM**: `SQLAlchemy` (SQLite database: `contragest.db`).
- **Image Processing**: `Pillow` (with `image_cache` for optimized UI assets).
- **Reporting**: `fpdf2`.
- **Logic**: Background scheduling for alerts, I18n support (EN/FR/AR), and RBAC (Role-Based Access Control) with an 'admin' bypass logic.

## 📋 Interaction Guidelines
- All clickable elements must have `cursor-pointer`.
- Hover states must provide clear visual feedback (subtle glow or border change).
- RTL (Right-to-Left) support is mandatory for Arabic localization.
- Performance: MainWindow must use an `image_cache` to minimize disk I/O.
