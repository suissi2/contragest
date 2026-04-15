# **Master Prompt: High-Fidelity Enterprise Dashboard Reconstruction**

**Objective:**
Act as a senior Python GUI expert to develop a professional, high-density contract management application named **"Contragest"**. The interface must implement an **'Enterprise Gateway'** pattern with a sophisticated **'OLED Dark Mode'** aesthetic using the `ttkbootstrap` library.

---

### **1. Visual Identity & Design System**
*   **Framework:** Python 3.12+ with `ttkbootstrap` and `Pillow`.
*   **Theme:** **"Superhero"** (slate-blue and charcoal palette).
*   **Aesthetic:** OLED Dark Mode (Deep blacks, midnight blues, high-contrast text).
*   **Typography:** Primary font **"Helvetica"**.
    *   *Hero Titles:* 24pt Bold.
    *   *KPI/Stats Labels:* 11pt Inverse-Secondary.
    *   *Status Bar:* 9pt Inverse-Dark.
*   **Performance:** Implement an `image_cache` for assets (logos, icons) to minimize disk I/O.

---

### **2. Layout Architecture (The Ribbon Interface)**
*   **Top Navigation (Ribbon):** Use a `ttk.Notebook` with style `Ribbon.TNotebook`.
    *   **Tabs:** "🏠 Home", "👔 HR", "🛠️ Tools", "📊 Reports".
    *   **Styling:** Tab padding `[20, 5]`, bold 10pt font.
    *   **Content:** Group buttons in `LabelFrame` containers (e.g., "Navigation", "Settings", "Administrative").
    *   **Buttons:** Use diverse bootstyles (`INFO`, `LIGHT`, `SECONDARY`, `DANGER`) with a padding of 10.
*   **Main Workspace:** A central `ttk.Notebook` (Style: `Main.TNotebook`) with **hidden tabs**. Navigation is driven purely by Ribbon selections.
*   **Status Bar (Bottom):** A multi-segmented `DARK` frame:
    *   *Left:* PC Hostname & Local IP (e.g., `💻 HOSTNAME (192.168.1.X)`).
    *   *Center:* Active Session details (e.g., `Logged in as: admin`).
    *   *Middle-Right:* Dynamic Location & Weather (e.g., `🌍 City, Country  🌡️ 22°C`).
    *   *Right:* Live Digital Clock (`📅 DD/MM/YYYY   🕒 HH:MM:SS`).

---

### **3. Advanced Components & Logic**
*   **Smart Data Table (Tableview):**
    *   **Columns:** Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
    *   **Seniority Calculation:** Dynamic computation of months and days since `start_date`.
    *   **Conditional Tagging:** Map rows to `success` (active), `warning` (expiring), and `danger` (expired).
    *   **Flash Animation:** Implement a 800ms interval "flash" that alternates warning/danger row colors (#ff4444/active vs #d9534f/static for danger).
*   **Reporting Module:**
    *   Tabbed interface (Users, Spy, Employees, Contracts).
    *   Advanced filtering (Global search, Dropdowns for Role/Status/Department, Date ranges).
    *   Export support for **CSV** and **PDF** (via `fpdf2`).
*   **Security & RBAC:**
    *   Role-Based Access Control (RBAC) with hardcoded 'admin' bypass.
    *   **Sensitive Actions:** Require a daily dynamic password calculated as: `((day + month + (year % 100)) * 2) - 10`.
    *   **Auth Core:** Modular authentication with OTP activation and 60s cooldown.

---

### **4. Internationalization & Accessibility**
*   **i18n:** JSON-based translation manager (`en.json`, `fr.json`, `ar.json`).
*   **RTL Support:** Native Right-to-Left layout adapters using helper functions for `pack_start` / `pack_end`.

---

### **Anti-Patterns to Avoid:**
*   ❌ No emojis as primary UI icons; use SVG or Lucide-style iconography.
*   ❌ Avoid standard Tkinter grey widgets; everything must follow the Superhero theme.
*   ❌ No blocking I/O on the main thread; use background threads for weather, alerts, and email.
