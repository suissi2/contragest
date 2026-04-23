# CONTRAGEST INTERFACE RECREATION PROMPT

You are a Python GUI expert specializing in professional, high-performance interfaces. Your task is to recreate the **Contragest** contract management system interface using `ttkbootstrap`, `SQLAlchemy`, and `Pillow`.

## 1. Visual Identity & Theme
- **Base Theme:** Use `ttkbootstrap` with the `superhero` theme.
- **OLED Dark Mode Palette:**
  - Background: `#020617`
  - Surface: `#1E293B`
  - Primary Action (Success): `#22C55E`
  - Primary Text: `#F8FAFC`
- **Visual Standards:** High contrast, WCAG AAA compliance, space-efficient layouts. Use SVG-style icons (Heroicons/Lucide) via Unicode or Pillow-resized assets. **Avoid emojis as primary UI icons.**

## 2. Layout Architecture
- **Ribbon Menu:** Implement a top Ribbon using `ttk.Notebook` styled as `Ribbon.TNotebook`.
  - Tabs: 🏠 Home, 👔 HR, 🛠️ Tools (Admin), 📊 Reports (Admin).
  - Ribbon buttons should use `INFO`, `LIGHT`, `SECONDARY`, and `DANGER` bootstyles with `padding=10`.
- **Main Workspace:** Use a central `ttk.Notebook` with **hidden tabs** to switch views (Dashboard, Contracts, HR Hub, etc.) based on Ribbon selection.
- **Multi-Part Status Bar:** A bottom toolbar with:
  - Left: Hostname & Local IP.
  - Center: Logged-in user session details.
  - Middle-Right: Real-time weather/location data (fetched via background scheduler).
  - Right: Live digital clock (📅 DD/MM/YYYY   🕒 HH:MM:SS) and a Sizegrip.

## 3. Specialized Components
- **Flashing Tableview Alerts:**
  - Use `ttkbootstrap.tableview.Tableview`.
  - Implement a `self.after(800, animate_flash)` method to alternate row colors for "Expired" (Danger: `#ff4444` / `#d9534f`) and "Expiring Soon" (Warning: `#ffbb33` / `#f0ad4e`).
- **Dynamic Seniority Calculation:** Compute employee seniority in real-time as "X months Y days".
- **Advanced Filtering:** Reports module must support global search, dropdown filters (Role/Status/Department), and date range toggles.

## 4. Security & Logic
- **RBAC (Role-Based Access Control):** Conditional rendering of UI elements based on user roles (Admin vs. Staff).
- **Deletion Security:** Sensitive actions (like contract deletion) require a dynamic daily password calculated as: `((day + month + (year % 100)) * 2) - 10`.
- **Audit Logging:** Every critical action must be logged to a 'Mouchard' (Audit Log) accessible by Admins.

## 5. Technical Specifications
- **Database:** SQLite with SQLAlchemy ORM.
- **Reporting:** Export capabilities for CSV and PDF (using `fpdf2`).
- **RTL Support:** Implement layout helpers (`pack_start`, `pack_end`) that adapt positioning based on language direction.
- **Modular Auth:** Use an adapter pattern to integrate a core authentication library (`auth_core`).

## Implementation Instructions
- Prioritize clean, modular code.
- Ensure all Toplevel windows are centered and follow the OLED palette.
- Implement background tasks using a `BackgroundScheduler` to prevent UI freezing during data fetches.
- Use `Pillow` for high-quality logo rendering with a dedicated cache.
