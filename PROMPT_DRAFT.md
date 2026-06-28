# Contragest Master Prompt: Cyberpunk-Corporate OLED Interface

## Visual Identity & Concept
**Concept:** "Cyberpunk-meets-Corporate" — A high-fidelity, professional administrative interface optimized for OLED displays. It combines the sleek, data-dense aesthetic of a sci-fi HUD (Heads-Up Display) with the structured authority of an enterprise ERP.

## Design Tokens (The "Contragest" Palette)
- **Background:** Deep OLED Black (`#020617`)
- **Surface/Cards:** Dark Slate Navy (`#1E293B` or `#0F172A`)
- **Primary Accent:** Cyber Emerald Green (`#22C55E`)
- **Muted Text:** Cool Slate (`#94A3B8`)
- **Danger Alert:** Flash (`#ff4444`) / Static (`#d9534f`)
- **Warning Alert:** Flash (`#ffbb33`) / Static (`#f0ad4e`)

## Typography System
- **Headers:** Lexend (Modern, geometric, highly legible)
- **Branding:** Playfair Display SC (Serif elegance for logos and accents)
- **Body Text:** Source Sans 3 (Professional, clean data presentation)
- **Data/Monospace:** Fira Code (Technical HUD elements and system logs)

## UI Architecture & Components
1. **Ribbon Navigation:**
   - Microsoft Office-style ribbon tabs: [Home], [Contracts], [HR], [Tools], [Reports].
   - Styling: Helvetica 10 Bold, high-contrast active states, synchronized with main workspace.
2. **Hero Dashboard:**
   - Centered branding: 300x300 minimalist serif 'V' logo (Vincci Hoteles inspired).
   - Dynamic Stats Bar: Real-time counters for [Active], [Expiring], and [Expired] contracts.
3. **HUD Status Bar (Fixed Bottom):**
   - Left: System telemetry (Local IP, Hostname).
   - Center: Environmental data (Location and weather sync).
   - Right: Persistent digital clock and window sizing grip.
4. **Data Grid (Tableview):**
   - High-density layouts with alternating row highlights.
   - Status Column: Critical alerts featuring 800ms blinking animations (Danger/Warning).
   - WCAG AAA contrast compliance for all text elements.

## Execution Directives
- **No Emojis:** Strictly use SVG/Lucide-style icons.
- **Transitions:** Universal 200ms ease-in-out for all hover and state changes.
- **Atmosphere:** Tech-noir, futuristic, dystopian but disciplined, high information density, space-efficient.
