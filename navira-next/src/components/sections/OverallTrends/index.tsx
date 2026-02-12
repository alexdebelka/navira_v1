"use client";

import { useNationalData } from '@/hooks/useNationalData';
import { InterventionTypeDonut } from './InterventionTypeDonut';
import { RoboticRateCard } from './RoboticRateCard';
import { ComplicationTrendChart } from './ComplicationTrendChart';
import { SurgeryDensityMap } from './SurgeryDensityMap';
import { Card, CardContent } from '@/components/ui/Card';

export function OverallTrends() {
    const { activity, robotic, complications, hospitalData, loading } = useNationalData();

    return (
        <div className="space-y-6 animate-in fade-in duration-700">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
                {/* Row 1 */}
                <div className="md:col-span-6 lg:col-span-4">
                    {/* Comparison Card (Placeholder for now) */}
                    <Card className="h-full min-h-[350px] bg-gradient-to-br from-blue-900/20 to-purple-900/20 border-white/10 relative overflow-hidden">
                        <div className="absolute inset-0 bg-grid-white/5 bg-[size:20px_20px] [mask-image:linear-gradient(to_bottom,white,transparent)]" />
                        <CardContent className="flex flex-col items-center justify-center h-full text-center p-6 relative">
                            <h3 className="text-xl font-bold text-white mb-2">Monthly Activity</h3>
                            <p className="text-gray-400 text-sm">Live analysis module coming soon.</p>
                            <div className="mt-8 w-full h-32 bg-white/5 rounded-lg animate-pulse" />
                        </CardContent>
                    </Card>
                </div>

                <div className="md:col-span-6 lg:col-span-4">
                    <InterventionTypeDonut data={activity} loading={loading} />
                </div>

                <div className="md:col-span-6 lg:col-span-4 flex flex-col gap-6">
                    <RoboticRateCard data={robotic} loading={loading} />
                    <div className="flex-1">
                        <ComplicationTrendChart data={complications} loading={loading} />
                    </div>
                </div>
            </div>

            {/* Row 2: Map */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="md:col-span-2">
                    <SurgeryDensityMap hospitalData={hospitalData} loading={loading} />
                </div>
            </div>
        </div>
    );
}
