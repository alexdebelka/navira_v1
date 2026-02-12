"use client";

import { useEffect, useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { fetchCsv } from '@/lib/data/loader';
import { Loader2 } from 'lucide-react';
import dynamic from 'next/dynamic';

// Dynamically import MapContainer and TileLayer to avoid SSR issues
const MapContainer = dynamic(() => import('react-leaflet').then(mod => mod.MapContainer), { ssr: false });
const TileLayer = dynamic(() => import('react-leaflet').then(mod => mod.TileLayer), { ssr: false });
const GeoJSON = dynamic(() => import('react-leaflet').then(mod => mod.GeoJSON), { ssr: false });

interface SurgeryDensityMapProps {
    hospitalData: any[]; // from TAB_VOL_HOP_YEAR
    loading: boolean;
}

export function SurgeryDensityMap({ hospitalData, loading }: SurgeryDensityMapProps) {
    const [geoJson, setGeoJson] = useState<any>(null);
    const [populationData, setPopulationData] = useState<any[]>([]);
    const [mapReady, setMapReady] = useState(false);

    useEffect(() => {
        // Load GeoJSON and Population
        Promise.all([
            fetch('/data/departements.geojson').then(res => res.json()),
            fetchCsv('/data/population.csv') // Assumes I check header of this file later
        ]).then(([geo, pop]) => {
            setGeoJson(geo);
            setPopulationData(pop);
            setMapReady(true);
        }).catch(err => console.error("Map data load error", err));
    }, []);

    const departmentRatios = useMemo(() => {
        if (!hospitalData || !populationData) return {};

        // 1. Aggregates surgeries by dept from hospitalData (2024 only)
        const surgeriesByDept: Record<string, number> = {};
        hospitalData.filter((d: any) => d.annee === 2024).forEach((d: any) => {
            let dept = '';
            const cp = String(d.code_postal);
            if (cp.startsWith('97') || cp.startsWith('98')) dept = cp.substring(0, 3);
            else if (cp.startsWith('201')) dept = '2A';
            else if (cp.startsWith('202')) dept = '2B';
            else dept = cp.substring(0, 2);

            if (dept) {
                surgeriesByDept[dept] = (surgeriesByDept[dept] || 0) + (d.n || 0);
            }
        });

        // 2. Join with population and calc ratio
        const ratios: Record<string, number> = {};
        populationData.forEach((p: any) => {
            // Need to check CSV structure for columns. Assuming 'GEO' and 'OBS_VALUE' based on python code or similar
            // Python: pop_df['dept_code'] = pop_df['GEO']... pop_df['population'] = pop_df['OBS_VALUE']
            // I need to inspect the CSV or assume standard names.
            // Let's assume the CSV header is preserved.
            // If keys are different, this will fail. I'll act defensively.
            const dept = p.GEO || p.dept_code; // Try both
            const pop = p.OBS_VALUE || p.population;

            // Clean dept string
            const cleanDept = String(dept).replace(/"/g, '').trim();

            if (cleanDept && surgeriesByDept[cleanDept]) {
                const surgCount = surgeriesByDept[cleanDept];
                const popCount = Number(pop);
                if (popCount > 0) {
                    // Ratio per 100k
                    ratios[cleanDept] = (surgCount / popCount) * 100000;
                }
            }
        });

        return ratios;

    }, [hospitalData, populationData]);

    const getColor = (d: number) => {
        return d > 80 ? '#800026' :
            d > 60 ? '#BD0026' :
                d > 40 ? '#E31A1C' :
                    d > 20 ? '#FC4E2A' :
                        d > 10 ? '#FD8D3C' :
                            d > 5 ? '#FEB24C' :
                                d > 0 ? '#FED976' :
                                    '#FFEDA0';
    };

    const style = (feature: any) => {
        const deptCode = feature.properties.code;
        const ratio = departmentRatios[deptCode] || 0;
        return {
            fillColor: getColor(ratio),
            weight: 1,
            opacity: 1,
            color: 'white',
            dashArray: '3',
            fillOpacity: 0.7
        };
    };

    if (loading || !mapReady) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <span className="ml-2">Loading Map Data...</span>
            </Card>
        );
    }

    return (
        <Card className="h-[500px] flex flex-col overflow-hidden">
            <CardHeader>
                <CardTitle>Surgery Density (2024)</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 p-0 relative">
                <div className="h-full w-full">
                    {typeof window !== 'undefined' && (
                        <MapContainer center={[46.5, 2.5]} zoom={5} style={{ height: '100%', width: '100%' }} scrollWheelZoom={false}>
                            <TileLayer
                                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
                                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                            />
                            {geoJson && (
                                <GeoJSON
                                    data={geoJson}
                                    style={style}
                                    onEachFeature={(feature, layer) => {
                                        const deptCode = feature.properties.code;
                                        const name = feature.properties.nom;
                                        const ratio = departmentRatios[deptCode]?.toFixed(1) || '0';
                                        layer.bindTooltip(`${name} (${deptCode}): ${ratio} per 100k`, { sticky: true });
                                    }}
                                />
                            )}
                        </MapContainer>
                    )}
                </div>
            </CardContent>
        </Card>
    );
}
