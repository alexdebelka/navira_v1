import { useState, useEffect } from 'react';
import { fetchCsv } from '@/lib/data/loader';
import Papa from 'papaparse';

export interface HospitalData {
    details: any | null;
    volume: any[];          // TAB_VOL_HOP_YEAR filtered
    trends: any | null;     // TAB_TREND_HOP filtered
    procedures: any[];      // TAB_TCN_HOP_12M filtered
    approaches: any[];      // TAB_APP_HOP_YEAR filtered
    revisional: any | null; // TAB_REV_HOP_12M filtered
    complications: any[];   // TAB_COMPL_HOP_YEAR filtered
    loading: boolean;
    error: Error | null;
}

export function useHospitalData(hospitalId: string | null) {
    const [data, setData] = useState<HospitalData>({
        details: null,
        volume: [],
        trends: null,
        procedures: [],
        approaches: [],
        revisional: null,
        complications: [],
        loading: false,
        error: null
    });

    useEffect(() => {
        if (!hospitalId) {
            setData(prev => ({ ...prev, loading: false }));
            return;
        }

        let isMounted = true;
        setData(prev => ({ ...prev, loading: true, error: null }));

        const loadData = async () => {
            try {
                // 1. Load Hospital Details (from 01_hospitals_redux)
                // We assume this might be loaded already or needs fetching. 
                // For simplicity, we fetch it again or pass it if available.
                // Here we fetch basics.

                const [
                    hospitalsRedux,
                    volHopYear,
                    trendHop,
                    tcnHop12m,
                    appHopYear,
                    revHop12m,
                    complHopYear
                ] = await Promise.all([
                    fetchCsv('/data/01_hospitals_redux.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_VOL_HOP_YEAR.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_TREND_HOP.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_TCN_HOP_12M.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_APP_HOP_YEAR.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_REV_HOP_12M.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_COMPL_HOP_YEAR.csv')
                ]);

                if (!isMounted) return;

                // Helper to normalize ID
                const normId = (id: any) => String(id).trim().replace(/^0+/, ''); // Remove leading zeros for comparison if needed, or keep strict
                const targetId = String(hospitalId).trim();

                // Filter Data
                const details = hospitalsRedux.find((h: any) => String(h.finessGeo).trim() === targetId) || null;
                const volume = volHopYear.filter((d: any) => String(d.finessGeoDP).trim() === targetId);
                const trends = trendHop.find((d: any) => String(d.finessGeoDP).trim() === targetId) || null;
                const procedures = tcnHop12m.filter((d: any) => String(d.finessGeoDP).trim() === targetId);
                const approaches = appHopYear.filter((d: any) => String(d.finessGeoDP).trim() === targetId);
                const revisional = revHop12m.find((d: any) => String(d.finessGeoDP).trim() === targetId) || null;
                const complications = complHopYear.filter((d: any) => String(d.finessGeoDP).trim() === targetId);

                setData({
                    details,
                    volume,
                    trends,
                    procedures,
                    approaches,
                    revisional,
                    complications,
                    loading: false,
                    error: null
                });

            } catch (err: any) {
                console.error("Error loading hospital data:", err);
                if (isMounted) {
                    setData(prev => ({ ...prev, loading: false, error: err }));
                }
            }
        };

        loadData();

        return () => { isMounted = false; };
    }, [hospitalId]);

    return data;
}
