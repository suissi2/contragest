# CONTRAGEST MASTER PROMPT v16: Cyberpunk-meets-Corporate OLED Interface

This document serves as the definitive high-fidelity blueprint for the **Contragest** enterprise interface. It synthesizes design tokens, architectural patterns, and technical specifications to guide the development of a professional, data-dense, and visually striking application.

## 1. Design Identity: "Cyberpunk-meets-Corporate"

The Contragest aesthetic bridges the gap between high-tech futurism and professional enterprise reliability. It is characterized by:
- **OLED-First Philosophy**: Pure blacks and deep navies to maximize contrast and power efficiency on modern displays.
- **Data-Density**: Efficient use of space for complex contract management workflows.
- **WCAG AAA Compliance**: Ensuring high readability and accessibility through rigorous color contrast.
- **Branding Core**: Anchored by the **Vincci Hoteles** visual identity (Elegance, Sophistication).

## 2. Design Tokens

### 2.1 Color Palette (OLED Dark Mode)
| Role | Hex | Application |
| :--- | :--- | :--- |
| **Background** | `#020617` | Main window background, deep black. |
| **Surface** | `#1E293B` | Cards, secondary frames, muted backgrounds. |
| **Corporate Navy** | `#0F172A` | Primary branding elements, headers. |
| **Primary/Success** | `#22C55E` | Positive indicators, primary CTAs, active status. |
| **Text (Primary)** | `#F8FAFC` | High-readability body and header text. |
| **Text (Muted)** | `#94A3B8` | Subheaders, labels, less critical information. |
| **Danger/Flash** | `#ff4444` / `#d9534f` | Critical alerts (Active/Static). |
| **Warning/Flash** | `#ffbb33` / `#f0ad4e` | Expiring soon alerts (Active/Static). |

### 2.2 Typography
- **Lexend**: Primary headers and navigation. (Modern, high readability).
- **Playfair Display SC**: Branding accents and logo-adjacent text. (Corporate elegance).
- **Source Sans 3**: Detailed body text and data grids. (Enterprise standard).
- **Fira Code**: Technical identifiers, IDs, and code-like data. (Tech noir aesthetic).

## 3. UI Architecture

### 3.1 Ribbon Navigation
- **Structure**: A customized `ttk.Notebook` (Style: `Ribbon.TNotebook`) located at the top.
- **Tabs**: Home, HR, Tools, Reports.
- **Buttons**: Grouped within `LabelFrame` containers inside tabs. Padding: 10px. Bootstyles: INFO, LIGHT, SECONDARY, DANGER.
- **Synchronization**: Ribbon tab changes drive the visibility of content in the `Main.TNotebook`.

### 3.2 Dashboard (Home) View
- **Hero Section**: Centered 300x300 Vincci Hoteles logo.
- **Branding**: "Contragest" (Lexend 24px Bold) + "Professional Contract Management System" (Lexend 14px).
- **Stats Bar**: Top-aligned, displaying Active, Expiring, and Expired contract counts.

### 3.3 Main Content Area
- **Container**: `Main.TNotebook` with `tabposition='n'` and an empty layout for tabs to hide them.
- **Data Tables**: `ttkbootstrap.widgets.tableview` (Note: deprecated `ttkbootstrap.tableview` should be avoided).
- **Visual Effects**: Smooth flashing animations (800ms intervals) for critical/expiring rows.

### 3.4 Status Bar (System HUD)
- **Position**: Bottom-aligned, `bootstyle=DARK`.
- **Components**:
    - **PC Info**: 💻 [PC Name] ([Local IP])
    - **Session**: Logged in as: [User] ([Role])
    - **Environment**: 🌍 [Location]   🌡️ [Temperature]
    - **Clock**: 📅 DD/MM/YYYY   🕒 HH:MM:S (Persistent update)

## 4. Technical Implementation Guidelines

- **Framework**: Python with `ttkbootstrap` (Base theme: `superhero`).
- **Icons**: SVG or Lucide-style icons (Avoid emoji for professional actions; use them sparingly in the status bar/tabs).
- **Transitions**: Smooth transitions (150-300ms) for UI state changes.
- **Security**:
    - **Deletion Formula**: `((day + month + year_short) * 2) - 10`.
    - **RBAC**: Strict role-based access control for 'admin' and 'user' roles.
- **I18n**: Full support for LTR/RTL layouts with dynamic translation loading.

## 5. Vision Summary

The goal is to provide a "Mission Control" experience for contract management—sleek, fast, and authoritative. Every pixel should reinforce the sense of a high-tech, secure enterprise tool.
