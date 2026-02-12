"use client";

import { OverallTrends } from '@/components/sections/OverallTrends';
import { HospitalsSection } from '@/components/sections/Hospitals';
import { TechniquesSection } from '@/components/sections/Techniques';
import { RobotSection } from '@/components/sections/Robot';
import { ComplicationsSection } from '@/components/sections/Complications';
import { AppSidebar } from '@/components/layout/AppSidebar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';

export default function NationalPage() {
    return (
        <div className="min-h-screen bg-background text-foreground">
            <AppSidebar />
            <main className="pl-64">
                <div className="container mx-auto p-8 max-w-7xl">
                    <header className="mb-8 flex items-end justify-between">
                        <div>
                            <h1 className="text-4xl font-bold text-white mb-2">National Overview</h1>
                            <p className="text-gray-400">Analysis of bariatric surgery trends, outcomes, and hospital performance.</p>
                        </div>
                    </header>

                    <Tabs defaultValue="trends" className="space-y-6">
                        <div className="border-b border-white/10 pb-4">
                            <TabsList className="bg-surface-elevated/50 p-1 border border-white/5">
                                <TabsTrigger value="trends" className="px-6">Overall Trends</TabsTrigger>
                                <TabsTrigger value="hospitals" className="px-6">Hospitals</TabsTrigger>
                                <TabsTrigger value="techniques" className="px-6">Techniques</TabsTrigger>
                                <TabsTrigger value="robot" className="px-6">Robot</TabsTrigger>
                                <TabsTrigger value="complications" className="px-6">Complications</TabsTrigger>
                            </TabsList>
                        </div>

                        <TabsContent value="trends" className="space-y-6">
                            <OverallTrends />
                        </TabsContent>

                        <TabsContent value="hospitals" className="space-y-6">
                            <HospitalsSection />
                        </TabsContent>

                        <TabsContent value="techniques" className="space-y-6">
                            <TechniquesSection />
                        </TabsContent>

                        <TabsContent value="robot" className="space-y-6">
                            <RobotSection />
                        </TabsContent>

                        <TabsContent value="complications" className="space-y-6">
                            <ComplicationsSection />
                        </TabsContent>
                    </Tabs>
                </div>
            </main>
        </div>
    );
}
