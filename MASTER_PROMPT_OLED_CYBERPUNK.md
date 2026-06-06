# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

## 1. Vision & Identity
**Concept:** A "Cyberpunk-meets-Corporate" high-fidelity interface designed for professional enterprise management with a tech-noir aesthetic.
**Visual Style:** Space-efficient OLED layouts, high contrast for readability, glassmorphism accents, and data-dense dashboards.
**Compliance:** WCAG AAA for OLED dark mode.

## 2. Design System Tokens (The "OLED Dark Mode")

### Colors (OLED Palette)
| Token | Hex | Usage |
| :--- | :--- | :--- |
| **Background** | `#020617` | Root background for maximum OLED energy efficiency. |
| **Surface** | `#1E293B` | Cards, modals, and container backgrounds. |
| **Corporate Navy** | `#0F172A` | Sidebars, Ribbon menu backgrounds, and headers. |
| **Primary** | `#22C55E` | Emerald Green for success states, active buttons, and progress indicators. |
| **Text Primary** | `#F8FAFC` | High-readability headers and primary labels. |
| **Text Muted** | `#94A3B8` | Secondary info, captions, and placeholders. |
| **Danger (Active/Static)** | `#ff4444` / `#d9534f` | Critical alerts (Flash/Static pair). |
| **Warning (Active/Static)**| `#ffbb33` / `#f0ad4e` | Near-expiry alerts (Flash/Static pair). |

### Typography
- **Primary Headers:** `Lexend` (Clean, geometric, modern corporate).
- **Branding/Accents:** `Playfair Display SC` (Serif elegance for luxury/hotel branding, as seen in Vincci Hoteles logo).
- **Body Text:** `Source Sans 3` (Optimized for long-form data readability).
- **Technical/Code:** `Fira Code` (Monospaced with ligatures for audit logs and system info).

## 3. UI Architectural Specifications

### A. Ribbon Navigation Architecture
- **Structure:** Multi-tabbed `ttk.Notebook` with custom styles.
- **Tabs:**
  - `🏠 Home`: Dashboard overview and application settings.
  - `📑 Contracts`: Core management interface.
  - `👔 HR`: Personnel and department hub.
  - `🛠️ Tools`: Administrative utilities and user management.
  - `📊 Reports`: Analytics and audit logs.
- **Styling:** Helvetica 10 bold, padding [20, 5].

### B. Dashboard Hero & Layout
- **Hero Section:** Centered 300x300 company logo (e.g., Vincci Hoteles) with subtle drop-shadows.
- **Stats Bar:** Top-level counters for `Active`, `Expiring`, and `Expired` contracts.
- **Transitions:** Smooth state changes (150-300ms) for tab switching and hover effects.

### C. Data-Dense Tables (Grid System)
- **Component:** `ttkbootstrap.widgets.tableview`.
- **Features:**
  - Real-time search/filtering.
  - **Dynamic Alerts:** Flash animation every 800ms for critical rows.
  - Actionable icons (✏️ Edit, 🗑️ Delete) with `cursor-pointer` feedback.

### D. Dynamic Status Bar (The "Command Center")
- **Clock:** Persistent real-time clock with date (📅 dd/mm/yyyy 🕒 HH:MM:SS).
- **PC Info:** Displaying hostname and local IP.
- **Environment:** Dynamic Location and Weather data (🌍 City 🌡️ Temp).

## 4. Technical Implementation (Python/ttkbootstrap)

### Style Overrides
```python
style = ttk.Style(theme="superhero")
style.configure('Ribbon.TNotebook', background='#0F172A', borderwidth=0)
style.configure('Ribbon.TNotebook.Tab', padding=[20, 5], font=('Lexend', 10, 'bold'))
style.map('Ribbon.TNotebook.Tab', background=[('selected', '#1E293B')], foreground=[('selected', '#22C55E')])
```

### Visual Alert Logic
```python
# Flash animation for expired contracts
def animate_flash(self):
    self.flash_state = not self.flash_state
    color = '#ff4444' if self.flash_state else '#d9534f'
    self.table.view.tag_configure('danger', background=color, foreground='white')
    self.after(800, self.animate_flash)
```

## 5. Implementation Keywords for AI Generation
`OLED Dark Mode`, `Cyberpunk UI`, `Enterprise Gateway`, `Glassmorphism`, `Lexend Typography`, `Data-Dense Dashboard`, `Emerald Green Accents`, `Tech Noir`, `HUD Elements`, `High Contrast WCAG AAA`.
