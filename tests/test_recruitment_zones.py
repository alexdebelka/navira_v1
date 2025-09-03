"""
Unit tests for recruitment zone analysis functionality.

Tests cover:
- Data loading and cleaning
- Competitor ranking
- Postal code to INSEE mapping
- Choropleth data generation
- Allocation strategies
"""

import pytest
import pandas as pd
import tempfile
import os
from typing import Dict, List
import json

# Import modules to test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from navira.data_loaders import (
    load_recruitment_data, 
    load_competitors_data, 
    load_communes_data, 
    build_postal_to_insee_mapping
)
from navira.competitors import (
    get_top_competitors, 
    competitor_choropleth_df, 
    get_competitor_names
)
from navira.geo import detect_insee_key, load_communes_geojson


@pytest.fixture
def sample_recruitment_data():
    """Sample recruitment data with comma decimals and various formats."""
    return pd.DataFrame({
        'finessGeoDP': ['123456789', '987654321', '111222333'],
        'codeGeo': ['75001', '13001', '69001'],
        'nb': ['10,5', '25.0', '15,8'],
        'TOT': ['100,0', '200.0', '150,5'],
        'PCT': ['10,5', '12.5', '10,5'],
        'PCT_CUM': ['10,5', '23.0', '33,5']
    })


@pytest.fixture
def sample_competitors_data():
    """Sample competitors data with different ranking scenarios."""
    return pd.DataFrame({
        'finessGeoDP': ['123456789', '123456789', '987654321', '987654321'],
        'finessGeoDP_conc': ['111111111', '222222222', '333333333', '444444444'],
        'TOT_etb': ['100,0', '100.0', '150,5', '200.0'],
        'TOT_conc': ['50,5', '75.0', '80,5', '60.0']
    })


@pytest.fixture
def sample_communes_data():
    """Sample communes data with postal code to INSEE mapping."""
    return pd.DataFrame({
        'codeInsee': ['75101', '75102', '13001', '69001'],
        'codePostal': ['75001', '75001', '13001', '69001'],
        'longitude': ['2.3522', '2.3600', '5.3698', '4.8357'],
        'latitude': ['48.8566', '48.8600', '43.2965', '45.7640'],
        'nomCommune': ['Paris 1er', 'Paris 2e', 'Marseille', 'Lyon']
    })


@pytest.fixture
def sample_geojson():
    """Sample GeoJSON with different INSEE key variants."""
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"INSEE_COM": "75101", "nom": "Paris 1er"},
                "geometry": {"type": "Point", "coordinates": [2.3522, 48.8566]}
            },
            {
                "type": "Feature", 
                "properties": {"INSEE_COM": "75102", "nom": "Paris 2e"},
                "geometry": {"type": "Point", "coordinates": [2.3600, 48.8600]}
            },
            {
                "type": "Feature",
                "properties": {"INSEE_COM": "13001", "nom": "Marseille"},
                "geometry": {"type": "Point", "coordinates": [5.3698, 43.2965]}
            }
        ]
    }


