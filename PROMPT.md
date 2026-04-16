# Contragest: Enterprise Contract Management Interface Specification

## Master Prompt for LLM Reconstruction

As a Senior Python Developer and UI/UX Expert specializing in desktop applications, your task is to recreate or extend the **Contragest** interface. This system is a professional, high-fidelity contract management dashboard built with **Python 3.x** and **ttkbootstrap**.

### 1. Visual Identity & Theme
- **Theme:** Use the `superhero` theme from `ttkbootstrap` as the foundation.
- **Aesthetic:** 'OLED Dark Mode' with high contrast. Primary colors: Navy/Slate blue (`#2B3E50`), Grey (`#4E5D6C`), and deep backgrounds.
- **Brand Integration:** Dynamically load and cache company logos. Use `PIL` (Pillow) for high-quality image resizing.
- **Typography:** Professional sans-serif (Helvetica/Fira Sans). Hero labels in 24pt Bold; stats in 11pt; status bar in 9pt.

### 2. Layout Architecture (The 'Enterprise Gateway' Pattern)
- **Ribbon Navigation:** Implement a top Ribbon menu using a styled `ttk.Notebook` (`Ribbon.TNotebook`). Tabs include '🏠 Home', '👔 HR', '🛠️ Tools', and '📊 Reports'. Use thick tabs ([20, 5] padding) and bold 10pt fonts.
- **Main Workspace:** A central area using a hidden-tab `ttk.Notebook` (`Main.TNotebook`) that switches views based on Ribbon selection.
- **Multi-Part Status Bar:** A sophisticated bottom bar (`DARK` bootstyle) with four sections:
    1. **Left:** PC Info (Hostname/IP).
    2. **Center:** Session Info (Logged in user/role).
    3. **Middle-Right:** Environmental data (Location and Weather) fetched via background threads.
    4. **Right:** A live digital clock (📅 DD/MM/YYYY   🕒 HH:MM:SS) updating every second.

### 3. Advanced Components & UX
- **Flashing Alerts:** The main contracts `Tableview` must implement a visual alert system. Expired rows (danger) and expiring rows (warning) should alternate colors every 800ms between vivid (#ff4444 / #ffbb33) and standard theme colors.
- **Interactive Tables:** `Tableview` with conditional row tagging (`success`, `warning`, `danger`), column autofitting, and embedded action icons (✏️ Edit, 🗑️ Delete) in the first two columns.
- **Modular Reports:** A tabbed reports interface supporting global search, multi-dropdown filtering (Role, Status, Department), and date range filtering. Support export to **CSV** and **PDF** (using `fpdf2`) with embedded company logos.

### 4. Technical Stack & Backend Integration
- **Framework:** `tkinter`, `ttkbootstrap`, `SQLAlchemy` (ORM), `SQLite`.
- **Concurrency:** Use a `BackgroundScheduler` for non-blocking tasks (weather updates, automated alerts, email dispatch).
- **Security Logic:**
    - **RBAC:** Role-Based Access Control that conditionally renders UI elements. 'admin' role bypasses all checks.
    - **OTP System:** Multi-factor authentication with 6-digit OTPs and a 60-second cooldown period.
    - **Deletion Protection:** Sensitive actions (like contract deletion) require a dynamic daily password calculated as: `((day + month + (year % 100)) * 2) - 10`.

### 5. UI/UX Principles (ui-ux-pro-max)
- **Icons:** Use SVG/Lucide-style icons; avoid standard emojis for core UI actions.
- **Feedback:** All interactive elements must have `cursor-pointer` (simulated in Tkinter via event bindings) and smooth transitions.
- **Anti-patterns to Avoid:** Ornate/busy designs, lack of filtering in data-dense views, and blocking UI during network calls.

---

*This specification serves as the master source of truth for the Contragest visual and functional identity.*
