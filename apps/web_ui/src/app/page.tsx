"use client";

import { useEffect, useState } from 'react';
import {
  Briefcase,
  Building2,
  TrendingUp,
  DollarSign,
  ArrowRight,
  Loader2
} from 'lucide-react';
import {
  ResponsiveContainer
} from 'recharts';
import Link from 'next/link';

const API_BASE = 'http://localhost:8000';

// Provided Component
const StatsCard = ({ title, value, subtitle, icon: Icon, trend, trendValue, accentColor }: any) => (
  <div className="bg-white rounded-2xl border border-slate-200 p-6 flex items-start justify-between hover:shadow-lg transition-shadow duration-300">
    <div>
      <p className="text-slate-500 text-sm font-medium mb-1">{title}</p>
      <h3 className="text-3xl font-bold text-slate-900 tracking-tight mb-2">{value}</h3>
      <div className="flex items-center gap-2">
        {trend === 'up' && (
          <span className="bg-emerald-50 text-emerald-600 text-xs px-2 py-0.5 rounded-full font-medium flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> {trendValue}
          </span>
        )}
        <span className="text-slate-400 text-xs">{subtitle}</span>
      </div>
    </div>
    <div
      className="w-12 h-12 rounded-xl flex items-center justify-center"
      style={{ backgroundColor: `${accentColor}15`, color: accentColor }}
    >
      <Icon className="w-6 h-6" />
    </div>
  </div>
);

export default function Dashboard() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({
    totalJobs: 0,
    activeCompanies: 0,
    avgSalary: 0,
    remotePercent: 0,
    remoteJobs: 0 // Added for new UI
  });
  const [recentCompanies, setRecentCompanies] = useState<any[]>([]);


  useEffect(() => {
    async function fetchData() {
      try {
        const [jobsRes, companiesRes, remoteRes, salaryRes] = await Promise.all([
          fetch(`${API_BASE}/jobs?page_size=1`),
          fetch(`${API_BASE}/companies?page_size=10&ordering=-job_count`),
          fetch(`${API_BASE}/jobs/stats/remote`),
          fetch(`${API_BASE}/jobs/stats/salary`),
        ]);

        const jobsData = await jobsRes.json();
        const companiesData = await companiesRes.json();
        const remoteData = await remoteRes.json();
        const salaryData = await salaryRes.json();

        setStats({
          totalJobs: jobsData.total,
          activeCompanies: companiesData.total,
          avgSalary: Math.round(salaryData.median_salary / 1000),
          remotePercent: remoteData.find((r: any) => r.name === 'remote')?.count
            ? Math.round((remoteData.find((r: any) => r.name === 'remote').count / (remoteData.reduce((a: any, b: any) => a + b.count, 0) || 1)) * 100)
            : 0,
          remoteJobs: remoteData.find((r: any) => r.name === 'remote')?.count || 0
        });

        // Filter out "Unknown" from hiring companies
        setRecentCompanies(companiesData.companies.filter((c: any) =>
          c.name && c.name.toLowerCase() !== 'unknown' && c.domain?.toLowerCase() !== 'unknown'
        ).slice(0, 5));

        setLoading(false);
      } catch (err) {
        console.error(err);
        setLoading(false);
      }
    }

    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#E07A5F] mx-auto mb-4" />
          <p className="text-slate-500">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-slate-500 mt-1">Job market intelligence at a glance</p>
        </div>
        <Link href="/jobs" className="bg-slate-900 hover:bg-slate-800 text-white rounded-xl h-11 px-6 gap-2 inline-flex items-center transition-colors font-medium">
          Explore Jobs
          <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Jobs"
          value={stats.totalJobs.toLocaleString()}
          subtitle="Active postings"
          icon={Briefcase}
          trend="up"
          trendValue="+12.5%"
          accentColor="#E07A5F"
        />
        <StatsCard
          title="Companies"
          value={stats.activeCompanies.toLocaleString()}
          subtitle="Actively hiring"
          icon={Building2}
          trend="up"
          trendValue="+8.2%"
          accentColor="#84A98C"
        />
        <StatsCard
          title="Median Salary"
          value={`$${stats.avgSalary}k`}
          subtitle="Across all roles"
          icon={DollarSign}
          trend="up"
          trendValue="+5.3%"
          accentColor="#0F172A"
        />
        <StatsCard
          title="Remote Jobs"
          value={`${stats.remotePercent}%`}
          subtitle={`${stats.remoteJobs} positions in sample`}
          icon={TrendingUp}
          accentColor="#52796F"
        />
      </div>


      {/* Top Hiring Companies */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-slate-900">Top Hiring Companies</h3>
          <Link href="/companies" className="text-sm text-[#E07A5F] hover:text-[#C45C40] font-medium flex items-center gap-1">
            View all
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="space-y-4">
          {recentCompanies.map((company, idx) => (
            <Link
              href={`/companies/${company.id}`} // Fixed Navigation
              key={company.id}
              className="flex items-center gap-4 p-4 rounded-xl hover:bg-slate-50 transition-colors cursor-pointer group"
            >
              <span className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-sm font-semibold text-slate-500">
                {idx + 1}
              </span>
              <div className="w-10 h-10 bg-gradient-to-br from-slate-100 to-slate-200 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
                <Building2 className="w-5 h-5 text-slate-400" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-900 truncate group-hover:text-[#E07A5F] transition-colors">{company.name}</p>
                <p className="text-sm text-slate-500">{company.domain || 'Technology'}</p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-slate-900">{company.job_count || 0}</p>
                <p className="text-xs text-slate-500">open roles</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
