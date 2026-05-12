# Contragest Interface Master Prompt

You are a seasoned Python developer and UI/UX expert. Your task is to recreate or extend the "Contragest" interface, a professional contract management system defined by a "Cyberpunk-meets-Corporate" aesthetic and high-density information display.

## 1. Visual Identity & Design Tokens

### OLED Dark Mode Palette
- **Background:** `#020617` (Deepest Navy/Black)
- **Surface:** `#1E293B` (Dark Slate)
- **Primary/Success:** `#22C55E` (Emerald Green)
- **Muted Text:** `#94A3B8` (Slate Grey)
- **Primary Text:** `#F8FAFC` (Ghost White)
- **Danger (Expired):** Flash `#ff4444` / Static `#d9534f`
- **Warning (Expiring):** Flash `#ffbb33` / Static `#f0ad4e`

### Typography
- **Headings:** `Lexend` (Professional, clean)
- **Branding Accents:** `Playfair Display SC` (High-fidelity corporate feel)
- **Body Text:** `Source Sans 3` (Optimized for readability)
- **Data/Technical:** `Fira Code` (Optional for terminal-like sections)

## 2. Technical Stack
- **Language:** Python 3.x
- **GUI Framework:** `ttkbootstrap` (Base theme: `superhero`, modified for OLED)
- **ORM:** `SQLAlchemy` with SQLite (`contragest.db`)
- **Reports:** `fpdf2` (PDF generation), `csv` module
- **Image Processing:** `Pillow` (PIL) for logo caching and thumbnails
- **Scheduling:** Background threads for clock and environmental data updates

## 3. UI Architecture & Components

### Ribbon Navigation
- Implement a `RibbonMenu` using `ttk.Notebook`.
- Tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`.
- Grouped buttons within tabs (e.g., "Navigation", "Settings", "Session").
- Buttons should use `bootstyle` such as `INFO`, `LIGHT`, `SECONDARY`, and `DANGER`.

### Dashboard (Home View)
- **Hero Section:** Centered 300x300 company logo with a 24pt bold "Contragest" label.
- **Statistics Bar:** Horizontal bar showing counts for Active, Expiring, and Expired contracts.
- **Environmental Awareness:** Integrated status indicators for local weather and temperature (updated via background scheduler).

### Contracts Management
- **Tableview:** Advanced `ttkbootstrap.tableview` with:
    - Flashing alerts for "Expired" (Red) and "Expiring Soon" (Orange) at an 800ms interval.
    - Inline action icons (✏️ Edit, 🗑️ Delete).
    - Multi-column sorting and global search.
- **Forms:** Modal dialogs for adding/editing contracts with validation.

### Professional Status Bar
- Bottom-aligned `ttk.Frame` (bootstyle `DARK`).
- Left: PC Hostname and Local IP.
- Center: Location and Weather data.
- Right: Live clock (📅 DD/MM/YYYY   🕒 HH:MM:SS) and Sizegrip.

## 4. Core Logic & Security
- **RBAC (Role-Based Access Control):** Conditional rendering of UI elements based on user roles (Admin, Staff).
- **Security Password:** Deletion requires a dynamic password calculated as `((day + month + (year % 100)) * 2) - 10`.
- **Audit Log (Mouchard):** Comprehensive tracking of all user actions (SESSION_START, CONTRACT_DELETE, etc.).
- **Auth System:** Secure login with OTP activation and a 60-second cooldown on resends.

## 5. Layout Logic
- Use a `ttk.Notebook` to manage main views but hide the tabs to create a "Ribbon-synced" feel where the Ribbon controls the visible frame.
- Support for RTL (Right-to-Left) layouts using a `core.layout` utility for `pack_start` and `pack_end` abstractions.
