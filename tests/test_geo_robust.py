"""
Comprehensive tests for robust GeoJSON loading and INSEE detection functionality.
"""

import json
import os
import tempfile
import gzip
from pathlib import Path
import pytest
import pandas as pd

# Test data
SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"code": "01001", "nom": "L'Abergement-Clémenciat"},
            "geometry": {"type": "Point", "coordinates": [5.0, 46.0]}
        },
        {
            "type": "Feature", 
            "properties": {"code": "01002", "nom": "L'Abergement-de-Varey"},
            "geometry": {"type": "Point", "coordinates": [5.1, 46.1]}
        },
        {
            "type": "Feature",
            "properties": {"code": "2A001", "nom": "Ajaccio"},
            "geometry": {"type": "Point", "coordinates": [8.7, 41.9]}
        }
    ]
}

SAMPLE_GEOJSON_INSEE_COM = {
    "type": "FeatureCollection", 
    "features": [
        {
            "type": "Feature",
            "properties": {"INSEE_COM": "01001", "NOM": "Test Commune 1"},
            "geometry": {"type": "Point", "coordinates": [5.0, 46.0]}
        },
        {
            "type": "Feature",
            "properties": {"INSEE_COM": "01002", "NOM": "Test Commune 2"}, 
            "geometry": {"type": "Point", "coordinates": [5.1, 46.1]}
        }
    ]
}


class TestGeoJSONLoading:
    """Test the robust GeoJSON loading functionality."""
    
    def test_load_from_explicit_path(self):
        """Test loading GeoJSON from explicit path."""
        from navira.geo import load_communes_geojson
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(SAMPLE_GEOJSON, f)
            temp_path = f.name
        
        try:
            geojson_data, diagnostics = load_communes_geojson(path_override=temp_path)
            
            assert geojson_data is not None
            assert len(geojson_data['features']) == 3
            assert diagnostics['feature_count'] == 3
            assert diagnostics['resolved_path'] == os.path.abspath(temp_path)
            assert diagnostics['insee_key'] == 'code'
            assert not diagnostics['errors']
        finally:
            os.unlink(temp_path)
    
    def test_load_gzipped_file(self):
        """Test loading gzipped GeoJSON file."""
        from navira.geo import load_communes_geojson
        
        with tempfile.NamedTemporaryFile(suffix='.geojson.gz', delete=False) as f:
            temp_path = f.name
        
        try:
            with gzip.open(temp_path, 'wt', encoding='utf-8') as f:
                json.dump(SAMPLE_GEOJSON, f)
            
            geojson_data, diagnostics = load_communes_geojson(path_override=temp_path)
            
            assert geojson_data is not None
            assert len(geojson_data['features']) == 3
            assert diagnostics['feature_count'] == 3
            assert not diagnostics['errors']
        finally:
            os.unlink(temp_path)
    
    def test_file_not_found(self):
        """Test handling of missing GeoJSON file."""
        from navira.geo import load_communes_geojson
        
        geojson_data, diagnostics = load_communes_geojson(path_override="/nonexistent/path.geojson")
        
        assert geojson_data is None
        assert len(diagnostics['errors']) > 0
        assert "File not found" in diagnostics['errors'][0]
    
    def test_invalid_json(self):
        """Test handling of invalid JSON file."""
        from navira.geo import load_communes_geojson
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            f.write("invalid json content {")
            temp_path = f.name
        
        try:
            geojson_data, diagnostics = load_communes_geojson(path_override=temp_path)
            
            assert geojson_data is None
            assert any("Invalid JSON" in error for error in diagnostics['errors'])
        finally:
            os.unlink(temp_path)
    
    def test_invalid_geojson_structure(self):
        """Test handling of invalid GeoJSON structure."""
        from navira.geo import load_communes_geojson
        
        invalid_geojson = {"type": "InvalidType", "features": []}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
            json.dump(invalid_geojson, f)
            temp_path = f.name
        
        try:
            geojson_data, diagnostics = load_communes_geojson(path_override=temp_path)
            
            assert geojson_data is None
            assert any("not a FeatureCollection" in error for error in diagnostics['errors'])
        finally:
            os.unlink(temp_path)


