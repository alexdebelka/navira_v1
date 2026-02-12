"use client";

import { useMemo, useState } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';

interface RoboticOverviewProps {
    appData: any[]; // TAB_APP_NATL_YEAR
    robHosp12m: any[]; // TAB_ROB_HOP_12M
    loading: boolean;
}

export function RoboticOverview({ appData, robHosp12m, loading }: RoboticOverviewProps) {
    const [show2024Only, setShow2024Only] = useState(false);

    const stats = useMemo(() => {
        if (!appData || appData.length === 0) return null;

        // Filter by year
        const years = show2024Only ? [2024] : [2021, 2022, 2023, 2024];
        const filtered = appData.filter((d: any) => years.includes(d.annee));

        // 1. Approach Mix
        const approachMapping: Record<string, string> = {
            'COE': 'Laparoscopy',
            'LAP': 'Open Surgery',
            'ROB': 'Robotic'
        };

        const approachCounts: Record<string, number> = { 'Laparoscopy': 0, 'Open Surgery': 0, 'Robotic': 0 };
        let totalProcedures = 0;

        filtered.forEach((d: any) => {
            const name = approachMapping[d.vda];
            if (name) {
                approachCounts[name] += (d.n || 0);
                totalProcedures += (d.n || 0);
            }
        });

        const pieData = Object.keys(approachCounts).map(name => ({
            name,
            value: approachCounts[name],
            percentage: totalProcedures > 0 ? (approachCounts[name] / totalProcedures) * 100 : 0
        })).sort((a, b) => b.value - a.value);

        const roboticShare = pieData.find(d => d.name === 'Robotic')?.percentage || 0;
        const roboticCount = pieData.find(d => d.name === 'Robotic')?.value || 0;

        // 2. Hospital Metrics (from TAB_ROB_HOP_12M) - only relevant for "Recent 12 Months" context generally, 
        // but we can show it as "Current Landscape"
        let hospMetrics = null;
        if (robHosp12m && robHosp12m.length > 0) {
            const numHospitals = robHosp12m.length;
            const totalRob = robHosp12m.reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);
            const avgPerHosp = numHospitals > 0 ? Math.round(totalRob / numHospitals) : 0;
            hospMetrics = { numHospitals, totalRob, avgPerHosp };
        }

        return { pieData, roboticShare, roboticCount, totalProcedures, hospMetrics };
    }, [appData, robHosp12m, show2024Only]);

    if (loading || !stats) {
        return (
            <Card className="h-[400px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    // Colors: Laparoscopy (Blue), Open (Light Blue), Robotic (Orange - Accent)
    const COLORS = {
        'Laparoscopy': '#2E86AB',
        'Open Surgery': '#A6CEE3',
        'Robotic': '#F7931E' // The requested accent
    };

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center bg-surface-elevated/30 p-4 rounded-xl border border-white/5 backdrop-blur-sm">
                <div>
                    <h2 className="text-2xl font-bold text-white">Surgical Approach Mix</h2>
                    <p className="text-sm text-gray-400">Distribution of surgical techniques ({show2024Only ? "2024" : "2021-2024"})</p>
                </div>
                <div className="flex items-center gap-2 bg-surface-elevated/50 p-2 rounded-lg border border-white/5">
                    <span className="text-sm text-gray-400">Show 2024 Only</span>
                    <input
                        type="checkbox"
                        checked={show2024Only}
                        onChange={(e) => setShow2024Only(e.target.checked)}
                        className="toggle toggle-primary toggle-sm accent-primary h-4 w-4"
                    />
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Key Metric Card - Robotic Share. Enhanced Styling */}
                <Card variant="glass" className="border-l-4 border-l-[#F7931E] relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-r from-[#F7931E]/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <CardContent className="p-6 relative z-10">
                        <p className="text-sm text-gray-400 uppercase tracking-widest font-semibold">Robotic Share</p>
                        <div className="flex items-baseline gap-2 mt-2">
                            <p className="text-4xl font-bold text-white">{stats.roboticShare.toFixed(1)}%</p>
                            <span className="text-sm text-[#F7931E] font-medium">of all procedures</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">{stats.roboticCount.toLocaleString()} robotic cases</p>
                    </CardContent>
                </Card>

                {/* Metric Card - Hospital Count */}
                <Card variant="glass" className="border-l-4 border-l-blue-500 relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <CardContent className="p-6 relative z-10">
                        <p className="text-sm text-gray-400 uppercase tracking-widest font-semibold">Active Centers</p>
                        <div className="flex items-baseline gap-2 mt-2">
                            <p className="text-4xl font-bold text-white">{stats.hospMetrics?.numHospitals || 0}</p>
                            <span className="text-sm text-blue-400 font-medium">hospitals</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">performing robotic surgery (12m)</p>
                    </CardContent>
                </Card>

                {/* Metric Card - Avg Volume */}
                <Card variant="glass" className="border-l-4 border-l-purple-500 relative overflow-hidden group">
                    <div className="absolute inset-0 bg-gradient-to-r from-purple-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <CardContent className="p-6 relative z-10">
                        <p className="text-sm text-gray-400 uppercase tracking-widest font-semibold">Avg Volume</p>
                        <div className="flex items-baseline gap-2 mt-2">
                            <p className="text-4xl font-bold text-white">{stats.hospMetrics?.avgPerHosp || 0}</p>
                            <span className="text-sm text-purple-400 font-medium">per hospital</span>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">robotic procedures / year</p>
                    </CardContent>
                </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card className="h-[400px] flex flex-col relative overflow-hidden">
                    <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-[#2E86AB] via-[#A6CEE3] to-[#F7931E]" />
                    <div className="p-6 pb-2">
                        <p className="text-lg font-bold text-white">Market Share by Approach</p>
                    </div>
                    <CardContent className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={stats.pieData}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={80}
                                    outerRadius={120}
                                    paddingAngle={2}
                                    dataKey="value"
                                >
                                    {stats.pieData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={COLORS[entry.name as keyof typeof COLORS] || '#888888'} stroke="rgba(0,0,0,0.2)" strokeWidth={2} />
                                    ))}
                                </Pie>
                                <Tooltip
                                    content={({ active, payload }) => {
                                        if (active && payload && payload.length) {
                                            const data = payload[0].payload;
                                            return (
                                                <div className="glass-card p-3 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                    <p className="font-bold mb-1 text-white">{data.name}</p>
                                                    <p className="text-gray-300 mb-1">Count: <span className="text-white font-mono">{data.value.toLocaleString()}</span></p>
                                                    <p className="text-gray-300">Share: <span className="text-[#F7931E] font-bold">{data.percentage.toFixed(1)}%</span></p>
                                                </div>
                                            );
                                        }
                                        return null;
                                    }}
                                />
                                <Legend verticalAlign="middle" align="right" layout="vertical" iconType="circle" />
                            </PieChart>
                        </ResponsiveContainer>
                    </CardContent>
                </Card>

                {/* Placeholder for description/insight text to balance layout */}
                <Card variant="glass" className="p-8 flex flex-col justify-center gap-4 bg-gradient-to-br from-surface-elevated/40 to-surface-elevated/10">
                    <h3 className="text-xl font-bold text-white flex items-center gap-2">
                        <span className="w-2 h-8 bg-[#F7931E] rounded-full"></span>
                        Key Findings ({show2024Only ? "2024" : "2021-2024"})
                    </h3>
                    <div className="space-y-4 text-gray-300 leading-relaxed">
                        <p>
                            <strong className="text-white">Robotic surgery</strong> currently accounts for <strong className="text-[#F7931E]">{stats.roboticShare.toFixed(1)}%</strong> of all procedures.
                            While <strong className="text-[#2E86AB]">Laparoscopy</strong> remains the dominant technique, robotic adoption is steadily increasing.
                        </p>
                        <p>
                            With <strong className="text-white">{stats.hospMetrics?.numHospitals} active centers</strong>, the technology is becoming more accessible, though most hospitals are still in the early adoption phase with distinct volume levels.
                        </p>
                    </div>
                </Card>
            </div>
        </div>
    );
}
