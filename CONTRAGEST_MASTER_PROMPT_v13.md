# CONTRAGEST MASTER PROMPT v13
## Cyberpunk-meets-Corporate OLED Interface Specification

**Objective:**
Reconstruct or extend the "Contragest" enterprise interface based on the "Cyberpunk-meets-Corporate" identity. The result must be a high-contrast, space-efficient OLED layout that maintains professional integrity while incorporating tech-noir/HUD aesthetics.

---

### 1. Identity & Design Tokens (OLED Dark Mode)
The interface is defined by deep blacks, high-contrast surfaces, and vibrant corporate accents.

*   **Background:** `#020617` (OLED Deep Navy/Black)
*   **Surface/Cards:** `#1E293B` (Slate Dark)
*   **Corporate Navy:** `#0F172A` (Rich Background Depth)
*   **Primary/Action:** `#22C55E` (Matrix/Emerald Green)
*   **Secondary/Muted:** `#94A3B8` (Cool Grey for metadata)
*   **Alerts (Flash/Static Pairs):**
    *   *Danger:* `#ff4444` (Active) / `#d9534f` (Static)
    *   *Warning:* `#ffbb33` (Active) / `#f0ad4e` (Static)

---

### 2. Typography (The Four Pillars)
Typography must balance luxury branding with technical data density.

*   **Brand & Accents:** *Playfair Display SC* (Serif, for luxury prestige and corporate branding).
*   **Primary Headers:** *Lexend* (Geometric Sans, for modern UI readability).
*   **Body Text:** *Source Sans 3* (High-legibility standard for detailed records).
*   **Data & Technical:** *Fira Code* (Monospaced, for HUD elements, IDs, and technical stats).

---

### 3. UI Architecture (Ribbon-Sync Design)
The interface utilizes a Ribbon-based navigation system synchronized with a modular content area.

*   **Ribbon Menu:**
    *   Use `ttkbootstrap` with a customized `Ribbon.TNotebook` style.
    *   Tabs: Home (🏠), Contracts (📑), HR (👔), Tools (🛠️), Reports (📊).
    *   Style: `Helvetica 10 bold` font, `[20, 5]` padding, and button groups in `SECONDARY`, `LIGHT`, or `INFO` bootstyles.
*   **Dashboard Hero:**
    *   Centered `300x300` company logo (Vincci Hoteles).
    *   Global Statistics Bar: Tracking "Active," "Expiring," and "Expired" statuses with high-contrast text.
*   **Global Status Bar (Bottom):**
    *   Display: 💻 PC Name/IP | 🌍 Location & Weather | 📅 Clock (digital, bold).
    *   Architecture: Powered by a `BackgroundScheduler` for real-time updates.

---

### 4. Interactions & Data Management
*   **Tableview Enhancements:**
    *   Utilize `ttkbootstrap.widgets.tableview` for data-heavy views.
    *   Implement an 800ms "Flash" animation for critical rows (Expiring/Expired).
*   **Security & RBAC:**
    *   Role-Based Access Control (RBAC) visibility for "Tools" and "Audit Log" (Mouchard).
    *   Secure Deletion Logic: Password-protected actions using date-based algorithmic calculation: `((day + month + year_short) * 2) - 10`.
*   **Performance:**
    *   Utilize an `image_cache` for UI assets to minimize disk I/O.
    *   Smooth transitions (150-300ms) for all UI state changes.

---

### 5. Technical Stack
*   **GUI:** Python with `ttkbootstrap` (Superhero theme base).
*   **Backend:** SQLAlchemy ORM with SQLite (`contragest.db`).
*   **Services:** `EmailService` with OTP activation and SMTP reliability.
*   **Reporting:** `fpdf2` for PDF exports and analytics.
*   **Standards:** WCAG AAA compliance for high-contrast OLED accessibility.
