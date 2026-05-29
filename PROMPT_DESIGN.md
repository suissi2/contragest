# Contragest UI Generation Prompt

Act as an expert UI/UX Designer and Frontend Developer specializing in "Cyberpunk-meets-Corporate" aesthetics. Your goal is to generate a comprehensive technical blueprint and implementation for an enterprise-grade contract management system named **Contragest**.

### Visual Identity & Concept
- **Concept**: "Cyberpunk-meets-Corporate" — A fusion of high-tech noir aesthetics with professional enterprise architecture.
- **Theme**: OLED Dark Mode (WCAG AAA compliant).
- **Core Design Tokens**:
    - **Background**: `#020617` (Deep OLED Black)
    - **Surface/Cards**: `#1E293B` (Deep Slate)
    - **Corporate Accent**: `#0F172A` (Navy)
    - **Primary Action/Success**: `#22C55E` (Vibrant Emerald)
    - **Danger/Expired**: Flash `#ff4444` / Static `#d9534f`
    - **Warning/Expiring**: Flash `#ffbb33` / Static `#f0ad4e`
    - **Muted Text**: `#94A3B8`

### Typography System
- **Primary Headers**: `Lexend` (Modern, clean, geometric)
- **Branding Accents**: `Playfair Display SC` (Serif elegance for headers/logos)
- **Body Text**: `Source Sans 3` (High readability for data-dense layouts)
- **Technical/Data**: `Fira Code` (Monospaced for ID and audit logs)

### UI Architecture
1. **Ribbon Menu**: A Microsoft Office-style ribbon at the top using a tabbed interface (Home, HR, Tools, Reports). Buttons within groups should have consistent padding and utilize bootstyles (INFO, LIGHT, SECONDARY).
2. **Dashboard Hero Section**:
    - Centered 300x300 brand logo (Vincci Hoteles inspired).
    - Large "Contragest" title in Playfair Display SC.
    - Subtitle "Professional Contract Management System".
3. **Top Statistics Bar**: A horizontal bar tracking "Active", "Expiring Soon", and "Expired" contract counts with color-coded badges.
4. **Main Workspace**:
    - A multi-tabbed `Notebook` interface.
    - Data-dense `Tableview` with custom row coloring based on status.
    - Advanced filtering (Global Search + Dropdowns for Role/Status/Department).
5. **System Status Bar (Footer)**:
    - Persistent OLED black bar.
    - Left: PC Info (Host, IP) and Environment Data (Location, Weather).
    - Center: Logged-in user status.
    - Right: Dynamic 24h Clock and Resize Grip.

### Technical Implementation Details
- Use **Python** with `ttkbootstrap` (Superhero base theme) for the GUI.
- Implement smooth transitions (150-300ms) for hover states.
- Utilize a background scheduler for real-time environment data updates.
- Ensure all clickable elements have clear visual feedback and the pointer cursor.
- Strictly avoid emojis for icons; use SVG-style or Lucide-equivalent symbols.

---
**Task**: Generate the complete Python/ttkbootstrap code to implement this interface, ensuring the "Enterprise Gateway" pattern is followed.
