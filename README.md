# AQI Evaluator (Django Web Application)

A web-based Air Quality Index (AQI) Evaluator built with Django, PySpark, and MariaDB that calculates, analyzes, and visualizes air quality metrics from environmental datasets.

## Repository Structure

```text
AQI_Delhi_Project/
├── manage.py                  # Django CLI entry point
├── requirements.txt           # Python dependencies
├── delhi-weather-aqi-2025.csv # Primary Delhi weather and AQI dataset
├── database/
│   └── aqi_evaluator_schema_and_data.sql  # Full MariaDB schema and seed data dump
├── sample_data/
│   └── sample_aqi_data.csv    # Sample CSV dataset for testing uploads/analysis
├── spark_outputs/             # Processed JSON outputs from PySpark algorithms
├── aqi_engine/                # Main Django app (models, views, URLs, templates, static assets)
└── core/                      # Django project settings and configuration
```

---

## Prerequisites

* **Python 3.10+**
* **MariaDB Server** (v10.5+)
* **Git**

---

## Installation & Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com
cd AQI_Delhi_Project
```

### 2. Create and Activate a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate      # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## MariaDB Database Setup

### 1. Create the Database
Log into your MariaDB server and create an empty database named `aqi_project`:
```bash
mariadb -u root -p -e "CREATE DATABASE aqi_project CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### 2. Import the Schema and Data
Load the included SQL dump into your new database:
```bash
mariadb -u root -p aqi_project < database/aqi_evaluator_schema_and_data.sql
```

### 3. Configure Database Credentials
Ensure the `DATABASES` configuration in `core/settings.py` (or your `.env` file) matches your local MariaDB username and password, then verify migrations:
```bash
python manage.py migrate
```

*(Optional)* To create an admin superuser for the Django Admin panel:
```bash
python manage.py createsuperuser
```

---

## Running the Application

1. Start the local Django development server:
   ```bash
   python manage.py runserver
   ```
2. Open your web browser and navigate to:
   * **Main Application:** `http://127.0.0`
   * **Admin Dashboard:** `http://127.0.0admin/`
3. Use `sample_data/sample_aqi_data.csv` when testing CSV data import features.
