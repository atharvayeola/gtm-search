"use client";

import { useEffect, useState } from 'react';
import { Building2, MapPin, Users, TrendingUp, Search, ArrowRight, ArrowLeft } from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';
import Link from 'next/link';

const API_BASE = 'http://localhost:8000';

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const debouncedSearch = useDebounce(search, 500);

  useEffect(() => {
    async function fetchCompanies() {
      setLoading(true);
      const params = new URLSearchParams();
      params.set('page', page.toString());
      params.set('page_size', '12'); // Grid layout usually 3x4
      params.set('ordering', '-job_count');
      if (debouncedSearch) params.set('q', debouncedSearch);

      try {
        const res = await fetch(`${API_BASE}/companies?${params.toString()}`);
        const data = await res.json();
        setCompanies(data.companies);
        setTotal(data.total);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    fetchCompanies();
  }, [page, debouncedSearch]);

  return (
    <div className="p-8 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <Link href="/" className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] flex items-center gap-1 mb-2 transition-colors">
            <ArrowLeft size={12} /> Back to Dashboard
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Companies</h1>
          <p className="text-[var(--text-secondary)]">{total} companies hiring now</p>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-md">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
        <input
          type="text"
          placeholder="Search companies by name..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="input-base !pl-12 w-full"
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            className="absolute right-2 top-1/2 -translate-y-1/2 bg-slate-200 text-slate-600 text-xs px-2 py-1 rounded-md hover:bg-slate-300 font-medium transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="py-20 text-center text-[var(--text-secondary)]">Loading directory...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {companies.map((company) => (
            <Link
              href={`/companies/${company.id}`}
              key={company.id}
              className="bg-white hover:shadow-lg group cursor-pointer flex flex-col h-full rounded-2xl p-5 border border-slate-200 transition-all duration-300 hover:border-slate-300"
            >
              <div className="flex justify-between items-start mb-4">
                <div className="w-12 h-12 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-400 group-hover:text-[#E07A5F] group-hover:bg-[#E07A5F]/5 transition-all">
                  <Building2 size={24} />
                </div>
                {company.job_count > 50 && (
                  <span className="bg-emerald-50 text-emerald-600 text-[10px] px-2 py-1 rounded-full flex items-center gap-1 font-medium border border-emerald-100">
                    <TrendingUp size={10} /> GROWING
                  </span>
                )}
              </div>

              <div className="mb-4">
                <h3 className="font-bold text-lg text-slate-900 mb-1 truncate pr-2 group-hover:text-[#E07A5F] transition-colors">{company.name}</h3>
                <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">
                  {company.domain || 'Tech Company'}
                </p>
              </div>

              <div className="mt-auto pt-4 border-t border-slate-100 flex justify-between items-center">
                <div className="flex items-center gap-1.5 text-slate-700 font-medium text-sm">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  {company.job_count} Open Roles
                </div>
                <ArrowRight size={16} className="text-slate-400 group-hover:translate-x-1 transition-transform group-hover:text-[#E07A5F]" />
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Pagination */}
      <div className="flex justify-center items-center gap-2 mt-12 pb-8">
        <button
          disabled={page === 1}
          onClick={() => setPage(p => p - 1)}
          className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <span className="sr-only">Previous</span>
          <ArrowLeft size={16} />
        </button>

        <div className="flex items-center gap-1">
          {(() => {
            const pageSize = 12;
            const totalPages = Math.ceil(total / pageSize);
            const pages = [];
            const maxVisible = 5;

            let start = Math.max(1, page - Math.floor(maxVisible / 2));
            let end = Math.min(totalPages, start + maxVisible - 1);

            if (end - start + 1 < maxVisible) {
              start = Math.max(1, end - maxVisible + 1);
            }

            for (let i = start; i <= end; i++) {
              pages.push(
                <button
                  key={i}
                  onClick={() => setPage(i)}
                  className={`w-10 h-10 rounded-lg text-sm font-medium transition-all ${page === i
                      ? 'bg-[#E07A5F] text-white shadow-md shadow-[#E07A5F]/20'
                      : 'text-slate-600 hover:bg-slate-50 border border-transparent hover:border-slate-200'
                    }`}
                >
                  {i}
                </button>
              );
            }
            return pages;
          })()}
        </div>

        <button
          disabled={page >= Math.ceil(total / 12)}
          onClick={() => setPage(p => p + 1)}
          className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}
