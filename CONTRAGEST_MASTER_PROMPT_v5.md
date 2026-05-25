# Contragest Interface Master Prompt v5.0

## Visual Identity: "Cyberpunk-meets-Corporate"
Create a high-fidelity, data-dense enterprise dashboard for a Python-based desktop application using `ttkbootstrap` and the `superhero` theme as a foundation. The interface must balance professional corporate reliability with a sleek, "tech noir" HUD aesthetic.

### 🎨 Color Palette (OLED Dark Mode)
- **Background:** `#020617` (Deep space black)
- **Surface/Cards:** `#1E293B` (Slate blue-grey)
- **Primary Accent:** `#22C55E` (Cyber green)
- **Muted Text:** `#94A3B8` (Soft slate)
- **Alert (Danger):** `#ff4444` (Active) / `#d9534f` (Static)
- **Alert (Warning):** `#ffbb33` (Active) / `#f0ad4e` (Static)

### 🔡 Typography
- **Primary Headers:** `Lexend` (Clean, geometric, accessible)
- **Branding Accents:** `Playfair Display SC` (Elegance/Trust)
- **Body & Data:** `Source Sans 3` (High readability for dense tables)
- **Technical/Monospace:** `Fira Code` (For audit logs and system info)

### 🏗️ UI Architecture
1. **Ribbon Navigation System:**
   - Top-mounted `ttk.Notebook` styled as a Ribbon Menu.
   - Tabs: `🏠 Home`, `📑 Contracts`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
   - Each tab reveals functional groupings in `LabelFrame` containers with custom icons.

2. **Dashboard Hero Section:**
   - Centered 300x300 company logo (`assets/company_logo.png`).
   - Integrated "Status At-A-Glance" bar tracking `Active`, `Expiring`, and `Expired` contracts.

3. **Multi-Tabbed Reports Module:**
   - Advanced filtering with global search and column-specific dropdowns (Role, Status, Department).
   - Date range pickers with toggle activation.
   - Export functionality to CSV and PDF (via `fpdf2`) with auto-generated headers and logo.

4. **Dynamic Status Bar:**
   - Persistent bottom bar showing:
     - `💻 PC Info`: Hostname and Local IP.
     - `🌍 Environment`: Live Location and Weather (via `ip-api` and `wttr.in`).
     - `📅 Persistent Clock`: Real-time date and seconds-level clock.

5. **Advanced Data Visualization:**
   - `Tableview` integration with animated flashing rows for critical states (800ms interval).
   - High-contrast tag-based coloring for row-level status indicators.

### 🛠️ Technical Stack
- **Language:** Python 3.12+
- **GUI Framework:** `ttkbootstrap` (Superhero theme)
- **Database/ORM:** SQLAlchemy with SQLite (`contragest.db`)
- **Image Processing:** `Pillow` (PIL) for responsive logo handling and UI assets.
- **Reporting:** `fpdf2` for professional document generation.

### 🚀 UX Guidelines
- Ensure **WCAG AAA compliance** for the OLED dark theme.
- Implement smooth transitions (150-300ms) for all interactive states.
- Use **SVG/Lucide-style icons** exclusively; avoid emojis for core UI elements.
- Maintain an "Enterprise Gateway" pattern: High integrity, conservative accents, and logical path selection.
