# WehbeGroup "A to Z" Web POS & Inventory System

A production-hardened, web-based Point of Sale and digital catalog system built with Django. Designed to bridge legacy FoxPro data with a modern, mobile-responsive web interface for wholesale operations.

## 🚀 Core Features

- **Bilingual Digital Catalog:** Image-driven, searchable product categories utilizing Tailwind CSS and Flowbite UI components.
- **Integrated Web POS:** Session-based ticketing system allowing staff to toggle between standard catalog browsing and active order building.
- **Legacy System Synchronization:** A robust Excel (`.xlsx`) upload portal that automatically syncs legacy inventory data into the web database, featuring `@transaction.atomic` safety locks and automatic duplicate prevention.
- **PDF Generation:** Automated, branded PDF receipt and catalog generation for clients.
- **Image Optimization:** Automated backend image compression using Pillow (PIL) to ensure fast load times across mobile networks.

## 🛡️ Security Architecture

This application has undergone a comprehensive security audit and implements strict production guardrails:

- **Environment Variables:** All secrets (Secret Key, Custom Admin Routes) are decoupled from the codebase via `python-dotenv`.
- **XSS Immune:** Frontend JavaScript Live Search utilizes strict `.textContent` DOM manipulation to neutralize Cross-Site Scripting vulnerabilities.
- **Dynamic HTTPS Enforcement:** Session and CSRF cookies are strictly locked to encrypted HTTPS connections in the production environment via automatic `DEBUG` state tracking.
- **Endpoint Protection:** CPU-heavy endpoints (like PDF rendering) and state-altering data routes are strictly locked behind Django's authentication middleware.

## 💻 Tech Stack

- **Backend:** Python 3.10+, Django 5.x
- **Frontend:** HTML5, Tailwind CSS, Flowbite, Vanilla JavaScript
- **Database:** SQLite
- **Data Processing:** OpenPyXL (Excel parsing)
- **Media Handling:** Pillow (Image compression), XHTML2PDF

## ⚙️ Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone [your-repo-url]
   cd wehbegroup-backend
   ```
