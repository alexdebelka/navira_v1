"""
Folium map renderer with choropleth layers for recruitment zone visualization.

This module provides functionality for:
- Creating interactive maps with hospital and competitor markers
- Adding toggleable choropleth layers for recruitment zones
- Integrating tooltips with commune names and patient counts
- Managing layer controls and visual styling
"""

import folium
import os
from folium import plugins
import pandas as pd
import streamlit as st
from typing import Dict, List, Optional, Any, Tuple
import branca.colormap as cm
from .competitors import get_top_competitors, competitor_choropleth_df, get_competitor_names, ChloroplethDiagnostics
from .data_loaders import build_postal_to_insee_mapping, load_communes_data
from .geo import load_communes_geojson, detect_insee_key, get_geojson_summary


class MapConfig:
    """Configuration constants for map rendering."""
    DEFAULT_CENTER = [46.5, 2.5]  # Center of France
    DEFAULT_ZOOM = 6
    HOSPITAL_ZOOM = 10
    MAX_ZOOM = 13
    CHOROPLETH_OPACITY = 0.7
    CHOROPLETH_LINE_OPACITY = 0.3
    COLORS = ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#2c7fb8', '#253494']


def create_recruitment_map(
    hospital_finess: str,
    hospital_info: Optional[Dict[str, Any]] = None,
    establishments_df: Optional[pd.DataFrame] = None,
    allocation: str = "even_split",
    max_competitors: int = 5
) -> Tuple[folium.Map, List[ChloroplethDiagnostics]]:
    """
    Create interactive Folium map with recruitment zone choropleths.
    
    Args:
        hospital_finess: 9-digit FINESS code of focal hospital
        hospital_info: Optional dict with hospital coordinates and name
        establishments_df: DataFrame with hospital information for competitor names
        allocation: Allocation strategy ("even_split" or "no_split")
        max_competitors: Maximum number of competitor layers to show
        
    Returns:
        Tuple of (folium.Map, List[ChloroplethDiagnostics])
        
    Notes:
        - Creates base map centered on hospital or France
        - Adds hospital marker and competitor markers if coordinates available
        - Generates up to max_competitors choropleth layers
        - Includes layer control and legend
        - Returns diagnostics for each choropleth layer
    """
    # Determine map center
    if hospital_info and 'latitude' in hospital_info and 'longitude' in hospital_info:
        try:
            center = [float(hospital_info['latitude']), float(hospital_info['longitude'])]
            zoom_start = MapConfig.HOSPITAL_ZOOM
        except (ValueError, TypeError):
            center = MapConfig.DEFAULT_CENTER
            zoom_start = MapConfig.DEFAULT_ZOOM
    else:
        center = MapConfig.DEFAULT_CENTER
        zoom_start = MapConfig.DEFAULT_ZOOM
    
    # Create base map
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles='CartoDB positron',
        max_zoom=MapConfig.MAX_ZOOM
    )
    # Ensure markers are always above choropleths using map panes
    try:
        from folium.map import CustomPane
        CustomPane("choropleths", z_index=390).add_to(m)
        CustomPane("markers", z_index=650).add_to(m)
    except Exception:
        pass
    
    # Load required data
    communes_df = load_communes_data()
    cp_to_insee = build_postal_to_insee_mapping(communes_df)
    
    # Get top competitors first
    competitors = get_top_competitors(hospital_finess, max_competitors)
    if not competitors:
        st.info("ℹ️ No competitors found for this hospital.")
        _add_hospital_marker(m, hospital_finess, hospital_info)
        return m, []
    
    # Get needed INSEE codes to filter GeoJSON for performance
    needed_insee_codes = []
    # Include selected hospital first so we can build its own layer distinctly
    focal_df, _ = competitor_choropleth_df(hospital_finess, cp_to_insee, allocation)
    if not focal_df.empty:
        needed_insee_codes.extend(focal_df['insee5'].tolist())
    for competitor in competitors[:max_competitors]:
        df, _ = competitor_choropleth_df(competitor, cp_to_insee, allocation)
        if not df.empty:
            needed_insee_codes.extend(df['insee5'].tolist())
    
    # Add aggregation target codes for major cities when we have arrondissement data
    has_paris_arr = any(code.startswith('751') for code in needed_insee_codes)
    has_marseille_arr = any(code.startswith('132') for code in needed_insee_codes)
    has_lyon_arr = any(code.startswith('6938') or code.startswith('6912') for code in needed_insee_codes)
    
    if has_paris_arr:
        needed_insee_codes.append('75056')  # Single Paris polygon
    if has_marseille_arr:
        needed_insee_codes.append('13055')  # Single Marseille polygon  
    if has_lyon_arr:
        needed_insee_codes.extend(['69380', '69123'])  # Lyon polygons
    
    # Load GeoJSON - simple and direct approach
    from .geo import load_communes_geojson_filtered, load_communes_geojson_simple, detect_insee_key
    
    # Try to load GeoJSON data
    
    # Check if we need Paris arrondissement detail
    has_paris_arrondissements = any(code.startswith('751') for code in needed_insee_codes)
    
    if has_paris_arrondissements:
        # Build a combined GeoJSON: nationwide communes + Paris arrondissements
        try:
            import json
            # Base: all needed communes
            base_geo = load_communes_geojson_filtered(needed_insee_codes) if needed_insee_codes else load_communes_geojson_simple()
            base_features = list(base_geo.get('features', [])) if base_geo else []
            # Remove single-Paris polygon if present
            filtered_base = []
            for feat in base_features:
                props = feat.get('properties', {})
                if str(props.get('code', '')).zfill(5) == '75056':
                    continue
                filtered_base.append(feat)
            # Load official arrondissement shapes and normalize property key to 'code'
            with open('data/paris_arrondissements_official.geojson', 'r', encoding='utf-8') as f:
                arr_geo = json.load(f)
            arr_features = []
            for feat in arr_geo.get('features', []):
                props = feat.get('properties', {})
                insee = str(props.get('c_arinsee', '')).zfill(5)
                if not insee:
                    continue
                # Duplicate under 'code' so downstream uses a single key
                props['code'] = insee
                feat['properties'] = props
                arr_features.append(feat)
            geojson_data = {"type": "FeatureCollection", "features": filtered_base + arr_features}
        except Exception:
            # Fallback to communes only
            geojson_data = load_communes_geojson_filtered(needed_insee_codes) if needed_insee_codes else load_communes_geojson_simple()
    else:
        # Use regular communes GeoJSON
        if needed_insee_codes:
            geojson_data = load_communes_geojson_filtered(needed_insee_codes)
        else:
            geojson_data = load_communes_geojson_simple()
    
    diagnostics_list = []
    
    # Check if GeoJSON loaded successfully
    if not geojson_data or 'features' not in geojson_data or not geojson_data['features']:
        # Fallback: still return map with hospital marker (no extra UI)
        _add_hospital_marker(m, hospital_finess, hospital_info)
        return m, diagnostics_list
    
    # Detect INSEE key. We standardize on 'code' even when arrondissements are merged
    insee_key = detect_insee_key(geojson_data)
    if not insee_key:
        # Fallback to 'code' which is used by our communes GeoJSON
        insee_key = 'code'
        
        if not insee_key:
            _add_hospital_marker(m, hospital_finess, hospital_info)
            return m, diagnostics_list
    
    # Get competitor names for display
    competitor_names = get_competitor_names(competitors, establishments_df if establishments_df is not None else pd.DataFrame())
    
    # Create choropleth layers
    global_min_value = float('inf')
    global_max_value = float('-inf')
    choropleth_data = {}
    
    # Pre-calculate all choropleth data to determine global scale
    for i, competitor_finess in enumerate(competitors):
        df, diagnostics = competitor_choropleth_df(competitor_finess, cp_to_insee, allocation)
        diagnostics_list.append(diagnostics)
        
        if not df.empty:
            choropleth_data[competitor_finess] = df
            min_val = df['value'].min()
            max_val = df['value'].max()
            global_min_value = min(global_min_value, min_val)
            global_max_value = max(global_max_value, max_val)
    
    # Handle case where no data is available
    if global_min_value == float('inf'):
        global_min_value = 0
        global_max_value = 1
    
    # Create colormaps: blue scale for selected hospital, orange-red for competitors
    comp_colormap = cm.linear.YlOrRd_06.scale(global_min_value, global_max_value)
    comp_colormap.caption = 'Patients recruited (competitors)'
    focal_colormap = cm.linear.Blues_06.scale(global_min_value, global_max_value)
    focal_colormap.caption = 'Patients recruited (selected)'
    
    # Add focal hospital choropleth layer first (distinct color)
    if not focal_df.empty:
        _add_choropleth_layer(
            m,
            geojson_data,
            focal_df,
            insee_key,
            layer_name=f"Selected hospital",
            colormap=focal_colormap,
            show=True,
            communes_df=communes_df
        )

    # Add competitor choropleth layers
    for i, competitor_finess in enumerate(competitors):
        if competitor_finess in choropleth_data:
            competitor_name = competitor_names.get(competitor_finess, f"Competitor {i+1}")

            _add_choropleth_layer(
                m, 
                geojson_data, 
                choropleth_data[competitor_finess], 
                insee_key,
                competitor_name,
                comp_colormap,
                show=False,
                communes_df=communes_df
            )
    
    # Add colormap legends to map
    focal_colormap.add_to(m)
    comp_colormap.add_to(m)
    
    # Add markers in separate toggleable layers
    markers_fg_selected = folium.FeatureGroup(name='Selected hospital marker', show=True)
    markers_fg_comp = folium.FeatureGroup(name='Competitor markers', show=True)

    _add_hospital_marker(markers_fg_selected, hospital_finess, hospital_info)
    _add_competitor_markers(markers_fg_comp, competitors, establishments_df)

    markers_fg_selected.add_to(m)
    markers_fg_comp.add_to(m)
    
    # Ensure marker groups always stay on top, even after toggling overlays
    try:
        js = folium.Element(
            f"""
            <script>
            var mapRef = {m.get_name()};
            function bringMarkersFront() {{
              try {{
                {markers_fg_selected.get_name()}.bringToFront();
                {markers_fg_comp.get_name()}.bringToFront();
              }} catch(e) {{}}
            }}
            mapRef.on('overlayadd', function(e) {{ bringMarkersFront(); }});
            mapRef.on('layeradd', function(e) {{ bringMarkersFront(); }});
            // initial
            bringMarkersFront();
            </script>
            """
        )
        m.get_root().html.add_child(js)
    except Exception:
        pass

    # Add layer control (collapsed for cleaner UI)
    folium.LayerControl(collapsed=True, position='topright').add_to(m)
    
    return m, diagnostics_list


