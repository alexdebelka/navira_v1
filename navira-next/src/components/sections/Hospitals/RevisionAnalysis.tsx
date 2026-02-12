"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface RevisionAnalysisProps {
    revNatl: any[];
    revStatus: any[];
    rev12m: any[];
    loading: boolean;
}

export function RevisionAnalysis({ revNatl, revStatus, rev12m, loading }: RevisionAnalysisProps) {
    const kpis = useMemo(() => {
        if (!revNatl || revNatl.length === 0) return null;
        const natl = revNatl[0];
        const r12 = rev12m && rev12m.length > 0 ? rev12m[0] : null;

        return {
            overallRate: natl.PCT_rev,
            totalRevisions: natl.TOT_rev,
            totalProcedures: natl.TOT,
            rate12m: r12 ? r12.PCT_rev : 0,
            revisions12m: r12 ? r12.TOT_rev : 0,
            primaryRate: 100 - natl.PCT_rev,
            primaryCount: natl.TOT - natl.TOT_rev
        };
    }, [revNatl, rev12m]);

    const chartData = useMemo(() => {
        if (!revStatus || revStatus.length === 0) return [];

        // Mapping
        const statusMapping: Record<string, string> = {
            'public academic': 'Public – Univ.',
            'public': 'Public – Non-Acad.',
            'private for profit': 'Private – For-profit',
            'private not-for-profit': 'Private – Not-for-profit'
        };

        const data = revStatus
            .map((d: any) => ({
                name: statusMapping[d.statut] || d.statut,
                rate: d.PCT_rev,
                revisions: d.TOT_rev,
                total: d.TOT
            }))
            .filter((d: any) => d.name) // Filter invalid
            .sort((a: any, b: any) => a.rate - b.rate); // Sort ascending for bar chart Y axis

        return data;
    }, [revStatus]);

    if (loading || !kpis) {
        return (
            <Card className="h-[350px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Overall Revision Rate</p>
                        <p className="text-3xl font-bold text-white mt-1">{kpis.overallRate.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 mt-1">{kpis.totalRevisions.toLocaleString()} revisions</p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Last 12 Months</p>
                        <p className="text-3xl font-bold text-white mt-1">{kpis.rate12m.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 mt-1">{kpis.revisions12m.toLocaleString()} revisions</p>
                    </CardContent>
                </Card>
                <Card variant="glass">
                    <CardContent className="p-6 text-center">
                        <p className="text-sm text-gray-400">Primary Procedures</p>
                        <p className="text-3xl font-bold text-white mt-1">{kpis.primaryRate.toFixed(1)}%</p>
                        <p className="text-xs text-gray-500 mt-1">{kpis.primaryCount.toLocaleString()} primary</p>
                    </CardContent>
                </Card>
            </div>

            <Card className="h-[400px] flex flex-col">
                <CardHeader>
                    <CardTitle>Revision Rate by Hospital Affiliation</CardTitle>
                </CardHeader>
                <CardContent className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart layout="vertical" data={chartData} margin={{ top: 20, right: 30, left: 100, bottom: 5 }}>
                            <XAxis type="number" domain={[0, 'auto']} hide />
                            <YAxis dataKey="name" type="category" width={120} stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        const data = payload[0].payload;
                                        return (
                                            <div className="glass-card p-3 text-xs border border-white/10">
                                                <p className="font-bold mb-1">{data.name}</p>
                                                <p className="text-orange-400 mb-1">Rate: {data.rate.toFixed(1)}%</p>
                                                <p className="text-gray-400">Revisions: {data.revisions}</p>
                                                <p className="text-gray-400">Total: {data.total}</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Bar dataKey="rate" fill="#f97316" radius={[0, 4, 4, 0]}>
                                {chartData.map((entry: any, index: number) => (
                                    <Cell key={`cell-${index}`} fill="#f97316" fillOpacity={0.8} />
                                ))}
                                {/* Recharts doesn't support 'text' inside bar easily without custom label list, relying on tooltip */}
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    );
}
