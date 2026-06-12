# Contragest Master Prompt: Cyberpunk-meets-Corporate Interface

## 1. Core Identity & Vision
The **Contragest** interface is a high-fidelity "Cyberpunk-meets-Corporate" dashboard. It synthesizes the technical edge of "Tech Noir" (High contrast, neon accents, HUD-style elements) with the reliability of an enterprise management system. The design is optimized for **OLED Dark Mode**, ensuring deep blacks and reduced eye strain for data-dense professional environments.

## 2. Design Tokens
### OLED Color Palette
- **Background:** `#020617` (True OLED Black)
- **Surface/Card:** `#1E293B` (Elevated dark blue-grey)
- **Corporate Accent:** `#0F172A` (Professional Navy)
- **Primary/Action:** `#22C55E` (Vivid Neon Green)
- **Secondary/Text:** `#94A3B8` (Muted Slate)
- **Danger:** `#ff4444` (Vivid Red)
- **Warning:** `#ffbb33` (Vivid Amber)

### Typography Hierarchy
- **Primary Heading:** `Lexend` (Geometric, high-clarity)
- **Branding/Accent:** `Playfair Display SC` (Serif elegance for logos/headers)
- **Body/Standard:** `Source Sans 3` (Highly readable enterprise sans-serif)
- **Code/Monospace:** `Fira Code` (Technical data and logs)

## 3. UI Architecture
### The Ribbon Navigation
The top-level navigation follows a **Ribbon Menu** pattern (standard in enterprise tools like Microsoft Office but styled with OLED tokens).
- **Tabs:** Home, HR, Tools, Reports.
- **Styling:** `Ribbon.TNotebook` with Helvetica 10 Bold font and `[20, 5]` padding.

### Dashboard Hero
The "Home" tab features a high-impact **Hero Section**:
- **Logo:** Centered 300x300 company logo (Ref: Vincci Hoteles).
- **Status Bar:** A top-aligned statistics bar displaying "Active", "Expiring", and "Expired" contract counts.

### Bottom Status Bar (The System Feed)
A persistent footer for real-time situational awareness:
- **PC Info:** Local hostname and IP.
- **Environment:** Real-time Location and Temperature.
- **Clock:** Persistent clock in `DD/MM/YYYY - HH:MM:SS` format.

## 4. Visual Standards
- **Contrast:** WCAG AAA compliance for OLED dark mode.
- **Transitions:** Smooth 150-300ms animations for all interactions.
- **Alerts:** Critical expiration alerts must use a "Glow/Flash" effect, alternating between vivid and muted states to grab attention without being distracting.
- **Iconography:** Use SVG/Lucide-style icons (Avoid emojis in production-grade layouts).

## 5. Security Context
Include a secure deletion challenge based on the current date: `((day + month + year_short) * 2) - 10`.
