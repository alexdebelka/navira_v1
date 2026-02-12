"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { LayoutDashboard, Globe, Activity, Settings } from 'lucide-react';

const NAV_ITEMS = [
    { href: '/national', label: 'National', icon: Globe },
    { href: '/hospitals', label: 'Hospitals', icon: LayoutDashboard }, // Placeholder
    // Add more
];

export function AppSidebar() {
    const pathname = usePathname();

    return (
        <div className="w-64 h-screen glass border-r border-white/10 flex flex-col fixed left-0 top-0 z-50">
            <div className="p-6">
                <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-cyan-300 tracking-tighter">
                    NAVIRA
                </h1>
                <p className="text-xs text-gray-400 mt-1">National Dashboard</p>
            </div>

            <nav className="flex-1 px-4 space-y-2">
                {NAV_ITEMS.map((item) => {
                    const Icon = item.icon;
                    const isActive = pathname.startsWith(item.href);

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all group",
                                isActive
                                    ? "bg-primary/20 text-primary border border-primary/20"
                                    : "text-gray-400 hover:text-white hover:bg-white/5"
                            )}
                        >
                            <Icon className={cn("w-5 h-5", isActive ? "text-primary" : "text-gray-500 group-hover:text-white")} />
                            {item.label}
                        </Link>
                    );
                })}
            </nav>

            <div className="p-4 border-t border-white/10">
                <div className="flex items-center gap-3 px-4 py-2 text-gray-400 text-xs">
                    <Activity className="w-4 h-4" />
                    <span>v2.0.0 (Next.js)</span>
                </div>
            </div>
        </div>
    );
}