def _add_choropleth_layer(
    m: folium.Map, 
    geojson_data: Dict[str, Any], 
    choropleth_df: pd.DataFrame,
    insee_key: str,
    layer_name: str,
    colormap: Any,
    show: bool = True,
    communes_df: Optional[pd.DataFrame] = None
) -> None:
    """Add a single choropleth layer to the map."""
    try:
        # Create value mapping for styling
        value_map = dict(zip(choropleth_df['insee5'].astype(str), choropleth_df['value']))

        # Detect which INSEE codes are present in the GeoJSON
        feature_codes = set()
        for f in geojson_data.get('features', []):
            props = f.get('properties', {})
            if insee_key in props:
                c = str(props[insee_key]).strip().upper()
                feature_codes.add(c if c.startswith(('2A','2B')) else c.zfill(5))
        
        # Presence checks (no UI output)
        paris_geo_codes = [c for c in feature_codes if c.startswith('75')]
        
        # Check if we're using arrondissement polygons (no aggregation needed)
        has_arrondissement_polygons = any(code.startswith('751') for code in feature_codes)
        if has_arrondissement_polygons:
            # Skip aggregation - show data directly on arrondissement polygons
            skip_aggregation = True
        else:
            skip_aggregation = False

        # Apply aggregation only if we don't have arrondissement polygons
        if not skip_aggregation:
            # If the GeoJSON does NOT contain arrondissement polygons for major cities,
            # aggregate arrondissement values into the single commune code present.
            def _collapse_arr_to_city(value_map_in: Dict[str, float]) -> Dict[str, float]:
                vm = value_map_in.copy()
                # Paris: arr 75101..75120 -> 75056
                has_75056 = '75056' in feature_codes
                has_arrondissements = any(code.startswith('751') for code in feature_codes)
                # Paris aggregation only when arrondissement polygons are absent
                
                if has_75056 and not has_arrondissements:
                    total = 0.0
                    arrondissement_count = 0
                    for i in range(1, 21):
                        k = f"751{str(i).zfill(2)}"
                        if k in vm:
                            total += float(vm.pop(k))
                            arrondissement_count += 1
                    if total > 0:
                        vm['75056'] = vm.get('75056', 0.0) + total
                    
                # Marseille: arr 13201..13216 -> 13055
                if ('13055' in feature_codes) and not any(code.startswith('132') for code in feature_codes):
                    total = 0.0
                    for i in range(1, 17):
                        k = f"132{str(i).zfill(2)}"
                        if k in vm:
                            total += float(vm.pop(k))
                    if total > 0:
                        vm['13055'] = vm.get('13055', 0.0) + total
                # Lyon: arr 69381..69389 -> 69380 (or legacy 69123 if present)
                lyon_city_code = '69380' if '69380' in feature_codes else ('69123' if '69123' in feature_codes else None)
                if lyon_city_code and not any(code.startswith('6938') for code in feature_codes):
                    total = 0.0
                    for i in range(1, 10):
                        k = f"6938{i}"
                        if k in vm:
                            total += float(vm.pop(k))
                    if total > 0:
                        vm[lyon_city_code] = vm.get(lyon_city_code, 0.0) + total
                return vm

            value_map = _collapse_arr_to_city(value_map)

        # Create commune name mapping for tooltips
        name_map = {}
        if communes_df is not None and not communes_df.empty:
            if 'codeInsee' in communes_df.columns and 'nomCommune' in communes_df.columns:
                name_map = dict(zip(
                    communes_df['codeInsee'].astype(str).str.zfill(5),
                    communes_df['nomCommune'].astype(str)
                ))
        
        # Create feature group for this layer
        feature_group = folium.FeatureGroup(name=layer_name, show=show)
        
        # Style function
        def style_function(feature):
            insee_code = str(feature['properties'].get(insee_key, '')).zfill(5)
            value = value_map.get(insee_code, 0)
            
            if value > 0:
                return {
                    'fillColor': colormap(value),
                    'color': '#333333',
                    'weight': 0.5,
                    'fillOpacity': MapConfig.CHOROPLETH_OPACITY,
                    'opacity': MapConfig.CHOROPLETH_LINE_OPACITY
                }
            else:
                return {
                    'fillColor': '#f0f0f0',
                    'color': '#cccccc',
                    'weight': 0.5,
                    'fillOpacity': 0.1,
                    'opacity': 0.2
                }
        
        # Tooltip function
        def create_tooltip(feature):
            insee_code = str(feature['properties'].get(insee_key, '')).zfill(5)
            value = value_map.get(insee_code, 0)
            commune_name = name_map.get(insee_code, f"INSEE {insee_code}")
            
            if value > 0:
                return f"<b>{commune_name}</b><br/>Patients: {value:.1f}"
            else:
                return f"<b>{commune_name}</b><br/>No patients"
        
        # Add GeoJSON layer
        folium.GeoJson(
            geojson_data,
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=[],
                aliases=[],
                labels=False,
                sticky=True,
                opacity=0.9
            )
        ).add_to(feature_group)
        
        # Add layer to map
        feature_group.add_to(m)
        
    except Exception as e:
        st.warning(f"Error adding choropleth layer '{layer_name}': {e}")


