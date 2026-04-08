# Contragest Interface Meta-Prompt

## Project Overview
**Contragest** is a professional contract management system built with Python and `ttkbootstrap`. It follows a "Data-Dense Dashboard" and "Enterprise Gateway" design pattern, optimized for administrative efficiency and visual clarity.

## Visual Identity & Theme
- **Base Theme:** `superhero` (ttkbootstrap).
- **Aesthetic:** "OLED Dark Mode" – High contrast, space-efficient layouts, professional slate blue and grey palette.
- **Visual Feedback:**
    - Smooth transitions (150-300ms).
    - Interactive elements use `cursor-pointer`.
    - **Flashing Alerts:** Critical rows in tables (Expired/Expiring) flash every 800ms between vivid (#ff4444, #ffbb33) and muted theme colors.

## Layout Architecture
### 1. Ribbon Navigation (`Ribbon.TNotebook`)
- **Structure:** A top-level Notebook with tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
- **Styling:** Tab padding `[20, 5]`, Bold 10pt Helvetica font.
- **Functional Groups:** Buttons are organized into `Labelframe` groups (e.g., "Navigation", "Settings", "Administrative").
- **Button Bootstyles:**
    - Primary actions: `INFO`
    - Secondary/Support: `LIGHT` / `SECONDARY`
    - Danger/Exit: `DANGER` / `outline-warning`

### 2. Main Workspace (`Main.TNotebook`)
- Tabs are hidden by clearing the `Tab` style layout.
- View switching is synchronized with Ribbon tab selection.

### 3. Status Bar
- **Position:** Bottom of window, `DARK` bootstyle.
- **Sections (Left to Right):**
    - **System Info:** Hostname and Local IP.
    - **Session Info:** Current username and role.
    - **Environment:** Live location and weather data (🌍/🌡️).
    - **Digital Clock:** Real-time date and time (📅/🕒).
    - **Sizegrip:** Standard window resizing handle.

## Advanced Components
### Data Tables (Tableview)
- **Columns:** Edit (✏️), Delete (🗑️), ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
- **Logic:**
    - **Seniority:** Computed dynamically in "X months Y days".
    - **Days Left:** Infinite (∞) for CDI, integer for CDD.
    - **Conditional Tagging:**
        - `success`: Active contracts.
        - `warning`: Expiring soon (threshold-based).
        - `danger`: Expired contracts.

### Report System
- **Interface:** Tabbed view within a Toplevel window.
- **Features:** Global search, column-specific dropdown filters, date range pickers.
- **Export:** High-quality CSV and PDF generation (using `fpdf`), including company logo headers and zebra-striped rows.

## Backend & Security Logic
### Role-Based Access Control (RBAC)
- **Levels:** Permissions defined per Screen and Action (View, Add, Edit, Delete).
- **Admin Bypass:** Users with the 'admin' role bypass specific permission checks.
- **Action Logging:** Every sensitive action is recorded in a "Mouchard" (Audit Log).

### Security Features
- **Sensitive Actions:** Deletion requires a dynamic session password calculated as: `((day + month + (year % 100)) * 2) - 10`.
- **Authentication:** Modular `auth_core` with OTP activation, password hashing, and 60-second cooldowns on resending codes.

### Background Services
- **Scheduler:** Manages periodic alerts and environment data updates.
- **EmailManager:** Thread-safe singleton with a priority-based retry queue and exponential backoff.

## Implementation Guidelines
- **i18n/RTL:** Support for multiple languages (EN, FR, AR) with a dedicated `LanguageManager`. Use `pack_start` and `pack_end` helpers for RTL-aware layouts.
- **Assets:** Use cached and resized images (Pillow) to minimize disk I/O.
- **Icons:** Use SVG/Lucide-style icons where possible; avoid standard emojis for UI elements except in specific status/ribbon contexts.
