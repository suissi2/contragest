# CONTRAGEST MASTER PROMPT: Cyberpunk-meets-Corporate OLED Interface

## Identity & Vision
Reconstruct the 'Contragest' interface, a high-fidelity enterprise management system that blends a 'Cyberpunk' aesthetic with 'Corporate' precision. The design must be optimized for OLED displays, utilizing deep blacks, high-contrast accents, and a space-efficient 'Ribbon' architecture.

## Branding: Vincci Hoteles
- **Logo:** Centerpiece branding using the Vincci Hoteles logo (stylized 'V').
- **Typography:**
  - **Primary Headers:** 'Lexend' (Modern, clean, corporate).
  - **Branding Accents:** 'Playfair Display SC' (Elegant, serif).
  - **Body Text:** 'Source Sans 3' (High readability).
  - **Data/Technical:** 'Fira Code' (Monospace).

## Color Palette (OLED Dark Mode)
- **Background:** `#020617` (Deepest Black/Navy)
- **Surface/Cards:** `#1E293B` (Slate Navy)
- **Corporate Accent:** `#0F172A` (Rich Navy)
- **Primary Action:** `#22C55E` (Cyber Green/Emerald)
- **Danger/Expired:** `#ff4444` (Flash) / `#d9534f` (Static)
- **Warning/Expiring:** `#ffbb33` (Flash) / `#f0ad4e` (Static)
- **Muted Text:** `#94A3B8`

## UI Architecture
1. **Ribbon Menu (Top):**
   - Multi-tabbed navigation (Home, Contracts, HR, Tools, Reports).
   - Custom 'Ribbon.TNotebook' style with large, padded tabs (`[20, 5]`).
   - Grouped buttons within LabelFrames for logical organization (Navigation, Settings, Session, Employees, etc.).
2. **Dashboard Hero (Home Tab):**
   - Centered 300x300 Vincci Hoteles logo.
   - Dynamic Stats Bar: Tracks 'Active', 'Expiring', and 'Expired' contracts with status counts.
3. **Data Grid (Contracts Tab):**
   - High-density Tableview (ttkbootstrap) with custom row tagging.
   - Smooth 800ms flash animation for critical (expired) and warning (expiring) items.
4. **Bottom Status Bar:**
   - Left Section: Dynamic PC Info (Hostname, IP) and Environmental Data (Real-time Location/Weather).
   - Right Section: Persistent Digital Clock (Date & Time).
   - Style: `inverse-dark` for high contrast against the OLED background.

## Technical Specifications
- **Framework:** Python with `ttkbootstrap` (Superhero base theme).
- **Transitions:** Smooth 150-300ms hover/active states.
- **Compliance:** WCAG AAA for contrast in Dark Mode.
- **Interactive Logic:** Secure deletion requires a daily-calculated password: `((day + month + year_short) * 2) - 10`.
