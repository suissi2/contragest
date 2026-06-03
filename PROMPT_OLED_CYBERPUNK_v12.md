# Contragest Master Prompt v12: 'Cyberpunk-meets-Corporate' OLED Interface

## Visual Identity & Core Concept
**Identity:** A sophisticated 'Cyberpunk-meets-Corporate' interface designed for high-density enterprise data management. It blends the futuristic, high-contrast aesthetic of 'Tech Noir' with the stability and authority of a 'Corporate Enterprise' gateway.
**Design System:** OLED Dark Mode optimized, emphasizing deep blacks, high-contrast neon accents, and professional typography.

## Technical Specifications & Design Tokens

### 1. Color Palette (OLED Optimized)
- **Background:** `#020617` (Deep Obsidian - OLED True Black)
- **Surface/Cards:** `#1E293B` (Slate Blue-Grey - Semi-transparent glassmorphism)
- **Corporate Accent:** `#0F172A` (Navy Midnight - Trust & Authority)
- **Primary Action:** `#22C55E` (Emerald Green - Success & Positive Indicators)
- **Danger/Expired:** Active `#ff4444` / Static `#d9534f` (Flash-ready)
- **Warning/Expiring:** Active `#ffbb33` / Static `#f0ad4e` (Flash-ready)
- **Muted Text:** `#94A3B8` (Slate-400)
- **Primary Text:** `#F8FAFC` (Slate-50)

### 2. Typography Pairings
- **Primary Headers:** `Lexend` (Modern, readable, geometric)
- **Branding/Accents:** `Playfair Display SC` (Elegant, traditional authority)
- **Body Text:** `Source Sans 3` (High legibility for data density)
- **Technical/Data:** `Fira Code` (Monospace with ligatures for code/IDs)

### 3. UI Architecture (The 'Enterprise Gateway' Pattern)
- **Ribbon Navigation:** A multi-tabbed Ribbon Menu (`ttkbootstrap.Notebook`) at the top, grouping actions into 'Home', 'Contracts', 'HR', 'Tools', and 'Reports'.
    - *Style:* `Ribbon.TNotebook` and `Ribbon.TNotebook.Tab` with `Helvetica 10 Bold` and `[20, 5]` padding.
- **Dashboard Hero:** A centered Hero section featuring a `300x300` company logo (Vincci Hoteles reference) on a glassmorphic surface.
- **Data-Dense Tableview:** High-contrast `Tableview` with status-based row highlighting and flashing alerts (800ms interval).
- **Dynamic Status Bar:** A persistent bottom bar displaying:
    - PC Information (Host & IP)
    - Environmental Data (Location & Weather)
    - Persistent Clock (📅 DD/MM/YYYY 🕒 HH:MM:SS)

### 4. Interactive Elements & Effects
- **Transitions:** Smooth state changes (150-300ms).
- **Icons:** SVG/Lucide-style (Strictly no emojis as primary UI icons).
- **Hover States:** Stable `cursor-pointer` with subtle glow/opacity shifts; no layout-shifting transforms.
- **Compliance:** Target WCAG AAA contrast ratios for the OLED theme.

## Implementation Prompt
"Design a professional Enterprise Management Dashboard using Python and ttkbootstrap with an 'OLED Dark Mode' aesthetic. Apply the 'Cyberpunk-meets-Corporate' concept using a palette of Deep Obsidian (#020617), Midnight Navy (#0F172A), and Emerald Green (#22C55E). Implement a Ribbon Menu architecture for navigation and a Data-Dense Hero section for the dashboard. Use Lexend for headers and Source Sans 3 for body text. Ensure high contrast (WCAG AAA) and integrate a dynamic system status bar at the bottom. Avoid playful gradients; focus on 'Tech Noir' precision and 'Trust & Authority' patterns."
