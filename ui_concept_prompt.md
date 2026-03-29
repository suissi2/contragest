# UI Concept Prompt: Contragest Contract Management System

As a Python specialist, I want to create a professional contract management application called "Contragest." The interface should be modern, modular, and highly functional. Below is a detailed prompt to achieve a concept similar to the Contragest interface.

---

## **Project Objective**
Build a desktop application for contract management using **Python** and the **ttkbootstrap** library for a modern, themed look (specifically the **'superhero'** dark-mode theme).

## **Key Interface Requirements**

### **1. Navigation & Layout**
*   **Ribbon Menu:** Implement a top-level ribbon menu using a customized `ttk.Notebook` (styled as `Ribbon.TNotebook`). Tabs should include:
    *   🏠 **Home:** General dashboard stats and company branding.
    *   👔 **HR:** Employee and contract management tools.
    *   🛠️ **Tools:** User management and administrative audits (RBAC-protected).
    *   📊 **Reports:** Detailed analytics and data exports.
*   **Main Workspace:** Use a secondary `ttk.Notebook` (`Main.TNotebook`) with hidden tabs to switch between views (Home, Contracts, Tools, etc.) based on ribbon selections.

### **2. Data Management & Visuals**
*   **Tableview:** Use a dynamic `Tableview` for the contracts list.
    *   **Conditional Formatting:** Implement an `animate_flash` method to alternate row colors for critical items (e.g., `#ff4444` for 'Expired', `#ffbb33` for 'Expiring Soon').
    *   **Action Icons:** Include columns for 'Edit' (✏️) and 'Delete' (🗑️) directly in the table rows.
*   **Search & Filtering:** Add a robust filter bar above tables with search entries and comboboxes for categorical filtering (e.g., Department, Status, Contract Type).

### **3. Advanced Features**
*   **Status Bar:** A multi-part bottom bar showing:
    *   **Left:** System Info (Hostname, IP).
    *   **Center:** Session Info (Logged-in user and role).
    *   **Middle-Right:** Environmental Data (Location, Temperature).
    *   **Right:** Live Digital Clock (Date and Time).
*   **Internationalization (i18n):** Support for multiple languages (English, French, Arabic) with a `LanguageManager`.
*   **RTL Support:** Implement helper functions (`pack_start`, `pack_end`) to dynamically flip layouts for Right-to-Left languages like Arabic.
*   **Image Handling:** Use an `image_cache` and **Pillow (PIL)** for optimized loading and resizing of UI assets like logos.

### **4. Backend & Security**
*   **Database:** Use **SQLAlchemy ORM** with **SQLite** for data persistence.
*   **RBAC (Role-Based Access Control):** Implement a permissions system that restricts UI elements (like 'Tools' or 'Delete' buttons) based on the user's role (Admin vs. User).
*   **Sensitive Actions:** Protect contract deletion with a dynamically calculated daily password.

### **5. Reporting & Exports**
*   **Export Formats:** Provide functionality to export filtered data to **CSV** and **PDF** (using `fpdf`).
*   **Automated Alerts:** A background scheduler to check for expiring contracts and send email notifications via SMTP.

---

## **Technical Stack Recommendation**
*   **Python 3.10+**
*   **GUI:** `ttkbootstrap`, `tkinter`
*   **ORM:** `SQLAlchemy`
*   **Image Processing:** `Pillow`
*   **Reports:** `fpdf`, `csv`
*   **Scheduling:** `BackgroundScheduler` (custom threading)

---

**Prompt for LLM Generation:**
"Generate a modular Python GUI application using `ttkbootstrap` with the 'superhero' theme. The main window should feature a Ribbon-style navigation at the top and a multi-part status bar at the bottom. The core functionality must include a searchable `Tableview` for contract management with conditional row highlighting for expired items. Implement a simple RBAC system and provide placeholders for PDF/CSV export logic."
