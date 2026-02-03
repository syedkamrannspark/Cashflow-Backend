# Cashflow Backend

A FastAPI-based backend application for cashflow management, invoice tracking, and financial forecasting using AI-powered agents.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Database Setup](#database-setup)
- [Seeding Sample Data](#seeding-sample-data)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

## Overview

This backend service provides:
- Invoice management and tracking
- Payment history recording
- Bank transaction logging
- Financial forecasting using LLM agents
- Dashboard with cashflow analytics
- RESTful API endpoints for integration

## Prerequisites

Before setting up the project, ensure you have:

- **Python 3.9+** - Download from [python.org](https://www.python.org/downloads/)
- **PostgreSQL 15+** - Install via [postgresql.org](https://www.postgresql.org/download/) or Homebrew
- **pip** - Python package manager (comes with Python)
- **OpenRouter API Key** - Get from [openrouter.ai](https://openrouter.ai/)

### macOS Installation (Homebrew)

```bash
# Install PostgreSQL
brew install postgresql@15

# Install Python (if needed)
brew install python@3.9
```

## Installation

### 1. Clone or Navigate to Project

```bash
cd /path/to/Cashflow-Backend
```

### 2. Create a Virtual Environment (Optional but Recommended)

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### 1. Create Environment Variables File

Create a `.env` file in the root directory:

```bash
cat > .env << 'EOF'
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cashflow_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password

# OpenRouter API Key for LLM
OPENROUTER_API_KEY=your_openrouter_api_key
EOF
```

### 2. Update Credentials

Edit the `.env` file with your actual credentials:

- **DB_PASSWORD**: Your PostgreSQL password
- **OPENROUTER_API_KEY**: Your OpenRouter API key from [openrouter.ai](https://openrouter.ai/)

## Database Setup

### 1. Start PostgreSQL Service

**macOS (Homebrew):**
```bash
# Start PostgreSQL
brew services start postgresql@15

# Or manually:
/opt/homebrew/Cellar/postgresql@15/15.15_1/bin/pg_ctl -D /opt/homebrew/var/postgresql@15 start
```

**Linux:**
```bash
sudo service postgresql start
```

### 2. Create Database

The database will be created automatically when you first run the application, but you can create it manually:

```bash
export PATH="/opt/homebrew/Cellar/postgresql@15/15.15_1/bin:$PATH"
createdb cashflow_db
```

### 3. Create PostgreSQL User

If the `postgres` user doesn't exist:

```bash
createuser postgres --superuser
```

## Running the Application

### Start the FastAPI Server

```bash
export PATH="/opt/homebrew/Cellar/postgresql@15/15.15_1/bin:$PATH"
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will start at `http://localhost:8000`

### Verify Server is Running

```bash
curl http://localhost:8000/docs
```

You should see the Swagger UI documentation page.

## Seeding Sample Data

To populate the database with test data:

```bash
python3 -c "
import sys
sys.path.insert(0, '.')
from seed_database import main
main()
"
```

**Sample Data Includes:**
- 5 test invoices
- 5 payment history records
- 8 bank transactions
- 6 forecast metrics

## API Documentation

### Interactive API Documentation

Once the server is running, access the documentation at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

### Main Endpoints

#### Dashboard
- `GET /api/v1/dashboard/stats` - Get dashboard statistics
- `GET /api/v1/dashboard/flow` - Get cashflow data
- `GET /api/v1/dashboard/forecast` - Get forecast data
- `GET /api/v1/dashboard/insights` - Get AI-powered insights

#### Invoices
- `GET /api/v1/invoices` - List all invoices
- `GET /api/v1/invoices/{invoice_number}` - Get invoice details
- `POST /api/v1/invoices` - Create new invoice
- `PUT /api/v1/invoices/{invoice_number}` - Update invoice

#### Workflows
- `POST /api/v1/workflows/run` - Run analysis workflow
- `GET /api/v1/workflows/status` - Get workflow status

## Project Structure

```
Cashflow-Backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── agents/                 # AI agent orchestration
│   │   ├── base.py
│   │   ├── orchestrator.py
│   │   └── specialized.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       └── endpoints/
│   │           ├── dashboard.py
│   │           ├── invoices.py
│   │           └── workflows.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py          # Configuration settings
│   │   ├── database.py        # Database connection
│   │   └── llm_client.py      # LLM client setup
│   ├── models/
│   │   ├── __init__.py
│   │   ├── invoice.py         # Invoice model
│   │   ├── payment_history.py # Payment history model
│   │   └── complex_models.py  # Other models
│   └── services/
│       ├── __init__.py
│       ├── ingestion_service.py
│       └── llm_service.py
├── .env                        # Environment variables
├── .gitignore
├── requirements.txt            # Python dependencies
├── seed_database.py           # Database seeding script
└── README.md                  # This file
```

## Environment Variables Explained

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL server host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `cashflow_db` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `yourpassword` |
| `OPENROUTER_API_KEY` | LLM API key | `sk-or-v1-...` |

## Troubleshooting

### PostgreSQL Connection Error

**Error**: `FATAL: role "postgres" does not exist`

**Solution**: Create the postgres user
```bash
createuser postgres --superuser
```

### Database Does Not Exist

**Error**: `FATAL: database "cashflow_db" does not exist`

**Solution**: Create the database
```bash
createdb cashflow_db
```

### Missing Environment Variables

**Error**: `ValidationError: ... fields required`

**Solution**: Ensure `.env` file exists with all required variables
```bash
ls -la .env
```

### Port 8000 Already in Use

**Error**: `Address already in use`

**Solution**: Use a different port
```bash
python3 -m uvicorn app.main:app --port 8001
```

### PostgreSQL Service Not Running

**Error**: `connection refused`

**Solution**: Start PostgreSQL
```bash
brew services start postgresql@15
```

### SSL/OpenSSL Warning

This is a non-critical warning from urllib3. The application will still function normally.

## Development

### Install Development Dependencies

```bash
pip install -r requirements.txt
```

### Run Tests (if available)

```bash
pytest tests/
```

### Code Formatting

```bash
black app/
flake8 app/
```

## Production Deployment

For production deployment:

1. Set `--reload` to `False`
2. Use a production ASGI server (e.g., Gunicorn with Uvicorn workers)
3. Set up a reverse proxy (e.g., Nginx)
4. Use environment-specific `.env` files
5. Enable CORS appropriately
6. Set up database backups
7. Monitor application logs

Example production command:
```bash
gunicorn app.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## Support

For issues or questions:
1. Check the Troubleshooting section
2. Review API documentation at `/docs`
3. Check application logs in console output

## License

Proprietary - Sparkprescience

---

**Last Updated**: January 29, 2026
