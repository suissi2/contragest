# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

## Visual Identity & Design System
Replicate a high-fidelity enterprise dashboard concept characterized by a **"Cyberpunk-meets-Corporate"** aesthetic, optimized for OLED displays.

### 1. Color Palette (OLED Dark Mode)
- **Background (Deep Space):** `#020617` (True Black/Dark Navy)
- **Surface (Steel):** `#1E293B`
- **Corporate Accent:** `#0F172A` (Navy depth)
- **Primary Action (Neon):** `#22C55E` (Vivid Green)
- **Alert - Critical (Flash):** `#ff4444` / `#d9534f`
- **Alert - Warning (Flash):** `#ffbb33` / `#f0ad4e`
- **Text - Primary:** `#F8FAFC`
- **Text - Muted:** `#94A3B8`

### 2. Typography
- **Headers:** `Lexend` (Clean, geometric)
- **Branding Accents:** `Playfair Display SC` (Serif elegance)
- **Body/Readability:** `Source Sans 3`
- **Data/Monospace:** `Fira Code`

---

## Technical Architecture (Python / ttkbootstrap)

### 1. Framework & Theme
- **Base:** Python 3.x with `ttkbootstrap`.
- **Theme:** "Superhero" (customized for OLED contrast).
- **Global Styles:** Implement custom `Ribbon.TNotebook` and `Ribbon.TNotebook.Tab` styles with `font=('Helvetica', 10, 'bold')` and `padding=[20, 5]`.

### 2. UI Layout Hierarchy
#### A. Ribbon Menu (Navigation)
- A top-anchored `ttk.Notebook` serving as the primary navigation.
- Group buttons within `ttk.LabelFrame` containers (e.g., "Navigation", "Administrative", "Reports").
- Use consistent `bootstyle` for buttons (INFO, LIGHT, SECONDARY, DANGER).

#### B. Central Workspace (Notebook Sync)
- A central `ttk.Notebook` with hidden tabs (`style.layout('Main.TNotebook.Tab', [])`).
- Programmatically sync the central view with Ribbon Tab selections (Home, Contracts, HR, Tools, Reports).

#### C. Dashboard Hero (Home View)
- **Top Stats Bar:** Horizontal bar tracking "Active", "Expiring Soon", and "Expired" metrics.
- **Hero Center:** Large centered company logo (300x300) with bold branding text ("Contragest") and subtitle.

#### D. Data Density (Tableview)
- Use `ttkbootstrap.tableview.Tableview`.
- Implement dynamic row tagging:
  - `success`: Background `#5cb85c`
  - `warning`: Background `#f0ad4e` (with periodic flashing to `#ffbb33`)
  - `danger`: Background `#d9534f` (with periodic flashing to `#ff4444`)

#### E. Systemic Status Bar
- A multi-pane footer containing:
  - **PC Info:** Local hostname and IP.
  - **Environment:** Dynamic Location and Weather (synced via background scheduler).
  - **Clock:** Real-time persistent `H:M:S` clock.

---

## Core Functional Logic
- **RBAC Integration:** UI components and Ribbon tabs must toggle visibility based on user role (Admin vs. User).
- **Background Tasks:** Utilize a non-blocking `BackgroundScheduler` for fetching weather/system data and triggering automated contract alerts.
- **Visual Alerting:** Implement an `animate_flash` loop (approx. 800ms) to toggle contrast on critical rows.
- **Secure Deletion:** Access to deletion/recovery tools requires a calculated daily password: `((day + month + year_short) * 2) - 10`.

---

## Prompt Summary for AI Implementation
"Generate a Python GUI application using `ttkbootstrap` and the 'superhero' theme. The interface must follow a 'Cyberpunk-meets-Corporate' design language with a deep OLED palette (#020617, #22C55E). The layout should feature a custom Ribbon navigation at the top, a hidden-tab central workspace, and a high-fidelity status bar with system info and a real-time clock. Implement a Dashboard Hero section with a 300x300 logo and a metrics bar. Ensure data is presented in a Tableview with color-coded, flashing alerts for critical statuses."
