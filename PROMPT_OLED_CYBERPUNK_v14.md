# Master Prompt: Contragest 'Cyberpunk-meets-Corporate' OLED Interface

## Vision Statement
Create a high-fidelity, enterprise-grade Python graphical interface using `ttkbootstrap` that embodies a **'Cyberpunk-meets-Corporate'** identity. The design must prioritize space-efficient OLED layouts, high contrast for readability (WCAG AAA compliant), and a professional yet futuristic 'Tech Noir' aesthetic.

## 1. Visual Identity & Design Tokens

### Color Palette (OLED Dark Mode)
*   **Deep Background**: `#020617` (The void, deepest navy)
*   **Surface/Card**: `#1E293B` (Muted slate for secondary containers)
*   **Corporate Navy**: `#0F172A` (Primary container background)
*   **Primary Accent**: `#22C55E` (Vibrant Emerald/Matrix Green)
*   **Secondary Text**: `#94A3B8` (Muted gray-blue for metadata)
*   **Static Danger**: `#d9534f` | **Flash Danger**: `#ff4444` (Expired/Critical)
*   **Static Warning**: `#f0ad4e` | **Flash Warning**: `#ffbb33` (Expiring/Caution)

### Typography Hierarchy
*   **Primary Headers**: Lexend (Modern, geometric, high legibility)
*   **Branding Accents**: Playfair Display SC (Sophisticated, serif contrast)
*   **Body Text**: Source Sans 3 (High-readability sans-serif)
*   **Data/Technical**: Fira Code (Monospaced with ligatures for HUD feel)

## 2. UI Architectural Specifications

### A. Ribbon Menu (Navigation Hub)
*   **Structure**: A `ttk.Notebook` styled as a Ribbon, with tabs for **Home**, **Contracts**, **HR**, **Tools**, and **Reports**.
*   **Styling**: Use `Ribbon.TNotebook` and `Ribbon.TNotebook.Tab` styles. Font: Helvetica 10 Bold. Padding: `[20, 5]`.
*   **Buttons**: Use various bootstyles (INFO, LIGHT, SECONDARY, DANGER) with standard padding of 10.

### B. Dashboard Hero Section
*   **Logo**: Centered 300x300 company logo.
*   **Branding**: "Contragest" in Lexend 24 Bold.
*   **Stats Bar**: Top horizontal bar tracking contract counts: `Active | Expiring Soon | Expired`.

### C. Dynamic Status Bar (System HUD)
*   **PC Info**: Display `💻 [Hostname] ([Local IP])`.
*   **Environment**: Real-time `🌍 [Location] [Temperature]` data.
*   **Clock**: Persistent `📅 DD/MM/YYYY   🕒 HH:MM:SS` with 1s updates.
*   **Theme**: `inverse-dark` bootstyle for a clean HUD look.

### D. Data Presentation (Tableview)
*   **Interactivity**: Color-coded rows based on status (Success, Warning, Danger).
*   **Visual Alerts**: Implement a smooth flashing animation (800ms interval) for critical/expiring rows to draw immediate attention.

## 3. Technical Execution Requirements
*   **Base Theme**: `ttkbootstrap` "superhero" theme, customized for OLED black (#020617).
*   **Responsiveness**: Default to `zoomed` state; utilize `pack` and `grid` with `expand=YES` for fluid layouts.
*   **Performance**: Optimize asset loading via caching (e.g., `image_cache` for logos).
*   **Feedback**: Smooth transitions (150-300ms) and clear visual states for all interactive elements.
