# Meta-Prompt: Contragest Enterprise Interface

**Role:** You are an expert Python GUI Developer specializing in modern, high-performance enterprise applications.

**Task:** Create a professional Contract Management System (CMS) named "Contragest" using `ttkbootstrap`. The application must adhere to a strict "OLED Dark Mode" aesthetic and follow the "Enterprise Gateway" design pattern.

## 1. Technical Stack & Foundation
- **Framework:** Python with `ttkbootstrap` (Theme: `superhero`).
- **Icons:** Use SVG/Lucide-style icons (represented as unicode symbols or external SVG assets, no emojis in UI).
- **Core Libraries:** `Pillow` (image processing), `SQLAlchemy` (ORM), `fpdf2` (PDF reports).
- **Layout Logic:** Implement a modular architecture with an `AppController` managing transitions between a "Secure Auth System" (Login) and the "Main Dashboard".

## 2. Visual Identity (OLED Dark Mode)
- **Background:** `#020617` (Deep Black)
- **Surfaces/Cards:** `#1E293B` (Slate)
- **Primary Action/CTA:** `#22C55E` (Emerald Green)
- **Text:** `#F8FAFC` (Ghost White)
- **Typography:** Fira Code for headings, Fira Sans for body text.

## 3. UI Architecture
- **Ribbon Menu:** A top-aligned `ttk.Notebook` (Style: `Ribbon.TNotebook`) with tabs for 🏠 Home, 👔 HR, 🛠️ Tools, and 📊 Reports. Buttons within the ribbon should use categorized `LabelFrame` groups (e.g., "Navigation", "Administrative").
- **Main Workspace:** A central area using a hidden-tab `ttk.Notebook` (Style: `Main.TNotebook`) for seamless view switching triggered by the Ribbon.
- **Status Bar:** A four-part bottom bar:
    - **Left:** PC Info (Hostname/IP).
    - **Center-Left:** Session details (Username/Role).
    - **Center-Right:** Live environmental data (Location/Weather via background thread).
    - **Right:** Digital Clock (Date/Time) with a `Sizegrip`.

## 4. Advanced Components & UX
- **Data Table:** A `Tableview` with conditional row tagging:
    - `danger`: Red (#d9534f) for expired items.
    - `warning`: Amber (#f0ad4e) for expiring soon items.
    - **Visual Alert:** Implement a 800ms "flash" animation for critical rows using `tag_configure`.
- **Dashboard "Hero" Section:** A centralized view featuring a large thumbnail of the company logo (300x300) and professional branding.
- **Right-to-Left (RTL) Support:** Layout must be adaptable via helper functions (`pack_start`/`pack_end`) and `LanguageManager`.

## 5. Security & Logic
- **RBAC:** UI elements (Tabs, Buttons) must be conditionally rendered or enabled based on user permissions checked through an `AuthService`.
- **Sensitive Actions:** Operations like "Contract Deletion" or "Recovery" must require a calculated daily password: `((day + month + (year % 100)) * 2) - 10`.
- **Background Services:** A `BackgroundScheduler` to handle automated alerts and data syncing.

## 6. Deliverable Expectation
Produce clean, modular, and PEP8-compliant Python code. Ensure all UI assets (logos, icons) are managed via an `image_cache` to minimize disk I/O. The result must be a professional, high-integrity interface suitable for corporate environments.
