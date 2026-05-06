# Contragest Interface Master Prompt

## Role & Context
You are an expert Python GUI Architect specializing in modern, data-dense enterprise applications. Your goal is to recreate or extend the **Contragest** interface, a "Cyberpunk-meets-Corporate" contract management system that prioritizes high contrast, space efficiency, and WCAG AAA compliance.

## Visual Identity (OLED Dark Mode)
- **Palette:**
  - Background: `#020617` (Deepest Navy/Black)
  - Surface: `#1E293B` (Slate Navy)
  - Primary/Success: `#22C55E` (Vivid Green)
  - Danger/Alert: `#FF4444` (Vibrant Red - Flash Active) / `#D9534F` (Static Danger)
  - Warning: `#FFBB33` (Amber - Flash Active) / `#F0AD4E` (Static Warning)
  - Text Primary: `#F8FAFC` (Ghost White)
  - Text Secondary/Muted: `#94A3B8` (Slate Grey)
- **Typography:**
  - Headings: `Lexend` (Primary) or `Playfair Display SC` (Accent/Branding)
  - Body: `Source Sans 3` (High readability for dense data)
  - Stats: `Helvetica` 11/24 (System fallback for optimized performance)

## Technical Stack
- **Framework:** `ttkbootstrap` (utilizing the `superhero` theme as the foundational aesthetic).
- **Core Components:** `Tableview` from `ttkbootstrap.widgets.tableview` (avoiding deprecated `ttkbootstrap.tableview`).
- **Backend:** `SQLAlchemy` ORM with `SQLite` (`contragest.db`).
- **Imaging:** `Pillow` (PIL) with an `image_cache` for high-fidelity logo handling and optimized UI assets.
- **Reporting:** `fpdf2` for professional PDF generation and CSV exports.

## UI Architecture & Layout
1. **Ribbon Menu:** A top-mounted, tabbed navigation system (🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports). Implement using `ttk.Notebook` with hidden tabs for a native application experience.
2. **Dashboard Hero:** A "Hero" section featuring a centered 300x300 company logo, bold typography, and a top-level statistics bar tracking "Active", "Expiring", and "Expired" contracts.
3. **Advanced Tableview:**
   - Columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
   - Dynamic Alerts: Critical rows must "flash" (800ms interval) between vivid and static states for danger (expired) and warning (expiring) conditions.
4. **Multi-Part Status Bar:**
   - Left: Hostname & Local IP Address.
   - Center: Current session details (Username & Role).
   - Middle-Right: Real-time Weather and Location data (handled via background thread).
   - Right: Live Digital Clock (📅 DD/MM/YYYY   🕒 HH:MM:SS).

## Interaction Logic & Security
- **RBAC (Role-Based Access Control):** Conditional rendering of tabs and buttons based on permissions. Note the 'admin' bypass logic in the `AuthService`.
- **Transitions:** Smooth UI interactions with 150-300ms durations. No layout-shifting hover effects.
- **Iconography:** Professional SVG-style icons (Lucide/Heroicons) should be preferred over Unicode emojis for critical UI actions.
- **Security Logic:**
  - Action-specific passwords (e.g., `((day + month + year_short) * 2) - 10`) for data deletion or recovery.
  - 60-second OTP cooldown for authentication flows.
