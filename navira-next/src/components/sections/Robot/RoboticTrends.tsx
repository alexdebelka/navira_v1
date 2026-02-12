"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid, AreaChart, Area } from 'recharts';

interface RoboticTrendsProps {
    appData: any[]; // TAB_APP_NATL_YEAR
    loading: boolean;
}

export function RoboticTrends({ appData, loading }: RoboticTrendsProps) {

    const trendData = useMemo(() => {
        if (!appData || appData.length === 0) return [];

        // Filter relevant years (2020/2021 - 2024). Python uses 2020-2024 for trends.
        const years = [2020, 2021, 2022, 2023, 2024];

        const data: any[] = [];
        years.forEach(year => {
            const yearData = appData.filter((d: any) => d.annee === year);
            const total = yearData.reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
            const robotic = yearData.filter((d: any) => d.vda === 'ROB').reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);

            if (total > 0 || robotic > 0) { // Keep even if minimal data to show trend
                data.push({
                    year,
                    total,
                    robotic,
                    rate: total > 0 ? (robotic / total) * 100 : 0
                });
            }
        });

        return data;
    }, [appData]);

    if (loading) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Growth in Volume - Area Chart */}
            <Card className="h-[400px] flex flex-col relative overflow-hidden border-t-4 border-t-[#F7931E]">
                <CardHeader>
                    <CardTitle>Total Robotic Surgeries (2020-2024)</CardTitle>
                    <p className="text-sm text-gray-500">Volume growth trajectory</p>
                </CardHeader>
                <CardContent className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={trendData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                            <defs>
                                <linearGradient id="colorRobotic" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#F7931E" stopOpacity={0.3} />
                                    <stop offset="95%" stopColor="#F7931E" stopOpacity={0} />
                                </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <div className="glass-card p-3 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                <p className="font-bold mb-1 text-white">{label}</p>
                                                <p className="text-[#F7931E] font-bold text-lg">{payload[0].value?.toLocaleString()}</p>
                                                <p className="text-gray-400">procedures</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Area type="monotone" dataKey="robotic" stroke="#F7931E" strokeWidth={3} fillOpacity={1} fill="url(#colorRobotic)" />
                        </AreaChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Adoption Rate - Line Chart */}
            <Card className="h-[400px] flex flex-col relative overflow-hidden border-t-4 border-t-purple-500">
                <CardHeader>
                    <CardTitle>Robotic Adoption Rate</CardTitle>
                    <p className="text-sm text-gray-500">% of all bariatric procedures</p>
                </CardHeader>
                <CardContent className="flex-1 min-h-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={trendData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                            <XAxis dataKey="year" stroke="#888888" fontSize={12} tickLine={false} axisLine={false} />
                            <YAxis stroke="#888888" fontSize={12} tickLine={false} axisLine={false} unit="%" domain={[0, 'auto']} />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <div className="glass-card p-3 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                <p className="font-bold mb-1 text-white">{label}</p>
                                                <p className="text-purple-400 font-bold text-lg">{Number(payload[0].value).toFixed(1)}%</p>
                                                <p className="text-gray-400">adoption rate</p>
                                            </div>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Line
                                type="monotone"
                                dataKey="rate"
                                stroke="#a855f7"
                                strokeWidth={3}
                                dot={{ r: 6, fill: "#a855f7", strokeWidth: 2, stroke: "#fff" }}
                                activeDot={{ r: 8 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </CardContent>
            </Card>

            {/* Stylized Insight Card */}
            <Card variant="glass" className="col-span-1 lg:col-span-2 p-6 bg-gradient-to-r from-surface-elevated/20 to-surface-elevated/5 border-l-4 border-l-[#F7931E]">
                <div className="flex flex-col md:flex-row gap-6 items-center">
                    <div className="flex-shrink-0 p-4 bg-[#F7931E]/20 rounded-full">
                        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#F7931E" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-trending-up"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></svg>
                    </div>
                    <div className="flex-1">
                        <h3 className="text-lg font-bold text-white mb-2">Growth Analysis</h3>
                        <p className="text-gray-300">
                            Robotic surgery has grown from <strong className="text-[#F7931E]">{trendData[0]?.robotic.toLocaleString()}</strong> procedures in 2020
                            to <strong className="text-[#F7931E]">{trendData[trendData.length - 1]?.robotic.toLocaleString()}</strong> in 2024.
                            The adoption rate has steadily climbed to <strong className="text-purple-400">{trendData[trendData.length - 1]?.rate.toFixed(1)}%</strong>,
                            indicating expanding capabilities across French hospitals.
                        </p>
                    </div>
                </div>
            </Card>
        </div>
    );
}
