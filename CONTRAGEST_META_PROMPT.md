# Contragest Interface Concept: Meta-Prompt for LLM Generation

To achieve a concept similar to the Contragest interface, use the following technical and visual specification prompt. This is designed for high-fidelity UI/UX generation or as a blueprint for AI-assisted coding.

---

## 🎨 Visual Identity & Aesthetic
- **Design System:** "Enterprise Gateway" (Professional, High Integrity).
- **Primary Style:** "OLED Dark Mode" – Deep black backgrounds (#020617) with Slate/Navy surfaces (#1E293B).
- **Color Palette:**
  - **Background:** `#020617` (True Black/Dark Slate)
  - **Surface:** `#1E293B` (Slate 800)
  - **Primary Action:** `#22C55E` (Emerald 500)
  - **Secondary Action:** `#3B82F6` (Blue 500)
  - **Critical Alert:** `#EF4444` (Red 500)
  - **Warning Alert:** `#F59E0B` (Amber 500)
  - **Primary Text:** `#F8FAFC` (Slate 50)
- **Typography:**
  - **Body/UI:** Fira Sans (Clean, readable)
  - **Data/Analytics:** Fira Code (Monospace, precise)
- **Mood:** Professional, Data-Dense, High-Performance, Secure.

## 🏗️ Layout Architecture
1. **Ribbon Menu (Header):**
   - Microsoft Office-style tabbed navigation (e.g., 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports).
   - Buttons grouped by functional categories (Navigation, Settings, Session).
   - Large, clear SVG/Lucide-style icons with text labels below.
2. **Main Workspace (Center):**
   - A multi-tab Notebook system where the tabs are hidden to give a seamless "Ribbon-synced" feel.
   - **Dashboard View:** Features a "Hero" section with a large company logo, a stats summary bar (Active/Expiring/Expired counts), and mission text.
   - **Data View (Contracts):** A dense Tableview with columns for ID, Employee Name, Contract Type, Dates, Seniority, and Status.
3. **Status Bar (Footer):**
   - Multi-segmented dark bar (#0F172A).
   - Left: System environment info (Hostname, Local IP).
   - Center: Current user session and role.
   - Middle-Right: Live weather and location data.
   - Far Right: High-precision digital clock (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## ✨ Key Features & Interactions
- **Dynamic Data Highlighting:**
  - Rows in the table should use conditional styling: Success (Green) for Active, Warning (Amber) for Expiring, Danger (Red) for Expired.
  - **Flashing Alerts:** Critical rows (Expired/Expiring) utilize a smooth 800ms "breathing" animation (alternating background colors) to draw immediate attention.
- **Security Logic:**
  - Role-Based Access Control (RBAC) where UI elements (buttons/tabs) are conditionally rendered based on user permissions.
  - Sensitive actions (like deletion) require a dynamic security password calculated via a date-based formula.
- **Seamless Integration:**
  - Sidebar-less design to maximize horizontal space for data tables.
  - Center-aligned Hero content for a balanced landing experience.

## 🛠️ Technical Implementation Strategy (Python)
- **UI Framework:** `tkinter` + `ttkbootstrap` (using 'superhero' theme as a baseline).
- **Database:** `SQLAlchemy` ORM with `SQLite`.
- **Assets:** `Pillow` (PIL) for image/logo caching and resizing.
- **Backend:** Modular Auth system with audit logging and a background scheduler for environmental updates (weather/IP).
- **Exporting:** Integrated CSV and PDF generation using `fpdf2`.

---

**AI Prompt Usage:**
> "Generate a professional Python GUI application using ttkbootstrap in 'superhero' dark mode. The layout must feature a top Ribbon Menu with tabbed navigation, a central data workspace with a flashing Tableview for status alerts, and a multi-segmented status bar at the bottom showing system info and a live clock. Use a color palette of deep blacks and emerald greens for an enterprise dashboard look."
