# Contragest UI/UX Implementation Prompt

**Role**: You are an expert UI/UX Designer and Desktop Application Architect specialized in Python and Modern GUI Frameworks (like `ttkbootstrap`).

**Objective**: Design and architect a professional **Enterprise Contract Management Dashboard** called "Contragest". The interface must follow a sophisticated "Enterprise Gateway" pattern with a focus on data density and operational efficiency.

---

### 1. Visual Identity & Theme
- **Primary Aesthetic**: "OLED Dark Mode" utilizing the **Superhero** theme (Slate #0F172A, Midnight Blue #1E293B, and Deep Black #020617).
- **Typography Hierarchy**:
    - **Hero Labels**: Helvetica 24pt Bold (Primary brand visibility).
    - **Stats/Data Labels**: Helvetica 11pt (Inverse-Secondary for readability).
    - **System/Status Labels**: Helvetica 9pt (Inverse-Dark for discrete info).
- **Visual Feedback**: Implement a "Flash Alert" system for critical data. For example, rows in a table representing expired contracts should alternate between Vivid Red (#ff4444) and standard Danger Red (#d9534f) every 800ms.

### 2. Layout Architecture
- **Navigation System**: A top-docked **Ribbon Menu** (`Ribbon.TNotebook`) with categorized tabs: `🏠 Home`, `👔 HR`, `🛠️ Tools`, and `📊 Reports`. Tabs should have [20, 5] padding and bold 10pt font.
- **Main Workspace**: A central `Notebook` where tabs are hidden (`Main.TNotebook` with no tab layout) to create a seamless "Single Page Application" feel, synchronized with the Ribbon selections.
- **Status Bar**: A multi-part bottom toolbar containing:
    - **Left**: PC Hostname and Local IP.
    - **Center**: Current user session details (Username & Role).
    - **Middle-Right**: Live Environment Data (Location & Weather/Temperature).
    - **Right**: A live Digital Clock (format: `📅 DD/MM/YYYY   🕒 HH:MM:SS`) and a window resizing grip.

### 3. Functional Modules
- **Contract Management Hub**: A data-dense table (`Tableview`) featuring columns: `Edit`, `Delete`, `ID`, `First Name`, `Last Name`, `Type`, `Start Date`, `End Date`, `Seniority` (Months/Days), `Days Left`, and `Status`.
- **Analytics & Reports Hub**: A modular view with advanced filtering (Dropdowns for Roles/Status/Departments and Date range toggles) and "One-Click" export capabilities to CSV and professionally formatted PDF (including company logo headers).
- **Internationalization (i18n)**: Native support for Right-to-Left (RTL) layouts and dynamic language switching via a dedicated `LanguageManager` and `tr()` helper.

### 4. Security & Logic Patterns
- **RBAC (Role-Based Access Control)**: UI elements (Ribbon tabs and buttons) must be conditionally rendered based on permissions verified through an `AuthService`.
- **Sensitive Action Verification**: Deletion of records must require a dynamic daily password. **Formula**: `((current_day + current_month + (current_year % 100)) * 2) - 10`.
- **Resilient Services**: Background workers for automated email alerts and a singleton `EmailManager` with a priority retry queue.

### 5. Design Guidelines (Anti-Patterns to Avoid)
- **No Emojis as UI Icons**: Use SVG-based icons (Heroicons or Lucide set) for professional consistency.
- **Stable Transitions**: All hover states must use smooth color/opacity transitions (150-300ms) without causing layout shifts.
- **Contrast**: Ensure a minimum contrast ratio of 4.5:1 for all text elements against the dark background.

---

**Instruction for the AI**: "Using the specifications above, generate the Python structure and the main UI class definitions using `ttkbootstrap` to implement this professional enterprise dashboard."
