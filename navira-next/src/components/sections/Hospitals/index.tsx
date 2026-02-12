"use client";

import { useNationalData } from '@/hooks/useNationalData';
import { VolumeDistribution } from './VolumeDistribution';
import { RevisionAnalysis } from './RevisionAnalysis';
import { AffiliationAnalysis } from './AffiliationAnalysis';
import { AdvancedProcedureMetrics } from './AdvancedProcedureMetrics';
import { Loader2 } from 'lucide-react';

export function HospitalsSection() {
    const {
        hospitalData,
        volNatl,
        revNatl,
        revStatus,
        rev12m,
        hospitalsRedux,
        volStatus,
        procedureDetails,
        loading,
        error
    } = useNationalData();

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[400px]">
                <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
                <p className="text-muted-foreground">Loading hospital data...</p>
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
                <h2 className="text-2xl font-bold text-white mb-2">Hospital Volume Distribution</h2>
                <p className="text-gray-400 mb-6">
                    Analysis of surgical volume distribution across hospitals, highlighting consolidation trends.
                </p>
                <VolumeDistribution
                    hospitalData={hospitalData}
                    nationalData={volNatl}
                    loading={loading}
                />
            </section>

            <div className="border-t border-white/10 my-8" />

            <section>
                <h2 className="text-2xl font-bold text-white mb-2">Revision Surgery Rate</h2>
                <p className="text-gray-400 mb-6">
                    Overview of revision surgery rates and breakdown by hospital affiliation.
                </p>
                <RevisionAnalysis
                    revNatl={revNatl}
                    revStatus={revStatus}
                    rev12m={rev12m}
                    loading={loading}
                />
            </section>

            <div className="border-t border-white/10 my-8" />

            <section>
                <h2 className="text-2xl font-bold text-white mb-2">Hospital Affiliation (2025)</h2>
                <p className="text-gray-400 mb-6">
                    Distribution of hospitals by sector and affiliation trends over time.
                </p>
                <AffiliationAnalysis
                    hospitalsRedux={hospitalsRedux}
                    volStatus={volStatus}
                    loading={loading}
                />
            </section>

            <div className="border-t border-white/10 my-8" />

            <section>
                <h2 className="text-2xl font-bold text-white mb-2">Advanced Procedure Metrics</h2>
                <p className="text-gray-400 mb-6">
                    Detailed insights into robotic adoption and procedure trends (2020-2024).
                </p>
                <AdvancedProcedureMetrics
                    procedureDetails={procedureDetails}
                    loading={loading}
                />
            </section>
        </div>
    );
}
