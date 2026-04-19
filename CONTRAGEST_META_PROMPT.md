# Contragest Meta-Prompt: Technical & Visual Specification

This document serves as the definitive guide for recreating the Contragest interface—a high-performance, enterprise-grade contract management system.

## 1. Visual Identity & Aesthetic (OLED Dark Mode)
The application utilizes an **OLED Dark Mode** palette designed for high contrast and power efficiency on modern displays.

- **Background:** `#020617` (Deep Midnight)
- **Surfaces/Cards:** `#1E293B` (Slate Blue)
- **Primary/Positive Actions:** `#22C55E` (Emerald Green)
- **Primary Text:** `#F8FAFC` (Ghost White)
- **Theme:** Based on `ttkbootstrap` "superhero" theme but customized for OLED contrast.

### Typography
- **Headings:** Helvetica 24pt Bold (Hero section) or 18pt Bold (Tab headers).
- **Body:** Helvetica 10pt/11pt.
- **Status Bar:** Helvetica 9pt.

## 2. Navigation Architecture
The layout follows the **Enterprise Gateway** pattern, replacing traditional sidebars with a **Ribbon Menu** and a **Hidden-Tab Notebook** workspace.

### Ribbon Menu (`Ribbon.TNotebook`)
- **Structure:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
- **Styling:** `Ribbon.TNotebook.Tab` with `[20, 5]` padding and bold font.
- **Interaction:** Selecting a Ribbon tab switches the view in the main workspace and updates available action buttons.

### Main Workspace (`Main.TNotebook`)
- Tabs are hidden by clearing the `Main.TNotebook.Tab` layout style to provide a seamless, integrated feel.

## 3. Specialized UI Components

### Flashing Tableview Alerts
- **Behavior:** Rows with "Expired" (danger) or "Expiring Soon" (warning) status must flash to capture user attention.
- **Interval:** 800ms cycle.
- **Colors (Active Flash):**
  - Danger: `#ff4444` (Background) / White (Foreground)
  - Warning: `#ffbb33` (Background) / Black (Foreground)
- **Colors (Static/Rest):**
  - Danger: `#d9534f`
  - Warning: `#f0ad4e`

### Advanced Status Bar
- **Four-Part Layout:**
  1. **System Info (Left):** Hostname and Local IP.
  2. **Session Info (Center):** Current user and Role.
  3. **Environmental Data (Middle-Right):** Real-time location and weather (e.g., 🌍 City 🌡️ 22°C).
  4. **Digital Clock (Right):** Live seconds update (📅 DD/MM/YYYY 🕒 HH:MM:SS).

## 4. Technical Constraints & Logic

### Tech Stack
- **Language:** Python 3.10+
- **GUI Framework:** `ttkbootstrap` (for modern widgets and themes).
- **ORM/DB:** `SQLAlchemy` with `SQLite`.
- **Imaging:** `Pillow` (PIL) for logo caching and dynamic resizing.
- **Reporting:** `fpdf2` for PDF export generation.

### Security & Access Control
- **RBAC:** Permission-based access to tabs and buttons (e.g., only 'admin' sees the 'Tools' tab).
- **Auth:** OTP-based activation with a 60-second resend cooldown.
- **Sensitive Actions:** Deletion requires a dynamic "Day-Code" password.
  - **Formula:** `((day + month + (year % 100)) * 2) - 10`

### Performance Optimization
- **Image Cache:** Resized UI assets (logos) must be stored in a dictionary to prevent redundant disk I/O.
- **Background Tasks:** Use a `BackgroundScheduler` for environmental updates and alert checks to keep the UI responsive.

## 5. Implementation Prompt for LLMs
To recreate this interface, use the following instruction:
> "Act as a Senior Python Developer specializing in GUI architecture. Build a contract management dashboard using `ttkbootstrap` with an **OLED Dark Mode** theme (`#020617` background). Implement a **Ribbon Menu** navigation system that controls a hidden-tab notebook workspace. The primary view must feature a `Tableview` with a **800ms flashing alert system** for expiring items. Include a multi-part status bar displaying system info, session details, and a live clock. Ensure the architecture supports RBAC and uses a BackgroundScheduler for non-blocking environmental updates. Focus on a high-density, professional enterprise aesthetic."
