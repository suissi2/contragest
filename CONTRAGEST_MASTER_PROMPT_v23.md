# CONTRAGEST MASTER PROMPT v23: Cyberpunk-meets-Corporate OLED Interface

## I. VISION & IDENTITY
**Brand Name:** Contragest
**Concept:** A "Cyberpunk-meets-Corporate" high-fidelity enterprise interface. It blends the efficiency and structure of a Tier-1 corporate ERP with the high-contrast, data-dense, and futuristic aesthetic of a sci-fi HUD.
**Core Aesthetic:** "OLED Dark Mode" — maximizing deep blacks for power efficiency and visual impact, accented by vibrant "Corporate Neon" highlights.

## II. DESIGN TOKENS (OLED SPECTRUM)
*   **Background (Absolute):** `#020617` (Deepest Void)
*   **Surface (Elevated):** `#1E293B` (Steel Blue Grey)
*   **Surface (Corporate):** `#0F172A` (Navy Midnight)
*   **Primary (Action):** `#22C55E` (Bio-Digital Green / Primary Highlight)
*   **Secondary (Info):** `#3B82F6` (Cyber Blue)
*   **Danger (Critical):** Vivid `#ff4444` / Static `#d9534f` (Flashing for expired states)
*   **Warning (Alert):** Vivid `#ffbb33` / Static `#f0ad4e` (Flashing for expiring states)
*   **Text (Primary):** `#F8FAFC` (Ghost White)
*   **Text (Muted):** `#94A3B8` (Slate Grey)

## III. TYPOGRAPHY SYSTEM
*   **Branding Accents:** *Playfair Display SC* (Serif, sophisticated, used for "Vincci Hoteles" style elegancy).
*   **Primary Headers:** *Lexend* (Geometric Sans, optimized for readability).
*   **Body Text:** *Source Sans 3* (Professional, balanced).
*   **Technical / Data Dense:** *Fira Code* (Monospaced with ligatures).

## IV. UI ARCHITECTURE (RIBBON-SYNC PATTERN)
1.  **Ribbon Navigation:**
    *   Utilizes a customized `ttkbootstrap.Notebook` style ('Ribbon.TNotebook').
    *   Tabs: **🏠 Home**, **👔 HR**, **🛠️ Tools**, **📊 Reports**.
    *   Button-based interface within each ribbon tab, organized in `LabelFrame` groups (e.g., "Navigation", "Settings", "Administrative").
2.  **Dashboard Hero:**
    *   Centered `300x300` Company Logo (Vincci Hoteles 'V' branding).
    *   High-contrast stats bar showing "Active | Expiring | Expired" counts.
3.  **Data Management:**
    *   `Tableview` from `ttkbootstrap.widgets.tableview` (Deprecation avoidance).
    *   Conditional row formatting with smooth flashing animations (800ms intervals) for critical contract statuses.
4.  **System Status Bar (Bottom):**
    *   Persistent display of PC Name, Local IP, Location/Weather data, and a real-time Clock.
    *   Visual separation with `ttk.Separator` and space-efficient padding.

## V. TECHNICAL SPECIFICATIONS
*   **Framework:** Python 3.10+
*   **GUI Engine:** `tkinter` + `ttkbootstrap` (Base Theme: `superhero`).
*   **Database:** `SQLAlchemy` (SQLite backend).
*   **Form Logic:** Standardized `padding=20` for containers, `pady=5` for rows, and `width=12` for labels.
*   **Security Features:** Secure deletion logic requires a dynamic daily password: `((day + month + year_short) * 2) - 10`.

## VI. BRANDING SYNERGY
The interface must integrate the **Vincci Hoteles** logo (`assets/company_logo.png`) as the visual centerpiece. The logo's minimalist black/white aesthetic should be preserved, set against the OLED background to create a seamless "Glassmorphism" or "Floating" effect within the Hero section.
