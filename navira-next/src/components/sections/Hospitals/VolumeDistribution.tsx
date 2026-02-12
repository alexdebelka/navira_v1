"use client";

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface VolumeDistributionProps {
    hospitalData: any[];     // TAB_VOL_HOP_YEAR
    nationalData: any[];     // TAB_VOL_NATL_YEAR
    loading: boolean;
}

export function VolumeDistribution({ hospitalData, nationalData, loading }: VolumeDistributionProps) {
    const [showComparison, setShowComparison] = useState(true);

    const stats = useMemo(() => {
        if (!hospitalData || hospitalData.length === 0) return null;

        // Filter 2024
        const df2024 = hospitalData.filter((d: any) => d.annee === 2024);
        const totalHospitals = new Set(df2024.map((d: any) => d.finessGeoDP)).size;
        const totalSurgeries = df2024.reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
        const avgPerHospital = totalHospitals > 0 ? totalSurgeries / totalHospitals : 0;

        // Assign Bins
        const assignBin = (n: number) => {
            if (n < 50) return "<50";
            if (n < 100) return "50-100";
            if (n < 200) return "100-200";
            return ">200";
        };

        const bins2024 = { "<50": 0, "50-100": 0, "100-200": 0, ">200": 0 } as Record<string, number>;
        df2024.forEach((d: any) => {
            const bin = assignBin(d.n || 0);
            if (bins2024[bin] !== undefined) bins2024[bin]++;
        });

        const lowVolumeCount = bins2024["<50"];
        const highVolumeCount = bins2024["100-200"] + bins2024[">200"];

        // Baseline (2021-2023)
        const dfBaseline = hospitalData.filter((d: any) => [2021, 2022, 2023].includes(d.annee));
        // Implementation of baseline logic (Group by Year then Bin, then Average)
        // Simplified:
        const baselineByYear = { 2021: { ...bins2024, "<50": 0, "50-100": 0, "100-200": 0, ">200": 0 }, 2022: { ...bins2024, "<50": 0 }, 2023: { ...bins2024, "<50": 0 } } as any;

        // Reset baseline counts
        Object.keys(baselineByYear).forEach(y => {
            baselineByYear[y] = { "<50": 0, "50-100": 0, "100-200": 0, ">200": 0 };
        });

        dfBaseline.forEach((d: any) => {
            const year = d.annee;
            if (baselineByYear[year]) {
                const bin = assignBin(d.n || 0);
                baselineByYear[year][bin]++;
            }
        });

        const avgBaseline = { "<50": 0, "50-100": 0, "100-200": 0, ">200": 0 } as Record<string, number>;
        Object.keys(avgBaseline).forEach(bin => {
            const sum = baselineByYear[2021][bin] + baselineByYear[2022][bin] + baselineByYear[2023][bin];
            avgBaseline[bin] = sum / 3;
        });

        const lowVolumeBase = avgBaseline["<50"];
        const highVolumeBase = avgBaseline["100-200"] + avgBaseline[">200"];

        return {
            totalHospitals,
            totalSurgeries,
            avgPerHospital,
            lowVolumeCount,
            lowVolumeDelta: lowVolumeCount - lowVolumeBase,
            highVolumeCount,
            highVolumeDelta: highVolumeCount - highVolumeBase,
            bins2024,
            avgBaseline
        };

    }, [hospitalData]);

    const chartData = useMemo(() => {
        if (!stats) return [];
        const order = ["<50", "50-100", "100-200", ">200"];
        return order.map(bin => ({
            name: bin,
            Current: stats.bins2024[bin],
            Baseline: parseFloat(stats.avgBaseline[bin].toFixed(1))
        }));
    }, [stats]);

    if (loading || !stats) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Total Hospitals (2024)</p>
                        <p className="text-3xl font-bold text-white mt-1">{stats.totalHospitals}</p>
                        <p className="text-xs text-gray-500 mt-1">Avg: {Math.round(stats.avgPerHospital)} proc/hosp</p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Total Surgeries (2024)</p>
                        <p className="text-3xl font-bold text-white mt-1">{stats.totalSurgeries.toLocaleString()}</p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Hospitals &lt;50/year</p>
                        <p className="text-3xl font-bold text-white mt-1">{stats.lowVolumeCount}</p>
                        <p className={`text-xs mt-1 font-medium ${stats.lowVolumeDelta > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {stats.lowVolumeDelta > 0 ? '+' : ''}{stats.lowVolumeDelta.toFixed(1)} vs avg
                        </p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Hospitals &ge;100/year</p>
                        <p className="text-3xl font-bold text-white mt-1">{stats.highVolumeCount}</p>
                        <p className={`text-xs mt-1 font-medium ${stats.highVolumeDelta > 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {stats.highVolumeDelta > 0 ? '+' : ''}{stats.highVolumeDelta.toFixed(1)} vs avg
                        </p>
                    </CardContent>
                </Card>
            </div>

            <Card className="h-[400px] flex flex-col">
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle>Volume Distribution by Hospital</CardTitle>
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">Show Baseline</span>
                        <input
                            type="checkbox"
                            checked={showComparison}
                            onChange={(e) => setShowComparison(e.target.checked)}
                            className="toggle toggle-primary toggle-sm accent-primary h-4 w-4"
                        />
                    </div>
                </CardHeader>
                <CardContent className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                            <XAxis dataKey="name" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <div className="glass-card p-3 text-xs border border-white/10">
                                                <p className="font-bold mb-2">{label} procedures/year</p>
                                                <p style={{ color: payload[0].color }}>2024: {payload[0].value}</p>
                                                {payload[1] && <p style={{ color: payload[1].color }}>Avg 21-23: {payload[1].value}</p>}
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Legend />
                            <Bar dataKey="Current" name="2024" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                            {showComparison && (
                                <Bar dataKey="Baseline" name="2021-2023 Avg" fill="#3b82f6" radius={[4, 4, 0, 0]} fillOpacity={0.5} />
                            )}
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    );
}
