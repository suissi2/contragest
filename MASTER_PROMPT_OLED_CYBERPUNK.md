# Contragest Master Prompt: "Cyberpunk-meets-Corporate" Interface

## Role & Goal
You are a seasoned **Python Developer** and **UI/UX Architect** specializing in enterprise data systems. Your goal is to recreate the **Contragest** interface—a high-fidelity management dashboard that blends a professional "Corporate" layout with a "Cyberpunk/HUD" aesthetic.

---

## 1. Design System & Aesthetic (OLED Dark Mode)
Implement a high-contrast, space-efficient design optimized for OLED displays.

*   **Theme Base:** `ttkbootstrap` using the **"superhero"** theme.
*   **Color Palette (Hex Tokens):**
    *   **Main Background:** `#020617` (Deepest OLED Black)
    *   **Surface/Container:** `#1E293B` (Steel Blue Gray)
    *   **Primary Accent:** `#22C55E` (Cyber Green)
    *   **Secondary Text:** `#94A3B8` (Muted Gray)
    *   **Urgency Flash (Danger):** `#ff4444` (Vivid Red) vs `#d9534f` (Static)
    *   **Urgency Flash (Warning):** `#ffbb33` (Vivid Gold) vs `#f0ad4e` (Static)
*   **Typography:**
    *   **Headers:** *Lexend* (for readability)
    *   **Branding Accents:** *Playfair Display SC* (Serif elegance)
    *   **Body/Data:** *Source Sans 3*
    *   **Technical/Monospaced:** *Fira Code*
*   **Visual Style:** Glassmorphism, Neon borders, WCAG AAA contrast compliance, and HUD-style data density.

---

## 2. Structural Architecture (Ribbon & Notebook)
The application must follow a modular **Single-Page Application (SPA)** feel using a custom Ribbon menu.

*   **Ribbon Menu (Top):**
    *   Use a `ttk.Notebook` styled as `Ribbon.TNotebook`.
    *   **Tabs:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
    *   **Styling:** Padding `[20, 5]`, Bold Font (Helvetica 10).
    *   **Logic:** Clicking a Ribbon tab switches the visible frame in the central `Main Notebook`.
*   **Main Content Area:**
    *   A central `ttk.Notebook` with **hidden tabs**.
    *   Content should focus on "Hero" layouts for Home and "Data-Dense Tables" for management.
*   **Status Bar (Bottom):**
    *   A `DARK` bootstyle frame divided into three segments:
        1.  **System:** 💻 [Hostname] ([Local IP])
        2.  **Environment:** 🌍 [City] | 🌡️ [Temp] (Real-time fetching via background thread)
        3.  **Clock:** 📅 DD/MM/YYYY | 🕒 HH:MM:SS (1-second update cycle)

---

## 3. Interaction & Logic Patterns
*   **Dynamic Table Urgency:** Implement an `animate_flash` loop (800ms) that alternates row background colors for "Expired" or "Expiring" records in the `Tableview`.
*   **Modular Callbacks:** All Ribbon buttons must trigger specific functions through a `callbacks` dictionary mapping (e.g., `callbacks['logout']`, `callbacks['refresh']`).
*   **Secure Actions:** For destructive actions (Deletion), require a calculated password based on the current date: `((day + month + year_short) * 2) - 10`.
*   **Responsive Layout:** Use `pack_start` and `pack_end` abstractions to support both LTR and potential RTL language configurations.

---

## 4. Technical Constraints (Python)
*   **Library:** `ttkbootstrap` (Tkinter-based).
*   **Asset Management:** Use `PIL.Image` and `ImageTk` with an `image_cache` for efficient logo rendering (e.g., 300x300 Hero logo vs 40x40 Ribbon logo).
*   **Concurrency:** Use a `BackgroundScheduler` for fetching weather/PC info to prevent UI freezing.
*   **Security:** Role-Based Access Control (RBAC) must check permissions before rendering specific Ribbon tabs or buttons.

---

**PROMPT:** "Generate a modular Python GUI using `ttkbootstrap` that implements the Contragest architecture. Focus on the `MainWindow` class with a `RibbonMenu` top-navigation and a `Tableview` featuring the urgency flashing effect. Adhere strictly to the OLED Dark Mode palette and typography specified."