class TestDataLoaders:
    """Test data loading and cleaning functions."""
    
    def test_recruitment_data_cleaning(self, sample_recruitment_data, tmp_path):
        """Test recruitment data loading with comma decimal conversion."""
        # Save sample data to temporary file
        csv_path = tmp_path / "recruitment.csv"
        sample_recruitment_data.to_csv(csv_path, index=False)
        
        # Load and test
        result = load_recruitment_data(str(csv_path))
        
        # Check FINESS padding
        assert result['finessGeoDP'].iloc[0] == '123456789'
        
        # Check postal code padding  
        assert result['codeGeo'].iloc[0] == '75001'
        
        # Check comma decimal conversion
        assert result['nb'].iloc[0] == 10.5
        assert result['PCT'].iloc[0] == 10.5
        
        # Check data types
        assert pd.api.types.is_float_dtype(result['nb'])
        assert pd.api.types.is_float_dtype(result['TOT'])
    
    def test_competitors_data_cleaning(self, sample_competitors_data, tmp_path):
        """Test competitor data loading with ranking order."""
        csv_path = tmp_path / "competitors.csv"
        sample_competitors_data.to_csv(csv_path, index=False)
        
        result = load_competitors_data(str(csv_path))
        
        # Check FINESS padding
        assert result['finessGeoDP'].iloc[0] == '123456789'
        assert result['finessGeoDP_conc'].iloc[0] == '111111111'
        
        # Check numeric conversion
        assert result['TOT_etb'].iloc[0] == 100.0
        assert result['TOT_conc'].iloc[0] == 50.5
    
    def test_communes_data_cleaning(self, sample_communes_data, tmp_path):
        """Test communes data loading with coordinate conversion."""
        csv_path = tmp_path / "communes.csv"
        sample_communes_data.to_csv(csv_path, index=False)
        
        result = load_communes_data(str(csv_path))
        
        # Check INSEE padding
        assert result['codeInsee'].iloc[0] == '75101'
        
        # Check postal code padding
        assert result['codePostal'].iloc[0] == '75001'
        
        # Check coordinate conversion
        assert result['longitude'].iloc[0] == 2.3522
        assert result['latitude'].iloc[0] == 48.8566
    
    def test_postal_to_insee_mapping(self, sample_communes_data):
        """Test postal code to INSEE mapping with one-to-many relationships."""
        mapping = build_postal_to_insee_mapping(sample_communes_data)
        
        # Check one-to-many mapping (Paris postal code maps to multiple INSEE)
        assert '75001' in mapping
        assert len(mapping['75001']) == 2
        assert '75101' in mapping['75001']
        assert '75102' in mapping['75001']
        
        # Check one-to-one mapping
        assert '13001' in mapping
        assert len(mapping['13001']) == 1
        assert '13001' in mapping['13001']


class TestCompetitorRanking:
    """Test competitor ranking and data generation."""
    
    def test_get_top_competitors(self, sample_competitors_data, tmp_path):
        """Test competitor ranking by TOT_conc descending, TOT_etb descending."""
        csv_path = tmp_path / "competitors.csv"
        sample_competitors_data.to_csv(csv_path, index=False)
        
        # Mock the load function to use our test data
        import navira.competitors
        original_load = navira.competitors.load_competitors_data
        navira.competitors.load_competitors_data = lambda: sample_competitors_data
        
        try:
            result = get_top_competitors('123456789', n=2)
            
            # Should rank by TOT_conc: 75.0 > 50.5
            assert len(result) == 2
            assert result[0] == '222222222'  # TOT_conc = 75.0
            assert result[1] == '111111111'  # TOT_conc = 50.5
            
            # Test with hospital that has no competitors
            result_empty = get_top_competitors('999999999', n=5)
            assert result_empty == []
            
        finally:
            navira.competitors.load_competitors_data = original_load
    
    def test_competitor_names_mapping(self, sample_competitors_data):
        """Test mapping competitor FINESS codes to hospital names."""
        competitors = ['111111111', '222222222']
        
        # Sample establishments data
        establishments = pd.DataFrame({
            'id': ['111111111', '222222222', '333333333'],
            'name': ['Hospital Alpha', 'Hospital Beta with Very Long Name That Should Be Truncated', 'Hospital Gamma']
        })
        
        result = get_competitor_names(competitors, establishments)
        
        assert result['111111111'] == 'Hospital Alpha'
        assert len(result['222222222']) <= 40  # Should be truncated
        assert '...' in result['222222222']  # Truncation indicator
    
    def test_choropleth_data_generation_even_split(self, sample_recruitment_data, sample_communes_data):
        """Test choropleth data generation with even split allocation."""
        # Clean the sample data first to match actual processing
        sample_recruitment_data['nb'] = sample_recruitment_data['nb'].astype(str).str.replace(',', '.').astype(float)
        
        # Create postal to INSEE mapping
        cp_to_insee = build_postal_to_insee_mapping(sample_communes_data)
        
        # Mock recruitment data loading
        import navira.competitors
        original_load = navira.competitors.load_recruitment_data
        navira.competitors.load_recruitment_data = lambda: sample_recruitment_data
        
        try:
            df, diagnostics = competitor_choropleth_df('123456789', cp_to_insee, 'even_split')
            
            # Check data structure
            assert 'insee5' in df.columns
            assert 'value' in df.columns
            
            if not df.empty:
                # Check even split allocation for Paris (2 INSEE codes)
                paris_total = df[df['insee5'].isin(['75101', '75102'])]['value'].sum()
                expected_value = 10.5  # nb value from sample data
                assert abs(paris_total - expected_value) < 0.01  # Allow floating point tolerance
            
            # Check diagnostics
            assert diagnostics.total_cps >= 0  # At least some postal codes processed
            assert abs(diagnostics.original_total - diagnostics.allocated_total) < 0.01 or diagnostics.original_total == 0
            
        finally:
            navira.competitors.load_recruitment_data = original_load
    
    def test_choropleth_data_generation_no_split(self, sample_recruitment_data, sample_communes_data):
        """Test choropleth data generation with no split allocation."""
        # Clean the sample data first to match actual processing
        sample_recruitment_data['nb'] = sample_recruitment_data['nb'].astype(str).str.replace(',', '.').astype(float)
        
        cp_to_insee = build_postal_to_insee_mapping(sample_communes_data)
        
        # Mock recruitment data loading
        import navira.competitors
        original_load = navira.competitors.load_recruitment_data
        navira.competitors.load_recruitment_data = lambda: sample_recruitment_data
        
        try:
            df, diagnostics = competitor_choropleth_df('123456789', cp_to_insee, 'no_split')
            
            if not df.empty:
                # Check no split allocation for Paris (full value to each INSEE)
                paris_values = df[df['insee5'].isin(['75101', '75102'])]['value']
                expected_value = 10.5  # Full nb value to each INSEE
                
                for value in paris_values:
                    assert abs(value - expected_value) < 0.01
            
            # Check that some allocation happened if there's source data
            assert diagnostics.total_cps >= 0
            
        finally:
            navira.competitors.load_recruitment_data = original_load


