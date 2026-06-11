# CONTRAGEST MASTER PROMPT v15: Cyberpunk-meets-Corporate OLED Interface

## Visual Identity & Design Philosophy
**Identity:** "Cyberpunk-meets-Corporate" — A fusion of high-stakes corporate enterprise and futuristic, data-dense aesthetics.
**Vibe:** Professional, high-integrity, technical, and space-efficient.
**Theme:** Ultra-dark OLED mode with vibrant neon accents and high-contrast typography.

## Core Design Tokens
### 1. Color Palette (OLED Dark Mode)
- **Background (Base):** `#020617` (True Black/Deepest Navy for OLED efficiency)
- **Surface (Elevated):** `#1E293B` (Used for containers, ribbons, and cards)
- **Accent/Primary:** `#22C55E` (Emerald Green - "Success" and action color)
- **Corporate Navy:** `#0F172A` (Secondary surface color for depth)
- **Text (Primary):** `#F8FAFC` (Off-white for readability)
- **Text (Muted):** `#94A3B8` (Secondary information)
- **Alert (Danger):** `#ff4444` (Flash) / `#d9534f` (Static)
- **Alert (Warning):** `#ffbb33` (Flash) / `#f0ad4e` (Static)

### 2. Typography
- **Primary Headers:** *Lexend* (Modern, geometric, high readability)
- **Branding Accents:** *Playfair Display SC* (Serif elegance for the logo/hero)
- **Body Text:** *Source Sans 3* (Professional, clean sans-serif)
- **Technical/Data:** *Fira Code* (Monospace for IDs, timestamps, and stats)

## UI Architecture (The Ribbon Layout)
### 1. Top Ribbon Navigation
- **Style:** `Ribbon.TNotebook` with `Ribbon.TNotebook.Tab`.
- **Navigation Tabs:** Home (🏠), Contracts (📑), HR (👔), Tools (🛠️), Reports (📊).
- **Tab Styling:** Helvetica 10 Bold, Padding `[20, 5]`.
- **Action Groups:** Grouped buttons within each tab (e.g., "Navigation", "Settings", "Session") inside styled `LabelFrame` containers.

### 2. Dashboard Hero Section
- **Composition:** Centered vertically and horizontally in the "Home" tab.
- **Logo:** High-fidelity company logo (e.g., Vincci Hoteles) scaled to `300x300`.
- **Title:** "Contragest" in large, bold Lexend font.
- **Subtitle:** "Professional Contract Management System" in subtle Source Sans 3.
- **Stats Bar:** A top-aligned bar showing: `Active: X | Expiring: Y | Expired: Z` using status-synced colors.

### 3. Data-Dense Tables (Tableview)
- **Implementation:** `ttkbootstrap.widgets.tableview`.
- **Visuals:** High-contrast rows with status-based coloring.
- **Dynamic Effects:** Smooth flashing animations (800ms intervals) for "Danger" (Expired) and "Warning" (Expiring) rows.
- **Interactions:** Inline action icons (✏️ Edit, 🗑️ Delete) in the first columns.

### 4. System Status Bar
- **Position:** Persistent at the bottom of the window.
- **Background:** `#020617` (Darkest).
- **Elements:**
  - **PC Info:** `💻 [MachineName] ([IP_Address])`
  - **Env Data:** `🌍 [Location]   🌡️ [Temperature]` (Dynamic updates)
  - **Clock:** `📅 DD/MM/YYYY   🕒 HH:MM:SS` (Persistent 1s interval)

## Technical Specification
- **Framework:** Python with `ttkbootstrap` (Superhero theme base).
- **Icons:** SVG-style icons or Lucide-inspired glyphs.
- **Transitions:** Smooth UI state changes (150-300ms).
- **RTL Support:** Bi-directional layout compatibility for internationalization (AR, EN, FR).
- **Compliance:** WCAG AAA contrast ratios for OLED dark theme.

## Prompt for AI Generation
> "Create a Python-based GUI using `ttkbootstrap` that embodies a 'Cyberpunk-meets-Corporate' aesthetic for an enterprise contract management system named 'Contragest'. Use an OLED-optimized palette featuring a `#020617` background with `#22C55E` emerald accents. Implement a multi-tabbed Ribbon Menu navigation at the top and a data-dense dashboard with a centralized Hero section containing a large company logo. The interface must include a persistent bottom status bar displaying dynamic system info (PC name, IP), live weather/location data, and a real-time clock. Ensure the design utilizes Lexend for headers and Source Sans 3 for body text, maintaining high contrast and professional density. Tables should feature status-based row highlighting with subtle flashing effects for critical alerts."
