"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from 'recharts';

interface AffiliationAnalysisProps {
    hospitalsRedux: any[]; // 01_hospitals_redux
    volStatus: any[];      // TAB_VOL_STATUS_YEAR
    loading: boolean;
}

export function AffiliationAnalysis({ hospitalsRedux, volStatus, loading }: AffiliationAnalysisProps) {

    const affiliationStats = useMemo(() => {
        if (!hospitalsRedux || hospitalsRedux.length === 0) return null;

        // Filter 2025
        const df2025 = hospitalsRedux.filter((d: any) => d.annee === 2025);

        const statusMapping: Record<string, string> = {
            'public academic': 'Public – Univ.',
            'public': 'Public – Non-Acad.',
            'private for profit': 'Private – For-profit',
            'private not-for-profit': 'Private – Not-for-profit'
        };

        const counts: Record<string, number> = {};
        const labelData: Record<string, { SOFFCO: number, CSO: number, Both: number, None: number }> = {};
        const totalHospitals = df2025.length;

        df2025.forEach((d: any) => {
            const affil = statusMapping[d.statut];
            if (!affil) return;

            counts[affil] = (counts[affil] || 0) + 1;

            if (!labelData[affil]) labelData[affil] = { SOFFCO: 0, CSO: 0, Both: 0, None: 0 };

            const hasCSO = d.cso === 1;
            const hasSOFFCO = d.LAB_SOFFCO === 1;

            if (hasCSO && hasSOFFCO) labelData[affil].Both++;
            else if (hasSOFFCO) labelData[affil].SOFFCO++;
            else if (hasCSO) labelData[affil].CSO++;
            else labelData[affil].None++;
        });

        const stackedChartData = Object.keys(labelData).map(affil => ({
            name: affil,
            ...labelData[affil]
        }));

        return {
            counts,
            totalHospitals,
            stackedChartData
        };
    }, [hospitalsRedux]);

    const trendsData = useMemo(() => {
        if (!volStatus || volStatus.length === 0) return [];

        const statusMapping: Record<string, string> = {
            'public academic': 'Public – Univ.',
            'public': 'Public – Non-Acad.',
            'private for profit': 'Private – For-profit',
            'private not-for-profit': 'Private – Not-for-profit'
        };

        // Transform to: [{ year: 2021, 'Public – Univ.': 123, ... }, ...]
        const byYear: Record<number, any> = {};

        volStatus.filter((d: any) => [2021, 2022, 2023, 2024].includes(d.annee)).forEach((d: any) => {
            const year = d.annee;
            const affil = statusMapping[d.statut];
            if (affil) {
                if (!byYear[year]) byYear[year] = { year };
                byYear[year][affil] = d.n;
            }
        });

        return Object.values(byYear).sort((a: any, b: any) => a.year - b.year);
    }, [volStatus]);

    if (loading || !affiliationStats) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    const { counts, totalHospitals, stackedChartData } = affiliationStats;

    return (
        <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {['Public – Univ.', 'Public – Non-Acad.', 'Private – For-profit', 'Private – Not-for-profit'].map(cat => (
                    <Card key={cat} variant="glass" className="border-l-4" style={{
                        borderLeftColor: cat.includes('Public') ? '#3b82f6' : '#f59e0b'
                    }}>
                        <CardContent className="p-4">
                            <p className="text-xs text-gray-400 uppercase tracking-wide">{cat}</p>
                            <p className="text-2xl font-bold text-white mt-1">{counts[cat] || 0}</p>
                            <p className="text-xs text-gray-500">{Math.round((counts[cat] || 0) / totalHospitals * 100)}% of total</p>
                        </CardContent>
                    </Card>
                ))}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="h-[400px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Hospital Labels by Affiliation</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={stackedChartData} margin={{ top: 20, right: 30, left: 0, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="name" stroke="#888888" fontSize={10} tickLine={false} axisLine={false} interval={0} />
                                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <Tooltip cursor={{ fill: 'rgba(255,255,255,0.05)' }} contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }} />
                                <Legend />
                                <Bar dataKey="SOFFCO" stackId="a" fill="#7fd8be" name="SOFFCO Label" />
                                <Bar dataKey="CSO" stackId="a" fill="#ffd97d" name="CSO Label" />
                                <Bar dataKey="Both" stackId="a" fill="#00bfff" name="Both Labels" />
                                <Bar dataKey="None" stackId="a" fill="#f08080" name="No Label" />
                            </BarChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                <Card className="h-[400px] flex flex-col">
                    <CardHeader>
                        <CardTitle>Volume Trends by Affiliation</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trendsData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                                <Tooltip contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }} />
                                <Legend />
                                <Line type="monotone" dataKey="Public – Univ." stroke="#ee6055" strokeWidth={2} dot={{ r: 4 }} />
                                <Line type="monotone" dataKey="Public – Non-Acad." stroke="#60d394" strokeWidth={2} dot={{ r: 4 }} />
                                <Line type="monotone" dataKey="Private – For-profit" stroke="#ffd97d" strokeWidth={2} dot={{ r: 4 }} />
                                <Line type="monotone" dataKey="Private – Not-for-profit" stroke="#7161ef" strokeWidth={2} dot={{ r: 4 }} />
                            </LineChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
