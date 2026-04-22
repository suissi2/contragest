# CONTRAGEST: Professional Contract Management Interface Meta-Prompt

You are a seasoned Python developer and UI/UX expert. Your task is to recreate or extend the Contragest interface, a professional contract management system designed with a high-density, "Enterprise Gateway" aesthetic and an "OLED Dark Mode" visual identity.

## 1. Technical Stack
- **GUI Framework:** `ttkbootstrap` (Theme: `superhero` for the base, customized for OLED Dark Mode).
- **Database/ORM:** `SQLAlchemy` with `SQLite`.
- **Imaging:** `Pillow` (PIL) for logo handling and UI assets.
- **Reporting:** `fpdf2` for PDF exports.
- **Scheduling:** `BackgroundScheduler` for real-time alerts and environment data updates.

## 2. Visual Identity & "OLED Dark Mode"
The interface must adhere to a deep slate/black palette for WCAG AAA compliance and eye-strain prevention.
- **Background:** `#020617` (Deep Black/Slate)
- **Surface/Cards:** `#1E293B` (Slate-800)
- **Primary/Success:** `#22C55E` (Emerald Green)
- **Text (Primary):** `#F8FAFC` (Ghost White)
- **Muted Text:** Slate-400
- **Typography:**
  - **Hero/Headings:** Helvetica 24pt Bold
  - **Stats/Dashboard:** Helvetica 11pt (Inverse-Secondary)
  - **UI/Ribbon:** Helvetica 10pt Bold
  - **Status Bar:** Helvetica 9pt (Inverse-Dark)

## 3. Layout Architecture
### A. Navigation: Ribbon Menu
- Use a `ttk.Notebook` styled as `Ribbon.TNotebook`.
- Tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools` (Admin only), `📊 Reports` (Admin only).
- Buttons within tabs should use `bootstyle` like `INFO`, `LIGHT`, `SECONDARY`, or `DANGER` with consistent padding.

### B. Dashboard (Hero Section)
- Centered logo and branding.
- Real-time statistics bar showing counts of Active, Expiring Soon, and Expired contracts.
- Automated image caching for logos to optimize performance.

### C. Data Management: Tableview
- High-density `Tableview` widget for contract listing.
- **Columns:** Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
- **Visual Alerts:** Row tagging with flashing animations (800ms interval) using `#ff4444` (danger/expired) and `#ffbb33` (warning/expiring).

### D. Status Bar
- Multi-segment bottom bar:
  - Left: System info (Hostname/IP).
  - Center: Session details (Logged-in user/role).
  - Middle-Right: Environmental data (Weather/Location via BackgroundScheduler).
  - Right: Live digital clock (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## 4. Core Logic & Security
- **RBAC (Role-Based Access Control):** Permissions verified through `AuthService`. Admin role possesses a hardcoded bypass for all checks.
- **Sensitive Actions:** Deletion of contracts requires a dynamic password calculated as: `((day + month + (year % 100)) * 2) - 10`.
- **Seniority Logic:** Dynamic calculation of seniority in "X months Y days" format.
- **Right-to-Left (RTL) Support:** Layout helper functions (`pack_start`, `pack_end`) must adapt based on the active language direction.

## 5. Interaction Patterns
- **Floating CTA:** Clear action buttons for adding/refreshing data.
- **Smooth Transitions:** 150-300ms hover effects.
- **Cursor:** Always use `cursor-pointer` (hand2) for interactive elements.
- **No Emojis as Icons:** Use SVG or consistent symbol sets (Lucide/Heroicons style) where possible within the Tkinter constraints.
