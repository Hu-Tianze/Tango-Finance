# 💹 Expense-Tracker AI
> **Transform messy natural language into structured financial records.**
> An AI-Agent driven expense management system powered by Django & Llama 3.1.

---

## 🚀 Project Overview
**Expense-Tracker AI** is a smart financial assistant designed to bridge the gap between human conversation and rigorous bookkeeping. Instead of manual data entry, users simply "chat" with the system. The backend leverages a high-performance architecture to ensure every transaction is parsed accurately and stored securely.



## 🌟 Key Features

### 🤖 AI-Powered Intelligence
* **Natural Language Accounting**: Converts phrases like *"Spent 15 quid on a burger at Five Guys"* into structured data (Amount, Currency, Category, Note).
* **Financial Memory (RAG-lite)**: Injects the user's last 30 days of spending history into the AI context for personalized analysis.
* **Deterministic Parsing**: Uses Llama 3.1 **JSON Mode** to ensure 100% reliable integration with the Django ORM.

### 🔐 Security & Authentication
* **Passwordless Login**: Seamless user experience via **Email OTP (One-Time Password)** verification.
* **Dual-Channel Auth**: Supports **SessionAuthentication** for web users and **TokenAuthentication** for automated Agent scripts.
* **Environment Isolation**: Sensitive credentials are fully decoupled using `.env` files.

### ⚡ Engineering Excellence
* **High-Concurrency Ready**: Offloads session and cache management to **Redis (RAM)** to minimize Disk I/O bottlenecks.
* **Data Integrity**: Uses `transaction.atomic()` to guarantee "all-or-nothing" operations during AI processing.
* **Financial Precision**: Implements the `Decimal` type for all monetary calculations to eliminate floating-point rounding errors.
* **Optimized Lookups**: Uses **B-Tree Indexing** on unique identifiers (Email) for $O(\log n)$ retrieval speed.



## 🛠️ Tech Stack
* **Framework**: Django 6.0, Django REST Framework (DRF)
* **LLM Engine**: Llama 3.1 (via Groq Cloud API)
* **Cache/Session**: Redis
* **Database**: SQLite3 (Development) / PostgreSQL (Production ready)
* **Security**: python-dotenv, DRF Tokens

---

## 🔧 Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone [https://github.com/Hu-Tianze/Expense-Tracker.git](https://github.com/Hu-Tianze/Expense-Tracker.git)
   cd Expense-Tracker# 💹 Expense-Tracker AI
> **Transform messy natural language into structured financial records.**
> An AI-Agent driven expense management system powered by Django & Llama 3.1.

---

## 🚀 Project Overview
**Expense-Tracker AI** is a smart financial assistant designed to bridge the gap between human conversation and rigorous bookkeeping. Instead of manual data entry, users simply "chat" with the system. The backend leverages a high-performance architecture to ensure every transaction is parsed accurately and stored securely.



## 🌟 Key Features

### 🤖 AI-Powered Intelligence
* **Natural Language Accounting**: Converts phrases like *"Spent 15 quid on a burger at Five Guys"* into structured data (Amount, Currency, Category, Note).
* **Financial Memory (RAG-lite)**: Injects the user's last 30 days of spending history into the AI context for personalized analysis.
* **Deterministic Parsing**: Uses Llama 3.1 **JSON Mode** to ensure 100% reliable integration with the Django ORM.

### 🔐 Security & Authentication
* **Passwordless Login**: Seamless user experience via **Email OTP (One-Time Password)** verification.
* **Dual-Channel Auth**: Supports **SessionAuthentication** for web users and **TokenAuthentication** for automated Agent scripts.
* **Environment Isolation**: Sensitive credentials are fully decoupled using `.env` files.

### ⚡ Engineering Excellence
* **High-Concurrency Ready**: Offloads session and cache management to **Redis (RAM)** to minimize Disk I/O bottlenecks.
* **Data Integrity**: Uses `transaction.atomic()` to guarantee "all-or-nothing" operations during AI processing.
* **Financial Precision**: Implements the `Decimal` type for all monetary calculations to eliminate floating-point rounding errors.
* **Optimized Lookups**: Uses **B-Tree Indexing** on unique identifiers (Email) for $O(\log n)$ retrieval speed.

---

## 🔧 Installation & Setup

To protect sensitive data, the `.env` file and `db.sqlite3` are not included in this repository. Follow these steps to set up your local environment:

### 1. Environment Configuration
Create a file named `.env` in the project root directory and add your keys:
```env
DJANGO_SECRET_KEY=your_random_secret_key
GROQ_API_KEY=your_groq_api_key
DEBUG=True

2. Install Dependencies
Ensure your virtual environment is activated, then run:

pip install -r requirements.txt

3. Initialize Database
Run the migrations to create the local SQLite3 database structure:

python manage.py migrate

4. Run the Server
Launch the development server:

python manage.py runserver

🛠️ Tech Stack
Framework: Django 6.0, Django REST Framework (DRF)

LLM Engine: Llama 3.1 (via Groq Cloud API)

Cache/Session: Redis

Database: SQLite3 (Development) / PostgreSQL (Production ready)

📈 Future Roadmap
Support for real-time exchange rate conversion.

Visualized financial reports using Chart.js.

Voice-to-text integration for mobile accounting.


