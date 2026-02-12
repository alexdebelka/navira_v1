"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts';

interface AdvancedProcedureMetricsProps {
    procedureDetails: any[]; // procedure_details.csv
    loading: boolean;
}

export function AdvancedProcedureMetrics({ procedureDetails, loading }: AdvancedProcedureMetricsProps) {

    const metrics = useMemo(() => {
        if (!procedureDetails || procedureDetails.length === 0) return null;

        const procedureNames: Record<string, string> = {
            'SLE': 'Sleeve Gastrectomy',
            'BPG': 'Gastric Bypass',
            'ANN': 'Gastric Banding',
            'REV': 'Revision Surgery',
            'ABL': 'Band Removal',
            'DBP': 'Bilio-pancreatic Diversion',
            'GVC': 'Gastroplasty',
            'NDD': 'Not Defined'
        };

        // 1. Robotic Rates 2024
        const data2024 = procedureDetails.filter((d: any) => d.year === 2024);

        // Group by procedure type
        const procStats: Record<string, { total: number, robotic: number }> = {};
        data2024.forEach((d: any) => {
            const type = d.procedure_type;
            if (!procStats[type]) procStats[type] = { total: 0, robotic: 0 };
            procStats[type].total += d.procedure_count;
            if (d.surgical_approach === 'ROB') {
                procStats[type].robotic += d.procedure_count;
            }
        });

        const roboticRates = Object.keys(procStats)
            .filter(type => ['SLE', 'BPG'].includes(type)) // Only major types
            .map(type => ({
                name: procedureNames[type] || type,
                rate: (procStats[type].robotic / procStats[type].total) * 100,
                robotic: procStats[type].robotic,
                total: procStats[type].total
            }))
            .sort((a, b) => b.rate - a.rate);

        // 2. Primary vs Revision 2024
        let primary = { total: 0, robotic: 0 };
        let revision = { total: 0, robotic: 0 };

        data2024.forEach((d: any) => {
            const isRev = d.is_revision === 1;
            if (isRev) {
                revision.total += d.procedure_count;
                if (d.surgical_approach === 'ROB') revision.robotic += d.procedure_count;
            } else {
                primary.total += d.procedure_count;
                if (d.surgical_approach === 'ROB') primary.robotic += d.procedure_count;
            }
        });

        // 3. Trends 2020-2024
        const trends: Record<number, Record<string, { total: number, robotic: number }>> = {};
        procedureDetails.forEach((d: any) => {
            if (d.year < 2020 || d.year > 2024) return;
            if (!trends[d.year]) trends[d.year] = {};

            const type = d.procedure_type;
            if (!trends[d.year][type]) trends[d.year][type] = { total: 0, robotic: 0 };

            trends[d.year][type].total += d.procedure_count;
            if (d.surgical_approach === 'ROB') trends[d.year][type].robotic += d.procedure_count;
        });

        const trendChartData = [];
        for (let year = 2020; year <= 2024; year++) {
            if (!trends[year]) continue;
            const point: any = { year };
            ['SLE', 'BPG'].forEach(type => {
                const stats = trends[year][type];
                if (stats && stats.total > 0) {
                    point[procedureNames[type] || type] = (stats.robotic / stats.total) * 100;
                } else {
                    point[procedureNames[type] || type] = 0;
                }
            });
            trendChartData.push(point);
        }

        return {
            roboticRates,
            primary,
            revision,
            trendChartData
        };

    }, [procedureDetails]);

    if (loading || !metrics) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card variant="glass">
                    <CardHeader>
                        <CardTitle className="text-lg">Primary Procedures (2024)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 gap-4 text-center">
                            <div>
                                <p className="text-2xl font-bold text-white">{metrics.primary.total.toLocaleString()}</p>
                                <p className="text-xs text-gray-500">Total Primary</p>
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-primary">{((metrics.primary.robotic / metrics.primary.total) * 100).toFixed(1)}%</p>
                                <p className="text-xs text-gray-500">Robotic Rate</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardHeader>
                        <CardTitle className="text-lg">Revision Procedures (2024)</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="grid grid-cols-2 gap-4 text-center">
                            <div>
                                <p className="text-2xl font-bold text-white">{metrics.revision.total.toLocaleString()}</p>
                                <p className="text-xs text-gray-500">Total Revisions</p>
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-primary">{((metrics.revision.robotic / metrics.revision.total) * 100).toFixed(1)}%</p>
                                <p className="text-xs text-gray-500">Robotic Rate</p>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="h-[400px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Robotic Adoption by Procedure (2024)</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart layout="vertical" data={metrics.roboticRates} margin={{ top: 20, right: 30, left: 100, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis type="number" domain={[0, 100]} stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis dataKey="name" type="category" width={120} stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }} />
                                <Bar dataKey="rate" fill="#a855f7" radius={[0, 4, 4, 0]} name="Robotic Rate %" />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                <Card className="h-[400px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Robotic Adoption Trends (2020-2024)</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={metrics.trendChartData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} label={{ value: '%', angle: -90, position: 'insideLeft' }} />
                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }} />
                                <Legend />
                                <Line type="monotone" dataKey="Sleeve Gastrectomy" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
                                <Line type="monotone" dataKey="Gastric Bypass" stroke="#ec4899" strokeWidth={2} dot={{ r: 4 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
