# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' Interface

## Concept Overview
Create a sophisticated graphical interface that merges the high-density data visualization of a sci-fi HUD with the structured authority of an enterprise ERP. The aesthetic is defined as 'Cyberpunk Corporate'—a tech-noir, OLED-optimized environment that prioritizes high contrast, professional typography, and WCAG AAA compliance.

## Technical Specifications & Design Tokens

### 1. Color Palette (OLED Dark Mode)
- **Background (Deep Space):** `#020617` (True Black/OLED)
- **Surface (Slate):** `#1E293B` (Cards and nested containers)
- **Primary (Corporate Navy):** `#0F172A` (Ribbon background and headers)
- **Accent (Success Green):** `#22C55E` (Primary actions and active states)
- **Alert (Danger Flash):** `#ff4444` / `#d9534f` (Blinking cycle for critical data)
- **Warning (Warning Flash):** `#ffbb33` / `#f0ad4e` (Blinking cycle for expiring data)
- **Muted Text:** `#94A3B8` (Secondary information)

### 2. Typography
- **Primary Headers:** `Lexend` (Clean, geometric, professional)
- **Branding Accents:** `Playfair Display SC` (Serif elegance for the 'V' logo and titles)
- **Body Text:** `Source Sans 3` (High-readability sans-serif for dense data)
- **Monospace/Data:** `Fira Code` (Technical precision for IDs and status codes)

### 3. UI Architecture (ttkbootstrap / Python)
- **Ribbon Navigation:** Implement a top-level Ribbon Menu using custom `Ribbon.TNotebook` styles with `Helvetica 10 Bold` font and `[20, 5]` padding. Synchronize ribbon tabs with hidden main content notebook tabs.
- **HUD Dashboard:** Centralized hero section featuring a 300x300 minimalist company logo. Top statistics bar tracking 'Active', 'Expiring', and 'Expired' statuses.
- **Dynamic Status Bar:** A bottom bar using `inverse-dark` bootstyle displaying:
  - System info (Hostname/IP)
  - Environment data (Location/Weather)
  - Persistent real-time clock (Format: `📅 DD/MM/YYYY 🕒 HH:MM:SS`)
- **Data Grids:** High-contrast tables with 800ms blinking cycles for rows requiring immediate attention (danger/warning states).

## Visual Directives
- **Iconography:** Strictly use SVG/Lucide-style icons. No emojis in the interface.
- **Transitions:** Smooth `200ms` transitions for all hover states and view switches.
- **Branding:** Centered minimalist serif branding asset ('V' logo) as the core visual anchor.
- **Layout:** Enterprise Gateway pattern with space-efficient OLED layouts.
