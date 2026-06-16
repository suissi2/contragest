# MASTER PROMPT: CONTRAGEST "CYBERPUNK-MEETS-CORPORATE" OLED INTERFACE

## 1. VISION & IDENTITY
Create a professional, high-fidelity enterprise dashboard named **Contragest**. The design identity is "Cyberpunk-meets-Corporate"—a fusion of high-tech "Tech Noir/HUD" aesthetics with the refined, trustworthy stability of an international corporate entity (inspired by the Vincci Hoteles aesthetic). The interface must be optimized for **OLED Dark Mode**, emphasizing deep blacks, high contrast, and space-efficient "Data-Dense" layouts.

## 2. DESIGN TOKENS (OLED PALETTE)
Strictly adhere to the following color specifications to ensure WCAG AAA compliance and OLED efficiency:
- **Background (Pure Dark):** `#020617` (Base container background)
- **Surface (Elevated):** `#1E293B` (Cards, sub-sections)
- **Corporate Navy:** `#0F172A` (Ribbon background, header areas)
- **Primary Accent (Matrix Green):** `#22C55E` (Buttons, active states, success indicators)
- **Muted Text/Secondary:** `#94A3B8` (Labels, captions)
- **High-Readability Text:** `#F8FAFC` (Primary content, body text)
- **Alerts (Static/Flash):**
  - Danger: `#ff4444` (Flash) / `#d9534f` (Static)
  - Warning: `#ffbb33` (Flash) / `#f0ad4e` (Static)

## 3. TYPOGRAPHY SYSTEM
- **Primary Headers:** Lexend (Modern, geometric, sans-serif)
- **Branding Accents:** Playfair Display SC (Elegant serif, used for logo text or section headers)
- **Body Text:** Source Sans 3 (Optimized for long-form readability)
- **Technical/Data:** Fira Code (Monospace for IDs, timestamps, and numerical data)

## 4. UI ARCHITECTURE: THE RIBBON MODEL
The interface utilizes a **Ribbon Menu** navigation system built on `ttkbootstrap` (Superhero base).
- **Ribbon Tabs:** Home, Contracts, HR, Tools, Reports.
- **Tab Styling:** `Ribbon.TNotebook.Tab` with Helvetica 10 Bold and `[20, 5]` padding.
- **Synchronized View:** The main content area is a `ttk.Notebook` where tabs are hidden (`style.layout('Main.TNotebook.Tab', [])`), synchronized perfectly with Ribbon selections to create a seamless "Single Page App" feel.
- **Dashboard Hero:**
  - Top Stats Bar: Tracking "Active", "Expiring", and "Expired" contracts.
  - Centered Branding: A large (300x300) Vincci Hoteles logo centered in the Hero section.
- **Status Bar (Bottom):** Persistent bar displaying:
  - System Info: PC Name and Local IP.
  - Environmental Data: Location and Weather (synced via BackgroundScheduler).
  - Clock: Persistent digital clock (`📅 dd/mm/yyyy   🕒 HH:MM:SS`).

## 5. TECHNICAL SPECIFICATIONS & INTERACTION
- **Framework:** Python + `ttkbootstrap` + `sqlalchemy`.
- **Transitions:** All state changes and UI transitions should be smooth (150-300ms).
- **Alert Animations:** Critical rows in tables (Expired/Expiring) must feature a smooth "flashing" effect (toggling between vivid and standard alert colors every 800ms).
- **Data Tables:** Use `Tableview` from `ttkbootstrap.widgets.tableview`. Data density is prioritized over whitespace.
- **Icons:** SVG/Lucide-style icons (Avoid emojis in production-grade components).

## 6. FORM & LAYOUT CONVENTIONS
- Main containers: `padding=20`.
- LabelFrames/Notebook tabs: `padding=10` or `15`.
- Form rows: `pady=5`.
- Labels: `width=12`.
- Action Buttons: `width=15`, `ipady=5`.
