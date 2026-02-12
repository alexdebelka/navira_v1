"use client";

import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';

interface InterventionTypeDonutProps {
    data: any[];
    loading: boolean;
}

const COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444']; // Blue, Orange, Green, Purple, Red

export function InterventionTypeDonut({ data, loading }: InterventionTypeDonutProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Filter for recent years (2021-2024 to match python code)
        const filtered = data.filter((d: any) => [2021, 2022, 2023, 2024].includes(d.annee));

        // Aggregate by procedure type
        const totals: Record<string, number> = {};
        filtered.forEach((d: any) => {
            const type = d.baria_t;
            const count = d.n;
            if (type && count) {
                totals[type] = (totals[type] || 0) + count;
            }
        });

        // Map to chart format
        // Map codes to names
        const names: Record<string, string> = {
            'SLE': 'Sleeve',
            'BPG': 'Bypass',
            'ANN': 'Ring',
            'REV': 'Revision',
            // others...
        };

        const result = Object.entries(totals).map(([key, value]) => ({
            name: names[key] || key,
            value: value
        }));

        // Sort by value desc
        return result.sort((a, b) => b.value - a.value);
    }, [data]);

    const total = useMemo(() => chartData.reduce((acc, curr) => acc + curr.value, 0), [chartData]);

    if (loading) {
        return (
            <Card className="h-[350px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <Card className="h-full min-h-[350px] flex flex-col">
            <CardHeader>
                <CardTitle>Intervention Types (2021-2024)</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 relative">
                <div className="absolute inset-0 flex items-center justify-center flex-col pointer-events-none">
                    <span className="text-3xl font-bold text-white">{total.toLocaleString()}</span>
                    <span className="text-xs text-muted-foreground uppercase tracking-widest">Total</span>
                </div>
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={80}
                            outerRadius={110}
                            paddingAngle={2}
                            dataKey="value"
                            stroke="none"
                        >
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                            ))}
                        </Pie>
                        <Tooltip
                            content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                    const data = payload[0].payload;
                                    const percent = ((data.value / total) * 100).toFixed(1);
                                    return (
                                        <div className="glass-card p-3 rounded-lg border border-white/10 shadow-xl">
                                            <div className="text-sm font-semibold mb-1" style={{ color: payload[0].fill }}>{data.name}</div>
                                            <div className="text-2xl font-bold">{data.value.toLocaleString()}</div>
                                            <div className="text-xs text-gray-400">{percent}% of total</div>
                                        </div>
                                    );
                                }
                                return null;
                            }}
                        />
                        <Legend
                            verticalAlign="bottom"
                            height={36}
                            iconType="circle"
                            wrapperStyle={{ paddingTop: '20px' }}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </CardContent>
        </Card>
    );
}
