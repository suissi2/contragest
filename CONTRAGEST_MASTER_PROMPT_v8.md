# CONTRAGEST MASTER PROMPT v8

## Concept: Cyberpunk-meets-Corporate
**Identity:** A professional, high-integrity enterprise contract management system reimagined through a tech-noir, HUD-inspired aesthetic. High-performance "OLED Dark Mode" with neon positive indicators and corporate-grade density.

## 1. Visual Identity & Design Tokens

### OLED Dark Mode Palette
- **Background (OLED Black):** `#020617` (True black for infinite contrast)
- **Surface (Steel Navy):** `#1E293B` (Cards, panels, and sidebars)
- **Primary (Corporate Navy):** `#0F172A` (Secondary surfaces)
- **Accent/CTA (Emerald Neon):** `#22C55E` (Success states, active buttons, positive trends)
- **Text (Ghost White):** `#F8FAFC` (High readability)
- **Alert (Danger):** Flash `#ff4444` / Static `#d9534f`
- **Warning:** Flash `#ffbb33` / Static `#f0ad4e`

### Typography Stack
- **Headings (Lexend):** Professional, geometric, accessible. Use for Dashboard Hero and Section Titles.
- **Branding (Playfair Display SC):** Small caps serif for refined corporate elegance in logos or accents.
- **Body (Source Sans 3):** High-readability sans-serif for data-dense tables and reports.
- **Data (Fira Code):** Monospace with ligatures for technical IDs, audit logs, and system metrics.

## 2. UI Architecture (Ribbon-based)

### The Ribbon Menu
- **Structure:** Tabbed navigation at the top (Home, HR, Tools, Reports).
- **Style:** `Ribbon.TNotebook` with `Helvetica 10 bold` font and `[20, 5]` padding.
- **Buttons:** Icon + Label groups (e.g., "Navigation", "Settings", "Session"). Use bootstyles (INFO, LIGHT, SECONDARY, DANGER).

### Dashboard Hero Section
- **Composition:** Centered 300x300 company logo in a high-contrast container.
- **Hero Text:** "Contragest" (Lexend 24 Bold) above "Professional Contract Management System" (Lexend 14).
- **Stats Bar:** Top-level summary tracking contract statuses (Active, Expiring, Expired) with real-time flashing alerts.

### System Status Bar (Persistent Bottom)
- **PC Info:** Display host name and local IP (💻 Hostname (192.168.x.x)).
- **Environment:** Dynamic location and weather data (🌍 City, Country 🌡️ 22°C).
- **Session:** "Logged in as: [Username] ([Role])".
- **Clock:** Persistent bold timestamp (📅 DD/MM/YYYY   🕒 HH:MM:SS).

## 3. Interaction & UX
- **Transitions:** Smooth 150-300ms fades for tab switching and hover states.
- **Animations:** 800ms flash interval for critical alerts (Danger/Warning).
- **Compliance:** WCAG AAA contrast compliance for the OLED theme.
- **Iconography:** Lucide/SVG-style icons only (No emojis).

## 4. Implementation Directives
- **Stack:** Python, `ttkbootstrap` (Superhero base theme), SQLAlchemy, PIL/Pillow.
- **Responsiveness:** Optimized for maximized desktop views (1440px+) but fluid down to 1024px.
- **I18n:** Full support for English, French, and Arabic (RTL support).
