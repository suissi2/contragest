# CONTRAGEST MASTER PROMPT v4: Cyberpunk-meets-Corporate Interface

## Role & Context
You are an expert Python UI/UX Developer specializing in `ttkbootstrap` and `tkinter`. Your mission is to implement "Contragest," a high-fidelity Enterprise Contract Management System. The design philosophy is **"Cyberpunk-meets-Corporate"**: a professional, data-dense interface with a sophisticated OLED Dark Mode aesthetic, drawing inspiration from high-tech HUDs and modern fintech dashboards.

## Visual Identity & Design Tokens

### 1. Color Palette (OLED Dark Mode)
- **Primary Background:** `#020617` (Deepest Midnight/OLED Black)
- **Surface/Card:** `#1E293B` (Slate Navy)
- **Primary Accent:** `#22C55E` (Emerald Green - "Success/System Ready")
- **Secondary Accent:** `#3B82F6` (Electric Blue - "Information")
- **Danger/Alert (Flash):** Active: `#ff4444` | Static: `#d9534f`
- **Warning/Alert (Flash):** Active: `#ffbb33` | Static: `#f0ad4e`
- **Typography:** Primary: `#F8FAFC` | Muted: `#94A3B8`

### 2. Typography Stack
- **Headings (Brand):** `Playfair Display SC` (Serif, Elegant Corporate)
- **Headers (UI):** `Lexend` (Geometric Sans, High Readability)
- **Body Text:** `Source Sans 3` (Clean Professional Sans)
- **Technical/Data:** `Fira Code` (Monospaced, Terminal Aesthetic)

## UI Architecture (The "Ribbon-Hero" Pattern)

### 1. Customized Ribbon Menu
- **Tabs:** Home, HR, Tools, Reports.
- **Style:** `Ribbon.TNotebook` with `[20, 5]` padding and `Helvetica 10 bold` font.
- **Logic:** Buttons are grouped within `LabelFrame` containers (Navigation, Settings, Session). Use `bootstyle` variations (INFO, LIGHT, SECONDARY, DANGER).

### 2. Dashboard Hero & Stats
- **Hero Section:** Centered 300x300 company logo, large "Contragest" header (Lexend 24 Bold), and "Professional Contract Management System" sub-header.
- **Stats Bar:** A horizontal `SECONDARY` frame displaying live counts: `Active: X | Expiring Soon: Y | Expired: Z`.

### 3. Data-Dense Tableview
- **Implementation:** `ttkbootstrap.widgets.tableview`.
- **Alert Logic:** Implement a 150-300ms smooth transition or an 800ms flash interval for rows with `danger` (expired) or `warning` (expiring) tags.
- **Features:** Global search, column autofit, double-click to edit.

### 4. Advanced Reports View
- **Tabbed Analytics:** Separate tabs for Users, Spy (Audit Log), Employees, and Contracts.
- **Filtering Hub:** Global search entry + Dropdown filters (Role, Status, Department) + Toggleable Date Range pickers.
- **Exports:** Integrated PDF (via `fpdf2`) and CSV export buttons with custom headers and logo inclusion.

### 5. System Status Bar
- **Architecture:** `DARK` bootstyle frame at the bottom.
- **Dynamic Data:**
    - Left: PC Info (Hostname/IP) + Logged-in user status.
    - Center: Environment data (Location + Weather/Temp).
    - Right: Persistent Clock (`dd/mm/yyyy - HH:MM:SS`) + Sizegrip.

## Technical Directives
- **Theme:** Base theme `superhero` (customized to OLED tokens).
- **Responsive:** Ensure `zoomed` state for main window; center all dialogs/popups.
- **Compliance:** WCAG AAA contrast ratios for the OLED theme.
- **Icons:** No emojis as primary icons; use SVG or Lucide-style symbols mapped to standard character sets.
- **Performance:** Use image caching for UI assets (logos) to prevent disk I/O lag.

## Prompt Example for Generation
"Create a Python tkinter application using ttkbootstrap with a 'superhero' theme. Implement a Ribbon Menu with tabs for 'Home' and 'Reports'. The Home tab should feature a Hero section with a centered logo and a stats bar. The bottom of the window must have a dark status bar showing a real-time clock and system information. Use a palette of #020617 for the background and #22C55E for success accents. Ensure all tables in the Reports view have row-level coloring for status alerts."
