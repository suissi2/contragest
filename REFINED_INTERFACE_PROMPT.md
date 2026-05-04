# High-Fidelity Design Prompt: Contragest OLED Interface

**Role:** Expert Python GUI Developer & UI/UX Designer.
**Objective:** Create a professional, high-density desktop application using **Python** and **ttkbootstrap**, following an **OLED Dark Mode** aesthetic.

## 1. Visual Identity & Palette (OLED Dark Mode)
Implement a high-contrast, "Cyberpunk-meets-Corporate" theme with the following hex code tokens:
- **Background:** `#020617` (True Black/Deep Navy)
- **Surface/Cards:** `#1E293B` (Slate)
- **Primary/Accent:** `#22C55E` (Vibrant Emerald Green)
- **Primary Text:** `#F8FAFC` (Ghost White)
- **Muted/Secondary Text:** `#94A3B8` (Slate Gray)
- **Danger (Alerts):** `#FF4444` (Flash) / `#D9534F` (Static)
- **Warning (Expiring):** `#FFBB33` (Flash) / `#F0AD4E` (Static)

## 2. Typography Hierarchy
- **Headings:** *Playfair Display SC* (Serif, Elegant, Professional)
- **UI Elements (Buttons/Tabs):** *Lexend* (Geometric, Readable)
- **Body Text/Data:** *Source Sans 3* (Functional, Data-Dense)

## 3. Layout Architecture
- **Ribbon Navigation:** A tabbed header categorized into `🏠 Home`, `👔 HR`, `🛠️ Tools`, and `📊 Reports`. Icons must be high-fidelity SVG/Lucide-style (no emojis).
- **Hero Dashboard:** A centered workspace featuring a 300x300 company logo, a primary stats bar (Active vs. Expiring vs. Expired), and professional hero typography.
- **Advanced Tableview:** A data grid with columns for *Edit, Delete, ID, Name, Type, Dates, Seniority,* and *Status*.
    - **Logic:** Implement a **800ms flashing alert** for rows in 'Danger' or 'Warning' states.
    - **Seniority Logic:** Dynamic calculation of months and days since the `start_date`.
- **Status Bar:** A sophisticated 4-part footer:
    - **Left:** System Info (PC Name/IP).
    - **Center:** Session Details (User/Role).
    - **Middle-Right:** Environmental Data (Location/Weather).
    - **Right:** Live Digital Clock (HH:MM:SS).

## 4. Technical Stack & Logic
- **UI Framework:** `ttkbootstrap` (inheriting from the 'superhero' theme).
- **Backend:** `SQLAlchemy` ORM with `SQLite`.
- **Security:** Implement a **Role-Based Access Control (RBAC)** system where UI elements (Ribbon tabs/buttons) are conditionally rendered based on permissions.
- **Reporting:** Support for CSV and PDF export (using `fpdf2`) with filtered data views.
- **Performance:** Use an `image_cache` dictionary for resized UI assets to minimize I/O.

## 5. Interaction Standards
- All clickable cards and buttons must have `cursor-pointer`.
- Smooth state transitions (150-300ms) for hover effects.
- WCAG AAA compliance for high-contrast dark mode readability.

---
**Final Instruction:** Generate the Python code for the `MainWindow` and `RibbonMenu` components that implement this specification, ensuring the layout is space-efficient and follows the "Enterprise Gateway" pattern.
