# CONTRAGEST MASTER PROMPT v9: Cyberpunk-meets-Corporate OLED Interface

## Visual Identity & Concept
**Concept:** 'Cyberpunk-meets-Corporate'
**Core Values:** High integrity, space-efficient, data-dense, professional, futuristic.
**Aesthetic:** OLED Dark Mode with high contrast, tech noir/HUD elements, and corporate polish.

## Design Tokens (OLED Dark Mode)
| Token | Hex Code | Usage |
|-------|----------|-------|
| **Background** | `#020617` | Deepest OLED black for main windows and frames. |
| **Surface** | `#1E293B` | Card backgrounds, elevated surfaces. |
| **Corporate Navy** | `#0F172A` | Primary container backgrounds, headers. |
| **Primary/Success** | `#22C55E` | Positive indicators, primary buttons, success states. |
| **Text (High)** | `#F8FAFC` | Main headings and primary content. |
| **Text (Muted)** | `#94A3B8` | Secondary labels and descriptions. |
| **Danger (Flash)** | `#ff4444` | Active alert/critical state. |
| **Danger (Static)**| `#d9534f` | Persistent critical status. |
| **Warning (Flash)** | `#ffbb33` | Active warning/expiring state. |
| **Warning (Static)**| `#f0ad4e` | Persistent warning status. |

## Typography
- **Primary Headings:** Lexend
- **Branding Accents:** Playfair Display SC
- **Body Text:** Source Sans 3
- **Technical/Data:** Fira Code (Monospace)
- **Ribbon Tabs:** Helvetica 10 Bold (Padding: [20, 5])

## UI Architecture (Python / ttkbootstrap)
### 1. Main Navigation: Ribbon Menu
- **Implementation:** `ttk.Notebook` styled as `Ribbon.TNotebook`.
- **Tabs:** Home (Dashboard), Contracts, HR, Tools, Reports.
- **Visuals:** Integrated feel, avoiding traditional tab borders.

### 2. Dashboard Hero
- **Centerpiece:** Centered 300x300 company logo (`assets/company_logo.png` - Vincci Hoteles).
- **Stats Bar:** Top-aligned section tracking 'Active', 'Expiring', and 'Expired' contracts.
- **Typography:** Lexend 24pt Bold for "Contragest".

### 3. Data Visualization: Tableview
- **Library:** `ttkbootstrap.widgets.tableview`.
- **Features:** Global search, pagination (optional), column autofit.
- **Alerts:** Dynamic flashing (800ms interval) for critical rows using tag configuration.

### 4. Status Bar (Bottom)
- **Layout:** Left (PC Info: 💻 Name, IP), Center-Left (Session: User/Role), Center-Right (Environment: 🌍 Location, 🌡️ Weather), Right (🕒 Clock: %d/%m/%Y %H:%M:%S).
- **Style:** Inverse-Dark theme.

### 5. Multi-Tabbed Reports
- Standalone `Toplevel` window.
- Tabs for: 👤 Users, 🕵️ Spy (Audit Log), 👥 Employees, 📑 Contracts.
- Filtering: Date ranges, global search, and dropdowns for Role/Status/Department.

## Implementation Guidelines
- **Performance:** Use `image_cache` (PIL) for resized UI assets.
- **Transitions:** Smooth state changes (150-300ms).
- **Compliance:** WCAG AAA for OLED contrast levels.
- **Icons:** Use SVG/Lucide-style icons (no emojis as primary UI elements).
- **Base Theme:** `ttkbootstrap` 'superhero' (OLED-optimized).
