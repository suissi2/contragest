# Contragest: Enterprise Contract Management Interface Specification

## Master Prompt for LLM Reconstruction

As a Senior Python Developer and UI/UX Expert specializing in professional desktop applications, your task is to recreate or extend the **Contragest** interface. This system is a high-fidelity contract management dashboard built with **Python 3.x** and **ttkbootstrap**.

### 1. Visual Identity & Theme (OLED Dark Mode)
- **Theme:** Use the `superhero` theme from `ttkbootstrap`.
- **Aesthetic:** Professional 'OLED Dark Mode' with high contrast.
- **Color Palette:**
    - **Background:** Deep navy/slate (`#020617` or `#2B3E50`)
    - **Surface:** Slate blue/grey (`#1E293B` or `#4E5D6C`)
    - **Primary Action:** Emerald/Success green (`#22C55E`)
    - **Text:** Slate-50/Off-white (`#F8FAFC`) for high readability.
- **Typography:** Professional sans-serif pairing. Headings in `Fira Code` (Dashboard/Data feel) and body in `Fira Sans`. Hero titles in 24pt Bold; stats in 11pt; status bar in 9pt.
- **Brand Integration:** Dynamically load and cache company logos using `PIL` (Pillow) for high-quality scaling.

### 2. Layout Architecture ('Enterprise Gateway' Pattern)
- **Ribbon Navigation:** A top-level Ribbon menu using a styled `ttk.Notebook` (`Ribbon.TNotebook`). Tabs: '🏠 Home', '👔 HR', '🛠️ Tools', and '📊 Reports'. Tabs use thick padding ([20, 5]) and bold 10pt fonts.
- **Main Workspace:** A central viewing area using a hidden-tab `ttk.Notebook` (`Main.TNotebook`) that switches content based on Ribbon selections.
- **Multi-Segment Status Bar:** A bottom toolbar (`DARK` bootstyle) containing:
    1. **System Info:** Hostname and IP address.
    2. **Session Details:** Logged-in username and role.
    3. **Environmental Data:** Real-time location and weather (handled via background threads).
    4. **Digital Clock:** Live updating date and time (📅 DD/MM/YYYY   🕒 HH:MM:SS).

### 3. Advanced Components & Interaction
- **Animated Tableview Alerts:** The main data table must implement a visual alert system for contract statuses. Critical rows (Expired/Expiring) must alternate colors every 800ms between vivid (#ff4444 / #ffbb33) and standard theme colors.
- **Data Tables:** `Tableview` with conditional row tagging (`success`, `warning`, `danger`), column autofitting, and action icons (✏️ Edit, 🗑️ Delete).
- **Filtering & Search:** Advanced filtering in reports (Global Search, Role/Status/Department dropdowns, Date Ranges).
- **Exports:** Support for **CSV** and **PDF** (via `fpdf2`) including embedded company logos.

### 4. Technical Stack & Security Logic
- **Core:** `tkinter`, `ttkbootstrap`, `SQLAlchemy`, `SQLite`.
- **Concurrency:** `BackgroundScheduler` for non-blocking UI during data fetching or email dispatch.
- **Security:**
    - **RBAC:** Fine-grained access control. 'admin' role has super-user bypass.
    - **MFA:** 6-digit OTP system with 60-second cooldown logic.
    - **Protection:** Sensitive actions (like deletion) require a dynamic daily password: `((day + month + (year % 100)) * 2) - 10`.

### 5. UI/UX Principles
- **Icons:** Use SVG/Lucide-style icons; avoid standard emojis for core UI actions.
- **Feedback:** `cursor-pointer` simulated on interactive elements; smooth 200ms transitions on hover.
- **Cleanliness:** No cluttered layouts; prioritize data density while maintaining white space (or "dark space").

---
*This specification serves as the master source of truth for the Contragest visual and functional identity.*
