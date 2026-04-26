# Contragest Meta-Prompt: High-Fidelity Interface Recreation

You are an expert Python developer specialized in high-end Graphical User Interfaces (GUIs) and robust data architectures. Your task is to recreate or extend the **Contragest** interface, a professional contract management system defined by its "Enterprise Gateway" architecture and "OLED Dark Mode" aesthetic.

## 1. Visual Identity & Design System

### OLED Dark Mode Palette
- **Background**: `#020617` (Deepest Navy/Black)
- **Surface/Cards**: `#1E293B` (Slate Navy)
- **Primary Action/Success**: `#22C55E` (Emerald Green)
- **Primary Text**: `#F8FAFC` (Ghost White)
- **Secondary Text/Muted**: `#94A3B8` (Slate Gray)
- **Base Theme**: `ttkbootstrap` "superhero" (highly customized).

### Typography
- **Display/Headers**: `Playfair Display SC` (Small Caps Serif) for a premium, authoritative feel.
- **Body/Interface**: `Lexend` or `Lexend Deca` for maximum readability and a modern tech look.
- **Hero Labels**: Helvetica 24pt Bold.
- **Dashboard Stats**: Helvetica 11pt (Inverse-Secondary).
- **Status Bar**: Helvetica 9pt.

### Iconography & Effects
- **Icons**: Replace Unicode emojis with high-fidelity SVG icons (Lucide or Heroicons) in production.
- **Transitions**: Smooth state changes (150-300ms).
- **Table Alerts**: Critical rows (expired/expiring) must use a smooth flashing effect (800ms interval) between vivid and muted states (e.g., `#ff4444` vs `#d9534f`).

## 2. Layout Architecture

### Navigation: The Ribbon Menu
The application uses a `Ribbon.TNotebook` style at the top to categorize actions:
- **🏠 Home**: Dashboard overview, system settings, and session control (Logout/Exit).
- **👔 HR**: Employee and Contract management hubs.
- **🛠️ Tools**: Administrative utilities (User Management, Audit Log/Mouchard).
- **📊 Reports**: Centralized analytics access.

### Main Workspace
- **Dashboard (Home)**: Features a "Hero Area" with a large company logo and professional branding.
- **Contracts View**: A data-dense `Tableview` with conditional row tagging (Success, Warning, Danger) based on contract status.
- **Status Bar**: A four-part responsive footer:
  1. PC Info: Hostname and IP.
  2. Session Info: Current username and role.
  3. Environment: Live location and weather data (updated via background thread).
  4. Clock: Real-time digital clock (DD/MM/YYYY HH:MM:SS).

## 3. Core Functional Logic

### Security & RBAC
- **AuthService**: Implements Role-Based Access Control using mixins.
- **Admin Bypass**: Users with the 'admin' role or belonging to an 'admin' role group bypass specific permission checks.
- **Sensitive Actions**: Deletion and recovery require a dynamic security password calculated as: `((day + month + (year % 100)) * 2) - 10`.
- **OTP Logic**: Resend activation OTP includes a 60-second cooldown.

### Data Management
- **Stack**: SQLAlchemy (ORM), SQLite (Local DB), Pillow (Image processing), fpdf2 (PDF generation).
- **Seniority Calculation**: Dynamic calculation of months and days since `start_date` using calendar-aware logic.
- **Background Tasks**: A `BackgroundScheduler` manages automated alerts and environmental data updates without blocking the UI.

## 4. Advanced Components

### Reports Module
A tabbed interface (`Users`, `Spy`, `Employees`, `Contracts`) featuring:
- **Global Search**: Real-time filtering across all columns.
- **Advanced Filters**: Role/Status/Department dropdowns and specific Date Range pickers.
- **Exporting**: One-click export to CSV and professionally formatted PDF (including company logo and timestamp).

### Right-to-Left (RTL) Support
The UI must adapt to Arabic (`ar`) locales using layout helpers (`pack_start`, `pack_end`) that flip the interface direction while maintaining logical consistency.

## 5. Implementation Directives
- **WCAG AAA Compliance**: Maintain high contrast ratios for the OLED theme.
- **Performance**: Use image caching for UI assets to minimize disk I/O.
- **Stability**: Ensure all database sessions are properly closed; use `selectinload` for RBAC permission collections to avoid `DetachedInstanceError`.
- **Hygiene**: Exclude `__pycache__`, `.db`, and `.log` files from version control.
