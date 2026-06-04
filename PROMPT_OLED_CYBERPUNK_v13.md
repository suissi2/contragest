# CONTRAGEST MASTER PROMPT v13: Cyberpunk-meets-Corporate OLED Interface

## 1. Visual Identity & Concept
**Concept:** A high-fidelity "Cyberpunk-meets-Corporate" interface designed for high-stakes enterprise management (Contragest). The aesthetic balances professional reliability with a futuristic, tech-noir HUD (Heads-Up Display) feel.
**Atmosphere:** Deep OLED blacks, high-contrast neon accents, and data-dense layouts.
**Design System:** "Enterprise Gateway" architecture with a focus on space-efficient OLED palettes and WCAG AAA compliance.

## 2. Color Palette (OLED Dark Mode)
- **Background (OLED Deep Black):** `#020617` (Primary background for maximum contrast and battery efficiency).
- **Surface (Midnight Slate):** `#1E293B` (Cards, panels, and secondary backgrounds).
- **Corporate Navy (Deep Blue):** `#0F172A` (Header backgrounds and structural elements).
- **Primary Accent (Success Green):** `#22C55E` (Main action buttons, positive status indicators, and HUD highlights).
- **Secondary Accent (Cyber Blue):** `#3B82F6` (Informational elements and navigation).
- **Text (Off-White):** `#F8FAFC` (High readability).
- **Muted Text:** `#94A3B8` (Labels and metadata).
- **Alert (Danger):** `#FF4444` (Flash) / `#D9534F` (Static).
- **Alert (Warning):** `#FFBB33` (Flash) / `#F0AD4E` (Static).

## 3. Typography Pairings
- **Primary Headers:** **Lexend** (Geometric, designed for maximum readability).
- **Branding Accents:** **Playfair Display SC** (Small caps serif for a touch of "Corporate Luxury").
- **Body Text:** **Source Sans 3** (Professional, highly readable at small sizes).
- **Technical/Monospace:** **Fira Code** (For IDs, dates, and status bars to reinforce the "Terminal/HUD" feel).

## 4. UI Architectural Specifications

### A. The Ribbon Menu (Command Center)
- **Structure:** Multi-tabbed ribbon (Home, Contracts, HR, Tools, Reports) using a customized `ttk.Notebook` style ('Ribbon.TNotebook').
- **Styling:** Helvetica 10 Bold font, [20, 5] padding.
- **Visual Grouping:** Buttons grouped in `LabelFrame` containers (e.g., "Navigation", "Administrative") with varying bootstyles (INFO, LIGHT, SECONDARY, DANGER).

### B. Dashboard Hero (Mission Control)
- **Layout:** Centered 300x300 company logo (e.g., Vincci Hoteles) on a deep black background.
- **Stats Bar:** A top-level summary displaying active, expiring, and expired contracts using high-contrast status colors.
- **Animation:** 800ms flash interval for critical alerts (Danger/Warning states) in data tables.

### C. Dynamic Status Bar (System HUD)
- **Location:** Persistent bottom bar.
- **Contents:**
  - **Left:** PC Info (Hostname + Local IP).
  - **Center:** Session Info (Logged-in user and role).
  - **Environment:** Dynamic Location and Weather data (updated via background scheduler).
  - **Right:** Persistent Clock (Date + Time in HH:MMS format).

## 5. Technical Implementation Guidelines (Python/ttkbootstrap)
- **Base Theme:** Use `ttkbootstrap` with the **"superhero"** theme as a foundation for the OLED aesthetic.
- **Window Management:** Zoomed state for desktops, centered for login (500x650).
- **Tableview:** Use `ttkbootstrap.widgets.tableview` (avoid deprecated `ttkbootstrap.tableview`). Implement dynamic row tagging for status-based coloring.
- **Image Optimization:** Implement an `image_cache` for UI assets (logos, icons) to ensure smooth transitions and minimal I/O.
- **Localization:** i18n support for French, Arabic (RTL), and English.

## 6. Prompt Keywords for Generation
> "Design a professional Python GUI using ttkbootstrap Superhero theme. Identity: Cyberpunk-meets-Corporate. Palette: OLED Black (#020617), Success Green (#22C55E), Corporate Navy (#0F172A). Typography: Lexend and Fira Code. Layout: Ribbon Menu with tabbed navigation, Dashboard Hero with large central logo, and a HUD-style bottom status bar displaying system info, location, weather, and a clock. High-contrast data tables with flashing alert states for critical rows."
