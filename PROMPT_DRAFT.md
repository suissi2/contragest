# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

## Identity & Core Concept
**Style Name**: Cyberpunk-meets-Corporate (OLED Dark Mode)
**Concept**: A fusion of high-density sci-fi HUD aesthetics with the structured authority of an enterprise ERP. Optimized for high contrast, space efficiency, and professional data visualization on OLED displays.

## Design Tokens (WCAG AAA Compliant)
- **Background**: `#020617` (OLED Deep Black)
- **Surface/Cards**: `#1E293B` (Slate Deep Blue)
- **Corporate Accent**: `#0F172A` (Navy Midnight)
- **Primary/Positive**: `#22C55E` (Emerald Neon Green)
- **Secondary/Muted**: `#94A3B8` (Cool Grey)
- **Danger/Alert**: `#ff4444` (Flash) / `#d9534f` (Static)
- **Warning/Pending**: `#ffbb33` (Flash) / `#f0ad4e` (Static)

## Typography (Hierarchy)
1. **Primary Headers**: `Lexend` (24pt+, Bold) - Modern, geometric authority.
2. **Branding Accents**: `Playfair Display SC` (Serif, Small Caps) - Luxury/Corporate prestige.
3. **Body Text**: `Source Sans 3` - High readability for dense information.
4. **Data/Technical**: `Fira Code` (Monospace) - Used for IDs, timestamps, and system logs.

## Layout & Components
- **Ribbon Navigation**: Top-docked 'Ribbon.TNotebook' with tabs for Home, Contracts, HR, Tools, and Reports. Active tabs use high-contrast emerald indicators.
- **Hero Dashboard**: Centralized 300x300 corporate logo with 24pt bold title and 14pt subtitle.
- **HUD Data Grids**: High-density table views (`ttkbootstrap.widgets.tableview`) with 800ms blinking cycles for critical alerts.
- **Status Bar**: Bottom-aligned HUD displaying local IP, Hostname, Environment data (Weather/Location), and a persistent seconds-accurate clock.

## Interactions & UX
- **Transitions**: Smooth 200ms `transition-colors` on all interactive elements.
- **Icons**: SVG/Lucide-style icons only (strictly no emojis in UI).
- **Feedback**: Blinking status alerts (800ms cycle) for data that requires immediate attention (e.g., expired contracts).
- **Accessibility**: Optimized for WCAG AAA contrast ratios.

## Technical Implementation (Python/ttkbootstrap)
- Use 'superhero' base theme modified for OLED black.
- Implement 'Main.TNotebook' with `tabposition='n'` and hidden layout to sync with Ribbon navigation.
- Sequential cleaning of dev environment to prevent binary artifact contamination.
