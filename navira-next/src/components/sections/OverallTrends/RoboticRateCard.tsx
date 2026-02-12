"use client";

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Loader2, TrendingUp } from 'lucide-react';

interface RoboticRateCardProps {
    data: any[];
    loading: boolean;
}

export function RoboticRateCard({ data, loading }: RoboticRateCardProps) {
    const metrics = useMemo(() => {
        if (!data || data.length === 0) return { current: 0, previous: 0, growth: 0 };

        // Filter robotic (ROB)
        const roboticData = data.filter((d: any) => d.vda === 'ROB');

        // Get 2024 and 2021 rates
        const row2024 = roboticData.find((d: any) => d.annee === 2024);
        const row2021 = roboticData.find((d: any) => d.annee === 2021);

        const rate2024 = row2024 ? row2024.pct : 0;
        const rate2021 = row2021 ? row2021.pct : 0;

        return {
            current: rate2024,
            previous: rate2021,
            growth: rate2024 - rate2021
        };
    }, [data]);

    if (loading) {
        return (
            <Card className="h-[200px] flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </Card>
        );
    }

    return (
        <Card className="relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <TrendingUp className="w-24 h-24 text-primary" />
            </div>
            <CardHeader>
                <CardTitle className="text-sm font-medium text-gray-400">MBS Robotic Rate (2024)</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="flex items-baseline gap-2 mt-2">
                    <span className="text-4xl font-bold text-white">{metrics.current.toFixed(1)}%</span>
                    <span className={`text-sm font-medium ${metrics.growth >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {metrics.growth >= 0 ? '+' : ''}{metrics.growth.toFixed(1)}% vs 2021
                    </span>
                </div>
                <div className="mt-4 h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full"
                        style={{ width: `${Math.min(metrics.current * 5, 100)}%` }} // Visual scaling
                    />
                </div>
                <p className="text-xs text-gray-500 mt-2">
                    Adoption rate of robotic-assisted procedures
                </p>
            </CardContent>
        </Card>
    );
}
