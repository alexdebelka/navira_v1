"""
Unit tests for robust KM computation system.
Tests different datasets producing different curves and caching behavior.
"""

import pytest
import pandas as pd
import numpy as np
from km import compute_km_from_aggregates, debug_signature
from utils.cache import dataframe_md5


def make_km_test_data(hazards: list, time_labels: list = None) -> pd.DataFrame:
    """Create synthetic KM test data with specified hazards per interval."""
    n_intervals = len(hazards)
    
    if time_labels is None:
        time_labels = [f"Y{i+1}" for i in range(n_intervals)]
    
    return pd.DataFrame({
        "time": time_labels,
        "at_risk": [100] * n_intervals,  # Constant at-risk population
        "events": [int(100 * h) for h in hazards],  # Events based on hazard rates
    })


class TestKMComputation:
    """Test suite for KM computation functions."""
    
    def test_km_curves_differ_with_different_hazards(self):
        """Test that different hazard patterns produce different KM curves."""
        # Decreasing hazard over time
        df1 = make_km_test_data([0.05, 0.04, 0.03])
        
        # Increasing hazard over time  
        df2 = make_km_test_data([0.02, 0.05, 0.06])
        
        # Compute KM curves
        curve1 = compute_km_from_aggregates(df1, "time", "events", "at_risk")
        curve2 = compute_km_from_aggregates(df2, "time", "events", "at_risk")
        
        # Curves should not be identical
        assert not curve1.empty
        assert not curve2.empty
        assert len(curve1) == len(curve2) == 3
        
        # Survival values should differ
        survival1 = curve1['survival'].round(6)
        survival2 = curve2['survival'].round(6)
        assert not all(survival1 == survival2), "KM curves should differ with different hazards"
        
        # First curve should have higher final survival (lower cumulative hazard)
        assert survival1.iloc[-1] > survival2.iloc[-1], "Decreasing hazard should yield higher final survival"
    
    def test_km_computation_with_zero_events(self):
        """Test KM computation handles zero events correctly."""
        df = make_km_test_data([0.0, 0.0, 0.0])  # No events
        
        curve = compute_km_from_aggregates(df, "time", "events", "at_risk")
        
        assert not curve.empty
        assert all(curve['survival'] == 1.0), "Zero events should maintain 100% survival"
        assert all(curve['hazard'] == 0.0), "Zero events should have zero hazard"
    
    def test_km_computation_with_missing_data(self):
        """Test KM computation handles missing/invalid data gracefully."""
        # Empty DataFrame
        empty_df = pd.DataFrame()
        curve_empty = compute_km_from_aggregates(empty_df, "time", "events", "at_risk")
        assert curve_empty.empty
        
        # DataFrame with missing required columns
        bad_df = pd.DataFrame({"wrong_col": [1, 2, 3]})
        with pytest.raises(ValueError, match="Missing required columns"):
            compute_km_from_aggregates(bad_df, "time", "events", "at_risk")
    
    def test_km_computation_with_groups(self):
        """Test KM computation with multiple groups."""
        # Create data for two groups with different hazard patterns
        df = pd.DataFrame({
            "time": ["Y1", "Y2", "Y3"] * 2,
            "group": ["A"] * 3 + ["B"] * 3,
            "events": [5, 4, 3, 2, 5, 6],  # Different patterns
            "at_risk": [100] * 6
        })
        
        curve = compute_km_from_aggregates(df, "time", "events", "at_risk", group_cols=["group"])
        
        assert not curve.empty
        assert len(curve) == 6  # 3 time points × 2 groups
        assert set(curve['group'].unique()) == {"A", "B"}
        
        # Groups should have different survival curves
        group_a = curve[curve['group'] == 'A']['survival']
        group_b = curve[curve['group'] == 'B']['survival']
        assert not all(group_a.round(6) == group_b.round(6)), "Different groups should have different curves"
    
    def test_km_computation_time_ordering(self):
        """Test that KM computation respects time ordering."""
        # Create data with explicit time ordering
        df = pd.DataFrame({
            "time": ["2023 Q1", "2023 Q2", "2023 Q3"],
            "events": [5, 10, 15],
            "at_risk": [100, 95, 85]
        })
        
        time_order = ["2023 Q1", "2023 Q2", "2023 Q3"]
        
        curve = compute_km_from_aggregates(
            df, "time", "events", "at_risk", 
            time_order=time_order
        )
        
        assert not curve.empty
        assert list(curve['time']) == time_order, "Time ordering should be preserved"
        
        # Survival should be monotonically decreasing
        survival_vals = curve['survival'].values
        assert all(survival_vals[i] >= survival_vals[i+1] for i in range(len(survival_vals)-1)), \
            "Survival should be monotonically decreasing"


