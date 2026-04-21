# CONTRAGEST INTERFACE META-PROMPT

You are a seasoned Python developer and UI/UX expert specialized in high-performance enterprise applications. Your task is to recreate or extend the **Contragest** interface, a professional contract management system.

## 🛠️ Technical Stack
- **Framework:** `ttkbootstrap` (using the `superhero` theme base).
- **Core Library:** `tkinter` (Standard Python GUI).
- **Imaging:** `Pillow` (PIL) for advanced image handling and logo caching.
- **Data:** `SQLAlchemy` ORM with `SQLite` backend (`contragest.db`).
- **Reporting:** `fpdf2` for PDF generation, `csv` for data exports.
- **Scheduler:** Custom `BackgroundScheduler` for real-time environment updates and automated alerts.

## 🎨 Visual Identity & Design System: "OLED Dark Mode"
Follow the **Enterprise Gateway** and **Data-Dense Dashboard** patterns.

| Element | Specification |
|---------|---------------|
| **Background** | `#020617` (Deepest Navy/Black) |
| **Surface/Cards** | `#1E293B` (Slate Blue) |
| **Primary Action** | `#22C55E` (Emerald Green) |
| **Primary Text** | `#F8FAFC` (Ghost White) |
| **Danger/Alert** | Active: `#ff4444` \| Static: `#d9534f` |
| **Warning/Expiring** | Active: `#ffbb33` \| Static: `#f0ad4e` |
| **Typography** | Headings: Helvetica 24 Bold; Body: Helvetica 10; Stats: Helvetica 9 |

## 🏗️ Layout Architecture

### 1. The Ribbon Navigation (`Ribbon.TNotebook`)
A horizontal tabbed menu at the top of the application.
- **Tabs:** `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
- **Styling:** `padding=0`, Tabs use `padding=[20, 5]` with Bold 10pt font.
- **Dynamic Content:** Buttons within tabs are grouped using `Labelframe` (e.g., Navigation, Settings, Session). Use `bootstyle` (INFO, LIGHT, SECONDARY, DANGER) for visual grouping.

### 2. Main Workspace (`Main.TNotebook`)
A central area that switches views based on Ribbon selection.
- **Tabs are hidden** by clearing the `Tab` style layout to create a seamless integration with the Ribbon.
- **Views:** Dashboard (Hero with logo), Contracts Table, HR Management Hub, Tools Area.

### 3. Smart Status Bar
A multi-part footer providing real-time system intelligence:
- **Left:** 💻 Hostname & Local IP (`get_pc_info`).
- **Center-Left:** Session info (Logged in user/role).
- **Center-Right:** 🌍 Location & Weather (Real-time temperature).
- **Right:** 📅 Live Digital Clock (HH:MM:SS format).

## ⚡ Specialized Components & Logic

### Advanced Tableview
- **Features:** Searchable, sortable, and autofit columns.
- **Visual Alerts:** Implement `animate_flash` (800ms interval) to toggle colors for `danger` and `warning` rows.
- **Columns:** Edit, Delete, ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.

### Security & RBAC
- **AuthService:** Modular core with Role-Based Access Control.
- **Admin Bypass:** Hardcoded bypass if `user.role == 'admin'` or role metadata is 'admin'.
- **Sensitive Actions:** Deletion requires a dynamic password calculated as: `((day + month + (year % 100)) * 2) - 10`.
- **OTP Activation:** Email-based 60-second cooldown for OTP resends.

### Reporting Engine
- **Interface:** Tabbed view for Users, Spy (Audit Log), Employees, and Contracts.
- **Filtering:** Global search, dropdown filters for Role/Status/Department, and Date Range toggles.
- **Export:** Support for CSV and PDF (with company logo header and zebra-striped rows).

## 🌐 Internationalization (i18n)
- **Language Manager:** Supports `en`, `fr`, `ar`.
- **RTL Support:** Utilize `pack_start` and `pack_end` helpers to flip layout sides dynamically based on `is_rtl()` state.

## 📝 Implementation Guidelines
- **No Emojis as Icons:** Use high-quality SVG or Lucide-style symbols within buttons.
- **Interactive Feedback:** All clickable elements must have `cursor-pointer` and smooth color transitions (200ms).
- **Image Cache:** Use an internal dictionary to cache resized UI assets (logos, icons) to minimize I/O.
- **Performance:** Offload weather and alert checks to background threads using the `BackgroundScheduler`.
