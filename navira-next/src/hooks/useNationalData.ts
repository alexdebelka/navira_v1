import { useEffect, useState } from 'react';
import { fetchCsv } from '@/lib/data/loader';

export interface NationalData {
    activity: any[];
    robotic: any[];
    complications: any[];
    trends: any[];
    hospitalData: any[]; // TAB_VOL_HOP_YEAR
    volNatl: any[];
    revNatl: any[];
    revStatus: any[];
    rev12m: any[];
    volStatus: any[];
    procedureDetails: any[];
    hospitalsRedux: any[]; // 01_hospitals_redux
    robHosp12m: any[];     // TAB_ROB_HOP_12M
    complNatlYear: any[];  // TAB_COMPL_NATL_YEAR
    complGradeNatlYear: any[]; // TAB_COMPL_GRADE_NATL_YEAR
    neverNatl: any[];      // TAB_NEVER_NATL
    losNatl: any[];        // TAB_LOS_NATL
    los7Natl: any[];       // TAB_LOS7_NATL
    loading: boolean;
    error: Error | null;
}

export function useNationalData() {
    const [data, setData] = useState<NationalData>({
        activity: [],
        robotic: [],
        complications: [],
        trends: [],
        hospitalData: [],
        volNatl: [],
        revNatl: [],
        revStatus: [],
        rev12m: [],
        volStatus: [],
        procedureDetails: [],
        hospitalsRedux: [],
        robHosp12m: [],
        complNatlYear: [],
        complGradeNatlYear: [],
        neverNatl: [],
        losNatl: [],
        los7Natl: [],
        loading: true,
        error: null,
    });

    useEffect(() => {
        async function load() {
            try {
                const [
                    activity,
                    robotic,
                    complications,
                    trends,
                    hospitalData,
                    volNatl,
                    revNatl,
                    revStatus,
                    rev12m,
                    volStatus,
                    procedureDetails,
                    hospitalsRedux,
                    robHosp12m,
                    complNatlYear,
                    complGradeNatlYear,
                    neverNatl,
                    losNatl,
                    los7Natl
                ] = await Promise.all([
                    fetchCsv('/data/ACTIVITY/TAB_TCN_NATL_YEAR.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_APP_NATL_YEAR.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_COMPL_GRADE_NATL_YEAR.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_TREND_NATL.csv').catch(() => []),
                    fetchCsv('/data/ACTIVITY/TAB_VOL_HOP_YEAR.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_VOL_NATL_YEAR.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_REV_NATL.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_REV_STATUS.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_REV_NATL_12M.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_VOL_STATUS_YEAR.csv'),
                    fetchCsv('/data/procedure_details.csv', { header: true, dynamicTyping: true, skipEmptyLines: true }),
                    fetchCsv('/data/01_hospitals_redux.csv'),
                    fetchCsv('/data/ACTIVITY/TAB_ROB_HOP_12M.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_COMPL_NATL_YEAR.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_COMPL_GRADE_NATL_YEAR.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_NEVER_NATL.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_LOS_NATL.csv'),
                    fetchCsv('/data/COMPLICATIONS/TAB_LOS7_NATL.csv'),
                ]);

                setData({
                    activity,
                    robotic,
                    complications,
                    trends,
                    hospitalData,
                    volNatl,
                    revNatl,
                    revStatus,
                    rev12m,
                    volStatus,
                    procedureDetails,
                    hospitalsRedux,
                    robHosp12m: robHosp12m || [],
                    complNatlYear: complNatlYear || [],
                    complGradeNatlYear: complGradeNatlYear || [],
                    neverNatl: neverNatl || [],
                    losNatl: losNatl || [],
                    los7Natl: los7Natl || [],
                    loading: false,
                    error: null,
                });
            } catch (err) {
                console.error("Error loading national data:", err);
                // Continue with partial data if possible or set error
                setData(prev => ({ ...prev, loading: false, error: err as Error }));
            }
        }

        load();
    }, []);

    return data;
}
