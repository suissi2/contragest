# CONTRAGEST MASTER PROMPT v3: Cyberpunk-Corporate Enterprise Interface

## THE MISSION
Recreate the "Contragest" interface, a professional contract management system defined by a 'Cyberpunk-meets-Corporate' identity. The UI must be a high-performance, OLED-optimized desktop application that balances data density with a sophisticated, tech-noir aesthetic.

## DESIGN TOKENS (OLED DARK MODE)
- **Palette:**
  - Background: `#020617` (Deepest Black)
  - Surface/Cards: `#1E293B` (Midnight Slate)
  - Primary/Success: `#22C55E` (Emerald Green)
  - Secondary: `#94A3B8` (Muted Blue-Grey)
  - Danger (Flash): `#ff4444` (Active) / `#d9534f` (Static)
  - Warning (Flash): `#ffbb33` (Active) / `#f0ad4e` (Static)
- **Typography:**
  - Branding/Accents: `Playfair Display SC`
  - Headers: `Lexend`
  - Body Text: `Source Sans 3`
  - Data/Technical: `Fira Code`
- **Visual Effects:**
  - Smooth transitions (150-300ms) for hovers and tab switches.
  - Status flashing: 800ms interval for critical/expiring alerts in tables.
  - WCAG AAA compliance for high-contrast OLED readability.

## ARCHITECTURAL COMPONENTS
### 1. Enterprise Ribbon Navigation
- Top-mounted `Ribbon.TNotebook` with custom styling: `padding=[20, 5]`, font `Helvetica 10 bold`.
- Tabs: 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
- Grouped actions within tabs using `LabelFrame` containers (e.g., "Navigation", "Session", "Administrative").
- Ribbon buttons with varied bootstyles (INFO, LIGHT, SECONDARY, DANGER).

### 2. Dashboard Hero Section
- Centered 300x300 company logo (Vincci Hoteles inspired) as the visual centerpiece.
- Branding: "Contragest" in `Lexend` 24pt Bold.
- Top Stats Bar: Tracking "Active", "Expiring Soon", and "Expired" counts.

### 3. Data-Dense Tableview
- Multi-column display: Action Icons (✏️, 🗑️), ID, Full Name, Contract Type, Dates, Seniority, Days Left, Status.
- Interactive row tagging with dynamic background colors for alerts.
- Searchable and paginated interface with autofit columns.

### 4. Sophisticated Status Bar
- Bottom toolbar in `DARK` bootstyle.
- Sections:
  - PC Info: 💻 [PC Name] ([Local IP])
  - Session: Logged in user and role.
  - Environment: 🌍 [Location] 🌡️ [Weather/Temp] (Fetched via background service).
  - Live Clock: 📅 DD/MM/YYYY 🕒 HH:MM:SS.

### 5. Multi-Tabbed Reports Hub
- Integrated analytics for Users, Spy (Audit Logs), Employees, and Contracts.
- Advanced filtering (Global Search, Role/Status/Department dropdowns).
- Export capabilities for CSV and PDF (fpdf2 implementation).

## IMPLEMENTATION DIRECTIVES
- Use `ttkbootstrap` for the core widget set and theme management.
- Implement a `BackgroundScheduler` for non-blocking UI updates (clock, weather, alerts).
- Maintain strict Role-Based Access Control (RBAC) for sensitive features (Audit Log, User Management).
- Ensure all icons are Lucide/SVG-style (no emojis in final production assets, though emojis are used as placeholders in code).
- Design for a `zoomed` (maximized) desktop state by default.
