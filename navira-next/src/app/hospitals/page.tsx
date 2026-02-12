"use client";

import { useState } from 'react';
import { HospitalSearch } from '@/components/dashboard/HospitalSearch';
import { HospitalHeader } from '@/components/dashboard/HospitalHeader';
import { HospitalSummary } from '@/components/dashboard/HospitalSummary';
import { useHospitalData } from '@/hooks/useHospitalData';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { Loader2, Search } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';

export default function HospitalPage() {
    const [selectedHospitalId, setSelectedHospitalId] = useState<string | null>(null);
    const data = useHospitalData(selectedHospitalId);

    return (
        <div className="min-h-screen bg-background text-foreground">
            <AppSidebar />
            <main className="pl-64">
                <div className="container mx-auto p-8 max-w-7xl">
                    <header className="mb-8 flex items-start justify-between gap-4">
                        <div>
                            <h1 className="text-4xl font-bold text-white mb-2">Hospital Dashboard</h1>
                            <p className="text-gray-400">Detailed performance analytics per establishment.</p>
                        </div>
                        <div className="w-[400px]">
                            <HospitalSearch
                                onSelect={setSelectedHospitalId}
                                selectedId={selectedHospitalId || undefined}
                            />
                        </div>
                    </header>

                    {!selectedHospitalId && (
                        <div className="flex flex-col items-center justify-center h-[60vh] text-center border-2 border-dashed border-white/10 rounded-2xl bg-surface/20">
                            <div className="p-6 bg-surface-elevated rounded-full mb-4">
                                <Search className="h-12 w-12 text-gray-500" />
                            </div>
                            <h2 className="text-2xl font-bold text-white mb-2">Select a Hospital</h2>
                            <p className="text-gray-400 max-w-md">
                                Use the search bar above to find a hospital by name, city, or FINESS code to view its dashboard.
                            </p>
                        </div>
                    )}

                    {selectedHospitalId && (
                        <div className="space-y-8 animate-in fade-in duration-500">
                            {data.loading && !data.details ? (
                                <div className="flex justify-center py-12">
                                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                </div>
                            ) : (
                                <>
                                    <HospitalHeader hospital={data.details} />

                                    <HospitalSummary data={data} />

                                    <div className="mt-8">
                                        <Tabs defaultValue="activity" className="space-y-6">
                                            <div className="border-b border-white/10 pb-4">
                                                <TabsList className="bg-surface-elevated/50 p-1 border border-white/5 w-full justify-start">
                                                    <TabsTrigger value="activity" className="px-8 py-3 text-lg">📈 Activity</TabsTrigger>
                                                    <TabsTrigger value="complications" className="px-8 py-3 text-lg">🧪 Complications</TabsTrigger>
                                                    <TabsTrigger value="geography" className="px-8 py-3 text-lg">🗺️ Geography</TabsTrigger>
                                                </TabsList>
                                            </div>

                                            <TabsContent value="activity">
                                                <div className="h-64 flex items-center justify-center glass-card rounded-xl text-gray-500">
                                                    Detailed Activity Analysis (Coming in next step)
                                                </div>
                                            </TabsContent>

                                            <TabsContent value="complications">
                                                <div className="h-64 flex items-center justify-center glass-card rounded-xl text-gray-500">
                                                    Detailed Complications Analysis (Coming in next step)
                                                </div>
                                            </TabsContent>

                                            <TabsContent value="geography">
                                                <div className="h-64 flex items-center justify-center glass-card rounded-xl text-gray-500">
                                                    Geography Module (Pending implementation)
                                                </div>
                                            </TabsContent>
                                        </Tabs>
                                    </div>
                                </>
                            )}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
