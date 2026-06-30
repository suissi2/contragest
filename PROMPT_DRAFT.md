# CONTRAGEST MASTER PROMPT: Cyberpunk-meets-Corporate OLED Interface

## 1. IDENTITY & CONCEPT
- **Identity:** "Cyberpunk-meets-Corporate" — A fusion of sci-fi HUD data-density with enterprise ERP structured authority.
- **Atmosphere:** High-contrast, space-efficient, "Tech Noir" aesthetic optimized for OLED displays.
- **Compliance:** WCAG AAA compliance for high-contrast dark themes.

## 2. DESIGN TOKENS (OLED DARK MODE)
| Element | Hex Code | Description |
| :--- | :--- | :--- |
| **Background** | `#020617` | True Black/Deep Slate for OLED power saving. |
| **Surface** | `#1E293B` | Slightly elevated cards/containers. |
| **Corporate Navy** | `#0F172A` | Primary branding and header backgrounds. |
| **Primary Accent** | `#22C55E` | "Success" Green for positive indicators and CTAs. |
| **Secondary Text** | `#94A3B8` | Muted slate for metadata and labels. |
| **Danger (Static)** | `#d9534f` | Standard error state. |
| **Danger (Flash)** | `#ff4444` | High-visibility alert state. |
| **Warning (Static)** | `#f0ad4e` | Standard warning state. |
| **Warning (Flash)** | `#ffbb33` | High-visibility warning state. |

## 3. TYPOGRAPHY
- **Primary Headers:** `Lexend` (Bold, professional, readable).
- **Branding Accents:** `Playfair Display SC` (Serif elegance for corporate identity).
- **Body Text:** `Source Sans 3` (High readability for data-dense tables).
- **Technical/Data:** `Fira Code` (Monospace for IDs, timestamps, and system logs).

## 4. ARCHITECTURAL PATTERNS (Python / ttkbootstrap)
- **Theme Base:** `ttkbootstrap` 'superhero' theme (customized for OLED).
- **Ribbon Navigation:**
    - Custom `Ribbon.TNotebook` style.
    - Hides standard tabs (`style.layout('Main.TNotebook.Tab', [])`).
    - Tabs for: Home, Contracts, HR, Tools, Reports.
    - Font: Helvetica 10 Bold, Padding: [20, 5].
- **HUD Grids:**
    - Critical data alerts with 800ms blinking cycles between static/flash color pairs.
    - Data density inspired by terminal/dashboard layouts.
- **Status Bar:**
    - Persistent bottom bar (Dark style).
    - Left: Dynamic system info (IP, Hostname).
    - Center: Environment data (Location, Weather).
    - Right: Persistent Clock (DD/MM/YYYY HH:MM:SS).

## 5. UI/UX GUIDELINES
- **Transitions:** Smooth 200ms transitions for all hover states.
- **Icons:** Strictly SVG/Lucide-style icons. **NO EMOJIS** in final UI components.
- **Buttons:** Standardized `width=15`, `ipady=5` for primary actions.
- **Forms:** `padding=20` for main containers, `pady=5` for rows, labels `width=12`.
- **Hero Section:** Centered 300x300 company logo, 24pt bold title, 14pt subtitle.

## 6. TECHNICAL STACK
- **Language:** Python 3.x
- **GUI Framework:** `tkinter` + `ttkbootstrap`
- **Logic:** `SQLAlchemy` (DB), `Pillow` (Images), `fpdf2` (Reports), `requests` (API).
- **Automation:** Background scheduling for alerts and environment sync.
