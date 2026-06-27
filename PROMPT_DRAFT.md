# UI/UX Generation Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

## Objective
Design a professional, data-dense enterprise dashboard with a "Cyberpunk-meets-Corporate" aesthetic, optimized for OLED displays. The interface should balance high-tech HUD elements with clean, structured corporate utility.

## 1. Visual Identity & Aesthetic
- **Style:** Tech-Noir / Minimalist Cyberpunk.
- **Atmosphere:** High contrast, space-efficient, professional, and futuristic.
- **Key Elements:** HUD-style grids, glassmorphism (subtle), blinking status alerts for critical data, and smooth 200ms transitions.

## 2. OLED Color Palette
- **Background:** `#020617` (Deepest Black/Midnight)
- **Surface/Cards:** `#1E293B` (Slate Navy)
- **Corporate Accent:** `#0F172A` (Professional Navy)
- **Primary/Success:** `#22C55E` (Vivid Green)
- **Danger/Alert:** `#ff4444` (Neon Red) static to `#d9534f` (Muted Red) flash
- **Warning:** `#ffbb33` (Amber) static to `#f0ad4e` (Muted Gold) flash
- **Muted Text:** `#94A3B8`

## 3. Typography
- **Primary Headers:** `Lexend` (Modern, geometric)
- **Branding/Accents:** `Playfair Display SC` (Elegant, serif)
- **Body Text:** `Source Sans 3` (High readability)
- **Technical/HUD Data:** `Fira Code` (Monospace, precise)

## 4. UI Architecture & Components
- **Navigation (Ribbon Menu):** A top-mounted Ribbon menu utilizing a synchronized tab system (like `Ribbon.TNotebook`). Tabs: Home, Contracts, HR, Tools, Reports.
- **Hero Section:** A centered branding centerpiece (300x300 logo) with a top statistics bar tracking "Active", "Expiring", and "Expired" statuses.
- **Data Tables:** High-density tables with color-coded status rows (Success, Warning, Danger) and interactive action icons (SVG/Lucide style, no emojis).
- **HUD Status Bar:** A triple-sectioned persistent bottom bar:
    1.  **System Info:** IP Address and Hostname.
    2.  **Environment:** Location and Weather (Temperature).
    3.  **Real-time Clock:** Persistent digital clock.

## 5. Technical Specifications
- **Accessibility:** WCAG AAA compliance for OLED dark theme.
- **Interactions:** All clickable elements must have `cursor-pointer`.
- **Motion:** 200ms smooth transitions for hover states and tab switching.
- **Icons:** Strictly SVG-based (Lucide/Heroicons). No emojis in the UI.