class TestINSEEDetection:
    """Test INSEE property key detection."""
    
    def test_detect_code_property(self):
        """Test detection of 'code' property."""
        from navira.geo import detect_insee_property
        
        result = detect_insee_property(SAMPLE_GEOJSON)
        assert result == "code"
    
    def test_detect_insee_com_property(self):
        """Test detection of 'INSEE_COM' property."""
        from navira.geo import detect_insee_property
        
        result = detect_insee_property(SAMPLE_GEOJSON_INSEE_COM)
        assert result == "INSEE_COM"
    
    def test_detect_no_valid_property(self):
        """Test handling when no valid INSEE property is found."""
        from navira.geo import detect_insee_property
        
        invalid_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "Test", "invalid_code": "abc"},
                    "geometry": {"type": "Point", "coordinates": [0, 0]}
                }
            ]
        }
        
        result = detect_insee_property(invalid_geojson)
        assert result is None
    
    def test_empty_geojson(self):
        """Test handling of empty GeoJSON."""
        from navira.geo import detect_insee_property
        
        empty_geojson = {"type": "FeatureCollection", "features": []}
        result = detect_insee_property(empty_geojson)
        assert result is None


class TestINSEEValidation:
    """Test INSEE code validation functions."""
    
    def test_valid_insee_codes(self):
        """Test validation of various valid INSEE codes."""
        from navira.geo import _is_valid_insee_code
        
        valid_codes = ["01001", "75001", "13001", "2A001", "2B001", 1001, 75001]
        
        for code in valid_codes:
            assert _is_valid_insee_code(code), f"Code {code} should be valid"
    
    def test_invalid_insee_codes(self):
        """Test rejection of invalid INSEE codes."""
        from navira.geo import _is_valid_insee_code
        
        invalid_codes = [None, "", "abc", "123", "000", "99999999", "3A001"]
        
        for code in invalid_codes:
            assert not _is_valid_insee_code(code), f"Code {code} should be invalid"
    
    def test_property_coverage_validation(self):
        """Test property coverage validation."""
        from navira.geo import _validate_insee_property_coverage
        
        features = SAMPLE_GEOJSON['features']
        
        # Should pass with 'code' property (100% coverage)
        assert _validate_insee_property_coverage(features, 'code')
        
        # Should fail with 'nom' property (0% coverage of INSEE codes)
        assert not _validate_insee_property_coverage(features, 'nom')


class TestChoroplethValidation:
    """Test choropleth input validation."""
    
    def test_valid_choropleth_inputs(self):
        """Test validation with valid DataFrame and GeoJSON."""
        from navira.geo import validate_choropleth_inputs
        
        # Create test DataFrame
        df = pd.DataFrame({
            'insee5': ['01001', '01002', '2A001'],
            'value': [10, 20, 15]
        })
        
        diagnostics = validate_choropleth_inputs(df, 'insee5', SAMPLE_GEOJSON, 'code')
        
        assert diagnostics['df_rows'] == 3
        assert diagnostics['df_unique_insee'] == 3
        assert diagnostics['geo_features'] == 3
        assert diagnostics['intersection_count'] == 3
        assert diagnostics['coverage_pct'] == 100.0
        assert not diagnostics['errors']
    
    def test_partial_coverage(self):
        """Test validation with partial coverage."""
        from navira.geo import validate_choropleth_inputs
        
        # DataFrame with some codes not in GeoJSON
        df = pd.DataFrame({
            'insee5': ['01001', '01002', '99999'],  # 99999 not in GeoJSON
            'value': [10, 20, 15]
        })
        
        diagnostics = validate_choropleth_inputs(df, 'insee5', SAMPLE_GEOJSON, 'code')
        
        assert diagnostics['coverage_pct'] < 100.0
        assert diagnostics['intersection_count'] == 2
        assert '99999' in diagnostics['missing_from_geo']
    
    def test_empty_dataframe(self):
        """Test validation with empty DataFrame."""
        from navira.geo import validate_choropleth_inputs
        
        df = pd.DataFrame()
        diagnostics = validate_choropleth_inputs(df, 'insee5', SAMPLE_GEOJSON, 'code')
        
        assert len(diagnostics['errors']) > 0
        assert "DataFrame is empty" in diagnostics['errors'][0]
    
    def test_missing_column(self):
        """Test validation with missing column."""
        from navira.geo import validate_choropleth_inputs
        
        df = pd.DataFrame({'other_col': [1, 2, 3]})
        diagnostics = validate_choropleth_inputs(df, 'insee5', SAMPLE_GEOJSON, 'code')
        
        assert len(diagnostics['errors']) > 0
        assert "Column 'insee5' not found" in diagnostics['errors'][0]


