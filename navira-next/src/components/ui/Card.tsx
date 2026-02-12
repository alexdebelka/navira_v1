import React from 'react';
import { cn } from '@/lib/utils'; // We need to create this util too

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
    children: React.ReactNode;
    variant?: 'default' | 'glass' | 'elevated';
}

export function Card({ className, children, variant = 'glass', ...props }: CardProps) {
    return (
        <div
            className={cn(
                "rounded-xl p-6 transition-all duration-300",
                variant === 'glass' && "glass-card text-foreground",
                variant === 'elevated' && "bg-surface-elevated border border-white/10 shadow-lg",
                variant === 'default' && "bg-surface-base border border-white/5",
                className
            )}
            {...props}
        >
            {children}
        </div>
    );
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("mb-4", className)} {...props}>{children}</div>;
}

export function CardTitle({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
    return <h3 className={cn("text-lg font-semibold tracking-tight text-white/90", className)} {...props}>{children}</h3>;
}

export function CardContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
    return <div className={cn("", className)} {...props}>{children}</div>;
}