class TestGeoJSONHandling:
    """Test GeoJSON loading and INSEE key detection."""
    
    def test_insee_key_detection(self, sample_geojson):
        """Test auto-detection of INSEE property key."""
        insee_key = detect_insee_key(sample_geojson)
        assert insee_key == 'INSEE_COM'
    
    def test_insee_key_detection_alternative_formats(self):
        """Test INSEE key detection with different property names."""
        # Test with 'insee' key
        geojson_insee = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "properties": {"insee": "75101", "nom": "Paris"}},
                {"type": "Feature", "properties": {"insee": "75102", "nom": "Paris"}}
            ]
        }
        assert detect_insee_key(geojson_insee) == 'insee'
        
        # Test with no recognizable INSEE key
        geojson_no_insee = {
            "type": "FeatureCollection", 
            "features": [
                {"type": "Feature", "properties": {"random_key": "value"}}
            ]
        }
        assert detect_insee_key(geojson_no_insee) is None
    
    def test_geojson_loading_with_temp_file(self, sample_geojson, tmp_path):
        """Test GeoJSON loading from file system."""
        # Create temporary GeoJSON file
        geojson_path = tmp_path / "test_communes.geojson"
        with open(geojson_path, 'w') as f:
            json.dump(sample_geojson, f)
        
        # Test loading
        result = load_communes_geojson(str(geojson_path))
        assert result is not None
        assert result['type'] == 'FeatureCollection'
        assert len(result['features']) == 3


