# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

**Objective:** Design and implement a high-fidelity, professional graphical interface for a contract management system called 'Contragest'. The interface must blend a 'Cyberpunk' aesthetic (Neon, HUD, Tech Noir) with 'Corporate' functionality (Enterprise Gateway, Data-Dense Dashboard).

## 1. Aesthetic Direction & Visual Identity
- **Concept:** Cyberpunk-meets-Corporate / Tech Noir.
- **Theme:** OLED Dark Mode. Primary background must be true black (#020617) to optimize for OLED displays and reduce eye strain in professional environments.
- **Visual Style:** High contrast, sharp edges, and a "HUD" (Heads-Up Display) feel. Use neon accents sparingly to highlight critical data and interactions.
- **UX Mood:** Secure, authoritative, data-dense, and futuristic.

## 2. Design Tokens
### A. Color Palette (WCAG AAA Compliant)
- **Background:** `#020617` (Deep Midnight / OLED Black)
- **Surface/Cards:** `#1E293B` (Slate Dark)
- **Brand/Navy:** `#0F172A` (Corporate Navy)
- **Primary/Action:** `#22C55E` (Neon Green - Positive/Active)
- **Muted Text:** `#94A3B8` (Slate Muted)
- **Danger:** Flash (`#ff4444`) / Static (`#d9534f`)
- **Warning:** Flash (`#ffbb33`) / Static (`#f0ad4e`)

### B. Typography
- **Headers:** `Lexend` (Optimized for readability and modern feel).
- **Branding Accents:** `Playfair Display SC` (Serif small-caps for an elite corporate touch).
- **Body Text:** `Source Sans 3` (Highly legible for detailed contracts and records).
- **Data/Technical:** `Fira Code` (Monospace for IDs, timestamps, and system logs).

## 3. UI Architecture & Components
### A. Navigation: The Ribbon Menu
- **Implementation:** Use a Tabbed Ribbon Menu (e.g., `ttkbootstrap.Notebook` styled as 'Ribbon.TNotebook').
- **Styling:** Tabs should be bold (`Helvetica 10 Bold`), padded `[20, 5]`, with no visible borders between the ribbon and the content area to create an integrated "one-piece" look.
- **Sections:** Home, Contracts, HR, Tools, Reports.

### B. Dashboard: The Hero Section
- **Branding:** Centered 300x300 company logo (Vincci Hoteles 'V' style) on the home tab.
- **Stats Bar:** Top-aligned horizontal bar tracking: `Active | Expiring | Expired` contracts.

### C. Data Visualization: HUD Grids
- **Tables:** Data-dense layouts with minimal padding.
- **Status Alerts:** Implement a blinking animation (800ms cycle) for critical status rows (e.g., Expired contracts).
- **Interactions:** 200ms smooth transitions for hover states.

### D. Utility: The System Status Bar
- **Location:** Sticky bottom bar.
- **Data Points:**
  - **Left:** System Info (Hostname, Local IP).
  - **Center:** Environment Data (City Location, Current Temperature).
  - **Right:** Persistent Real-time Clock (`dd/mm/yyyy HH:MM:SS`).

## 4. Technical & Interaction Standards
- **Icons:** Strictly use SVG or Lucide-style line icons. **Do not use emojis** for UI elements.
- **Compliance:** Ensure all text/background combinations meet WCAG AAA contrast ratios.
- **Responsiveness:** Layout must support 'zoomed' (maximized) desktop states and handle resizing gracefully without horizontal scroll.
- **Feedback:** All clickable elements must have a `cursor: pointer` equivalent and clear visual feedback on click/hover.
