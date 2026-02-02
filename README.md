# Flex

A monorepo with a Next.js frontend and FastAPI backend.

## Project Structure

```
flex/
├── frontend/    # Next.js app (TypeScript, Tailwind CSS)
└── backend/     # FastAPI server
```

## Getting Started

### Backend

1. Create and activate a virtual environment:
   ```bash
   cd backend
   uv venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   uv pip install -r requirements.txt
   ```

3. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

Or run directly without activating the venv:
```bash
cd backend
uv run uvicorn main:app --reload
```

The API will be available at http://localhost:8000

### Frontend

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

The app will be available at http://localhost:3000

## API Endpoints

| Method | Endpoint      | Description         |
|--------|---------------|---------------------|
| GET    | `/`           | Hello message       |
| GET    | `/api/health` | Health check        |
