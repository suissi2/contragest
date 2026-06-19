# MASTER PROMPT: CONTRAGEST "CYBERPUNK-MEETS-CORPORATE" OLED INTERFACE

## Concept: Corporate Noir / High-Fidelity Enterprise Dashboard
Create a high-fidelity Python graphical interface using `ttkbootstrap` that merges a **Cyberpunk/Tech-Noir** aesthetic with a **clean, high-integrity Corporate** identity. The design must be optimized for OLED displays, prioritizing deep blacks, high-contrast neon accents, and space-efficient "Data-Dense" layouts.

---

### 1. Visual Identity & Branding (Inspired by Vincci Hoteles)
- **Branding Accents:** Utilize minimalist, elegant Serif typography (Playfair Display SC) for branding elements.
- **Hero Logo:** Centered 300x300 Vincci-style logo (stylized 'V') in the dashboard hero section.
- **Identity:** The interface should feel like a "Security Hub" or "Enterprise Gateway"—stable and professional, yet futuristic.

### 2. Design Tokens (OLED Dark Mode)
- **Background:** `#020617` (True OLED Black)
- **Surface/Cards:** `#1E293B` (Deep Navy Slate)
- **Primary Accent:** `#22C55E` (Cyberpunk Green / Matrix-inspired)
- **Text (Primary):** `#F8FAFC` (Clean White)
- **Text (Muted):** `#94A3B8` (Slate Grey)
- **Alerts (Flash/Static):**
  - Danger: `#ff4444` (Flash) / `#d9534f` (Static)
  - Warning: `#ffbb33` (Flash) / `#f0ad4e` (Static)

### 3. Typography Hierarchy
- **Primary Headers:** `Lexend` (Modern, geometric, high readability).
- **Branding/Accents:** `Playfair Display SC` (Corporate elegance).
- **Body Text:** `Source Sans 3` (Optimized for data-dense tables).
- **Technical/Data:** `Fira Code` (Monospaced for ID codes and system info).

### 4. Technical Architecture (Python / ttkbootstrap)
- **Base Theme:** Use `superhero` as the foundation, customized for OLED black.
- **Ribbon Menu Navigation:**
  - Implementation: `ttk.Notebook` with `tabposition='n'`.
  - Style: `Ribbon.TNotebook` with hidden tabs (`style.layout('Main.TNotebook.Tab', [])`).
  - Tabs: Home, HR, Tools, Reports.
- **Dashboard Hero:**
  - Layout: Top Stats Bar + Centered Hero Content.
  - Stats: Tracking Active, Expiring, and Expired contracts.
- **Integrated Status Bar:**
  - Sections: PC Info (Name/IP), Session User, Environmental Data (Location/Weather), and a Persistent Clock.
  - Transitions: 150-300ms smooth state changes.

### 5. UI/UX Guidelines
- **WCAG AAA Compliance:** Ensure maximum contrast for the OLED dark theme.
- **Icons:** Use SVG/Lucide-style icons (avoid emojis).
- **Interactions:** Hover states must be clear (color shifts, no layout shifts) with `cursor-pointer` feedback.
- **Form Layouts:** `padding=20`, `pady=5`, fixed label widths (`width=12`) for alignment.

---

## Technical Snippet (Styling Foundation)
```python
style = ttk.Style()
style.configure('Main.TNotebook', tabposition='n', padding=0)
style.layout('Main.TNotebook.Tab', []) # Effectively hide tabs for Ribbon-sync
style.configure('Ribbon.TNotebook.Tab', padding=[20, 5], font=('Lexend', 10, 'bold'))
# Flash animation logic (800ms intervals)
# Deletion Security: ((day + month + year_short) * 2) - 10
```
