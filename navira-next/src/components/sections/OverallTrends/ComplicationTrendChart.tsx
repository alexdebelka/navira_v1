"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

interface ComplicationTrendChartProps {
    data: any[];
    loading: boolean;
}

export function ComplicationTrendChart({ data, loading }: ComplicationTrendChartProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Filter for grades 3, 4, 5 (severe)
        const severe = data.filter((d: any) => [3, 4, 5].includes(d.clav_cat_90));

        // Group by year and sum percentages (this simplifies what python code did: sum of pct for grade 3,4,5)
        // Python: yearly_severe = df_comp.groupby('annee')['COMPL_pct'].sum()
        const byYear: Record<number, number> = {};

        severe.forEach((d: any) => {
            const year = d.annee;
            if (year && d.COMPL_pct) {
                byYear[year] = (byYear[year] || 0) + d.COMPL_pct;
            }
        });

        return Object.entries(byYear)
            .map(([year, pct]) => ({ year: parseInt(year), pct }))
            .sort((a, b) => a.year - b.year)
            .filter(d => d.year >= 2021 && d.year <= 2024);

    }, [data]);

    if (loading) {
        return (
            <Card className="h-[200px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <Card className="flex flex-col h-full">
            <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-400">Severe Complications (Grade ≥3)</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 min-h-[150px]">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                        <XAxis
                            dataKey="year"
                            stroke="#666"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                        />
                        <YAxis
                            stroke="#666"
                            fontSize={12}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(val) => `${val.toFixed(1)}%`}
                            domain={[0, 'auto']}
                        />
                        <Tooltip
                            content={({ active, payload, label }) => {
                                if (active && payload && payload.length) {
                                    return (
                                        <div className="glass-card p-2 rounded border border-white/10 text-xs">
                                            <div className="font-bold mb-1">{label}</div>
                                            <div className="text-orange-400 font-medium">
                                                {Number(payload[0].value).toFixed(2)}% Severe Complications
                                            </div>
                                        </div>
                                    );
                                }
                                return null;
                            }}
                        />
                        <Line
                            type="monotone"
                            dataKey="pct"
                            stroke="#f97316"
                            strokeWidth={3}
                            dot={{ r: 4, fill: '#f97316', strokeWidth: 0 }}
                            activeDot={{ r: 6, stroke: '#fff', strokeWidth: 2 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}
