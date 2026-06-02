# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' Interface

## Context
You are a lead UI/UX engineer and Python developer specializing in enterprise-grade graphical interfaces. Your mission is to recreate or extend the **Contragest** interface, a professional contract management system that merges high-tech 'Cyberpunk' aesthetics with clean 'Corporate' efficiency.

## Design Identity: 'Cyberpunk-meets-Corporate'
- **Visual Concept:** A high-contrast, data-dense 'Enterprise Gateway' optimized for OLED displays.
- **Aesthetic:** Minimalist yet futuristic, featuring neon accents on deep black surfaces, HUD-inspired elements, and tech-noir typography.
- **Compliance:** All UI elements must maintain WCAG AAA compliance for readability in dark mode.

## Visual Specifications (OLED Dark Mode)
### Color Palette
- **Background:** `#020617` (True OLED Black)
- **Surface/Cards:** `#1E293B` (Slate Dark)
- **Corporate Navy:** `#0F172A` (Secondary Surface)
- **Primary Accent:** `#22C55E` (Matrix/Vibrant Green)
- **Secondary Text:** `#94A3B8` (Muted Slate)
- **Danger States:** High-vivid `#ff4444` (Flash) / `#d9534f` (Static)
- **Warning States:** High-vivid `#ffbb33` (Flash) / `#f0ad4e` (Static)
- **Primary Text:** `#F8FAFC`

### Typography
- **Headings:** **Lexend** (Modern, clean)
- **Branding Accents:** **Playfair Display SC** (Sophisticated serif)
- **Body Text:** **Source Sans 3** (Maximum readability)
- **Technical/Code:** **Fira Code** (Monospace)

## Architectural Blueprint
### 1. Ribbon Menu (Primary Navigation)
- **Style:** Custom `Ribbon.TNotebook` and `Ribbon.TNotebook.Tab`.
- **Fonts:** Helvetica 10 Bold with `[20, 5]` padding.
- **Structure:**
  - **Home:** Dashboard overview, Application/Company settings, Session controls.
  - **HR:** Employee and Contract management hubs.
  - **Tools:** User Management, Audit Log (Mouchard).
  - **Reports:** Analytical Hub access.

### 2. Dashboard Hero
- **Layout:** Centered hero section featuring a **300x300 company logo**.
- **Statistics Bar:** Top-level tracker for contract states: **Active**, **Expiring Soon**, and **Expired**.
- **Branding:** "Contragest" header (24pt Bold) with "Professional Contract Management System" subtitle.

### 3. Data Presentation (Tableview)
- **Configuration:** High-density grids with `ttkbootstrap.widgets.tableview`.
- **Interaction:** Double-click to edit, integrated action icons (✏️, 🗑️).
- **Visual Alerts:** Row-level flashing effects (800ms interval) for critical contract statuses using danger and warning tokens.

### 4. System Status Bar (Bottom)
- **Features:** Dynamic PC information (Hostname/IP), Real-time environment data (Location/Weather), and a persistent digital clock (`📅 dd/mm/yyyy   🕒 HH:MM:SS`).

## Implementation Guidelines
- **Transitions:** Smooth color/opacity transitions (150-300ms).
- **Icons:** Use SVG or Lucide-style icons; strictly avoid standard emojis for UI actions.
- **Responsiveness:** Optimize for desktop environments with a default 'zoomed' state, while ensuring grid scalability.
- **Performance:** Utilize image caching for logos and background threads for non-UI services (Clock, Weather, Alerts).
