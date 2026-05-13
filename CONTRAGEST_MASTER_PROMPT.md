# CONTRAGEST INTERFACE MASTER PROMPT

**Objective:** Recreate or extend a high-fidelity "Enterprise Gateway" interface utilizing a "Cyberpunk-meets-Corporate" OLED Dark Mode aesthetic.

## 1. Visual Identity & Design Tokens
- **Design System:** "Enterprise Gateway" with a focus on high contrast and space efficiency.
- **Palette (OLED Dark Mode):**
  - **Background:** `#020617` (Deepest Black/Navy)
  - **Surface/Cards:** `#1E293B` (Slate Navy)
  - **Primary/Accent:** `#22C55E` (Emerald Green)
  - **Text (Primary):** `#F8FAFC` (Ghost White)
  - **Text (Secondary/Muted):** `#94A3B8` (Slate Gray)
  - **Danger/Alert (Active):** `#FF4444`
  - **Danger/Alert (Static):** `#D9534F`
  - **Warning/Alert (Active):** `#FFBB33`
  - **Warning/Alert (Static):** `#F0AD4E`
- **Typography:**
  - **Primary Headers:** Lexend (clean, modern, highly readable)
  - **Branding Accents:** Playfair Display SC (sophisticated serif)
  - **Body Text:** Source Sans 3 (optimized for data-dense environments)
  - **Monospace (Data):** Fira Code (optional for terminal-style elements)

## 2. Layout Architecture
- **Navigation:** Top-mounted **Ribbon Menu** using a Tabbed interface.
  - **Tabs:** `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
  - **Ribbon Buttons:** Logical grouping (Navigation, Settings, Session) with SVG/Lucide-style icons.
- **Dashboard (Home):**
  - **Hero Section:** Centered 300x300 company logo with large bold headers.
  - **Stats Bar:** Top-level summary of active, expiring, and expired contracts.
- **Data Management (Contracts/Reports):**
  - **Tableview:** Advanced sorting, global search filtering, and pagination.
  - **Flashing Alerts:** Smooth transition (800ms) for critical rows (Danger/Warning states).
- **Status Bar:** Bottom toolbar displaying PC info (IP/Hostname), environmental data (Weather/Location), and a live real-time clock.

## 3. Technical Stack
- **Language:** Python 3
- **GUI Framework:** `ttkbootstrap` (utilizing `superhero` as a base theme, extensively customized).
- **Database:** SQLAlchemy ORM with SQLite (`contragest.db`).
- **Reporting:** `fpdf2` for professional PDF export with company branding.
- **Imaging:** `Pillow` (PIL) for logo processing and UI assets.
- **Security:** Role-Based Access Control (RBAC) with hardcoded 'admin' bypass logic for core management.

## 4. Interaction Logic
- **Smooth Transitions:** State changes and hover effects between 150-300ms.
- **Permissions:** Conditional rendering of UI elements based on user role (e.g., Tools and Reports tabs restricted to Admin).
- **Automation:** Background scheduler for expiration alerts and environmental data updates.
- **Accessibility:** WCAG AAA compliance for OLED dark theme contrast.

## 5. Implementation Prompt for LLM
"Act as a seasoned Python developer and UI/UX expert. Create a professional contract management system named 'Contragest' using `ttkbootstrap` and the 'superhero' theme as a baseline. The interface must feature an OLED Dark Mode (#020617) with emerald green (#22C55E) accents. Implement a Ribbon Menu with tabs for Home, HR, and Tools. The dashboard should include a Hero section with a large logo and a real-time status bar at the bottom showing system and environmental info. Include a data table for contracts that uses a flashing visual alert (800ms interval) for expiring items. Use Lexend for headers and Source Sans 3 for body text. Ensure the code is modular, utilizing SQLAlchemy for data persistence and fpdf2 for reports."
