"use client";

import { useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

interface ComplicationsOverviewProps {
    complNatlYear: any[]; // TAB_COMPL_NATL_YEAR
    loading: boolean;
}

export function ComplicationsOverview({ complNatlYear, loading }: ComplicationsOverviewProps) {

    const trendData = useMemo(() => {
        if (!complNatlYear || complNatlYear.length === 0) return [];

        // Filter relevant years (2021-2024 as per python code)
        const years = [2021, 2022, 2023, 2024];
        const data: any[] = [];

        years.forEach(year => {
            const row = complNatlYear.find((d: any) => d.annee === year);
            if (row && row.COMPL_pct !== undefined) {
                data.push({
                    year,
                    rate: row.COMPL_pct || 0
                });
            }
        });
        return data;
    }, [complNatlYear]);

    if (loading) {
        return (
            <Card className="h-[200px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    // Calculate trend
    const currentRate = trendData.length > 0 ? trendData[trendData.length - 1].rate : 0;
    const previousRate = trendData.length > 1 ? trendData[trendData.length - 2].rate : 0;

    let trendLabel = 'Stable';
    let trendColor = 'text-gray-400';

    if (currentRate < previousRate) {
        trendLabel = 'Improving';
        trendColor = 'text-green-400';
    } else if (currentRate > previousRate) {
        trendLabel = 'Increasing';
        trendColor = 'text-orange-400'; // Using orange as "warning" or accent
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Metric Card */}
            <Card variant="glass" className="border-l-4 border-l-[#FF8C00] relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-r from-[#FF8C00]/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                <CardContent className="p-6 relative z-10">
                    <p className="text-sm text-gray-400 uppercase tracking-widest font-semibold">Overall Rate (90d)</p>
                    <div className="flex items-baseline gap-2 mt-2">
                        <p className="text-4xl font-bold text-white">{currentRate?.toFixed(1)}%</p>
                        <span className={`text-sm font-medium ${trendColor}`}>{trendLabel} vs '23</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">Any complication within 90 days</p>
                </CardContent>
            </Card>

            {/* Trend Chart */}
            <Card variant="glass" className="col-span-1 md:col-span-2 relative overflow-hidden">
                <div className="p-6 pb-0">
                    <h3 className="text-lg font-bold text-white">Complication Rate Trend (2021-2024)</h3>
                </div>
                <div className="h-[200px] flex-1 min-h-0 w-full p-4">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={trendData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} unit="%" domain={[0, 'auto']} />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <div className="glass-card p-3 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                <p className="font-bold mb-1 text-white">{label}</p>
                                                <p className="text-[#FF8C00] font-bold text-lg">{Number(payload[0].value).toFixed(1)}%</p>
                                                <p className="text-gray-400">rate</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Line
                                type="monotone"
                                dataKey="rate"
                                stroke="#FF8C00"
                                strokeWidth={3}
                                dot={{ r: 4, fill: "#FF8C00", strokeWidth: 2, stroke: "#fff" }}
                                activeDot={{ r: 6 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </Card>
        </div>
    );
}
