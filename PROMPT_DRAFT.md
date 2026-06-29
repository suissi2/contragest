# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' Interface

## Concept Overview
Create a high-fidelity, "Cyberpunk-meets-Corporate" OLED interface for a professional Enterprise Resource Planning (ERP) dashboard. The design must bridge the gap between high-density sci-fi HUD aesthetics and the structured authority of a modern corporate application.

## 1. Visual Identity & Design Tokens
- **Theme:** OLED Dark Mode (Deepest Blacks, High Contrast).
- **Color Palette:**
    - **Background:** `#020617` (Deep Obsidian).
    - **Surface/Cards:** `#1E293B` (Steel Slate).
    - **Corporate Accents:** `#0F172A` (Navy Authority).
    - **Primary Action/Success:** `#22C55E` (Emerald Cyber-Green).
    - **Alerts (Static/Flash):**
        - **Danger:** `#ff4444` / `#d9534f`
        - **Warning:** `#ffbb33` / `#f0ad4e`
- **Typography:**
    - **Primary Headers:** Lexend (Modern, Geometric).
    - **Branding Accents:** Playfair Display SC (Sophisticated Serif).
    - **Detailed Body:** Source Sans 3 (High Readability).
    - **Technical/Data Density:** Fira Code (Monospaced, Data-centric).

## 2. Layout Architecture
- **Navigation:** Implementation of a customized "Ribbon Menu" with tabs (Home, HR, Tools, Reports). Use a 'Main.TNotebook' style where tabs are synchronized but the physical tab bar is hidden to create a seamless interface feel.
- **Hero Section:** Centered centerpiece featuring a 300x300 minimalist company logo.
- **Dashboard Grid:** HUD-style data-dense layout tracking contract statuses (Active, Expiring, Expired).
- **Status Bar:** A persistent bottom bar displaying dynamic system telemetry:
    - Left: PC Info (Hostname, Local IP).
    - Center: Environment Data (Location, Temperature).
    - Right: Persistent Digital Clock (📅 DD/MM/YYYY   🕒 HH:MM:SS).

## 3. Interaction & Motion
- **Transitions:** Smooth 200ms transitions for all hover states and view switches.
- **Blinking Alerts:** Critical data rows in HUD grids must feature an 800ms alternating flash effect between vivid and muted alert colors to indicate urgency.
- **Accessibility:** Ensure WCAG AAA compliance for the OLED theme, emphasizing clear text contrast against the `#020617` background.
- **Icons:** Strictly use minimalist SVG/Lucide-style icons; avoid emojis to maintain professional corporate authority.

## 4. Prompt Keywords
"Enterprise Gateway, Data-Dense Dashboard, Tech Noir, HUD, OLED Dark Mode, Corporate Authority, Sci-fi ERP, High-Contrast UI, Professional Minimalist."
