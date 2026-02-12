"use client";

import { useNationalData } from '@/hooks/useNationalData';
import { RoboticOverview } from './RoboticOverview';
import { RoboticTrends } from './RoboticTrends';
import { Loader2 } from 'lucide-react';

export function RobotSection() {
    const {
        robotic, // TAB_APP_NATL_YEAR (using this as base for now, though activity has better procedure granularity)
        robHosp12m, // TAB_ROB_HOP_12M
        loading,
        error
    } = useNationalData();

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[400px]">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Loading robotic data...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-8 text-center">
                <p className="text-red-500">Error loading data: {error.message}</p>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            <section>
                <RoboticOverview
                    appData={robotic}
                    robHosp12m={robHosp12m}
                    loading={loading}
                />
            </section>

            <div className="border-t border-white/10 my-8" />

            <section>
                <h2 className="text-2xl font-bold text-white mb-4">Adoption Trends</h2>
                <RoboticTrends
                    appData={robotic}
                    loading={loading}
                />
            </section>
        </div>
    );
}
