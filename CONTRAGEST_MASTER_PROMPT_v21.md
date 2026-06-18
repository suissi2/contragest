# CONTRAGEST MASTER PROMPT v21: CYBERPUNK-CORPORATE OLED INTERFACE

## Concept Identity
- **Name:** Contragest "Enterprise Noir"
- **Aesthetic:** Cyberpunk-meets-Corporate. A high-fidelity, OLED-optimized dark interface that blends the efficiency of an Enterprise Resource Planning (ERP) system with the aesthetic of tech-noir and HUD (Heads-Up Display) elements.
- **Brand Reference:** Influenced by the minimalist elegance of the Vincci Hoteles logo (Monochromatic, Serif branding).

## Design System & Tokens
### 1. Color Palette (OLED Optimized)
- **Background (Main):** `#020617` (Deepest Navy/Black)
- **Surface (Cards/Ribbon):** `#1E293B`
- **Corporate Accent:** `#0F172A`
- **Primary / Action (Positive):** `#22C55E` (Vibrant Neon Green)
- **Danger (Alerts):** `#ff4444` (Flash) / `#d9534f` (Static)
- **Warning (Warning):** `#ffbb33` (Flash) / `#f0ad4e` (Static)
- **Typography (Primary):** `#F8FAFC`
- **Typography (Muted):** `#94A3B8`

### 2. Typography Hierarchy
- **Primary Headers:** `Lexend` (Modern, geometric, highly readable)
- **Branding Accents:** `Playfair Display SC` (Elegance for title and luxury elements)
- **Body Text:** `Source Sans 3` (Professional, data-dense optimization)
- **Technical/Monospace:** `Fira Code` (For IDs, clock, and system logs)

### 3. UI Architecture (Python/ttkbootstrap)
- **Ribbon Menu:**
    - Tabs: [🏠 Home], [👔 HR], [🛠️ Tools], [📊 Reports]
    - Grouping: Buttons grouped within LabelFrames (e.g., "Navigation", "Session", "Administrative").
    - Style: `Ribbon.TNotebook` with `padding=[20, 5]` for tabs.
- **Dashboard Hero:**
    - Centered `300x300` Company Logo (Vincci 'V' Style).
    - Large Title: "Contragest" in `Lexend` 24pt Bold.
    - Subtitle: "Professional Contract Management System".
- **Navigation Sync:** Notebook-based switching where tabs are hidden (`style.layout('Main.TNotebook.Tab', [])`) to allow the Ribbon to control the view.
- **Bottom Status Bar:**
    - Persistent widgets for: `💻 PC Info`, `🌍 Location/Weather`, and a `🕒 Real-time Clock`.
    - Integrated `Sizegrip` and session identifiers.

### 4. Component Specifications
- **Data Tables:** High-density `Tableview` with flashing row states for expired (Danger) or expiring (Warning) contracts (800ms oscillation).
- **Forms:** `LabelFrame` containers with `padding=20`, standard label widths of 12, and button widths of 15.
- **Transitions:** Smooth UI interactions with 150-300ms durations.

## Technical Execution (Prompt Strategy)
"Develop a Python graphical interface using `ttkbootstrap` and `Pillow`. Apply a 'Cyberpunk-meets-Corporate' OLED Dark Mode using a palette of #020617 (Background) and #22C55E (Primary). Implement a Ribbon Menu architecture with a hidden-tab Notebook for navigation. Feature a centered Hero section with a 300x300 logo and a top statistics bar tracking 'Active', 'Expiring', and 'Expired' statuses. Ensure the bottom status bar includes system info and a persistent clock. Use Lexend for headers and Source Sans 3 for body text. All critical data rows must feature a smooth flashing animation between vivid and standard alert colors."
