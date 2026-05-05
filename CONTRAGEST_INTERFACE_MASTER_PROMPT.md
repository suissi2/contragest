# Master Prompt: Contragest Enterprise Interface

Act as a Senior Python UI/UX Developer. Your goal is to recreate or extend the "Contragest" interface—a professional, high-fidelity contract management system using the "Enterprise Gateway" and "OLED Dark Mode" design patterns.

## 1. Core Visual Identity & Design System
- **Theme:** "OLED Dark Mode" (Cyberpunk-meets-Corporate).
- **Palette:**
    - **Background:** `#020617` (Deepest Navy/Black)
    - **Surface/Cards:** `#1E293B` (Slate)
    - **Primary/Success:** `#22C55E` (Vibrant Green)
    - **Text (Main):** `#F8FAFC` (Off-white)
    - **Text (Muted):** `#94A3B8` (Slate Blue-Grey)
    - **Danger/Expired:** `#FF4444` (Flash) / `#D9534F` (Static)
    - **Warning/Expiring:** `#FFBB33` (Flash) / `#F0AD4E` (Static)
- **Typography:**
    - **Headings:** Lexend (clean, geometric, professional)
    - **Body:** Source Sans 3 (highly readable)
    - **Accents:** Playfair Display SC (for high-end enterprise touch)
- **Accessibility:** Ensure WCAG AAA compliance for high contrast.
- **Icons:** Use SVG-style high-fidelity icons (Lucide or Heroicons). No unicode emojis.

## 2. Technical Stack
- **GUI Framework:** Python with `ttkbootstrap` (utilizing the 'superhero' base theme but heavily customized with the OLED palette).
- **Backend:** SQLAlchemy (SQLite) for ORM.
- **Image Processing:** Pillow (PIL) for high-quality logo handling and image caching.
- **Reporting:** `fpdf2` for professional CSV/PDF exports.

## 3. UI Architecture
- **Ribbon Navigation:**
    - Implement a Ribbon Menu at the top using a `ttk.Notebook` style.
    - Tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
    - Each tab contains grouped action buttons with standard padding (10) and specific bootstyles (INFO, LIGHT, SECONDARY, DANGER).
- **Dashboard Layout:**
    - **Hero Section:** Centered 300x300 company logo with a bold "Contragest" title and a subtitle.
    - **Stats Bar:** A top-level horizontal bar tracking "Active", "Expiring", and "Expired" contract counts.
- **Data Tables (Tableview):**
    - High-density `Tableview` widget for contract management.
    - Columns: Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
    - **Visual Alerts:** Implement a smooth flashing effect for critical rows (800ms interval) using the Danger and Warning palettes.
- **Status Bar:**
    - Multi-part bottom bar providing:
        1. PC Info (Hostname/IP)
        2. Session Status (User/Role)
        3. Environment Data (Location/Weather)
        4. Live Digital Clock (Right-aligned).

## 4. Key Logic & Security
- **RBAC:** Implement Role-Based Access Control. Admin users bypass specific permission checks.
- **Seniority Logic:** Dynamically calculate months and days since `start_date`.
- **Security Password:** For destructive actions (e.g., Delete), use a daily formula: `((day + month + (year % 100)) * 2) - 10`.
- **Background Tasks:** Use a scheduler for automatic expiration alerts and environmental data updates.

## 5. Implementation Instructions
- Prioritize space-efficient, professional layouts.
- Use smooth transitions (150-300ms) for interactive elements.
- Maintain strict repository hygiene (exclude binary .db, __pycache__, and .log files).
- Implement a modular `AuthService` core for scalable security management.
