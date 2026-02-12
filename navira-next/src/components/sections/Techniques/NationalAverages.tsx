"use client";

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';

interface NationalAveragesProps {
    hospitalData: any[]; // TAB_VOL_HOP_YEAR
    activityData: any[]; // TAB_TCN_NATL_YEAR
    roboticData: any[];  // TAB_APP_NATL_YEAR
    loading: boolean;
}

export function NationalAverages({ hospitalData, activityData, roboticData, loading }: NationalAveragesProps) {
    const [show2024Only, setShow2024Only] = useState(false);

    const stats = useMemo(() => {
        if (!hospitalData || !activityData || !roboticData) return null;

        const years = show2024Only ? [2024] : [2021, 2022, 2023, 2024];

        // 1. Avg Procedures per Hospital
        // Filter hospital data by year
        const hospFiltered = hospitalData.filter((d: any) => years.includes(d.annee));
        // Correct calculation: Sum of all procedures / Number of unique hospitals (for each year, then average? Or sum of all / sum of unique hospitals?)
        // Python logic: 
        //   df_vol_filtered = year_filter(df_vol)
        //   hospital_totals = df_vol_filtered.groupby('finessGeoDP')['n'].sum()
        //   avg_procedures_per_hospital = int(hospital_totals.mean())
        // So: Group by hospital ID -> sum volume across all selected years -> take mean of those sums.
        // Wait, if multiple years selected, Python logic sums ALL volume for that hospital over the period?
        // "hospital_totals = df_vol_filtered.groupby('finessGeoDP')['n'].sum()" -> YES, this sums 4 years of volume.
        // "hospital_totals.mean()" -> Average TOTAL volume per hospital over the 4-year period.
        // Example: Hospital A does 100/year. 4 years = 400 total. Mean = 400.
        // The metric label is "Avg Procedures per Hospital". If it's over 4 years, it might be misleading if interpreted as annual.
        // The python code says: "**{avg_procedures_per_hospital:,} procedures** over 4 years" (line 511). Okay, so it IS total over the period.

        // JS Implementation:
        const hospMap: Record<string, number> = {};
        hospFiltered.forEach((d: any) => {
            hospMap[d.finessGeoDP] = (hospMap[d.finessGeoDP] || 0) + (d.n || 0);
        });
        const hospValues = Object.values(hospMap);
        const avgProcedures = hospValues.length > 0
            ? Math.round(hospValues.reduce((a, b) => a + b, 0) / hospValues.length)
            : 0;


        // 2. Avg Sleeve %
        const actFiltered = activityData.filter((d: any) => years.includes(d.annee));
        const totalProceduresTcn = actFiltered.reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
        const sleeveProcedures = actFiltered
            .filter((d: any) => d.baria_t === 'SLE')
            .reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
        const sleevePct = totalProceduresTcn > 0 ? (sleeveProcedures / totalProceduresTcn) * 100 : 0;


        // 3. Avg Robotic %
        const robFiltered = roboticData.filter((d: any) => years.includes(d.annee));
        const totalProceduresApp = robFiltered.reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
        const roboticProcedures = robFiltered
            .filter((d: any) => d.vda === 'ROB')
            .reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
        const roboticPct = totalProceduresApp > 0 ? (roboticProcedures / totalProceduresApp) * 100 : 0;

        return {
            avgProcedures,
            sleevePct,
            roboticPct
        };

    }, [hospitalData, activityData, roboticData, show2024Only]);

    if (loading || !stats) {
        return (
            <Card className="h-[200px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <h2 className="text-2xl font-bold text-white">National Averages Summary ({show2024Only ? "2024" : "2021-2024"})</h2>
                <div className="flex items-center gap-2 bg-surface-elevated/50 p-2 rounded-lg border border-white/5">
                    <span className="text-sm text-gray-400">Show 2024 Data Only</span>
                    <input
                        type="checkbox"
                        checked={show2024Only}
                        onChange={(e) => setShow2024Only(e.target.checked)}
                        className="toggle toggle-primary toggle-sm accent-primary h-4 w-4"
                    />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Avg Procedures per Hospital</p>
                        <p className="text-3xl font-bold text-white mt-1">{stats.avgProcedures.toLocaleString()}</p>
                        <p className="text-xs text-gray-500 mt-1">{show2024Only ? "in 2024" : "over 4 years"}</p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Avg Sleeve Gastrectomy</p>
                        <p className="text-3xl font-bold text-blue-400 mt-1">{stats.sleevePct.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 mt-1">of total procedures</p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Avg Robotic Approach</p>
                        <p className="text-3xl font-bold text-purple-400 mt-1">{stats.roboticPct.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 mt-1">adoption rate</p>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