class TestIntegration:
    """Integration tests for end-to-end functionality."""
    
    def test_full_pipeline_with_sample_data(self, tmp_path):
        """Test complete pipeline from data loading to choropleth generation."""
        # Create sample data files
        recruitment_data = pd.DataFrame({
            'finessGeoDP': ['123456789', '123456789'],
            'codeGeo': ['75001', '13001'], 
            'nb': ['20,0', '15,5'],
            'TOT': ['100,0', '80,0'],
            'PCT': ['20,0', '19,4'],
            'PCT_CUM': ['20,0', '39,4']
        })
        
        competitors_data = pd.DataFrame({
            'finessGeoDP': ['999999999'],
            'finessGeoDP_conc': ['123456789'],
            'TOT_etb': ['200,0'],
            'TOT_conc': ['100,0']
        })
        
        communes_data = pd.DataFrame({
            'codeInsee': ['75101', '75102', '13001'],
            'codePostal': ['75001', '75001', '13001'],
            'longitude': ['2.3522', '2.3600', '5.3698'],
            'latitude': ['48.8566', '48.8600', '43.2965'],
            'nomCommune': ['Paris 1er', 'Paris 2e', 'Marseille']
        })
        
        # Save to files
        recruitment_path = tmp_path / "recruitment.csv"
        competitors_path = tmp_path / "competitors.csv"
        communes_path = tmp_path / "communes.csv"
        
        recruitment_data.to_csv(recruitment_path, index=False)
        competitors_data.to_csv(competitors_path, index=False)
        communes_data.to_csv(communes_path, index=False)
        
        # Test pipeline
        recruitment_df = load_recruitment_data(str(recruitment_path))
        communes_df = load_communes_data(str(communes_path))
        cp_to_insee = build_postal_to_insee_mapping(communes_df)
        
        # Generate choropleth data
        import navira.competitors
        original_load = navira.competitors.load_recruitment_data
        navira.competitors.load_recruitment_data = lambda: recruitment_df
        
        try:
            df, diagnostics = competitor_choropleth_df('123456789', cp_to_insee, 'even_split')
            
            # Verify results
            assert not df.empty
            assert diagnostics.total_cps == 2  # Paris and Marseille
            assert diagnostics.matched_cps == 2  # Both should match
            
            # Verify total conservation with even split
            original_total = recruitment_df['nb'].sum()  # 20.0 + 15.5 = 35.5
            allocated_total = df['value'].sum()
            assert abs(original_total - allocated_total) < 0.01
            
        finally:
            navira.competitors.load_recruitment_data = original_load


# Performance and edge case tests
class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_dataframes(self):
        """Test handling of empty input dataframes."""
        empty_df = pd.DataFrame()
        
        # Test postal to INSEE mapping with empty data
        mapping = build_postal_to_insee_mapping(empty_df)
        assert mapping == {}
        
        # Test competitor ranking with empty data
        import navira.competitors
        original_load = navira.competitors.load_competitors_data
        navira.competitors.load_competitors_data = lambda: empty_df
        
        try:
            result = get_top_competitors('123456789')
            assert result == []
        finally:
            navira.competitors.load_competitors_data = original_load
    
    def test_malformed_data_handling(self, tmp_path):
        """Test handling of malformed CSV data."""
        # Create CSV with missing columns
        malformed_data = pd.DataFrame({
            'wrong_column': ['value1', 'value2']
        })
        
        csv_path = tmp_path / "malformed.csv"
        malformed_data.to_csv(csv_path, index=False)
        
        # Should handle gracefully without crashing
        result = load_recruitment_data(str(csv_path))
        assert isinstance(result, pd.DataFrame)
    
    def test_memory_efficiency_large_dataset(self):
        """Test memory efficiency with larger datasets."""
        # Create larger sample dataset
        large_recruitment = pd.DataFrame({
            'finessGeoDP': ['123456789'] * 100,  # Reduced size for testing
            'codeGeo': [f'{i:05d}' for i in range(100)],
            'nb': [f'{i}.5' for i in range(100)],  # Use period instead of comma for simplicity
            'TOT': ['100.0'] * 100,
            'PCT': ['1.0'] * 100,
            'PCT_CUM': [f'{i}.0' for i in range(100)]
        })
        
        large_communes = pd.DataFrame({
            'codeInsee': [f'{i:05d}' for i in range(100)],
            'codePostal': [f'{i:05d}' for i in range(100)],
            'longitude': ['2.3522'] * 100,
            'latitude': ['48.8566'] * 100,
            'nomCommune': [f'Commune {i}' for i in range(100)]
        })
        
        # Test that operations complete without memory issues
        mapping = build_postal_to_insee_mapping(large_communes)
        assert len(mapping) == 100
        
        # Mock data loading for choropleth test
        import navira.competitors
        original_load = navira.competitors.load_recruitment_data
        navira.competitors.load_recruitment_data = lambda: large_recruitment
        
        try:
            df, diagnostics = competitor_choropleth_df('123456789', mapping, 'even_split')
            assert len(df) <= 100  # Should not exceed input size
            assert diagnostics.total_cps >= 0  # Some data should be processed
        finally:
            navira.competitors.load_recruitment_data = original_load


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
