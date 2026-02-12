"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface TabsProps {
    defaultValue: string;
    className?: string;
    children: React.ReactNode;
}

const TabsContext = React.createContext<{
    value: string;
    onValueChange: (value: string) => void;
} | null>(null);

export function Tabs({ defaultValue, className, children }: TabsProps) {
    const [value, setValue] = React.useState(defaultValue);

    return (
        <TabsContext.Provider value={{ value, onValueChange: setValue }}>
            <div className={cn("w-full", className)}>{children}</div>
        </TabsContext.Provider>
    );
}

interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> { }

export function TabsList({ className, children, ...props }: TabsListProps) {
    return (
        <div
            className={cn(
                "inline-flex h-10 items-center justify-center rounded-lg bg-surface-base p-1 text-muted-foreground",
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    value: string;
}

export function TabsTrigger({ className, value, children, ...props }: TabsTriggerProps) {
    const context = React.useContext(TabsContext);
    const isActive = context?.value === value;

    return (
        <button
            className={cn(
                "inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
                isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "hover:bg-white/5 hover:text-white",
                className
            )}
            onClick={() => context?.onValueChange(value)}
            {...props}
        >
            {children}
        </button>
    );
}

interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
    value: string;
}

export function TabsContent({ className, value, children, ...props }: TabsContentProps) {
    const context = React.useContext(TabsContext);
    if (context?.value !== value) return null;

    return (
        <div
            className={cn(
                "mt-4 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 animate-in fade-in slide-in-from-top-2 duration-300",
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}
