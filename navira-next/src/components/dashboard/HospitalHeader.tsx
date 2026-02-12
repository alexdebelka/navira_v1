"use client";

import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { MapPin, Building2, GraduationCap, Award, Activity } from 'lucide-react';

interface HospitalHeaderProps {
    hospital: any; // Reduced hospital object from 01_hospitals_redux
}

export function HospitalHeader({ hospital }: HospitalHeaderProps) {
    if (!hospital) return null;

    // Format postal code
    const postal = hospital.code_postal ? String(Math.floor(Number(hospital.code_postal))) : '';

    return (
        <div className="space-y-6 animate-in fade-in duration-500">
            {/* Main Header */}
            <div>
                <h1 className="text-3xl font-bold text-white mb-2 flex items-center gap-3">
                    <Building2 className="h-8 w-8 text-primary" />
                    {hospital.rs}
                </h1>
                <div className="flex flex-wrap items-center gap-4 text-gray-400">
                    <div className="flex items-center gap-1">
                        <MapPin className="h-4 w-4" />
                        <span>{hospital.adresse}, {postal} {hospital.ville}</span>
                    </div>
                    {/* Status Tag */}
                    <Badge variant="outline" className="text-xs border-white/20 text-gray-300">
                        {hospital.statut}
                    </Badge>
                </div>
            </div>

            <div className="border-b border-white/10" />

            {/* Labels & Certifications Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* University Label */}
                <LabelCard
                    active={hospital.university === 1}
                    icon={GraduationCap}
                    label="University Hospital"
                    inactiveLabel="No University Affiliation"
                    color="text-blue-400"
                />
                {/* SOFFCO Label */}
                <LabelCard
                    active={hospital.LAB_SOFFCO === 1}
                    icon={Award}
                    label="Centre of Excellence (SOFFCO)"
                    inactiveLabel="No SOFFCO Label"
                    color="text-yellow-400"
                />
                {/* Health Ministry Label */}
                <LabelCard
                    active={hospital.cso === 1}
                    icon={Activity}
                    label="Centre of Excellence (Health Ministry)"
                    inactiveLabel="No Health Ministry Label"
                    color="text-green-400"
                />
            </div>
        </div>
    );
}

function LabelCard({ active, icon: Icon, label, inactiveLabel, color }: any) {
    return (
        <div className={`
            flex items-center gap-3 p-3 rounded-lg border transition-colors
            ${active
                ? 'bg-surface-elevated/50 border-white/10'
                : 'bg-surface/30 border-white/5 opacity-60'}
        `}>
            <div className={`p-2 rounded-full ${active ? 'bg-white/5' : 'bg-transparent'}`}>
                <Icon className={`h-5 w-5 ${active ? color : 'text-gray-500'}`} />
            </div>
            <div>
                <p className={`font-medium text-sm ${active ? 'text-white' : 'text-gray-500'}`}>
                    {active ? label : inactiveLabel}
                </p>
            </div>
        </div>
    );
}
