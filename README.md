# 🛒 SwiftMart – Python POS System

SwiftMart is a lightweight yet feature-rich Point of Sale (POS) system built entirely in Python for small to medium retail businesses. Designed as a portable single-file application, it delivers enterprise-style functionality while maintaining simplicity, flexibility, and ease of deployment. Developed as part of an academic project at Christ University, Bangalore (Aug 2025 – Present).

## 🚀 Overview

SwiftMart enables retailers to manage billing, inventory, customers, suppliers, and reporting from a unified system. It integrates secure authentication, barcode-based product management, loyalty programs, multiple payment options, and automated reporting — all powered by SQLite, a lightweight embedded database. The system is optimized for small and medium retail stores, supermarkets, local businesses, offline-first retail management, and academic demonstration of POS architecture.

## ✨ Key Features

### 👤 Cashier / User Panel
- Secure login with role-based authentication  
- Add products using barcode scan or product ID  
- Per-item and order-level discount support  
- Multiple payment modes (Cash, Card, UPI, Split Payments)  
- Loyalty points tracking (1 point per ₹100 spent)  
- Automatic receipt generation  
- Real-time billing calculations  

### 🛠️ Admin Panel
- Product management (Add / Update / Delete / Search)  
- Supplier management  
- Customer management  
- Inventory tracking with low-stock alerts  
- Import / Export data support  
- Backup and restore functionality  
- Sales analytics and reporting  
- Role-based permission configuration  
- Receipt and report generation (PDF)  

## 🧱 Tech Stack

- Programming Language: Python  
- Database: SQLite (Embedded, file-based — no external server required)  
- Libraries Used:
  - fpdf – PDF receipt generation  
  - python-barcode – Barcode creation and management  
  - matplotlib – Sales reports & visualizations  
  - sqlite3 – Built-in Python database module  

## 🏗️ System Architecture

SwiftMart follows a modular yet portable design consisting of an Authentication Layer (Role-Based Access Control), Business Logic Layer (Billing, Discounts, Loyalty, Inventory), Data Persistence Layer (SQLite Embedded Database), Reporting Layer (PDF and Charts), and Backup & Recovery Module. Since SQLite is embedded, no separate database installation or configuration is required — the database file is automatically created and managed by the application.

## 💳 Billing Workflow

1. User logs in (Cashier/Admin)  
2. Products added via barcode or ID  
3. Discounts applied (if any)  
4. Payment mode selected  
5. Loyalty points updated  
6. Receipt generated  
7. Inventory automatically adjusted  
8. Sales data stored in the SQLite database file  

## 📊 Reporting & Analytics

SwiftMart generates daily sales reports, revenue summaries, inventory movement insights, low-stock notifications, PDF-based receipts, and graphical sales visualizations using Matplotlib. This enables better retail decision-making and performance monitoring.

## 🔐 Security & Access Control

The system implements role-based authentication, admin-only configuration access, controlled settings modification, and backup protection mechanisms to ensure data reliability and operational security.

## 📦 Installation & Setup

### Prerequisites
- Python 3.x installed

### Install Dependencies
```bash
pip install fpdf python-barcode matplotlib
```

### Run the Application
```bash
python swiftmart.py
```

No separate database setup is required. The SQLite database file is automatically created on first run, making SwiftMart fully portable and easy to deploy.

## 📁 Project Structure (Sample)

```
swiftmart-pos/
│
├── swiftmart.py
└── README.md
```

## 💡 Design Philosophy

SwiftMart was built with minimal setup, offline-first functionality, lightweight deployment, enterprise-like features, extendable architecture, and clean, maintainable logic in mind. The goal was to create a zero-configuration POS system that can run immediately without complex infrastructure.

## 📈 Potential Enhancements

Future improvements may include web dashboard integration, REST API support, cloud synchronization, multi-store analytics, GST/tax automation module, real-time dashboard, AI-based demand prediction, QR-based billing, and customer mobile app integration.

## 🎓 Academic Context

This project demonstrates practical implementation of database design using SQLite, role-based authentication systems, file handling and backup systems, business logic modeling, retail workflow simulation, data visualization, and automated reporting. Associated with Christ University, Bangalore.

## 📜 License

This project is developed for academic and portfolio purposes. Feel free to fork, modify, and enhance with attribution.

## 👨‍💻 Author

Developed by Tejas R M  
Christ University, Bangalore  

## ⭐ Support

If you find this project useful, consider giving it a star and contributing improvements.
