# CONTRAGEST MASTER PROMPT v10 - THE CYBERPUNK CORPORATE INTERFACE

## Concept: "Cyberpunk-meets-Corporate"
Create a high-fidelity enterprise graphical interface for "Contragest", a professional contract management system. The design should merge the sterile efficiency of a corporate application with the high-contrast, data-dense aesthetic of Cyberpunk/Tech Noir (HUDs, OLED optimization, Glassmorphism).

## 1. Visual Identity & Brand
- **Branding:** "Contragest" - Professional, secure, and futuristic.
- **Logo Reference:** Vincci Hoteles logo (Stylized "V") should be integrated as the corporate centerpiece, particularly in a large, centered Hero section (300x300).
- **Aesthetic:** Dark Mode optimized for OLED (pure blacks), high contrast, minimal borders, and smooth transitions (150-300ms).

## 2. Color Palette (OLED Dark Mode)
- **Background (Pure Black):** `#020617` (The void)
- **Surface (Slate):** `#1E293B` (For frames, buttons, and secondary backgrounds)
- **Corporate Navy:** `#0F172A` (For headers and deep surfaces)
- **Primary Accent (Cyber Green):** `#22C55E` (Success, active states, and primary actions)
- **Muted Text:** `#94A3B8` (For secondary information)
- **Static Danger:** `#d9534f` / **Flash Danger:** `#ff4444` (For expired/critical alerts)
- **Static Warning:** `#f0ad4e` / **Flash Warning:** `#ffbb33` (For expiring/near-critical alerts)

## 3. Typography
- **Primary Headers:** `Lexend` (Clean, geometric, modern)
- **Branding Accents:** `Playfair Display SC` (Serif elegance for a corporate touch)
- **Body Text:** `Source Sans 3` (High-readability for data-dense grids)
- **Technical/Data:** `Fira Code` (Monospaced for telemetry and logs)

## 4. UI Architecture (The Ribbon Layout)
- **Ribbon Menu:**
    - Customized `ttkbootstrap` Notebook with `Ribbon.TNotebook` style.
    - Tabs: Home (🏠), HR (👔), Tools (🛠️), Reports (📊).
    - Buttons inside the ribbon should be grouped by function (e.g., Navigation, Settings, Session) with clear icons and `padding=10`.
- **Dashboard Hero:**
    - Centered logo (300x300) with "Contragest" branding in large font (24pt).
    - A stats bar at the top displaying active, expiring, and expired contract counts.
- **Main Content Area:**
    - A multi-tabbed interface (Notebook) to switch between the Hero Dashboard and the Contracts Management table.
    - Tables should use `ttkbootstrap.widgets.tableview` with custom row coloring based on status.
- **Dynamic Status Bar:**
    - Located at the bottom with a `DARK` bootstyle.
    - Left: PC Info (Host, IP) and Login Session info.
    - Center: Environmental Data (Location, Weather/Temperature) fetched via background services.
    - Right: A persistent, real-time clock (📅 dd/mm/yyyy 🕒 HH:MM:SS).

## 5. Visual Interactions
- **Alert Flashing:** Expiring or Expired items in tables should alternate colors every 800ms between their static and flash variants to draw immediate attention.
- **Transitions:** Layout changes and tab switching should feel snappy yet smooth.
- **RTL Support:** The UI must be architected to support Right-to-Left (RTL) layouts for Arabic/Hebrew locales, flipping side-packing logic accordingly.

## 6. Technical Keywords
Python, ttkbootstrap, SQLAlchemy, Pillow (PIL), fpdf2, OLED UI, Cyberpunk HUD, Enterprise Dashboard, Data-Dense Grid, Glassmorphism, WCAG AAA Compliance, Tech Noir.
