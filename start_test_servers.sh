#!/bin/bash

echo "=========================================="
echo "   🧪 Testowe serwery Mapa Czarna"
echo "=========================================="
echo ""

# Zatrzymaj stare procesy
echo "→ Zatrzymywanie starych procesów..."
pkill -f "python3 app.py" 2>/dev/null
pkill -f "python3 test_server.py" 2>/dev/null
pkill -f "python3 -m http.server 8000" 2>/dev/null
sleep 1

# Uruchom testowy backend
echo "→ Uruchamianie testowego backendu (mockowe dane)..."
cd backend
python3 test_server.py > test_server.log 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"
cd ..
sleep 2

# Uruchom frontend serwer
echo "→ Uruchamianie serwera HTTP dla frontend..."
python3 -m http.server 8000 > frontend_server.log 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"
sleep 2

echo ""
echo "=========================================="
echo "   ✓ Serwery uruchomione!"
echo "=========================================="
echo ""
echo "🔧 Backend API (mockowe dane):"
echo "   http://127.0.0.1:5000"
echo "   http://127.0.0.1:5000/api/stats"
echo ""
echo "🌐 Frontend:"
echo "   http://127.0.0.1:8000"
echo ""
echo "📊 Strona statystyk (OTWÓRZ TĘ STRONĘ):"
echo "   → http://127.0.0.1:8000/wlasciciele/stats.html"
echo ""
echo "📝 Aby zatrzymać serwery:"
echo "   pkill -f 'python3 test_server.py'"
echo "   pkill -f 'python3 -m http.server'"
echo ""
echo "📂 Logi:"
echo "   backend/test_server.log"
echo "   frontend_server.log"
echo ""
echo "ℹ️  To jest wersja testowa z mockowymi danymi."
echo "   Nie wymaga połączenia z bazą danych PostgreSQL."
echo "=========================================="