def _add_hospital_marker(
    m: folium.Map, 
    hospital_finess: str, 
    hospital_info: Optional[Dict[str, Any]]
) -> None:
    """Add hospital marker to map."""
    try:
        if hospital_info and 'latitude' in hospital_info and 'longitude' in hospital_info:
            location = [float(hospital_info['latitude']), float(hospital_info['longitude'])]
            name = hospital_info.get('name', f'Hospital {hospital_finess}')
            
            folium.Marker(
                location=location,
                popup=f"<b>{name}</b><br/>FINESS: {hospital_finess}",
                tooltip=f"Selected Hospital: {name}",
                icon=folium.Icon(color='red', icon='hospital-o', prefix='fa')
            ).add_to(m)
            
    except (ValueError, TypeError) as e:
        st.warning(f"Could not add hospital marker: invalid coordinates ({e})")


def _add_competitor_markers(
    m: folium.Map, 
    competitors: List[str], 
    establishments_df: Optional[pd.DataFrame]
) -> None:
    """Add competitor hospital markers as circles with size gradation."""
    if establishments_df is None or establishments_df.empty:
        return
    
    required_cols = ['id', 'name', 'latitude', 'longitude']
    if not all(col in establishments_df.columns for col in required_cols):
        return
    
    # Define circle sizes and colors for competitors (largest to smallest)
    base_radius = 20
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
    
    try:
        # Format FINESS codes for matching
        establishments_copy = establishments_df.copy()
        establishments_copy['id'] = establishments_copy['id'].astype(str).str.zfill(9)
        
        for i, competitor_finess in enumerate(competitors):
            finess_formatted = str(competitor_finess).zfill(9)
            matching = establishments_copy[establishments_copy['id'] == finess_formatted]
            
            if not matching.empty:
                row = matching.iloc[0]
                try:
                    location = [float(row['latitude']), float(row['longitude'])]
                    name = str(row['name'])
                    
                    # Calculate radius based on rank (1st largest, 2nd smaller, etc.)
                    radius = base_radius - (i * 3)  # Decrease by 3 pixels per rank
                    radius = max(radius, 8)  # Minimum size of 8 pixels
                    
                    # Get color for this competitor
                    color = colors[i % len(colors)]
                    
                    # Add circle marker
                    folium.CircleMarker(
                        location=location,
                        radius=radius,
                        popup=f"<b>{name}</b><br/>FINESS: {competitor_finess}<br/>Rank: #{i+1}",
                        tooltip=f"Competitor #{i+1}: {name}",
                        color=color,  # Use the same color but darker for border
                        weight=3,     # Slightly thicker border
                        fillColor=color,
                        fillOpacity=0.6  # Lighter center fill
                    ).add_to(m)
                    
                except (ValueError, TypeError):
                    continue  # Skip invalid coordinates
                    
    except Exception as e:
        st.warning(f"Error adding competitor markers: {e}")


