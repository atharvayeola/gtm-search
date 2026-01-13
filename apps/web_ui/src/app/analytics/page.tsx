"use client";

import { useEffect, useState } from 'react';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell,
    Legend
} from 'recharts';
import { Activity } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

// Updated Palette: Terra Cotta, Sage, Charcoal, Sandy, Dark Sage
const CHART_COLORS = ['#E07A5F', '#84A98C', '#3D405B', '#F2CC8F', '#52796F'];

export default function AnalyticsPage() {
    const [loading, setLoading] = useState(true);
    const [jobsByDept, setJobsByDept] = useState<any[]>([]);
    const [workArrangement, setWorkArrangement] = useState<any[]>([]);
    const [salaryDist, setSalaryDist] = useState<any[]>([]);
    const [seniorityLevels, setSeniorityLevels] = useState<any[]>([]);

    useEffect(() => {
        async function fetchData() {
            try {
                const [functionsRes, seniorityRes, remoteRes, salaryBucketsRes] = await Promise.all([
                    fetch(`${API_BASE}/jobs/stats/functions`),
                    fetch(`${API_BASE}/jobs/stats/seniority`),
                    fetch(`${API_BASE}/jobs/stats/remote`),
                    fetch(`${API_BASE}/jobs/stats/salary/buckets`),
                ]);

                const functionsData = await functionsRes.json();
                const seniorityData = await seniorityRes.json();
                const remoteData = await remoteRes.json();
                const bucketsData = await salaryBucketsRes.json();

                // 1. Department
                setJobsByDept(functionsData.slice(0, 10).map((d: any) => ({
                    name: d.name.charAt(0).toUpperCase() + d.name.slice(1).replace('_', ' '),
                    value: d.count
                })));

                // 2. Work Arrangement
                setWorkArrangement(remoteData.map((r: any) => ({
                    name: r.name.charAt(0).toUpperCase() + r.name.slice(1),
                    value: r.count
                })));

                // 3. Salary Distribution
                setSalaryDist(bucketsData.map((b: any) => ({
                    name: b.name,
                    value: b.count
                })));

                // 4. Seniority
                setSeniorityLevels(seniorityData.map((s: any) => ({
                    name: s.name.toUpperCase(),
                    value: s.count
                })));

                setLoading(false);
            } catch (err) {
                console.error(err);
            }
        }
        fetchData();
    }, []);

    if (loading) return <div className="p-10 text-slate-500 flex items-center gap-3"><Activity className="animate-spin text-[#E07A5F]" /> Analyzing market data...</div>;

    return (
        <div className="p-8 space-y-8">
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-slate-900 mb-2">Analytics</h1>
                <p className="text-slate-500">Deep dive into job market insights based on recent postings.</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Department */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="font-bold text-slate-900 mb-6">Jobs by Department</h3>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={jobsByDept} layout="vertical" margin={{ left: 40 }}>
                                <XAxis type="number" hide />
                                <YAxis dataKey="name" type="category" width={100} tick={{ fill: '#64748B', fontSize: 12 }} axisLine={false} tickLine={false} />
                                <Tooltip cursor={{ fill: '#F1F5F9' }} contentStyle={{ backgroundColor: '#fff', borderColor: '#E2E8F0', color: '#0F172A', borderRadius: '12px' }} />
                                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                                    {jobsByDept.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Work Arrangement */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="font-bold text-slate-900 mb-6">Work Arrangement</h3>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <PieChart>
                                <Pie
                                    data={workArrangement}
                                    cx="50%" cy="50%"
                                    innerRadius={60}
                                    outerRadius={100}
                                    paddingAngle={5}
                                    dataKey="value"
                                >
                                    {workArrangement.map((_, index) => (
                                        <Cell key={`cell-${index}`} fill={CHART_COLORS[index % 5]} stroke="#fff" strokeWidth={2} />
                                    ))}
                                </Pie>
                                <Tooltip contentStyle={{ backgroundColor: '#fff', borderColor: '#E2E8F0', color: '#0F172A', borderRadius: '12px' }} />
                                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                            </PieChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Salary Distribution */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="font-bold text-slate-900 mb-6">Salary Distribution</h3>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={salaryDist}>
                                <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 11 }} axisLine={false} tickLine={false} />
                                <Tooltip cursor={{ fill: '#F1F5F9' }} contentStyle={{ backgroundColor: '#fff', borderColor: '#E2E8F0', color: '#0F172A', borderRadius: '12px' }} />
                                <Bar dataKey="value" fill="#84A98C" radius={[4, 4, 0, 0]} barSize={40} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                {/* Seniority Levels */}
                <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
                    <h3 className="font-bold text-slate-900 mb-6">Seniority Levels</h3>
                    <div className="h-[300px]">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={seniorityLevels} layout="vertical" margin={{ left: 40 }}>
                                <XAxis type="number" hide />
                                <YAxis dataKey="name" type="category" width={100} tick={{ fill: '#64748B', fontSize: 12 }} axisLine={false} tickLine={false} />
                                <Tooltip cursor={{ fill: '#F1F5F9' }} contentStyle={{ backgroundColor: '#fff', borderColor: '#E2E8F0', color: '#0F172A', borderRadius: '12px' }} />
                                <Bar dataKey="value" fill="#3D405B" radius={[0, 4, 4, 0]} barSize={20} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>

            </div>
        </div>
    );
}
