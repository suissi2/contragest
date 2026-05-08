# Contragest Interface Master Prompt

This document provides a comprehensive technical and visual specification for recreating or extending the **Contragest** interface, an Enterprise Contract Management System designed with a "Cyberpunk-meets-Corporate" aesthetic.

## 1. Visual Identity & Design System

### OLED Dark Mode Palette
- **Background:** `#020617` (Deep Midnight Black)
- **Surface/Cards:** `#1E293B` (Slate Blue)
- **Primary/Positive:** `#22C55E` (Emerald Green)
- **Text (Main):** `#F8FAFC` (Ghost White)
- **Secondary Text:** `#94A3B8` (Muted Slate)
- **Danger/Expired:** Active `#ff4444` / Static `#d9534f`
- **Warning/Expiring:** Active `#ffbb33` / Static `#f0ad4e`

### Typography
- **Primary Headers:** Lexend (Modern, geometric)
- **Branding Accents:** Playfair Display SC (Elegant, serif)
- **Body Text:** Source Sans 3 (High readability)
- **Alternative (Technical):** Fira Code

### Key Effects
- **Smooth Transitions:** 150-300ms for hover and state changes.
- **Flashing Alerts:** 800ms interval for critical table rows (Danger/Warning).
- **Transparency:** Minimal use of glassmorphism; focus on high contrast for WCAG AAA compliance.

## 2. Layout & Architecture

### Navigation: Ribbon Menu
- **Tabs:** 🏠 Home, 👔 HR, 🛠️ Tools, 📊 Reports.
- **Home:** General dashboard stats, application settings, company logo management, and session controls (Logout/Exit).
- **HR:** Dedicated workspace for Employees and Contracts management.
- **Tools:** Administrative utilities like User Management and "Mouchard" (Audit Log).
- **Reports:** Centralized analytics hub.

### Dashboard (Home View)
- **Stats Bar:** Top-level summary of contract statuses (Active, Expiring, Expired).
- **Hero Section:** Centered 300x300 company logo with a bold title and tagline.
- **Status Bar:** Multi-part bottom bar with:
  - System info (Hostname/IP)
  - Current session details
  - Real-time location and weather data
  - Live digital clock

### Tables (Data Dense)
- High-contrast layouts with color-coded rows based on status.
- Support for global search, dropdown filters, and date range selection.
- Export capabilities for CSV and PDF (cleanly formatted with logo headers).

## 3. Technical Stack

- **Backend:** Python 3.x
- **GUI Framework:** `ttkbootstrap` (Theme: `superhero`)
- **ORM:** SQLAlchemy (SQLite database: `contragest.db`)
- **Image Processing:** Pillow (`PIL`)
- **Reporting:** `fpdf2` for PDF generation
- **Security:**
  - RBAC (Role-Based Access Control) with "admin" super-user bypass.
  - Audit logging of all critical actions.
  - Secure OTP-based activation flow for new users.

## 4. Logic & Security

- **Seniority Calculation:** Precise logic using month/day breakdown.
- **Deletion Security:** Dynamic formula-based password for sensitive actions (e.g., deleting contracts).
- **Automated Alerts:** Background scheduler for expiration notifications via SMTP.

---
*This prompt is intended for LLMs to maintain consistency and fidelity across all Contragest modules.*
