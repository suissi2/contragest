# CONTRAGEST MASTER PROMPT v14: THE CYBERPUNK-MEETS-CORPORATE INTERFACE

You are a Senior UI/UX Architect and Lead Python Developer. Your mission is to recreate and extend the **Contragest** interface: a high-fidelity, data-dense professional contract management system that fuses **Cyberpunk aesthetics** (OLED dark mode, neon accents, HUD-style precision) with **Enterprise-grade Corporate identity** (clean layouts, ribbon navigation, WCAG AAA compliance).

## 1. VISUAL IDENTITY & BRANDING (VINCCI HOTELES SYNTHESIS)
The interface must center around the **Vincci Hoteles** corporate branding, characterized by a minimalist, serif-heavy luxury aesthetic.
- **Centerpiece:** A high-contrast version of the Vincci "V" logo (serif, elegant) presented in a Dashboard Hero section.
- **Atmosphere:** "Luxury Noir." It should feel like a high-end executive terminal from a near-future metropolis.

## 2. DESIGN TOKENS (OLED DARK MODE)
Implement the following color palette and typography to ensure maximum contrast and space efficiency:

### A. Color Palette (Hex Codes)
- **Background (Deep OLED):** `#020617` (The void)
- **Surface (Card/Elevated):** `#1E293B`
- **Corporate Navy (Accent):** `#0F172A`
- **Primary / Action (Neon Emerald):** `#22C55E`
- **Secondary / Muted Text:** `#94A3B8`
- **Alert - Danger (Vivid/Static):** `#ff4444` / `#d9534f`
- **Alert - Warning (Vivid/Static):** `#ffbb33` / `#f0ad4e`

### B. Typography
- **Primary Headers:** `Lexend` (Clean, geometric, highly legible)
- **Branding Accents:** `Playfair Display SC` (Serif, elegant, for the "Vincci" luxury feel)
- **Body Text:** `Source Sans 3` (Optimized for long reading of contract data)
- **Data/Technical:** `Fira Code` (Monospace for IDs, timestamps, and PC info)

## 3. UI ARCHITECTURE (RIBBON & DASHBOARD)
The application utilizes a **Ribbon-based navigation system** to maintain a clean "Enterprise Gateway" feel while maximizing screen real estate.

### A. The Ribbon Menu (`ttkbootstrap.Notebook`)
- **Style:** `Ribbon.TNotebook` (Top-aligned, tabs without borders until active).
- **Tabs:** `Home`, `HR`, `Tools`, `Reports`.
- **Button Grouping:** Use `LabelFrame` wrappers within ribbon tabs to group related actions (e.g., "Navigation", "Settings", "Session").
- **Buttons:** Large, padded (`padding=10`), using `INFO`, `LIGHT`, and `DANGER` bootstyles for visual hierarchy.

### B. The Dashboard Hero
- **Layout:** Centered 300x300 logo in a high-contrast Hero section.
- **Stats Bar:** A horizontal bar at the top of the dashboard tracking:
  - `Active Contracts`
  - `Expiring Soon` (Warning flash: 800ms interval)
  - `Expired` (Danger flash: 800ms interval)

### C. The Bottom Status Bar
- **System HUD:** Display dynamic information in a `#0F172A` bar at the bottom:
  - **Left:** PC Info (Hostname & IP) + Current Session User.
  - **Center:** Environment Data (Location & Weather via `wttr.in`).
  - **Right:** Persistent Clock (`dd/mm/yyyy   HH:MM:SS`).

## 4. TECHNICAL SPECIFICATIONS (PYTHON / TTKBOOTSTRAP)
- **Base Theme:** `ttkbootstrap` "superhero" (modified for OLED Dark Mode).
- **Table View:** Use `ttkbootstrap.tableview` (import from `ttkbootstrap.widgets.tableview` to avoid deprecation).
- **Transitions:** Smooth UI transitions (150-300ms).
- **Interactions:**
  - Double-click to Edit.
  - Interactive icons (✏️, 🗑️) in table columns.
  - Context-aware Ribbon tabs that update the main view.
- **Security:** Logic for secure deletion based on date-calculated passwords: `((day + month + year_short) * 2) - 10`.

## 5. DESIGN PHILOSOPHY
- **Data-Density:** Prioritize information over whitespace.
- **Accessibility:** Maintain WCAG AAA compliance for text contrast.
- **HUD Elements:** Use borders, separators, and subtle glows to give a "glassmorphism" or "HUD" feel to the corporate interface.

---
**Instruction:** Generate a complete Python implementation using `ttkbootstrap` and `PIL` that builds this interface, ensuring the Ribbon Menu correctly switches between the Dashboard Hero and the Contract Management Table.
