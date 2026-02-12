"use client";

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2 } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis } from 'recharts';
import { HospitalData } from '@/hooks/useHospitalData';
import { useMemo } from 'react';

interface HospitalSummaryProps {
    data: HospitalData;
}

export function HospitalSummary({ data }: HospitalSummaryProps) {
    const { volume, trends, procedures, approaches, revisional, complications } = data;

    const metrics = useMemo(() => {
        // 1. Total Procedures 2021-2024
        const periodVolume = volume
            .filter((d: any) => d.annee >= 2021 && d.annee <= 2024)
            .reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);

        // 2. Ongoing Year (2025)
        // In Python code it looks for 2025 specifically or max year > 2024
        const ongoingVolume = volume
            .filter((d: any) => d.annee === 2025)
            .reduce((acc: number, curr: any) => acc + (curr.n || 0), 0);

        // 3. Expected Trend
        const trendValue = trends ? trends.diff_pct : null;

        // 4. Revisional Rate
        const revisionRate = revisional ? revisional.PCT_rev : null;

        // 5. Complication Rate (Latest complete year, logic from py)
        // Finding latest year in complications data
        const years = complications.map((d: any) => d.annee).filter((y: any) => y).sort().reverse();
        // Logic: if > 1 year, take 2nd latest (complete). If 1, take latest.
        let targetYear = null;
        const uniqueYears = Array.from(new Set(years));
        if (uniqueYears.length >= 2) targetYear = uniqueYears[1];
        else if (uniqueYears.length === 1) targetYear = uniqueYears[0];

        const complicationRate = targetYear
            ? complications.find((d: any) => d.annee === targetYear)?.COMPL_pct
            : null;

        return { periodVolume, ongoingVolume, trendValue, revisionRate, complicationRate };
    }, [volume, trends, revisional, complications]);

    const charts = useMemo(() => {
        // Procedure Mix (Pie) - from TCN data
        // Map codes to names: SLE->Sleeve, BPG->Bypass, etc.
        const procMap: any = { 'SLE': 'Sleeve', 'BPG': 'Gastric Bypass' };
        const procCounts: any = { 'Sleeve': 0, 'Gastric Bypass': 0, 'Other': 0 };

        procedures.forEach((d: any) => {
            const code = String(d.baria_t).trim();
            const label = procMap[code] || 'Other';
            procCounts[label] += (d.n || 0);
        });

        const pieData = Object.keys(procCounts)
            .filter(k => procCounts[k] > 0)
            .map(k => ({ name: k, value: procCounts[k] }))
            .sort((a, b) => b.value - a.value);

        // Robotic Share (Bar) - from APP data
        // Latest year logic
        const appYears = approaches.map((d: any) => d.annee);
        const latestAppYear = appYears.length > 0 ? Math.max(...appYears) : null;

        let barData: any[] = [];
        if (latestAppYear) {
            const appYearData = approaches.filter((d: any) => d.annee === latestAppYear);
            const totals: any = {};
            let total = 0;
            appYearData.forEach((d: any) => {
                const vda = String(d.vda).trim(); // ROB, COE, LAP
                const n = d.n || 0;
                totals[vda] = (totals[vda] || 0) + n;
                total += n;
            });

            if (total > 0) {
                const map: any = { 'ROB': 'Robotic', 'COE': 'Coelioscopy', 'LAP': 'Open Surgery' };
                barData = Object.keys(totals).map(k => ({
                    name: map[k] || k,
                    value: (totals[k] / total) * 100,
                    color: k === 'ROB' ? '#F7931E' : (k === 'COE' ? '#2E86AB' : '#A23B72')
                }));
            }
        }

        return { pieData, barData };
    }, [procedures, approaches]);

    // Colors for Pie
    const PIE_COLORS: any = { 'Sleeve': '#1f77b4', 'Gastric Bypass': '#ff7f0e', 'Other': '#2ca02c' };

    return (
        <div className="space-y-6">
            <h2 className="text-xl font-bold text-white mb-4 border-l-4 border-primary pl-3">Summary</h2>

            {/* Top Row Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <MetricCard
                    label="Nb procedures (2021-2024)"
                    value={metrics.periodVolume.toLocaleString()}
                    subtext="Total volume"
                />
                <MetricCard
                    label="Nb procedures ongoing (2025)"
                    value={metrics.ongoingVolume.toLocaleString()}
                    subtext="Year to date"
                />
                <MetricCard
                    label="Expected Trend (2025)"
                    value={metrics.trendValue ? `${Number(metrics.trendValue) > 0 ? '+' : ''}${Number(metrics.trendValue).toFixed(1)}%` : "—"}
                    subtext="vs previous year"
                    valueColor={metrics.trendValue ? (Number(metrics.trendValue) > 0 ? 'text-green-400' : 'text-red-400') : 'text-gray-400'}
                />
            </div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Procedure Mix */}
                <Card variant="glass" className="h-[280px] flex flex-col">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm uppercase text-gray-400">Type of Procedures</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        {charts.pieData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={charts.pieData}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={40}
                                        outerRadius={70}
                                        paddingAngle={2}
                                        dataKey="value"
                                    >
                                        {charts.pieData.map((entry, index) => (
                                            <Cell key={`cell-${index}`} fill={PIE_COLORS[entry.name] || '#8884d8'} />
                                        ))}
                                    </Pie>
                                    <Tooltip
                                        content={({ active, payload }) => {
                                            if (active && payload && payload.length) {
                                                const data = payload[0].payload;
                                                return (
                                                    <div className="glass-card p-2 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                        <p className="font-bold text-white">{data.name}</p>
                                                        <p className="text-gray-300">{data.value.toLocaleString()}</p>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                </PieChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-gray-500 text-sm">No Data</div>
                        )}
                    </CardContent>
                </Card>

                {/* Robotic Share */}
                <Card variant="glass" className="h-[280px] flex flex-col">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm uppercase text-gray-400">Robotic Share (2024)</CardTitle>
                    </CardHeader>
                    <CardContent className="flex-1 min-h-0">
                        {charts.barData.length > 0 ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={charts.barData} layout="vertical" margin={{ left: 40 }}>
                                    <XAxis type="number" hide domain={[0, 100]} />
                                    <YAxis dataKey="name" type="category" width={80} tick={{ fontSize: 10, fill: '#888' }} />
                                    <Tooltip
                                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                        content={({ active, payload }) => {
                                            if (active && payload && payload.length) {
                                                const data = payload[0].payload;
                                                return (
                                                    <div className="glass-card p-2 text-xs border border-white/10 backdrop-blur-xl bg-black/80">
                                                        <p className="font-bold text-white">{data.name}</p>
                                                        <p className="text-[#F7931E]">{data.value.toFixed(1)}%</p>
                                                    </div>
                                                );
                                            }
                                            return null;
                                        }}
                                    />
                                    <Bar dataKey="value" barSize={20} radius={[0, 4, 4, 0]}>
                                        {charts.barData.map((entry: any, index: number) => (
                                            <Cell key={`cell-${index}`} fill={entry.color} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="h-full flex items-center justify-center text-gray-500 text-sm">No Data</div>
                        )}
                    </CardContent>
                </Card>

                {/* Bubbles: Revision & Complication */}
                <div className="grid grid-rows-2 gap-4 h-[280px]">
                    <BubbleCard
                        label="Revisional Rate"
                        value={metrics.revisionRate !== null ? `${metrics.revisionRate.toFixed(0)}%` : "N/A"}
                        color="bg-teal-600"
                    />
                    <BubbleCard
                        label="Complication Rate"
                        value={metrics.complicationRate !== null ? `${metrics.complicationRate.toFixed(1)}%` : "N/A"}
                        color="bg-purple-600"
                    />
                </div>
            </div>
        </div>
    );
}

function MetricCard({ label, value, subtext, valueColor = "text-white" }: any) {
    return (
        <Card variant="glass" className="p-6">
            <p className="text-sm text-gray-400 font-medium mb-1">{label}</p>
            <p className={`text-3xl font-bold ${valueColor}`}>{value}</p>
            {subtext && <p className="text-xs text-gray-500 mt-1">{subtext}</p>}
        </Card>
    );
}

function BubbleCard({ label, value, color }: any) {
    return (
        <Card variant="glass" className="flex items-center justify-between p-6">
            <div>
                <p className="text-sm text-gray-400 uppercase tracking-wider font-semibold">{label}</p>
            </div>
            <div className={`h-16 w-16 rounded-full ${color} flex items-center justify-center shadow-lg shadow-black/20`}>
                <span className="text-xl font-bold text-white">{value}</span>
            </div>
        </Card>
    );
}
