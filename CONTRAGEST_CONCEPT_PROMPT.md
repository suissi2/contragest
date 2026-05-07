# Contragest Interface Master Prompt: "Enterprise Gateway" OLED Dark Mode

You are a seasoned Python developer and UI/UX expert tasked with recreating or extending the **Contragest** interface. This professional contract management system follows a "Cyberpunk-meets-Corporate" aesthetic, emphasizing high-density data, OLED efficiency, and WCAG AAA compliance.

## 1. Visual Identity & Design Tokens

### Core Aesthetic
- **Style:** "Enterprise Gateway" meets "OLED Dark Mode".
- **Theme Base:** `ttkbootstrap` "superhero" theme, heavily customized for deeper blacks and higher contrast.
- **Palette (OLED Dark Mode):**
  - **Background:** `#020617` (Deep Black/Navy)
  - **Surface/Cards:** `#1E293B` (Slate Blue)
  - **Primary/Success:** `#22C55E` (Vibrant Green)
  - **Text (Primary):** `#F8FAFC` (Ghost White)
  - **Text (Muted/Secondary):** `#94A3B8` (Slate Grey)
  - **Danger (Alert):** Active `#ff4444` / Static `#d9534f`
  - **Warning (Alert):** Active `#ffbb33` / Static `#f0ad4e`

### Typography
- **Branding Accents:** *Playfair Display SC*
- **Primary Headings:** *Lexend* (Professional & Accessible)
- **Body/Detail Text:** *Source Sans 3* (High Readability)
- **Technical/Stats:** *Helvetica* or *Fira Code* (Precise)

## 2. Layout Architecture

### Main Window Structure
- **Ribbon Navigation:** A tabbed `Notebook` at the top (`🏠 Home`, `👔 HR`, `🛠️ Tools`, `📊 Reports`). Buttons within tabs use `INFO`, `LIGHT`, `SECONDARY`, and `outline-warning` bootstyles.
- **Hero Dashboard (Home Tab):**
  - **Stats Bar:** Top-level horizontal bar tracking "Active", "Expiring", and "Expired" counts.
  - **Hero Section:** Centered layout featuring a 300x300 company logo and bold branding ("Contragest").
- **Status Bar:** Multi-part footer with:
  - **Left:** System info (Hostname/IP).
  - **Center:** Session details (User role/Username).
  - **Middle-Right:** Environmental data (Weather/Location via background thread).
  - **Right:** Live digital clock (📅 DD/MM/YYYY  🕒 HH:MM:SS).

## 3. Component Specifications

### Advanced Tableview
- **Columns:** Edit (Icon), Delete (Icon), ID, First Name, Last Name, Type, Start Date, End Date, Seniority, Days Left, Status.
- **Alert Logic:** Rows with "Expired" or "Expiring Soon" status must **flash** at an 800ms interval, toggling between active and static alert colors.
- **Interactivity:** Double-click to edit; icon-based triggers for row-level actions.

### Forms & Dialogs
- **Constraint:** Use `ttkbootstrap.dialogs` (Messagebox, Querybox) for high-fidelity styled interactions.
- **Security:** Critical actions (like deletion or recovery) require a dynamically calculated password based on the date formula: `((day + month + (year % 100)) * 2) - 10`.

## 4. Technical Stack & Backend Integration
- **Framework:** Python 3.x with `ttkbootstrap` and `Tkinter`.
- **Database:** `SQLAlchemy` ORM targeting a local `contragest.db` (SQLite).
- **Security:** Role-Based Access Control (RBAC) with an 'admin' bypass. Multi-factor authentication (OTP) for account activation.
- **Utilities:** `Pillow` for image/logo caching; `fpdf2` for PDF report generation; `i18n` for multi-language support (EN/FR/AR).

## 5. Implementation Directives
- **No Unicode Emojis:** Replace all UI icons with high-fidelity SVG equivalents (Lucide or Heroicons).
- **Transitions:** Implement smooth 150-300ms transitions for hover states.
- **Performance:** Utilize an `image_cache` for resized assets to minimize disk I/O.
- **Hygiene:** Ensure compiled artifacts (`__pycache__`), databases (`*.db`), and logs are excluded from the core repository structure.
