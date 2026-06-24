# CONTRAGEST MASTER PROMPT v24: Cyberpunk-Corporate OLED Interface

## Identity & Concept
Create a high-fidelity, professional "Cyberpunk-meets-Corporate" interface for the Contragest enterprise contract management system. The design must balance a tech-noir/HUD aesthetic with executive-level clarity and data density.

## Design Tokens (OLED Dark Mode)
- **Background:** `#020617` (Deepest Space)
- **Surface:** `#1E293B` (Steel Slate)
- **Corporate Navy:** `#0F172A` (Accent Surface)
- **Primary:** `#22C55E` (Emerald Tech - Active/Success)
- **Secondary/Muted:** `#94A3B8` (Cool Grey - Body text/Subtitles)
- **Danger (Critical):** Flash `#ff4444` / Static `#d9534f`
- **Warning (Expiring):** Flash `#ffbb33` / Static `#f0ad4e`
- **Compliance:** Full WCAG AAA contrast compliance for all UI elements.

## Typography
- **Primary Headers:** Lexend (Modern, clean, geometric)
- **Branding Accents:** Playfair Display SC (Classic serif for high-end corporate feel)
- **Body Text:** Source Sans 3 (Optimized for long-form readability)
- **Technical/Monospace:** Fira Code (For data-dense grids and system status)

## Layout & Architecture
1. **Ribbon Navigation:**
   - Implementation: `ttkbootstrap` Ribbon-style Notebook.
   - Tabs: Home, Contracts, HR, Tools, Reports.
   - Style: `Ribbon.TNotebook` with `[20, 5]` padding, bold 10pt Lexend font.
   - Synchronization: Ribbon tabs must drive the main workspace view via a hidden-tab notebook.

2. **Dashboard (Hero Section):**
   - Centerpiece: High-fidelity 300x300 Vincci Hoteles logo (minimalist serif 'V').
   - Statistics Bar: Top-aligned HUD tracking Active, Expiring, and Expired contracts.
   - Transitions: Smooth 200ms animations for state changes.

3. **Status Bar (System HUD):**
   - Location: Sticky bottom bar.
   - Content:
     - Left: 💻 Hostname & IP Address.
     - Center: 🌍 Geolocation & Weather (Real-time).
     - Right: 🕒 Persistent Digital Clock (Fira Code).

4. **Data Management:**
   - Grid Style: High-density HUD grids with `ttkbootstrap.widgets.tableview`.
   - Alerts: Blinking status indicators for contracts within the threshold (800ms cycle).
   - Icons: Strictly SVG/Lucide-style vector icons (avoid emojis in production build).

## UI/UX Standards
- **Interactivity:** Every actionable element should have a clear hover state using Primary or Secondary glow.
- **Micro-interactions:** Use subtle 200ms transitions for menu expansions and button presses.
- **Accessibility:** Ensure clear visual hierarchy and high readability for detailed contract data.
- **Responsiveness:** Maintain a "Data-Dense Dashboard" pattern that scales for desktop enterprise use.
