#!/usr/bin/env python3
"""
Testowy serwer z mockowymi danymi - do testowania frontendu bez bazy danych
"""

from flask import Flask, jsonify
from flask_cors import CORS
import random

app = Flask(__name__)
CORS(app)
app.config['JSON_AS_ASCII'] = False

# Mockowe dane
def generate_mock_stats():
    """Generuje mockowe dane statystyk"""
    
    # Mockowe nazwiska
    surnames = ['Kowalski', 'Nowak', 'Wiśniewski', 'Wójcik', 'Kowalczyk', 
                'Kamiński', 'Lewandowski', 'Zieliński', 'Szymański', 'Woźniak']
    
    # Land ownership
    land_ownership = []
    for i, surname in enumerate(surnames):
        area_sqm = random.randint(5000, 500000)
        land_ownership.append({
            'nazwa_wlasciciela': f'{surnames[i % len(surnames)]} {chr(65+i)}',
            'unikalny_klucz': f'owner_{i+1}',
            'numer_protokolu': str(100 + i),
            'area_sqm': area_sqm,
            'area_ares': round(area_sqm / 100, 2),
            'area_hectares': round(area_sqm / 10000, 2)
        })
    
    # Sortuj po powierzchni
    land_ownership.sort(key=lambda x: x['area_sqm'], reverse=True)
    
    # Parcel rankings
    parcel_rankings = []
    categories = ['rolna', 'budowlana', 'las', 'pastwisko']
    for i in range(20):
        area_sqm = random.randint(1000, 100000)
        parcel_rankings.append({
            'id': i + 1,
            'numer': f'{100 + i}',
            'kategoria': categories[i % len(categories)],
            'wlasciciele': f'{surnames[i % len(surnames)]}',
            'area_sqm': area_sqm,
            'area_hectares': round(area_sqm / 10000, 2)
        })
    
    parcel_rankings.sort(key=lambda x: x['area_sqm'], reverse=True)
    
    # Rivers and roads
    rivers = []
    for i in range(5):
        length_m = random.randint(500, 15000)
        rivers.append({
            'nazwa': f'Rzeka {chr(65+i)}',
            'length_m': length_m,
            'length_km': round(length_m / 1000, 2)
        })
    
    rivers.sort(key=lambda x: x['length_m'], reverse=True)
    
    roads = []
    for i in range(8):
        length_m = random.randint(200, 8000)
        roads.append({
            'nazwa': f'Droga {i+1}',
            'length_m': length_m,
            'length_km': round(length_m / 1000, 2)
        })
    
    roads.sort(key=lambda x: x['length_m'], reverse=True)
    
    def calc_stats(items):
        if not items:
            return {
                'longest': None,
                'shortest': None,
                'average': 0,
                'total_count': 0,
                'items': []
            }
        lengths = [item['length_m'] for item in items]
        return {
            'longest': items[0],
            'shortest': items[-1],
            'average': round(sum(lengths) / len(lengths), 2),
            'total_count': len(items),
            'items': items
        }
    
    rivers_roads_stats = {
        'rivers': calc_stats(rivers),
        'roads': calc_stats(roads)
    }
    
    # Podstawowe statystyki
    rankings_real = {
        'all_plots': [
            {
                'nazwa_wlasciciela': f'{surnames[i % len(surnames)]} {chr(65+i)}',
                'unikalny_klucz': f'owner_{i+1}',
                'numer_protokolu': str(100 + i),
                'plot_count': random.randint(1, 50)
            }
            for i in range(20)
        ]
    }
    rankings_real['all_plots'].sort(key=lambda x: x['plot_count'], reverse=True)
    
    return {
        'general_stats': {
            'total_owners': len(surnames),
            'total_plots': 150
        },
        'protocols_per_day': [],
        'rankings_real': rankings_real,
        'rankings_protocol': rankings_real,
        'demografia': [],
        'category_counts': {
            'rolna': 50,
            'budowlana': 30,
            'las': 40,
            'pastwisko': 20,
            'droga': 5,
            'rzeka': 5
        },
        'genealogy_stats': {
            'total_people': 0,
            'male_count': 0,
            'female_count': 0,
            'top_surnames': [],
            'births_by_decade': {'labels': [], 'data': []},
            'deaths_by_decade': {'labels': [], 'data': []},
            'marriages_by_decade': {'labels': [], 'data': []},
            'infant_mortality': {},
            'lifespan_by_generation': {},
            'death_age_distribution': {},
            'family_structure': {}
        },
        'land_ownership': land_ownership,
        'parcel_rankings': parcel_rankings,
        'rivers_roads_stats': rivers_roads_stats
    }

@app.route('/')
def index():
    return jsonify({
        'status': 'ok',
        'message': 'Testowy serwer z mockowymi danymi',
        'endpoints': ['/api/stats']
    })

@app.route('/api/stats')
def get_stats():
    """Zwraca mockowe statystyki"""
    return jsonify(generate_mock_stats())

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 TESTOWY SERWER Z MOCKOWYMI DANYMI")
    print("="*60)
    print("\nSerwer uruchomiony na: http://127.0.0.1:5000")
    print("Endpoint statystyk: http://127.0.0.1:5000/api/stats")
    print("\nTo jest wersja testowa bez połączenia z bazą danych.")
    print("Dane są generowane losowo przy każdym zapytaniu.")
    print("="*60 + "\n")
    
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
