"""
================================================================================
Plik: test_api_genealogia_stats.py
Opis: Testy jednostkowe dla nowych endpointów statystyk genealogicznych
================================================================================
"""

import pytest


def test_infant_mortality_endpoint(client):
    """Test endpointu śmiertelności niemowląt."""
    response = client.get('/api/genealogia/infant-mortality')
    assert response.status_code == 200
    
    data = response.get_json()
    assert 'total_infant_deaths' in data
    assert 'mortality_rate' in data
    assert 'age_distribution' in data
    assert 'labels' in data
    assert 'data' in data
    
    assert isinstance(data['total_infant_deaths'], int)
    assert isinstance(data['mortality_rate'], (int, float))
    assert isinstance(data['age_distribution'], dict)
    assert isinstance(data['labels'], list)
    assert isinstance(data['data'], list)


def test_lifespan_by_generation_endpoint(client):
    """Test endpointu długości życia według pokoleń."""
    response = client.get('/api/genealogia/lifespan-by-generation')
    assert response.status_code == 200
    
    data = response.get_json()
    assert 'labels' in data
    assert 'data' in data
    assert 'count_per_decade' in data
    
    assert isinstance(data['labels'], list)
    assert isinstance(data['data'], list)
    assert isinstance(data['count_per_decade'], dict)
    
    assert len(data['labels']) == len(data['data'])


def test_seasonality_endpoint(client):
    """Test endpointu sezonowości urodzeń i zgonów."""
    response = client.get('/api/genealogia/seasonality')
    assert response.status_code == 200
    
    data = response.get_json()
    assert 'labels' in data
    assert 'births' in data
    assert 'deaths' in data
    
    assert isinstance(data['labels'], list)
    assert isinstance(data['births'], list)
    assert isinstance(data['deaths'], list)
    
    assert len(data['labels']) == 12
    assert len(data['births']) == 12
    assert len(data['deaths']) == 12


def test_family_structure_endpoint(client):
    """Test endpointu struktury rodzin."""
    response = client.get('/api/genealogia/family-structure')
    assert response.status_code == 200
    
    data = response.get_json()
    assert 'average_children' in data
    assert 'total_families' in data
    assert 'family_size_distribution' in data
    assert 'labels' in data
    assert 'data' in data
    assert 'average_household_size' in data
    assert 'total_households' in data
    
    assert isinstance(data['average_children'], (int, float))
    assert isinstance(data['total_families'], int)
    assert isinstance(data['family_size_distribution'], dict)
    assert isinstance(data['labels'], list)
    assert isinstance(data['data'], list)
    assert isinstance(data['average_household_size'], (int, float))
    assert isinstance(data['total_households'], int)


def test_infant_mortality_data_consistency(client):
    """Test spójności danych śmiertelności niemowląt."""
    response = client.get('/api/genealogia/infant-mortality')
    data = response.get_json()
    
    total_from_distribution = sum(data['age_distribution'].values())
    assert data['total_infant_deaths'] >= 0
    assert data['mortality_rate'] >= 0
    assert data['mortality_rate'] <= 100


def test_lifespan_data_validity(client):
    """Test poprawności danych długości życia."""
    response = client.get('/api/genealogia/lifespan-by-generation')
    data = response.get_json()
    
    for age in data['data']:
        assert age >= 0
        assert age <= 150


def test_seasonality_data_validity(client):
    """Test poprawności danych sezonowości."""
    response = client.get('/api/genealogia/seasonality')
    data = response.get_json()
    
    for count in data['births']:
        assert count >= 0
    
    for count in data['deaths']:
        assert count >= 0


def test_family_structure_data_validity(client):
    """Test poprawności danych struktury rodzin."""
    response = client.get('/api/genealogia/family-structure')
    data = response.get_json()
    
    assert data['average_children'] >= 0
    assert data['total_families'] >= 0
    assert data['average_household_size'] >= 0
    assert data['total_households'] >= 0
    
    total_from_distribution = sum(data['family_size_distribution'].values())
    if data['total_families'] > 0:
        assert total_from_distribution == data['total_families']
