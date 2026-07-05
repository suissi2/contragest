# Master Prompt: Cyberpunk-Corporate OLED Interface

## Identity & Concept
**Identity:** Cyberpunk-meets-Corporate (Tech Noir Enterprise).
**Concept:** High-density HUD data-visualization combined with the structured authority of a modern ERP. Optimized for OLED displays.

## Design System (Tokens)
- **Background:** `#020617` (Deep Black / OLED)
- **Surface:** `#1E293B` (Slate Dark)
- **Corporate Navy:** `#0F172A` (Rich Background Contrast)
- **Primary / Success:** `#22C55E` (Vivid Green)
- **Danger (Static/Flash):** `#d9534f` / `#ff4444`
- **Warning (Static/Flash):** `#f0ad4e` / `#ffbb33`
- **Muted Text:** `#94A3B8`

## Typography
- **Headers:** Lexend (Modern, readable)
- **Branding Accents:** Playfair Display SC (Sophisticated)
- **Body Text:** Source Sans 3 (High clarity)
- **Technical/Data:** Fira Code (Monospaced HUD feel)

## Architecture & Layout
- **Navigation:** Top Ribbon Menu (Custom `Ribbon.TNotebook` style) with tabs for Home, Contracts, HR, Tools, and Reports.
- **Main View:** Hidden-tab Notebook (`Main.TNotebook` with `tabposition='n'`) synchronized with Ribbon selection.
- **Dashboard:** Hero section with 300x300 centered logo, 24pt bold title, and top statistics bar.
- **HUD Elements:** High-contrast status bar with dynamic system info (IP, Hostname) and environmental data (Weather/Clock).
- **Interactions:** 200ms smooth transitions, 800ms blinking cycles for critical alerts.

## Technical Standards
- **Compliance:** WCAG AAA (Contrast & Readability).
- **Icons:** SVG/Lucide-style (No emojis).
- **Frameworks:** Python, `ttkbootstrap` (Superhero base theme).
- **Best Practices:** Use `ttkbootstrap.widgets.tableview` for data-dense grids.
