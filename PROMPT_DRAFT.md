# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

Act as a Senior Python UI/UX Engineer. Your task is to implement a professional, data-dense Enterprise Resource Planning (ERP) interface using **Python** and **ttkbootstrap**. The design language is "Cyberpunk-meets-Corporate"—a fusion of sci-fi HUD aesthetics with high-authority corporate structure.

### 1. Visual Identity & Design Tokens (OLED Dark Mode)
The interface MUST achieve WCAG AAA compliance for deep black environments.
- **Background:** `#020617` (True Black/Navy)
- **Surface:** `#1E293B` (Elevated Panels)
- **Corporate Navy:** `#0F172A` (Header/Navigation)
- **Primary Accent:** `#22C55E` (Tactical Green for success/actions)
- **Danger (Blink):** Static `#d9534f` / Flash `#ff4444` (800ms cycle)
- **Warning (Blink):** Static `#f0ad4e` / Flash `#ffbb33`
- **Typography:**
    - **Headers:** `Lexend` (Clean, geometric)
    - **Branding:** `Playfair Display SC` (Serif authority)
    - **Body:** `Source Sans 3` (High readability)
    - **Monospace:** `Fira Code` (For data/IDs)

### 2. Architectural Components
- **Ribbon Navigation:** Implement a custom `ttk.Notebook` styled as a ribbon menu. Tabs (Home, Contracts, HR, Tools, Reports) should have large padding `[20, 5]` and `Helvetica 10 bold`. Hide standard notebook tab markers to create a seamless toolbar integration.
- **Hero Dashboard:** A centered `300x300` logo centerpiece (Minimalist Serif 'V') with a `24pt Bold` title "Contragest" and a `14pt` professional subtitle.
- **HUD Data Grids:** Use `ttkbootstrap.widgets.tableview`. Implement high-contrast row tagging:
    - **Danger:** Expired items (Red background, white text)
    - **Warning:** Expiring soon (Amber background, white text)
- **Bottom Status Bar:** A persistent `inverse-dark` bootstyle bar displaying:
    - System Info: PC Name and Local IP.
    - Environment: Location and Weather (mocked or API-fed).
    - Precision Clock: `📅 DD/MM/YYYY   🕒 HH:MM:SS`.

### 3. Functional Interaction Specs
- **Transitions:** All hover states and UI changes must utilize smooth `200ms` transitions.
- **Icons:** Use SVG or Lucide-style iconography. **STRICTLY PROHIBITED:** Standard emojis (🎨, 🚀).
- **Security:** Implement a secure deletion password based on the date formula: `((day + month + year_short) * 2) - 10`.
- **Alerts:** Critical data rows must blink between danger/warning color pairs on an 800ms cycle.

### 4. Implementation Requirements
- **Theme:** Use the `superhero` ttkbootstrap theme as the foundational layer.
- **Layout:** Use `padding=20` for main containers and `padding=10/15` for inner frames.
- **Standards:** Ensure the code is modular, following a features-based directory structure (core, features, logic, lib).

Generate the Python code for the `MainWindow` and `RibbonMenu` components that embody this high-fidelity technical vision.