class TestKMCaching:
    """Test suite for KM caching behavior."""
    
    def test_different_data_produces_different_hashes(self):
        """Test that different datasets produce different cache keys."""
        df1 = make_km_test_data([0.05, 0.04, 0.03])
        df2 = make_km_test_data([0.02, 0.05, 0.06])
        
        hash1 = dataframe_md5(df1)
        hash2 = dataframe_md5(df2)
        
        assert hash1 != hash2, "Different datasets should produce different hashes"
    
    def test_identical_data_produces_same_hash(self):
        """Test that identical datasets produce the same cache key."""
        df1 = make_km_test_data([0.05, 0.04, 0.03])
        df2 = make_km_test_data([0.05, 0.04, 0.03])  # Identical
        
        hash1 = dataframe_md5(df1)
        hash2 = dataframe_md5(df2)
        
        assert hash1 == hash2, "Identical datasets should produce same hash"
    
    def test_km_computation_with_cache_key(self):
        """Test that KM computation works with explicit cache keys."""
        df = make_km_test_data([0.05, 0.04, 0.03])
        data_hash = dataframe_md5(df)
        
        # Should not raise any errors
        curve = compute_km_from_aggregates(
            df, "time", "events", "at_risk",
            data_hash=data_hash,
            cache_version="test_v1"
        )
        
        assert not curve.empty
        assert len(curve) == 3


class TestKMDebugging:
    """Test suite for KM debugging utilities."""
    
    def test_debug_signature_generation(self):
        """Test that debug signatures are generated correctly."""
        df = make_km_test_data([0.05, 0.04, 0.03])
        
        sig = debug_signature(df)
        
        assert 'n_rows' in sig
        assert 'n_events' in sig
        assert 'intervals' in sig
        assert 'hash' in sig
        
        assert sig['n_rows'] == 3
        assert sig['n_events'] > 0  # Should have some events
        assert len(sig['intervals']) <= 10  # Truncated for brevity
    
    def test_debug_signature_with_empty_data(self):
        """Test debug signature generation with empty data."""
        empty_df = pd.DataFrame()
        
        sig = debug_signature(empty_df)
        
        assert 'n_rows' in sig
        assert sig['n_rows'] == 0


class TestKMEdgeCases:
    """Test suite for KM edge cases and error conditions."""
    
    def test_km_with_zero_at_risk(self):
        """Test KM computation filters out zero at-risk periods."""
        df = pd.DataFrame({
            "time": ["Y1", "Y2", "Y3"],
            "events": [5, 0, 3],
            "at_risk": [100, 0, 50]  # Zero at-risk in Y2
        })
        
        curve = compute_km_from_aggregates(df, "time", "events", "at_risk")
        
        # Should only have 2 time points (Y1 and Y3)
        assert len(curve) == 2
        assert set(curve['time']) == {"Y1", "Y3"}
    
    def test_km_with_events_exceeding_at_risk(self):
        """Test KM computation handles invalid event counts gracefully."""
        df = pd.DataFrame({
            "time": ["Y1", "Y2", "Y3"],
            "events": [5, 150, 3],  # 150 events > 100 at-risk
            "at_risk": [100, 100, 50]
        })
        
        curve = compute_km_from_aggregates(df, "time", "events", "at_risk")
        
        # Should still compute, but hazard might be > 1.0
        assert not curve.empty
        assert curve.loc[curve['time'] == 'Y2', 'hazard'].iloc[0] > 1.0
    
    def test_km_with_non_numeric_events(self):
        """Test KM computation coerces non-numeric values."""
        df = pd.DataFrame({
            "time": ["Y1", "Y2", "Y3"],
            "events": ["5", None, "3.5"],  # Mixed types
            "at_risk": [100, 100, 50]
        })
        
        curve = compute_km_from_aggregates(df, "time", "events", "at_risk")
        
        assert not curve.empty
        # Should coerce and fill NaN with 0
        assert all(pd.notna(curve['events']))
        assert all(curve['events'] >= 0)


if __name__ == "__main__":
    # Run tests if executed directly
    pytest.main([__file__, "-v"])
