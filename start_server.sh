#!/bin/bash

echo "=========================================="
echo "   Uruchamianie serwerów Mapa Czarna"
echo "=========================================="
echo ""

# Sprawdź czy backend już działa
if pgrep -f "python3 app.py" > /dev/null; then
    echo "✓ Backend Flask już działa"
else
    echo "→ Uruchamianie backendu Flask..."
    cd backend
    python3 app.py > server.log 2>&1 &
    BACKEND_PID=$!
    echo "  Backend PID: $BACKEND_PID"
    sleep 2
    cd ..
fi

# Sprawdź czy frontend serwer już działa
if pgrep -f "python3 -m http.server 8000" > /dev/null; then
    echo "✓ Frontend serwer HTTP już działa"
else
    echo "→ Uruchamianie serwera HTTP dla frontend..."
    python3 -m http.server 8000 > frontend_server.log 2>&1 &
    FRONTEND_PID=$!
    echo "  Frontend PID: $FRONTEND_PID"
fi

sleep 2

echo ""
echo "=========================================="
echo "   Serwery uruchomione!"
echo "=========================================="
echo ""
echo "Backend API:  http://127.0.0.1:5000"
echo "Frontend:     http://127.0.0.1:8000"
echo ""
echo "Strona statystyk:"
echo "→ http://127.0.0.1:8000/wlasciciele/stats.html"
echo ""
echo "Aby zatrzymać serwery:"
echo "  pkill -f 'python3 app.py'"
echo "  pkill -f 'python3 -m http.server'"
echo ""
echo "Logi backendu: backend/server.log"
echo "Logi frontendu: frontend_server.log"
echo "=========================================="
