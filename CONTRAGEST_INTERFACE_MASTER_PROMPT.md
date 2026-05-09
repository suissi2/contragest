# CONTRAGEST INTERFACE MASTER PROMPT

**Role:** Expert Python GUI Developer & UI/UX Designer
**Objective:** Recreate the "Contragest" Enterprise Contract Management Interface using a "Cyberpunk-meets-Corporate" aesthetic with a high-fidelity OLED Dark Mode.

---

### 1. Visual Identity & Design Tokens (OLED Dark Mode)
Implement a high-contrast, space-efficient layout following the **Enterprise Gateway** pattern.
- **Palette:**
    - **Background:** `#020617` (True Black/Deep Slate)
    - **Surface/Cards:** `#1E293B` (Slate Blue)
    - **Primary/Success:** `#22C55E` (Vibrant Green)
    - **Text Primary:** `#F8FAFC` (Cloud White)
    - **Text Muted:** `#94A3B8` (Slate Grey)
    - **Danger (Alerts):** Active `#ff4444` / Static `#d9534f`
    - **Warning (Alerts):** Active `#ffbb33` / Static `#f0ad4e`
- **Typography:**
    - **Headers:** `Lexend` (Professional & Geometric)
    - **Branding Accents:** `Playfair Display SC` (Elegant Serif)
    - **Body Text:** `Source Sans 3` (High Readability)
    - **Technical/Data:** `Fira Code` (Monospace)
- **Theme Base:** `ttkbootstrap` "superhero" theme, customized for OLED compliance (WCAG AAA).

---

### 2. Layout Architecture
- **Ribbon Navigation:**
    - A top-mounted `RibbonMenu` with categorized tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools`, and `📊 Reports`.
    - Permission-based rendering: Admin-only access for 'Tools' and 'Reports' tabs.
    - Flat, icon-centric buttons with `transition-colors` feedback.
- **Dashboard (Hero Section):**
    - **Statistics Bar:** Top-aligned bar tracking "Active", "Expiring Soon", and "Expired" contracts.
    - **Hero Area:** Centered 300x300 company logo with high-impact typography ("Contragest - Professional Contract Management").
- **Data-Dense Workspace:**
    - `Tableview` widget with custom row coloring.
    - **Visual Alerts:** Implement a flashing effect for critical rows (Danger/Warning) using an 800ms interval toggle.
- **Multi-Part Status Bar:**
    - **Left:** PC Hostname and Local IP.
    - **Center:** User Session details (Username/Role).
    - **Middle-Right:** Real-time Weather and Location data.
    - **Right:** Live digital clock (Date/Time) and `Sizegrip`.

---

### 3. Technical Requirements & Logic
- **Tech Stack:** Python 3.x, `ttkbootstrap`, `SQLAlchemy` (ORM), `SQLite`, `Pillow` (Image handling), `fpdf2` (PDF Exports).
- **Core Features:**
    - **RBAC (Role-Based Access Control):** Secure `AuthService` with decorator-based permission checks (`@AuthService.require_permission`).
    - **OTP Authentication:** Two-step activation with email verification and a 60-second cooldown on resends.
    - **Report Engine:** Advanced filtering (Global Search, Role/Status/Department dropdowns) with PDF/CSV export capabilities.
    - **System Health:** Background `Scheduler` for real-time alerts and environmental data updates.
- **Micro-Interactions:**
    - Smooth transitions (150-300ms) for all hover states.
    - No emojis for UI icons; use SVG or Lucide-style iconography.
    - Tableview double-click to edit, icon-based actions (✏️/🗑️).

---

### 4. Implementation Guidelines
- **Performance:** Utilize an `image_cache` for resized assets to minimize I/O.
- **Accessibility:** Ensure WCAG AAA contrast ratios are maintained across the OLED palette.
- **Modularity:** Separate UI logic from backend services. Use the "Adapter" pattern for the authentication layer.
- **Security:** Implement a daily-changing "Security Password" formula for critical deletions: `((day + month + (year % 100)) * 2) - 10`.

---

**Output Format:** Provide clean, modular Python code using `ttkbootstrap` and `SQLAlchemy`, ensuring all design tokens and architectural rules are strictly followed.
