# Astro ICT Charting Panel - Full one-push package

This repo contains a FastAPI backend and a static frontend (Lightweight Charts + TradingView widget toggle).  
Services run with Docker Compose.

## Run
1. Build and start:
   docker-compose up --build -d

2. Frontend: http://localhost:3000/  
   Backend: http://localhost:8000/  
   WebSocket: ws://localhost:8000/ws/signals

## Backend protected endpoint
/ict/signals/add is protected by API_TOKEN (set in backend/.env or compose environment).
