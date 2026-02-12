"use client";

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts';

interface ProcedureChartsProps {
    activityData: any[]; // TAB_TCN_NATL_YEAR
    loading: boolean;
}

export function ProcedureCharts({ activityData, loading }: ProcedureChartsProps) {
    const [show2024Only, setShow2024Only] = useState(false);

    const procedureNameMap: Record<string, string> = {
        'SLE': 'Sleeve Gastrectomy',
        'BPG': 'Gastric Bypass',
        'ANN': 'Gastric Banding',
        'ABL': 'Band Removal',
        'REV': 'Revision Surgery',
        'DBP': 'Bilio-pancreatic Diversion',
        'GVC': 'Gastroplasty',
        'NDD': 'Not Defined'
    };

    const chartData = useMemo(() => {
        if (!activityData || activityData.length === 0) return { totalProcedures: [], trendData: [] };

        // Filter relevant years
        const years = show2024Only ? [2024] : [2020, 2021, 2022, 2023, 2024];
        const filteredData = activityData.filter((d: any) => years.includes(d.annee));

        // --- Chart 1: Total Procedures by Type ---
        const totalsByType: Record<string, number> = {};
        let grandTotal = 0;

        filteredData.forEach((d: any) => {
            const type = d.baria_t;
            const count = d.n || 0;
            totalsByType[type] = (totalsByType[type] || 0) + count;
            grandTotal += count;
        });

        const otherCodes = ['NDD', 'GVC', 'DBP', 'ANN', 'ABL', 'REV']; // Including more in "Other" for cleaner chart if needed, but following python logic
        // Python logic: 'NDD', 'GVC', 'DBP' are explicitly "Other". 
        // Wait, python logic in `render_techniques` lines 108-109: other_procedures = ['NDD', 'GVC', 'DBP']
        // It keeps ANN, ABL, REV as separate if they have data.

        // Let's stick to the python logic for "Other"
        const strictOtherCodes = ['NDD', 'GVC', 'DBP'];
        const displayData: any[] = [];
        let otherCount = 0;

        Object.keys(totalsByType).forEach(code => {
            if (strictOtherCodes.includes(code)) {
                otherCount += totalsByType[code];
            } else {
                const name = procedureNameMap[code] || code;
                displayData.push({
                    name,
                    value: totalsByType[code],
                    percentage: grandTotal > 0 ? (totalsByType[code] / grandTotal) * 100 : 0
                });
            }
        });

        if (otherCount > 0) {
            displayData.push({
                name: 'Other',
                value: otherCount,
                percentage: grandTotal > 0 ? (otherCount / grandTotal) * 100 : 0
            });
        }

        const sortedTotalProcedures = displayData.sort((a, b) => b.value - a.value); // Descending for readability

        // --- Chart 2: Procedure Mix Trends ---
        // Stacked bar of percentage share per year
        // We need data for all years in range, even if show2024Only is true (though if 2024 only, it's just one bar)

        // Python logic: 
        // Sleeve, Bypass, Other (EVERYTHING else)
        const trendYears = show2024Only ? [2024] : [2021, 2022, 2023, 2024]; // Python uses 2021-2024 for trends
        const trendData: any[] = [];

        trendYears.forEach(year => {
            const yearData = activityData.filter((d: any) => d.annee === year);
            const sleeve = yearData.filter((d: any) => d.baria_t === 'SLE').reduce((acc: number, curr: any) => acc + curr.n, 0);
            const bypass = yearData.filter((d: any) => d.baria_t === 'BPG').reduce((acc: number, curr: any) => acc + curr.n, 0);

            // "Other" for trends includes everything else: ANN, ABL, REV, NDD, GVC, DBP
            const others = yearData.filter((d: any) => !['SLE', 'BPG'].includes(d.baria_t)).reduce((acc: number, curr: any) => acc + curr.n, 0);

            const total = sleeve + bypass + others;

            if (total > 0) {
                trendData.push({
                    year,
                    Sleeve: (sleeve / total) * 100,
                    Bypass: (bypass / total) * 100,
                    Other: (others / total) * 100,
                    totalCount: total
                });
            }
        });

        return { totalProcedures: sortedTotalProcedures, trendData };

    }, [activityData, show2024Only]);

    if (loading) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-end mb-4">
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

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="h-[500px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Total Procedures by Type ({show2024Only ? "2024" : "2020-2024"})</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart layout="vertical" data={chartData.totalProcedures} margin={{ top: 20, right: 30, left: 100, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis type="number" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis dataKey="name" type="category" width={120} stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <Tooltip
                                    content={({ active, payload, label }) => {
                                        if (active && payload && payload.length) {
                                            const data = payload[0].payload;
                                            return (
                                                <div className="glass-card p-3 text-xs border border-white/10">
                                                    <p className="font-bold mb-1">{data.name}</p>
                                                    <p className="text-blue-400 mb-1">Count: {data.value.toLocaleString()}</p>
                                                    <p className="text-gray-400">Share: {data.percentage.toFixed(1)}%</p>
                                                </div>
                                            );
                                        }
                                        return null;
                                    }}
                                />
                                <Bar dataKey="value" fill="#4C84C8" radius={[0, 4, 4, 0]} barSize={30} />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                <Card className="h-[500px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Procedure Mix Trends ({show2024Only ? "2024" : "2021-2024"})</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={chartData.trendData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} unit="%" />
                                <Tooltip
                                    content={({ active, payload, label }) => {
                                        if (active && payload && payload.length) {
                                            return (
                                                <div className="glass-card p-3 text-xs border border-white/10">
                                                    <p className="font-bold mb-1">Year {label}</p>
                                                    {payload.map((entry: any, index: number) => (
                                                        <p key={index} style={{ color: entry.color }}>
                                                            {entry.name}: {entry.value.toFixed(1)}%
                                                        </p>
                                                    ))}
                                                </div>
                                            );
                                        }
                                        return null;
                                    }}
                                />
                                <Legend />
                                <Bar dataKey="Sleeve" stackId="a" fill="#4C84C8" name="Sleeve" />
                                <Bar dataKey="Bypass" stackId="a" fill="#7aa7f7" name="Gastric Bypass" />
                                <Bar dataKey="Other" stackId="a" fill="#f59e0b" name="Other" />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
