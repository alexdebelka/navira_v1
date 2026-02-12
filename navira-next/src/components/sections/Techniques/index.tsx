"use client";

import { useNationalData } from '@/hooks/useNationalData';
import { ProcedureCharts } from './ProcedureCharts';
import { NationalAverages } from './NationalAverages';
import { Loader2 } from 'lucide-react';

export function TechniquesSection() {
    const {
        activity,
        robotic,
        hospitalData,
        loading,
        error
    } = useNationalData();

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[400px]">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Loading techniques data...</p>
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
                <h2 className="text-2xl font-bold text-white mb-2">Procedures</h2>
                <p className="text-gray-400 mb-6">
                    Detailed breakdown of bariatric procedure types, trends, and adoption rates.
                </p>
                <ProcedureCharts
                    activityData={activity}
                    loading={loading}
                />
            </section>

            <div className="border-t border-white/10 my-8" />

            <section>
                <NationalAverages
                    hospitalData={hospitalData}
                    activityData={activity}
                    roboticData={robotic}
                    loading={loading}
                />
            </section>
        </div>
    );
}
