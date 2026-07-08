# Master Prompt: Cyberpunk-meets-Corporate Interface

## Visual Identity & Core Concept
Create a professional Python GUI using `ttkbootstrap` that embodies a **"Cyberpunk-meets-Corporate"** aesthetic. The design must merge the high-density, real-time data visualization of a sci-fi **HUD (Heads-Up Display)** with the structured, authoritative hierarchy of an **Enterprise ERP Gateway**.

### Design Tokens (OLED Dark Mode)
- **Background:** `#020617` (Deepest OLED Black)
- **Surface/Containers:** `#1E293B` (Corporate Slate)
- **Primary Accent:** `#22C55E` (Cyber Emerald)
- **Corporate Base:** `#0F172A` (Midnight Navy)
- **Muted/Secondary Text:** `#94A3B8` (Slate Blue)
- **Alert (Danger):** Pair `#ff4444` and `#d9534f` (Blinking 800ms cycle)
- **Alert (Warning):** Pair `#ffbb33` and `#f0ad4e` (Blinking 800ms cycle)

### Typography Hierarchy
- **Headers/Display:** **Lexend** (Clean, geometric, authoritative)
- **Branding Accents:** **Playfair Display SC** (Small caps serif for a "Premium Corporate" feel)
- **Body/UI Elements:** **Source Sans 3** (High readability for dense data)
- **Technical/Data Grids:** **Fira Code** (Monospaced with ligatures for HUD-style data density)

### Architectural Patterns
1. **Ribbon Navigation:** Implement a top-mounted Ribbon Menu (using `ttk.Notebook` style 'Ribbon.TNotebook') with functional tabs for *Home, Contracts, HR, Tools, and Reports*.
2. **Enterprise Gateway:** Focus on industry-specific tab switching and mega-menus.
3. **HUD Status Bar:** A persistent bottom bar (`bootstyle="inverse-dark"`) displaying:
   - Dynamic System Info (IP, Hostname)
   - Environmental Data (Location, Weather)
   - Persistent Digital Clock
4. **Data-Dense Dashboard:**
   - Hero Section: Centered 300x300 logo on a 24pt bold title.
   - Status Bar Stats: Real-time tracking of contract statuses (Active, Expiring, Expired).
   - High-Contrast Grids: Use `Tableview` with custom tag configurations for flashing alerts.

### Interactive Standards
- **Transitions:** Smooth 200ms animations for all state changes.
- **Iconography:** Strictly SVG/Lucide-style silhouettes; avoid emojis and skeuomorphism.
- **Compliance:** Ensure WCAG AAA contrast ratios against the #020617 background.
- **Micro-interactions:** Implement 800ms blinking cycles for critical data alerts in HUD grids.
