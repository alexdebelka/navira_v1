"use client";

import { useNationalData } from '@/hooks/useNationalData';
import { ComplicationsOverview } from './ComplicationsOverview';
import { ComplicationsCharts } from './ComplicationsCharts';
import { Loader2 } from 'lucide-react';

export function ComplicationsSection() {
    const {
        complNatlYear,      // TAB_COMPL_NATL_YEAR
        complGradeNatlYear, // TAB_COMPL_GRADE_NATL_YEAR
        neverNatl,          // TAB_NEVER_NATL
        losNatl,            // TAB_LOS_NATL
        los7Natl,           // TAB_LOS7_NATL
        loading,
        error
    } = useNationalData();

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[400px]">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Loading complications data...</p>
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
                <ComplicationsOverview
                    complNatlYear={complNatlYear}
                    loading={loading}
                />
            </section>

            <div className="border-t border-white/10 my-8" />

            <section>
                <h2 className="text-2xl font-bold text-white mb-4">Detailed Analysis</h2>
                <ComplicationsCharts
                    complGradeNatlYear={complGradeNatlYear} // Pass actual data
                    neverNatl={neverNatl}
                    losNatl={losNatl}
                    los7Natl={los7Natl}
                    loading={loading}
                />
            </section>
        </div>
    );
}
