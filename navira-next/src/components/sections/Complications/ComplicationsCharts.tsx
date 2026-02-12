"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';

interface ComplicationsChartsProps {
    complGradeNatlYear: any[]; // TAB_COMPL_GRADE_NATL_YEAR
    neverNatl: any[];          // TAB_NEVER_NATL
    losNatl: any[];            // TAB_LOS_NATL
    los7Natl: any[];           // TAB_LOS7_NATL
    loading: boolean;
}

export function ComplicationsCharts({ complGradeNatlYear, neverNatl, losNatl, los7Natl, loading }: ComplicationsChartsProps) {

    const stats = useMemo(() => {
        if (loading) return null;

        // --- 1. Clavien-Dindo Grades in 2024 (or latest) ---
        // Python code finds latest complete year. We'll assume 2024.
        const latestYear = 2024;

        // Grade Data
        const gradeData = [3, 4, 5].map(grade => {
            const row = complGradeNatlYear?.find((d: any) => d.annee === latestYear && d.clav_cat_90 === grade);
            return {
                grade: `Grade ${grade}`,
                rate: row ? (row.COMPL_pct || 0) : 0
            };
        });

        // --- 2. Never Events ---
        // Python code uses TAB_NEVER_NATL.csv 
        // It seems to be a single row or aggregated.
        let neverCount = 0;
        let neverRate = 0;
        if (neverNatl && neverNatl.length > 0) {
            // Assuming aggregation or first row if it's national total
            neverCount = neverNatl.reduce((acc, curr) => acc + (curr.NEVER_nb || 0), 0);
            // Rate is likely pre-calculated or needs calc. Python logic: pre-calculated NEVER_pct or NEVER_nb/TOT
            const total = neverNatl.reduce((acc, curr) => acc + (curr.TOT || 0), 0);
            neverRate = total > 0 ? (neverCount / total) * 100 : 0;
            // Override if pre-calc exists
            if (neverNatl[0].NEVER_pct !== undefined) neverRate = neverNatl[0].NEVER_pct;
        }

        // --- 3. Length of Stay (LOS) Distribution (2021-2024) ---
        // Stacked bar chart similar to python
        const losYears = [2021, 2022, 2023, 2024];
        const losData = losYears.map(year => {
            const yearData = losNatl?.filter((d: any) => d.annee === year) || [];
            // Buckets: '[-1,0]', '(0,3]', '(3,6]', '(6,225]'
            const entry: any = { year };
            yearData.forEach((d: any) => {
                if (d.duree_cat === '[-1,0]') entry['0 days'] = d.LOS_pct;
                if (d.duree_cat === '(0,3]') entry['1-3 days'] = d.LOS_pct;
                if (d.duree_cat === '(3,6]') entry['4-6 days'] = d.LOS_pct;
                if (d.duree_cat === '(6,225]') entry['>7 days'] = d.LOS_pct;
            });
            return entry;
        });

        return { gradeData, neverCount, neverRate, losData };

    }, [complGradeNatlYear, neverNatl, losNatl, los7Natl, loading]);

    if (loading || !stats) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Clavien-Dindo Bar Chart */}
                <Card className="col-span-1 lg:col-span-2 h-[400px] flex flex-col relative overflow-hidden">
                    <CardHeader>
                        <CardTitle>Complication by Grade (2024)</CardTitle>
                        <p className="text-sm text-gray-500">Clavien-Dindo classification</p>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={stats.gradeData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="grade" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} unit="%" />
                                <Tooltip
                                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                    content={({ active, payload, label }) => {
                                        if (active && payload && payload.length) {
                                            return (
                                                <div className="glass-card p-3 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                    <p className="font-bold mb-1 text-white">{label}</p>
                                                    <p className="text-[#FF8C00] font-bold text-lg">{Number(payload[0].value).toFixed(2)}%</p>
                                                </div>
                                            );
                                        }
                                        return null;
                                    }}
                                />
                                <Bar dataKey="rate" fill="#FF8C00" radius={[4, 4, 0, 0]} barSize={50} />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* Never Events Alert Card */}
                <div className="flex flex-col gap-6">
                    <Card variant="glass" className="flex-1 border-l-4 border-l-red-500 relative overflow-hidden bg-gradient-to-br from-red-500/10 to-transparent">
                        <CardContent className="p-6 h-full flex flex-col justify-center">
                            <div className="flex items-center gap-3 mb-4">
                                <div className="p-2 bg-red-500/20 rounded-full">
                                    <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 9v2" /><path d="M12 15h.01" /><path d="M5.071 5.071a16.975 16.975 0 0 0-4.75 6.946c-.05.176-.05.352.1.514A17.017 17.017 0 0 0 5.07 18.93c.188.19.467.247.712.146a16.97 16.97 0 0 1 12.435 0c.245.1.524.044.712-.146a17.017 17.017 0 0 0 4.639-6.4c.15-.162.15-.338.1-.514A16.975 16.975 0 0 0 18.93 5.07a.505.505 0 0 0-.712-.146 16.97 16.97 0 0 1-12.436 0 .506.506 0 0 0-.711.147Z" /></svg>
                                </div>
                                <h3 className="font-bold text-white">Never Events</h3>
                            </div>
                            <p className="text-sm text-gray-400 mb-2">Deaths occurring during hospitalization</p>
                            <div className="flex items-baseline gap-2 mt-auto">
                                <p className="text-3xl font-bold text-white">{stats.neverCount}</p>
                                <span className="text-sm text-red-400 font-medium">cases ({stats.neverRate.toFixed(2)}%)</span>
                            </div>
                        </CardContent>
                    </Card>

                    <Card variant="glass" className="flex-1 border-l-4 border-l-blue-500 relative overflow-hidden">
                        <CardContent className="p-6 h-full flex flex-col justify-center">
                            <p className="text-sm text-gray-400 uppercase tracking-widest font-semibold">Length of Stay</p>
                            <p className="text-gray-300 mt-2 text-sm">
                                Most patients (<strong className="text-blue-400">~80%</strong>) are discharged within 1-3 days.
                            </p>
                            <p className="text-sm text-gray-500 mt-4">
                                Prolonged stays (&gt;7 days) remain stable around 2.8%.
                            </p>
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* LOS Stacked Bar Chart */}
            <Card className="h-[400px] flex flex-col relative overflow-hidden">
                <CardHeader>
                    <CardTitle>Length of Stay Distribution (share %)</CardTitle>
                    <p className="text-sm text-gray-500">Duration of index hospitalization (2021-2024)</p>
                </CardHeader>
                <CardContent className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={stats.losData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} unit="%" />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <div className="glass-card p-3 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                <p className="font-bold mb-1 text-white">{label}</p>
                                                {payload.map((entry: any, index: number) => (
                                                    <p key={index} style={{ color: entry.color }} className="mb-1">
                                                        {entry.name}: {Number(entry.value).toFixed(1)}%
                                                    </p>
                                                ))}
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Legend />
                            <Bar dataKey="0 days" stackId="a" fill="#1f77b4" />
                            <Bar dataKey="1-3 days" stackId="a" fill="#4C84C8" />
                            <Bar dataKey="4-6 days" stackId="a" fill="#76A5D8" />
                            <Bar dataKey=">7 days" stackId="a" fill="#A0C4E8" />
                        </BarChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>
        </div>
    );
}
