# CONTRAGEST MASTER PROMPT: Cyberpunk-meets-Corporate OLED Interface

## Visual Identity & Brand Concept
The interface must embody a **'Cyberpunk-meets-Corporate'** identity. This is a high-contrast, professional, and data-dense aesthetic designed for enterprise efficiency with a tech-noir edge.

**Branding Centerpiece:** Vincci Hoteles (using the 'V' monogram and serif typography from `assets/company_logo.png`).

## Design Tokens (OLED Dark Mode)
- **Background (Deep Space):** `#020617` (True OLED Black)
- **Surface (Elevated):** `#1E293B` (Slate Navy)
- **Corporate Navy:** `#0F172A` (Secondary Surface)
- **Primary / Success (Neon Mint):** `#22C55E` (Vivid Green)
- **Text (High Contrast):** `#F8FAFC` (Ghost White)
- **Muted / Secondary Text:** `#94A3B8` (Slate Grey)
- **Danger / Alert:** `#ff4444` (Vivid Red) / `#d9534f` (Static Red)
- **Warning / Pending:** `#ffbb33` (Vivid Amber) / `#f0ad4e` (Static Amber)

## Typography Stack
- **Primary Headers:** `Lexend` (Geometric, high-readability)
- **Branding Accents:** `Playfair Display SC` (Elegance, serif for Vincci identity)
- **Body Text:** `Source Sans 3` (Professional enterprise clarity)
- **Data / Technical:** `Fira Code` (Monospaced for numbers and logs)

## Technical Architecture (Python / ttkbootstrap)
- **Theme Base:** `ttkbootstrap` with the `superhero` theme as a foundation for OLED customization.
- **Ribbon Navigation:**
    - Implementation: `ttk.Notebook` with style `Ribbon.TNotebook`.
    - Tab Styling: `padding=[20, 5]`, `font=('Helvetica', 10, 'bold')`.
    - Elements: Group buttons in `ttk.LabelFrame` within ribbon tabs.
- **Main Content Sync:**
    - Implementation: A secondary `ttk.Notebook` (`Main.TNotebook`).
    - **Crucial Hook:** Hide the tabs of this notebook using:
      ```python
      style.layout('Main.TNotebook.Tab', [])
      ```
    - Synchronization: Ribbon tab changes must programmatically switch the index of the main notebook.
- **Dashboard Hero:**
    - Centered 300x300 Vincci logo on home tab.
    - Top stats bar tracking 'Active', 'Expiring', and 'Expired' contracts.
- **Status Bar:**
    - Bottom persistent bar containing:
        - System Info (PC Name, IP)
        - Environment Data (Location, Weather via API)
        - Persistent Clock (📅 dd/mm/yyyy   🕒 HH:MM:SS)

## Interactive Standards
- **Transitions:** Smooth transitions (150-300ms) for hover states.
- **Visual Feedback:** 800ms flashing cycle for critical rows in tables (alternating between vivid and static danger/warning colors).
- **Accessibility:** WCAG AAA compliance for the OLED dark theme.
- **Iconography:** SVG-style icons (Lucide/Heroicons inspired), strictly avoiding emojis for primary UI actions.

## Security & Logic
- **RBAC:** Explicit Role-Based Access Control filtering Ribbon tabs and actions (Admin vs User).
- **Secure Deletion:** Password-protected deletion using the formula: `((day + month + year_short) * 2) - 10`.
