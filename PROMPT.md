### **Prompt: Professional Contract Management Dashboard (Python/ttkbootstrap)**

**Goal:** Create a modern, desktop-based management application in Python using the `ttkbootstrap` library, specifically designed for HR and contract oversight with a "superhero" dark-mode theme.

**1. Visual Identity & Theme:**
*   **Library:** Python 3.10+ with `ttkbootstrap` and `Pillow`.
*   **Theme:** Apply the **"superhero"** dark-mode theme (slate blue, grey, and high-contrast accents).
*   **Typography:** Standardize on **"Helvetica"**.
    *   *Hero Titles:* 24pt Bold.
    *   *KPI/Stats Labels:* 11pt.
    *   *System/Status Text:* 9pt.

**2. Layout & Navigation:**
*   **Ribbon Menu (Top):** Implement a Microsoft Office-style Ribbon using a `ttk.Notebook` (Style: `Ribbon.TNotebook`, 0 padding).
    *   **Tabs:** "🏠 Home", "👔 HR", "🛠️ Tools", and "📊 Reports".
    *   **Groups:** Within each tab, use `LabelFrame` containers to group buttons (e.g., "Contract Actions", "Administrative", "Session"). Use `INFO`, `SECONDARY`, and `DANGER` bootstyles for buttons.
*   **Central Workspace:** Use a `ttk.Notebook` with **hidden tabs** to dynamically switch between views (Dashboard, Contracts Table, Reports) based on Ribbon selection.
*   **Sophisticated Status Bar (Bottom):** A multi-part `DARK` frame containing:
    *   *Section 1:* PC Hostname and Local IP.
    *   *Section 2:* Current user session and role.
    *   *Section 3:* Real-time location 🌍 and weather 🌡️ placeholders.
    *   *Section 4:* A live digital clock (📅 DD/MM/YYYY   🕒 HH:MM:SS).

**3. Advanced Components & Logic:**
*   **Interactive Data Table:**
    *   A `Tableview` widget with columns for Action Icons (Edit/Delete), ID, Name, Dates, Seniority, and Status.
    *   **Conditional Formatting:** Automatically tag rows as `success` (active), `warning` (expiring), or `danger` (expired).
    *   **Visual Alert:** Implement a "flash" animation (800ms interval) that alternates colors for warning/danger rows to draw attention.
*   **Localization & UX:**
    *   Full **Right-to-Left (RTL)** layout support for RTL languages.
    *   Internationalization (i18n) framework for multi-language support.
    *   **Security:** Multi-step verification for sensitive actions (e.g., a deletion password formula based on current date).

**4. Backend Integration:**
*   **ORM:** SQLAlchemy for SQLite database management.
*   **Automation:** Background scheduling for system alerts and automated email notifications (SMTP).

***

### **Developer Insight:**
To maintain high performance, utilize an `image_cache` for UI assets like logos to minimize disk I/O, and ensure the Ribbon tabs have a padding of `[20, 5]` with bold fonts for a professional feel.
