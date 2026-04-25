# PROMPT: Contragest High-Fidelity Enterprise Interface

**Role:** Expert Python Developer / UI-UX Designer
**Task:** Recreate/Extend the "Contragest" Enterprise Interface using a high-fidelity "OLED Dark Mode" aesthetic.

## 1. Technical Stack
- **Framework:** `ttkbootstrap` (Core UI), `tkinter` (Base)
- **Database/ORM:** `SQLAlchemy` + `SQLite` (contragest.db)
- **Logic:** `BackgroundScheduler` for alerts, `AuthService` for RBAC.
- **Image Processing:** `Pillow` (PIL) for high-quality asset rendering and image caching.
- **Reporting:** `fpdf2` for PDF exports.

## 2. Visual Identity & Design System
- **Theme Name:** Enterprise Gateway (OLED Dark Mode)
- **Palette:**
  - **Background (Main):** `#020617` (Deep Black/Midnight)
  - **Surface (Containers/Ribbon):** `#1E293B` (Slate)
  - **Primary/Action:** `#22C55E` (Vibrant Green)
  - **Secondary:** `#334155`
  - **Text (Primary):** `#F8FAFC`
  - **Text (Muted):** `#94A3B8`
  - **Danger/Alert:** `#EF4444`
  - **Warning/Expiring:** `#F59E0B`
- **Typography:**
  - **Headings/Code:** `Fira Code` (Weight: 600)
  - **UI/Body:** `Fira Sans` or `Helvetica` (Weight: 400)
- **Effects:**
  - Subdued neon glow on primary buttons (`text-shadow` style).
  - Smooth transitions (200ms) for hover states.
  - No Unicode emojis as icons; use high-quality SVG assets (Heroicons/Lucide style).

## 3. Layout Architecture
### A. Ribbon Navigation (`Ribbon.TNotebook`)
- **Tabs:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
- **Padding:** `[20, 5]` for tabs; bold 10pt font.
- **Grouping:** Labels grouped in `Labelframe` containers within tabs (e.g., "Navigation", "Contracts", "Administrative").

### B. Main Workspace (`Main.TNotebook`)
- A centralized Notebook with **hidden tabs** (style layout cleared).
- Transitions between "Home" (Hero/Stats), "Contracts" (Management Grid), and "HR Hub" are triggered by Ribbon events.

### C. Advanced Tableview
- Columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
- **Dynamic Animation:** Rows with "Expired" or "Expiring Soon" status must utilize an `animate_flash` method (800ms interval) that toggles between vivid alert colors (`#FF4444` / `#FFBB33`) and static theme colors.

### D. Sophisticated Status Bar
- Multi-part layout using `ttk.Frame` (bootstyle=DARK).
- **Left:** PC Name + Local IP (💻 icon).
- **Center:** Session User + Role.
- **Middle-Right:** Real-time Environment (🌍 Location + 🌡️ Temperature via BackgroundScheduler).
- **Right:** Digital Clock (📅 DD/MM/YYYY   🕒 HH:MM:SS) + Sizegrip.

## 4. Security & Business Logic
- **RBAC:** All actions (Add, Edit, Delete, View Logs) must wrap with `@AuthService.require_permission`.
- **Deletion Password:** Calculated as `((day + month + (year % 100)) * 2) - 10`.
- **Seniority:** Calculated dynamically in months/days using `relativedelta` logic.

## 5. Output Expectation
Produce clean, modularized Python code that prioritizes separation of concerns (Features vs. Core). Ensure all widgets have the `cursor-pointer` property where interactive and follow WCAG AAA accessibility standards for contrast.
