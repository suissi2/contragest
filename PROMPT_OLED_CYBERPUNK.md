# Master Prompt: Contragest "Cyberpunk-meets-Corporate" OLED Interface

## Visual Identity Concept
**Identity:** A fusion of high-integrity corporate enterprise software and a high-tech "Tech Noir" terminal. Designed for OLED displays with maximum contrast, glassmorphic depth, and functional HUD elements.

## Design Tokens (OLED Palette)
- **Background (True/Deep Black):** `#020617`
- **Surface (Glassmorphic):** `#1E293B` (with 20-40% opacity where supported)
- **Corporate Navy (Ribbon/UI Accents):** `#0F172A`
- **Primary Accent (Neon Green):** `#22C55E` (Active/Success states)
- **Alert - Danger (Neon Red):** `#ff4444` (Expired/Critical)
- **Alert - Warning (Neon Amber):** `#ffbb33` (Expiring/Pending)
- **Text Primary:** `#F8FAFC` (High contrast white)
- **Text Muted:** `#94A3B8` (Secondary information)

## Typography System
- **Branding/Headers:** *Lexend* (Modern, professional, geometric)
- **Body/System:** *Source Sans 3* (Optimized for readability)
- **Technical/Data:** *Fira Code* (Monospace for terminal-feel metrics)

## UI Architecture & Components

### 1. Ribbon Navigation (Top)
- **Style:** `Ribbon.TNotebook` with custom Helvetica 10 Bold font.
- **Tabs:** Home (🏠), Contracts (📑), HR (👔), Tools (🛠️), Reports (📊).
- **Behavior:** Dynamic buttons with neon outline-warning or primary bootstyles.

### 2. Dashboard Hero (Home View)
- **Logo:** Centered `300x300` company logo with a soft neon outer glow.
- **Statistics Bar:** Top-aligned `SECONDARY` bootstyle frame tracking "Active", "Expiring", and "Expired" counts.
- **HUD Elements:** Subtle scanline overlays and 150-300ms smooth transitions on hover.

### 3. Management Workspace (Data Grids)
- **Component:** `ttkbootstrap.widgets.tableview`.
- **Aesthetic:** Dark-themed rows with custom flashing effects.
- **Critical Alerts:** Alternating flash between vivid red (`#ff4444`) and static maroon (`#d9534f`) at 800ms intervals for expired items.

### 4. System Status Bar (Bottom)
- **Style:** `DARK` bootstyle with persistent system telemetry.
- **Left:** PC Info (Host/IP) and Session User.
- **Center:** Environment HUD (Location 🌍 + Temperature 🌡️).
- **Right:** Persistent Clock (📅 DD/MM/YYYY   🕒 HH:MM:SS).

## Technical Implementation (Python/ttkbootstrap)
- **Base Theme:** `superhero` (customized via style overrides).
- **Logic:** Background `Scheduler` for real-time telemetry; `AlertManager` for status tracking.
- **Layout:** Space-efficient OLED layout with `pack_start` and `pack_end` utilities.
