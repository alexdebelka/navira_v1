# Navira Next.js Migration PoC

This directory contains a Proof of Concept for migrating the Navira dashboard to a modern Next.js + FastAPI stack.

## Structure

- **backend/**: A FastAPI Python application that serves the data. It reuses the existing CSV files from `../new_data`.
- **frontend/**: A Next.js React application with Tailwind CSS and Framer Motion for the UI.

## How to Run

### 1. Start the Backend

Open a terminal and run:

```bash
cd next_migration/backend
# Install dependencies if needed
pip install fastapi uvicorn pandas
# Run the server
python -m uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`.

### 2. Start the Frontend

Open a **new** terminal window and run:

```bash
cd next_migration/frontend
# Install dependencies (already done, but good practice)
npm install
# Run the development server
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

## Features Implemented

- **Futuristic UI**: Dark mode, glassmorphism, and smooth animations.
- **Live Data**: Fetches real data from your existing CSVs via the Python backend.
- **Summary Cards**: Displays Volume, Trend, Revisional Rate, and Complication Rate.