class TestFilteredLoading:
    """Test filtered GeoJSON loading."""
    
    def test_filtered_loading(self):
        """Test loading filtered GeoJSON with specific INSEE codes."""
        from navira.geo import load_communes_geojson_filtered
        
        # Mock the main loader to return our sample data
        import navira.geo
        original_loader = navira.geo.load_communes_geojson
        
        def mock_loader(*args, **kwargs):
            return SAMPLE_GEOJSON, {}
        
        navira.geo.load_communes_geojson = mock_loader
        
        try:
            # Request only specific codes
            filtered_geojson = load_communes_geojson_filtered(['01001', '2A001'])
            
            assert filtered_geojson is not None
            assert len(filtered_geojson['features']) == 2
            
            # Check that only requested codes are included
            codes = {f['properties']['code'] for f in filtered_geojson['features']}
            assert codes == {'01001', '2A001'}
            
        finally:
            navira.geo.load_communes_geojson = original_loader
    
    def test_filtered_loading_no_matches(self):
        """Test filtered loading when no codes match."""
        from navira.geo import load_communes_geojson_filtered
        
        import navira.geo
        original_loader = navira.geo.load_communes_geojson
        
        def mock_loader(*args, **kwargs):
            return SAMPLE_GEOJSON, {}
        
        navira.geo.load_communes_geojson = mock_loader
        
        try:
            # Request codes that don't exist
            filtered_geojson = load_communes_geojson_filtered(['99999'])
            
            # Should return original GeoJSON when no matches
            assert filtered_geojson is not None
            assert len(filtered_geojson['features']) == 3  # Original count
            
        finally:
            navira.geo.load_communes_geojson = original_loader


class TestBackwardCompatibility:
    """Test backward compatibility functions."""
    
    def test_detect_insee_key_compatibility(self):
        """Test that detect_insee_key still works."""
        from navira.geo import detect_insee_key
        
        result = detect_insee_key(SAMPLE_GEOJSON)
        assert result == "code"
    
    def test_get_geojson_summary_compatibility(self):
        """Test that get_geojson_summary works with and without diagnostics."""
        from navira.geo import get_geojson_summary
        
        # Test with diagnostics
        diagnostics = {
            'feature_count': 3,
            'insee_key': 'code',
            'file_size': 1024
        }
        
        summary_with_diag = get_geojson_summary(SAMPLE_GEOJSON, diagnostics)
        assert "3 communes loaded" in summary_with_diag
        assert "INSEE key: code" in summary_with_diag
        
        # Test without diagnostics (backward compatibility)
        summary_without_diag = get_geojson_summary(SAMPLE_GEOJSON)
        assert "3 communes loaded" in summary_without_diag
        assert "INSEE key: code" in summary_without_diag


if __name__ == "__main__":
    pytest.main([__file__])
