'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Activity, TrendingUp, AlertCircle, RefreshCw, Hospital, BarChart2, PieChart } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart as RePieChart, Pie, Cell } from 'recharts';
import clsx from 'clsx';

interface SummaryData {
  procedures_2021_2024: number;
  procedures_2025: number;
  trend_2025: string;
  revisional_rate: number;
  complication_rate: number | null;
  volume_history: { year: number; count: number }[];
  approach_mix: { name: string; value: number }[];
}

const HOSPITAL_ID = "930100037"; // Example ID for PoC

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042'];

export default function Dashboard() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch(`http://localhost:8000/api/summary/${HOSPITAL_ID}`);
        if (res.ok) {
          const json = await res.json();
          setData(json);
        }
      } catch (error) {
        console.error("Failed to fetch data", error);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { y: 20, opacity: 0 },
    show: { y: 0, opacity: 1 }
  };

  return (
    <main className="min-h-screen p-8 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-slate-900 via-[#0f172a] to-black text-white">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div>
            <h1 className="text-4xl font-bold tracking-tight">
              <span className="text-gradient">Navira</span> Dashboard
            </h1>
            <p className="text-slate-400 mt-2">Real-time surgical analytics • Next.js PoC</p>
          </div>
          <div className="flex gap-3">
            <div className="px-4 py-2 rounded-full glass text-sm font-medium text-blue-300 flex items-center gap-2">
              <Hospital size={16} />
              Hospital {HOSPITAL_ID}
            </div>
          </div>
        </motion.div>

        {/* Metrics Grid */}
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 animate-pulse">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-40 glass-card rounded-xl bg-slate-800/50"></div>
            ))}
          </div>
        ) : data ? (
          <motion.div
            variants={container}
            initial="hidden"
            animate="show"
            className="space-y-6"
          >
            {/* Top Row: Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Card 1: Total Volume */}
              <motion.div variants={item} className="glass-card relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <Activity size={100} />
                </div>
                <div className="flex items-center gap-3 mb-4 text-blue-400">
                  <Activity size={24} />
                  <h3 className="font-medium">Total Procedures</h3>
                </div>
                <div className="space-y-1">
                  <div className="text-4xl font-bold text-white">
                    {data.procedures_2021_2024.toLocaleString()}
                  </div>
                  <p className="text-sm text-slate-400">2021 – 2024</p>
                </div>
              </motion.div>

              {/* Card 2: 2025 Volume & Trend */}
              <motion.div variants={item} className="glass-card relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <TrendingUp size={100} />
                </div>
                <div className="flex items-center gap-3 mb-4 text-emerald-400">
                  <TrendingUp size={24} />
                  <h3 className="font-medium">2025 Activity</h3>
                </div>
                <div className="flex items-end gap-4">
                  <div>
                    <div className="text-4xl font-bold text-white">
                      {data.procedures_2025.toLocaleString()}
                    </div>
                    <p className="text-sm text-slate-400">Procedures (YTD)</p>
                  </div>
                  <div className={clsx(
                    "px-3 py-1 rounded-full text-sm font-bold mb-1",
                    data.trend_2025.includes('+') ? "bg-emerald-500/20 text-emerald-300" : "bg-red-500/20 text-red-300"
                  )}>
                    {data.trend_2025}
                  </div>
                </div>
              </motion.div>

              {/* Card 3: Key Rates */}
              <motion.div variants={item} className="glass-card relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                  <AlertCircle size={100} />
                </div>
                <div className="flex items-center gap-3 mb-4 text-purple-400">
                  <AlertCircle size={24} />
                  <h3 className="font-medium">Key Indicators</h3>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-2xl font-bold text-white">
                      {data.revisional_rate.toFixed(1)}%
                    </div>
                    <p className="text-xs text-slate-400 flex items-center gap-1">
                      <RefreshCw size={12} /> Revisional
                    </p>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-white">
                      {data.complication_rate ? `${data.complication_rate.toFixed(1)}%` : 'N/A'}
                    </div>
                    <p className="text-xs text-slate-400 flex items-center gap-1">
                      <AlertCircle size={12} /> Complications
                    </p>
                  </div>
                </div>
              </motion.div>
            </div>

            {/* Bottom Row: Charts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Chart 1: Volume History */}
              <motion.div variants={item} className="glass-card h-[350px] flex flex-col">
                <div className="flex items-center gap-3 mb-6 text-blue-400">
                  <BarChart2 size={20} />
                  <h3 className="font-medium">Volume History</h3>
                </div>
                <div className="flex-1 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.volume_history}>
                      <XAxis
                        dataKey="year"
                        stroke="#94a3b8"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        stroke="#94a3b8"
                        fontSize={12}
                        tickLine={false}
                        axisLine={false}
                      />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }}
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                      />
                      <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </motion.div>

              {/* Chart 2: Surgical Approach */}
              <motion.div variants={item} className="glass-card h-[350px] flex flex-col">
                <div className="flex items-center gap-3 mb-6 text-purple-400">
                  <PieChart size={20} />
                  <h3 className="font-medium">Surgical Approach (2024)</h3>
                </div>
                <div className="flex-1 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <RePieChart>
                      <Pie
                        data={data.approach_mix}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        fill="#8884d8"
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {data.approach_mix.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }}
                      />
                    </RePieChart>
                  </ResponsiveContainer>
                  <div className="flex justify-center gap-4 mt-4">
                    {data.approach_mix.map((entry, index) => (
                      <div key={index} className="flex items-center gap-2 text-xs text-slate-400">
                        <div className="w-3 h-3 rounded-full" style={{ backgroundColor: COLORS[index % COLORS.length] }} />
                        {entry.name}
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            </div>

          </motion.div>
        ) : (
          <div className="text-center text-red-400 p-8 glass-card">
            Failed to load data. Ensure the backend is running.
          </div>
        )}
      </div>
    </main>
  );
}
