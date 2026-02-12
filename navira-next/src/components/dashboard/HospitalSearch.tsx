"use client";

import * as React from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
} from "@/components/ui/Command";
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/Popover";
import { fetchCsv } from '@/lib/data/loader';

interface HospitalSearchProps {
    onSelect: (hospitalId: string) => void;
    selectedId?: string;
    className?: string;
}

interface HospitalOption {
    value: string; // ID
    label: string; // Name + City
    search: string; // Searchable text
}

export function HospitalSearch({ onSelect, selectedId, className }: HospitalSearchProps) {
    const [open, setOpen] = React.useState(false);
    const [value, setValue] = React.useState(selectedId || "");
    const [options, setOptions] = React.useState<HospitalOption[]>([]);
    const [loading, setLoading] = React.useState(false);
    const [searchTerm, setSearchTerm] = React.useState("");

    React.useEffect(() => {
        // Load hospitals list
        setLoading(true);
        fetchCsv('/data/01_hospitals_redux.csv')
            .then((data) => {
                const opts = data.map((h: any) => ({
                    value: String(h.finessGeo).trim(),
                    label: `${h.rs} (${h.ville})`,
                    search: `${h.rs} ${h.ville} ${h.finessGeo}`.toLowerCase()
                })).sort((a: any, b: any) => a.label.localeCompare(b.label));
                setOptions(opts);
                setLoading(false);
            })
            .catch((err) => {
                console.error("Failed to load hospitals for search", err);
                setLoading(false);
            });
    }, []);

    React.useEffect(() => {
        if (selectedId) setValue(selectedId);
    }, [selectedId]);

    const filteredOptions = React.useMemo(() => {
        if (!searchTerm) return options.slice(0, 50);
        const lower = searchTerm.toLowerCase();
        return options
            .filter(o => o.search.includes(lower))
            .slice(0, 50);
    }, [options, searchTerm]);

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    className={cn("w-full justify-between bg-surface-elevated/50 border-white/10 text-left font-normal", className)}
                >
                    {value
                        ? options.find((framework) => framework.value === value)?.label
                        : "Search hospital by name, city or FINESS..."}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[400px] p-0 bg-surface-elevated border-white/10 backdrop-blur-xl">
                <Command className="bg-transparent" shouldFilter={false}>
                    <CommandInput
                        placeholder="Search hospital..."
                        className="text-white"
                        onValueChange={setSearchTerm}
                    />
                    <CommandList>
                        <CommandEmpty>
                            {loading ? "Loading..." : "No hospital found."}
                        </CommandEmpty>
                        <CommandGroup>
                            {filteredOptions.map((framework) => (
                                <CommandItem
                                    key={framework.value}
                                    value={framework.value} // Use ID as value since we handle filtering
                                    onSelect={(currentValue) => {
                                        setValue(currentValue);
                                        onSelect(currentValue);
                                        setOpen(false);
                                    }}
                                    className="text-gray-300 aria-selected:bg-white/10 aria-selected:text-white"
                                >
                                    <Check
                                        className={cn(
                                            "mr-2 h-4 w-4",
                                            value === framework.value ? "opacity-100" : "opacity-0"
                                        )}
                                    />
                                    {framework.label}
                                </CommandItem>
                            ))}
                        </CommandGroup>
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    );
}
