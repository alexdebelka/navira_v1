import Papa from 'papaparse';

export interface CsvRow {
    [key: string]: string | number | null | undefined;
}

export interface LoadOptions {
    header?: boolean;
    dynamicTyping?: boolean;
    skipEmptyLines?: boolean;
}

const CACHE: Record<string, any[]> = {};

export async function fetchCsv<T>(
    path: string,
    options: LoadOptions = { header: true, dynamicTyping: true, skipEmptyLines: true }
): Promise<T[]> {
    if (CACHE[path]) {
        return CACHE[path] as T[];
    }

    try {
        const response = await fetch(path);
        if (!response.ok) {
            throw new Error(`Failed to fetch CSV at ${path}: ${response.statusText}`);
        }
        const csvText = await response.text();

        return new Promise((resolve, reject) => {
            Papa.parse(csvText, {
                ...options,
                complete: (results: Papa.ParseResult<any>) => {
                    if (results.errors.length > 0) {
                        console.warn(`CSV parsing warnings for ${path}:`, results.errors);
                    }
                    const data = results.data as T[];
                    CACHE[path] = data;
                    resolve(data);
                },
                error: (error: Error) => {
                    reject(error);
                },
            });
        });
    } catch (error) {
        console.error(`Error loading CSV ${path}:`, error);
        return [];
    }
}

// Specific Data Loaders

export interface ActivityData {
    annee: number;
    n: number;
    baria_t?: string | null;
    vda?: string | null;
    finessGeoDP?: string | number | null;
    [key: string]: any;
}

export interface HospitalData {
    finessGeoDP: string | number;
    nom_etablissement?: string | null;
    statut?: string | null;
    cso?: number | null;
    LAB_SOFFCO?: number | null;
    annee: number;
    [key: string]: any;
}

export interface ComplicationData {
    annee: number;
    COMPL_pct?: number | null;
    COMPL_nb?: number | null;
    clav_cat_90?: number | null;
    finessGeoDP?: string | number | null;
    [key: string]: any;
}