def render_map_diagnostics(diagnostics_list: List[ChloroplethDiagnostics], competitor_names: Dict[str, str]) -> None:
    """
    Render diagnostics information for choropleth layers.
    
    Args:
        diagnostics_list: List of diagnostics from choropleth generation
        competitor_names: Mapping of FINESS codes to hospital names
    """
    if not diagnostics_list:
        return
    
    with st.expander("📊 Data Quality Diagnostics", expanded=False):
        st.markdown("**Postal Code → INSEE Mapping Results:**")
        
        for i, diag in enumerate(diagnostics_list):
            if diag.total_cps > 0:
                # Get competitor name
                competitor_finess = list(competitor_names.keys())[i] if i < len(competitor_names) else f"Competitor {i+1}"
                competitor_name = competitor_names.get(competitor_finess, f"Competitor {i+1}")
                
                # Calculate metrics
                match_rate = (diag.matched_cps / diag.total_cps) * 100
                
                # Color code based on match rate
                if match_rate >= 90:
                    status_color = "🟢"
                elif match_rate >= 70:
                    status_color = "🟡" 
                else:
                    status_color = "🔴"
                
                st.markdown(f"**{status_color} {competitor_name}**")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Postal Codes", f"{diag.matched_cps}/{diag.total_cps}", f"{match_rate:.1f}% matched")
                with col2:
                    st.metric("Total Patients", f"{diag.original_total:.0f}")
                with col3:
                    if abs(diag.allocation_difference) > 0.01:
                        st.metric("Allocated", f"{diag.allocated_total:.0f}", f"{diag.allocation_difference:+.0f}")
                    else:
                        st.metric("Allocated", f"{diag.allocated_total:.0f}", "✓")
                
                # Show unmatched examples if any
                if diag.unmatched_cps > 0 and diag.unmatched_cp_examples:
                    examples = ", ".join(diag.unmatched_cp_examples[:5])
                    if len(diag.unmatched_cp_examples) > 5:
                        examples += f" (+{len(diag.unmatched_cp_examples)-5} more)"
                    st.caption(f"⚠️ Unmatched postal codes: {examples}")
                
                st.markdown("---")
        
        # Overall summary
        total_layers = len([d for d in diagnostics_list if d.total_cps > 0])
        total_matched = sum(d.matched_cps for d in diagnostics_list)
        total_cps = sum(d.total_cps for d in diagnostics_list)
        
        if total_cps > 0:
            overall_rate = (total_matched / total_cps) * 100
            st.markdown(f"**Overall: {total_matched:,}/{total_cps:,} postal codes mapped ({overall_rate:.1f}%) across {total_layers} competitors**")
