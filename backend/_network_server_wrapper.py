import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from app import app

if __name__ == '__main__':
    print('🚀 Uruchamianie serwera Flask w trybie sieciowym...')
    print('📡 Serwer nasłuchuje na wszystkich interfejsach (0.0.0.0)')
    print('=' * 60)
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
