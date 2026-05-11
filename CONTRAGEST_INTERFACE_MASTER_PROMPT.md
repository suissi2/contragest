# Contragest Interface Master Prompt

This prompt is designed for an LLM to recreate or extend the high-fidelity graphical interface of the 'Contragest' Enterprise Contract Management System. It captures the visual identity, technical stack, and core UI architecture.

---

## 🎨 Visual Identity & Design Tokens (OLED Dark Mode)

The interface follows a 'Cyberpunk-meets-Corporate' aesthetic, optimized for high contrast and modern data density.

- **Background:** `#020617` (Deepest Navy/Black)
- **Surface/Cards:** `#1E293B` (Slate Navy)
- **Primary/Success:** `#22C55E` (Vivid Green)
- **Secondary/Muted:** `#94A3B8` (Cool Grey)
- **Text:** `#F8FAFC` (Off-white)
- **Danger (Alerts):** Active: `#ff4444` | Static: `#d9534f`
- **Warning (Alerts):** Active: `#ffbb33` | Static: `#f0ad4e`

### Typography
- **Primary Headers:** `Lexend` (Professional & Modern)
- **Branding Accents:** `Playfair Display SC` (Elegant Serif)
- **Body Text:** `Source Sans 3` (High readability)
- **Data/Monospace:** `Fira Code` (Optional for technical sections)

---

## 🛠️ Technical Stack

- **Language:** Python 3.12+
- **GUI Framework:** `ttkbootstrap` (Theme: `superhero` with extensive custom overrides)
- **Database/ORM:** `SQLAlchemy` (SQLite)
- **Image Processing:** `Pillow` (PIL) for logo caching and thumbnails.
- **Reporting:** `fpdf2` for PDF generation.
- **Security:** Role-Based Access Control (RBAC), OTP-based activation.

---

## 🏗️ UI Architecture & Components

### 1. Main Navigation: The Ribbon Menu
- **Tabs:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
- **Structure:** `ttk.Notebook` styled to remove tabs, synchronized with Ribbon button clicks.
- **Buttons:** Large, descriptive icons (Lucide/SVG style) with `bootstyle` categorization (INFO, LIGHT, SECONDARY, DANGER).

### 2. Dashboard: The Hero Section
- **Stats Bar:** Top-aligned bar showing contract counts (Active, Expiring, Expired) using `inverse-secondary` bootstyle.
- **Hero Area:** Centered company logo (300x300) with bold branding typography and a professional subtitle.

### 3. Data View: Advanced Tableview
- **Table:** `ttkbootstrap.widgets.tableview` (Deprecation Note: Do not use `ttkbootstrap.tableview`).
- **Dynamic Alerts:** Rows representing 'Expired' or 'Expiring Soon' contracts must **flash** every 800ms, alternating between Vivid and Static colors.
- **Actions:** Inline icons (✏️, 🗑️) for quick record manipulation.

### 4. Status Bar
- Bottom-aligned HUD displaying:
  - 💻 PC Name & Local IP
  - 👤 Logged-in user & Role
  - 🌍 Location & Weather (Background task update)
  - 📅 Live Clock (HH:MM:SS)

---

## 🔐 Core Logic Implementation Notes

- **RBAC:** Conditional rendering of UI elements (Ribbon tabs, Buttons) based on `AuthService.check_access`.
- **OTP Cooldown:** 60-second window for resending activation codes.
- **Deletion Security:** Master deletion password calculated dynamically: `((day + month + (year % 100)) * 2) - 10`.
- **Image Cache:** Maintain an internal dictionary of resized images to prevent disk I/O lag during GUI refreshes.

---

## 🚀 Prompt for Re-creation

> "Act as a Senior Python Developer and UI/UX Expert. Create a desktop application using `ttkbootstrap` that implements the 'Contragest' Enterprise Gateway. Use an OLED Dark Mode palette (#020617, #1E293B, #22C55E). Implement a Ribbon-style navigation menu with tabs for Home, HR, Tools, and Reports. The Dashboard should feature a high-fidelity Hero section with a centered logo and a stats bar. Include a data-dense Tableview with a flashing alert mechanism for critical status rows (800ms interval). Ensure WCAG AAA compliance for text contrast and use Lexend for headings. Integrate a bottom HUD-style status bar showing system info and a live clock. The backend should utilize SQLAlchemy with a secure RBAC system."
