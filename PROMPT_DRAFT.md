# Contragest Master Prompt: Cyberpunk-Corporate OLED Interface

## 1. Visual Identity & Concept
**Concept:** "Cyberpunk-meets-Corporate"
**Style Description:** A high-fidelity fusion of sci-fi HUD (Heads-Up Display) data-density with the structured authority of an Enterprise ERP. It emphasizes high contrast, space-efficient layouts, and an OLED-optimized aesthetic.
**Identity Keywords:** Professional, Futuristic, Tech-Noir, High-Integrity, Data-Driven.

## 2. Design Tokens (OLED Dark Mode)
### Color Palette
- **Background:** `#020617` (True OLED Black)
- **Surface/Card:** `#1E293B` (Slate-800)
- **Corporate Navy:** `#0F172A` (Slate-900)
- **Primary/Success:** `#22C55E` (Emerald-500)
- **Danger (Static/Flash):** `#d9534f` / `#ff4444`
- **Warning (Static/Flash):** `#f0ad4e` / `#ffbb33`
- **Muted Text:** `#94A3B8` (Slate-400)
- **Primary Text:** `#F8FAFC` (Slate-50)

### Typography Pairing
- **Branding Accents:** `Playfair Display SC` (Serif, Small Caps)
- **Primary Headers:** `Lexend` (Geometric Sans, High Readability)
- **Technical/Data:** `Fira Code` (Monospace, Ligatures)
- **Body Text:** `Source Sans 3` (Professional Sans)

## 3. Architectural Components & Layout
### Core Navigation: Ribbon Menu
- **Style:** `Ribbon.TNotebook` / `Ribbon.TNotebook.Tab`
- **Font:** `Helvetica 10 Bold`
- **Padding:** `[20, 5]`
- **Sync:** Hidden main notebook tabs (`tabposition='n'`) to create a synchronized Ribbon-to-Content transition.

### Dashboard Hero Section
- **Logo:** 300x300 minimalist branding asset (Centered).
- **Title:** 24pt Bold Lexend.
- **Subtitle:** 14pt Source Sans 3.
- **Stats Bar:** Top-aligned bar tracking Active, Expiring, and Expired contract statuses.

### HUD-Style Data Grids
- **Component:** `ttkbootstrap.widgets.tableview` (Avoid deprecated tableview).
- **Alerts:** Critical data must use an **800ms blinking cycle** between static and flash color pairs.
- **Contrast:** Ensure WCAG AAA compliance (7:1 ratio recommended for OLED).

### System Status Bar
- **Theme:** `inverse-dark` bootstyle.
- **Persistent Elements:**
  - Hostname & IP Address (Left).
  - Location & Weather Data (Center).
  - Clock: `📅 DD/MM/YYYY  🕒 HH:MM:SS` (Right).

## 4. Interaction & Motion
- **Transitions:** Global `200ms` smooth transitions for hover and state changes.
- **Icons:** Strictly use **SVG/Lucide-style** vector icons. **DO NOT USE EMOJIS** for UI actions.
- **Cursors:** Explicit `cursor-pointer` on all interactive cards and buttons.

## 5. Technical Requirements
- **Stack:** Python, `ttkbootstrap` (Superhero theme base), `SQLAlchemy`, `Pillow`.
- **Compliance:** Full WCAG AAA contrast compliance for low-light environments.
- **Responsive Logic:** Optimized for 1024px to 4K resolutions (Desktop-first).
