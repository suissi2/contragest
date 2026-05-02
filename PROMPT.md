# Master Prompt: Contragest "Enterprise Gateway" Interface Recreation

**Role:** Expert Python GUI Developer & Senior UI/UX Designer specializing in desktop dashboard applications.
**Objective:** Develop a high-fidelity, professional "Enterprise Gateway" dashboard using Python and `ttkbootstrap` that recreates the visual and functional architecture of the "Contragest" contract management system.

---

### 1. Visual Identity & Theme
*   **Framework:** Use `ttkbootstrap` with the `superhero` theme to establish a modern "OLED Dark Mode" aesthetic.
*   **Palette:**
    - **Backgrounds:** Deep Slate/Navy (#0F172A or similar from the Superhero palette).
    - **Primary Accents:** Success Green (#22C55E) for active states.
    - **Alert Accents:** Warning Amber (#F0AD4E) for expiring items; Danger Red (#D9534F) for expired/critical items.
*   **Typography:** Professional sans-serif (Helvetica, Source Sans 3, or Lexend). Use **Bold 24pt** for hero titles, **Semibold 11pt** for stats, and **Monospace 9pt** for system telemetry in the status bar.

---

### 2. Layout Architecture: The Ribbon-Notebook Hybrid
*   **Top Navigation (Ribbon Menu):**
    - A custom `ttk.Frame` containing a `ttk.Notebook` with no visible tab borders.
    - Tabs: 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
    - Content: Buttons organized into `ttk.LabelFrame` "Action Groups" (e.g., "Navigation," "Settings," "Session").
    - Button Styling: Large, padded buttons with categorical bootstyles (`INFO`, `LIGHT`, `SECONDARY`).
*   **Central Workspace (Main Content):**
    - A `ttk.Notebook` with **hidden tabs** (`style.layout('Main.TNotebook.Tab', [])`).
    - Logic: Selecting a tab in the Ribbon Menu programmatically switches the central workspace view.
*   **Bottom Status Bar:**
    - A multi-segmented footer in `DARK` bootstyle containing:
        - **Left:** System Info (💻 Hostname and Local IP).
        - **Center-Left:** Session Details (Logged-in User and Role).
        - **Center-Right:** Environment Telemetry (🌍 Location and 🌡️ Temperature, updated via background threads).
        - **Right:** Live Digital Clock (📅 DD/MM/YYYY | 🕒 HH:MM:SS).

---

### 3. Advanced Component Specifications
*   **Dashboard Hero Section:**
    - A centralized 300x300 company logo.
    - A "Statistics Bar" at the top showing real-time counts: `Active: X | Expiring Soon: Y | Expired: Z`.
*   **Dynamic Tableview Alerts:**
    - A searchable `Tableview` widget for data management.
    - **Flashing Logic:** Implement a background loop (using `after()`) that alternates the background color of "Danger" and "Warning" tagged rows every 800ms (e.g., swapping between vivid #ff4444 and muted #d9534f).
*   **Iconography:** Integrate high-fidelity SVG or Unicode icons (Lucide/Heroicons style) for all primary actions (✏️ Edit, 🗑️ Delete, ➕ New, 🚪 Logout).

---

### 4. Technical Logic & Security
*   **Authentication Flow:** A centered Login window that transitions seamlessly into the `MainWindow` upon verification.
*   **Role-Based Access Control (RBAC):** Conditionally render Ribbon tabs and specific administrative tools (e.g., "Mouchard" audit log, "User Management") based on the `user.role` (admin vs. staff).
*   **Threading:** Use `BackgroundScheduler` or Python threads to fetch environmental data and system info without freezing the UI.

---

### 5. Implementation Roadmap
1.  **Stage 1:** Configure `ttkbootstrap` styles and root window geometry (zoomed/maximized).
2.  **Stage 2:** Build the `StatusBar` and its background update loops.
3.  **Stage 3:** Create the `RibbonMenu` and `MainNotebook`, establishing the switching controller.
4.  **Stage 4:** Design the `Home` hero view and the statistics dashboard.
5.  **Stage 5:** Implement the `Tableview` with custom tagging and the asynchronous flashing animation logic.
