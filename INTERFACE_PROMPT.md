### Prompt for Interface Reconstruction: Professional Contract Management System (Contragest)

**Objective:**
Design and implement a modern, high-fidelity desktop application interface for "Contragest," a contract management system, using Python and `ttkbootstrap`. The goal is to achieve an enterprise-grade aesthetic that balances high data density with visual clarity.

**1. Design Language & Theme:**
- **Theme:** Use the `ttkbootstrap` 'superhero' theme (a professional dark mode palette with slate blues, greys, and vibrant status colors).
- **Typography:** Primary font is 'Helvetica' or 'Segoe UI'. Use bold 10pt for tabs and 12-16pt for headers.
- **Branding:** Integrate a company logo in the top-left header and a larger centered version (300x300) in the dashboard 'Hero' area.

**2. Layout Architecture:**
- **Ribbon Menu (Top):** Implement a ribbon-style navigation using a `ttk.Notebook` with zero padding. Tabs should be labeled with emojis (e.g., 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports).
- **Main Workspace (Center):** A second `ttk.Notebook` where tabs are hidden (to simulate a single-page application feel controlled by the Ribbon).
- **Status Bar (Bottom):** A multi-part `ttk.Frame` (bootstyle=DARK) containing:
    - Left: PC name and IP address.
    - Center-Left: Session status (e.g., "Logged in as: admin").
    - Center-Right: Real-time environmental data (Location 🌍 and Weather 🌡️).
    - Right: A live digital clock (📅 DD/MM/YYYY 🕒 HH:MM:SS) and a window resize grip.

**3. Data Visualization & Table Components:**
- **Dynamic Tableview:** Use `ttkbootstrap.tableview.Tableview` for the main contract list.
- **Columns:** Edit (icon), Delete (icon), ID, First Name, Last Name, Type (CDI/CDD), Start Date, End Date, Seniority (calculated as "X months Y days"), Days Left, and Status.
- **Conditional Formatting:**
    - **Danger (#d9534f):** Expired contracts or critical errors.
    - **Warning (#f0ad4e):** Contracts expiring within a 30-day threshold.
    - **Success (#5cb85c):** Active/valid contracts.
- **Visual Feedback:** Implement a "flash" animation for 'Danger' and 'Warning' rows using a background color toggle every 800ms to draw immediate attention.

**4. Functional Components:**
- **Reports View:** A tabbed interface for filtered reporting (Users, Spy/Audit Log, Employees, Contracts) with built-in CSV and PDF export capabilities.
- **Forms:** Modal `Toplevel` windows for data entry (e.g., ContractForm) using `Labelframe` for grouping fields and specialized widgets like `DateEntry` and `Spinbox`.
- **RBAC (Role-Based Access Control):** The UI must dynamically toggle the visibility of the "Tools" and "Reports" ribbon tabs based on the user's role (admin vs. user).

**5. Security Features:**
- **Calculated Passwords:** Implement a daily security password for sensitive actions (like deletion) using the formula: `((day + month + (year % 100)) * 2) - 10`.
- **Audit Log (Mouchard):** A dedicated view to track system actions with timestamps and entity details.
