# Contragest Interface Recreation Prompt

## Project Goal
Create a sophisticated, professional desktop contract management application using **Python** and **ttkbootstrap**. The interface should follow an "Enterprise Dashboard" aesthetic with a productivity-focused **Ribbon Menu** navigation system and a data-dense main workspace.

## Visual Identity & Theme
- **Theme:** Use the `superhero` theme from `ttkbootstrap` (OLED-friendly dark mode with slate, grey, and high-contrast accent colors).
- **Branding:** Feature a company logo in two locations: a small version in the global stats header (40x40) and a large "hero" version on the Home dashboard (300x300).
- **Fonts:** Primary UI font is **Helvetica** (9pt for status bars, 10pt bold for tabs, 11pt for stats, and 24pt bold for hero titles).

## Layout Architecture
1. **Ribbon Menu (Top):**
   - Use a `ttk.Notebook` styled as a Ribbon (0 padding, bold tabs).
   - Tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
   - Content: Grouped buttons inside `Labelframes` (e.g., "Navigation", "Settings", "Employees", "Administrative").
   - Buttons: Utilize various bootstyles (`INFO`, `LIGHT`, `SECONDARY`, `DANGER`) with a padding of 10.

2. **Main Content Area (Center):**
   - A `ttk.Notebook` where tabs are hidden (`tabposition='n'`, layout cleared) to act as a dynamic view switcher.
   - Views: Home/Dashboard, Contracts Table, HR Hub, Administrative Tools, and Analytics Hub.

3. **Status Bar (Bottom):**
   - A dark-styled footer split into four sections:
     - **Left:** System telemetry (PC Name and Local IP).
     - **Middle-Left:** Current session info (User and Role).
     - **Middle-Right:** Environmental data (Location and Weather) updated via background tasks.
     - **Right:** Live digital clock (Date and Time) with a `Sizegrip`.

## Specialized Components & Logic
- **Contracts Table (`Tableview`):**
   - Columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
   - **Conditional Styling:** Tag rows based on status (`success` for active, `warning` for expiring, `danger` for expired).
   - **Alert Animation:** Implement a "flash" effect for `danger` and `warning` rows (alternating colors every 800ms) to grab user attention.
- **Access Control (RBAC):**
   - UI elements (Ribbon tabs, specific buttons) must be conditionally enabled or rendered based on user permissions.
   - 'admin' role acts as a super-user bypassing standard checks.
- **Reporting & Export:**
   - A tabbed Reports interface with global search and multi-parameter filters (dropdowns and date ranges).
   - Support for PDF and CSV exports (using `fpdf` for PDF generation).
- **Internationalization (i18n):**
   - Support for multiple languages and RTL (Right-to-Left) layouts using helper functions to adapt UI orientation.

## Backend Integration
- **Database:** SQLite with SQLAlchemy ORM.
- **Scheduling:** A `BackgroundScheduler` to handle automated alerts and periodic environmental data refreshes.
- **Security:** Re-authentication (password check) for sensitive actions like contract deletion.
