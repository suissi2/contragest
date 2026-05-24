# Contragest Design Prompt

## High-Fidelity UI/UX Prompt: "Contragest Enterprise Gateway"

**Visual Identity & Aesthetic:**
> "Create a high-density enterprise dashboard titled **'Contragest'** using a **'Cyberpunk-meets-Corporate'** design language. The interface must prioritize an **OLED-optimized Dark Mode** with high contrast and tech-noir elements, emphasizing precision, data density, and professional authority."

### 1. Color Palette (OLED Dark Mode)
*   **Background:** `#020617` (OLED Deep Black)
*   **Surface/Cards:** `#1E293B` (Slate Navy)
*   **Primary Accent:** `#22C55E` (Emerald Green - for positive indicators and CTAs)
*   **Secondary Text:** `#94A3B8` (Muted Slate)
*   **Static Danger/Warning:** `#d9534f` / `#f0ad4e`
*   **Flash Alerts:** `#ff4444` / `#ffbb33`

### 2. Typography System
*   **Brand/Headers:** `Lexend` (Clean, geometric, modern)
*   **Branding Accents:** `Playfair Display SC` (Serif elegance for a corporate feel)
*   **Body Text:** `Source Sans 3` (Highly readable for data tables)
*   **Data/Monospace:** `Fira Code` (For technical or system information)

### 3. UI Architecture & Components
*   **Ribbon Navigation:** A top-mounted ribbon menu (Microsoft Office style) using a tabbed notebook interface. Styles: `Ribbon.TNotebook` with `Helvetica 10 Bold` tabs. Categories: *Home, HR, Tools, Reports*.
*   **Dashboard Hero:** A centered Hero section featuring a large `300x300` company logo (Vincci Hoteles style) with a top statistics bar displaying contract statuses (Active, Expiring, Expired).
*   **Data Tables:** Dense, sortable table views (ttkbootstrap style) with dynamic row highlighting. Expiring items should have a 'Flash' effect (switching between static and vivid colors every 800ms).
*   **Multi-Tabbed Reports:** A dedicated module with global search, role/department dropdown filters, and date-range pickers. Support for "Export to CSV" and "Export to PDF" actions.
*   **System Status Bar:** A persistent bottom bar displaying dynamic system info (PC name, IP), environmental data (Location, Weather), and a large persistent Clock.

### 4. Interaction & Effects
*   **Transitions:** Smooth state transitions (150-300ms).
*   **Glassmorphism:** Subtle background blur on modals and overlays.
*   **WCAG AAA Compliance:** Ensure maximum legibility against the deep black background.
*   **Icons:** Use Lucide-style SVG icons; strictly avoid emojis within the functional UI.

---

### Technical Implementation Notes for Developers
*   **Framework:** Python with `ttkbootstrap` (Superhero theme as base) and `Pillow` for image scaling.
*   **Database:** SQLAlchemy ORM with SQLite.
*   **Key Libraries:** `fpdf2` (PDF exports), `requests` (Weather API), `PIL` (Image Caching).
*   **Security:** Implement a RBAC (Role-Based Access Control) system with a "Mouchard" (Audit Log) window for administrative oversight.
