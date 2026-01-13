"use client";

import React, { useState, useEffect, useCallback, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Building2,
  MapPin,
  Clock,
  DollarSign,
  Search,
  Sparkles,
  Zap,
  Tag,
  ChevronDown,
  X,
  ArrowLeft,
  ArrowRight
} from 'lucide-react';
import Link from 'next/link';
import { useDebounce } from '@/hooks/useDebounce';

const API_BASE = 'http://localhost:8000';

interface Job {
  id: string;
  role_title: string;
  company_name: string;
  company_id: string;
  location_city: string | null;
  location_state: string | null;
  location_country: string | null;
  remote_type: string;
  seniority_level: string;
  job_function: string;
  employment_type: string;
  salary_min_usd: number | null;
  salary_max_usd: number | null;
  confidence: number;
}

interface SkillSuggestion {
  id: string;
  name: string;
  type: string | null;
  job_count: number;
}

const FILTER_OPTIONS = {
  seniority: [
    { label: 'Intern', value: 'intern' },
    { label: 'Junior', value: 'junior' },
    { label: 'Mid-Level', value: 'mid' },
    { label: 'Senior', value: 'senior' },
    { label: 'Staff', value: 'staff' },
    { label: 'Principal', value: 'principal' },
    { label: 'Manager', value: 'manager' },
    { label: 'Director', value: 'director' },
    { label: 'VP', value: 'vp' },
    { label: 'CXO', value: 'cxo' },
  ],
  functions: [
    { label: 'Engineering', value: 'engineering' },
    { label: 'Product Marketing', value: 'product_marketing' },
    { label: 'Sales Operations', value: 'sales_ops' },
    { label: 'Operations', value: 'operations' },
    { label: 'Solutions Engineering', value: 'solutions_engineering' },
    { label: 'HR', value: 'hr' },
    { label: 'Security', value: 'security' },
    { label: 'GTM Engineering', value: 'gtm_engineering' },
    { label: 'Customer Success', value: 'customer_success' },
    { label: 'Finance', value: 'finance' },
    { label: 'IT', value: 'it' },
    { label: 'Legal', value: 'legal' },
    { label: 'Data', value: 'data' },
    { label: 'RevOps', value: 'revops' },
    { label: 'Marketing', value: 'marketing' },
    { label: 'Sales', value: 'sales' },
  ],
  remote: [
    { label: 'Remote', value: 'remote' },
    { label: 'Hybrid', value: 'hybrid' },
    { label: 'On-site', value: 'onsite' },
  ],
};

function FilterSelect({ label, value, options, onChange, align = 'left' }: {
  label: string,
  value: string,
  options: { label: string, value: string }[],
  onChange: (val: string) => void,
  align?: 'left' | 'right'
}) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectedLabel = options.find(o => o.value === value)?.label;

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-all ${value
          ? 'bg-[#E07A5F]/10 border-[#E07A5F] text-[#E07A5F]'
          : 'bg-white border-slate-200 text-slate-600 hover:border-slate-300'
          }`}
      >
        <span>{value ? selectedLabel : label}</span>
        <ChevronDown size={14} className={`transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className={`absolute top-full mt-1 w-64 bg-white border border-slate-200 rounded-xl shadow-lg z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100 ${align === 'right' ? 'right-0' : 'left-0'}`}>
          <div className="px-3 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wider bg-slate-50 border-b border-slate-100">
            Select {label}
          </div>
          <div className="max-h-60 overflow-y-auto p-1">
            {options.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  onChange(opt.value === value ? '' : opt.value);
                  setIsOpen(false);
                }}
                className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors flex items-center justify-between ${opt.value === value
                  ? 'bg-[#E07A5F]/10 text-[#E07A5F] font-medium'
                  : 'text-slate-700 hover:bg-slate-50'
                  }`}
              >
                <span className="truncate pr-2">{opt.label}</span>
                {opt.value === value && <div className="w-1.5 h-1.5 rounded-full bg-[#E07A5F] flex-shrink-0" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function JobsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // State
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  // Filters
  const [textSearch, setTextSearch] = useState('');
  const [naturalQuery, setNaturalQuery] = useState('');
  const [seniority, setSeniority] = useState<string[]>([]);
  const [jobFunction, setJobFunction] = useState<string[]>([]);
  const [remoteType, setRemoteType] = useState<string[]>([]);
  const [location, setLocation] = useState<string>('');
  const [locationOptions, setLocationOptions] = useState<{ label: string, value: string }[]>([]);
  const [salaryMin, setSalaryMin] = useState<string>('');
  const [salaryMax, setSalaryMax] = useState<string>('');
  const [selectedSkills, setSelectedSkills] = useState<SkillSuggestion[]>([]);

  // NLP State
  const [isParsing, setIsParsing] = useState(false);
  const [parseExplanation, setParseExplanation] = useState('');

  const debouncedSearch = useDebounce(textSearch, 500);

  // Fetch Jobs
  const fetchJobs = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();

    // Core params
    params.set('page', page.toString());
    params.set('page_size', '20');

    // Filters
    if (debouncedSearch) params.set('q', debouncedSearch);
    seniority.forEach(s => params.append('seniority', s));
    jobFunction.forEach(f => params.append('function', f));
    remoteType.forEach(r => params.append('remote_type', r));
    if (salaryMin) params.set('salary_min', salaryMin);
    if (salaryMax) params.set('salary_max', salaryMax);
    if (location) {
      const [city, state] = location.split(',').map(s => s.trim());
      if (city) params.set('city', city);
      if (state) params.set('state', state);
    }
    selectedSkills.forEach(s => params.append('skill', s.name));

    try {
      const res = await fetch(`${API_BASE}/jobs?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data.jobs);
        setTotal(data.total);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, debouncedSearch, seniority, jobFunction, remoteType, location, salaryMin, salaryMax, selectedSkills]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  useEffect(() => {
    const fetchLocationOptions = async () => {
      try {
        const res = await fetch(`${API_BASE}/jobs/stats/locations`);
        if (res.ok) {
          const data = await res.json();
          setLocationOptions(data.map((l: any) => ({ label: l.name, value: l.name })));
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchLocationOptions();
  }, []);

  // NLP Search Handler
  const handleNaturalSearch = async () => {
    if (!naturalQuery.trim()) return;
    setIsParsing(true);
    setParseExplanation('');

    try {
      const res = await fetch(`${API_BASE}/search/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: naturalQuery })
      });

      if (res.ok) {
        const data = await res.json();
        const f = data.filters;

        // Apply Filters
        if (f.seniority) setSeniority(f.seniority);
        if (f.job_function) setJobFunction(f.job_function);
        if (f.remote_type) setRemoteType(f.remote_type);
        if (f.salary_min) setSalaryMin(f.salary_min.toString());

        if (f.location_city && f.location_state) {
          setLocation(`${f.location_city}, ${f.location_state}`);
        } else if (f.location_city && f.location_city !== 'Unknown') {
          setTextSearch(f.location_city);
        }

        setParseExplanation(data.explanation);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsParsing(false);
    }
  };

  // Smart Search Logic
  useEffect(() => {
    if (!debouncedSearch) return;

    // Check for exact matches in filter options
    const term = debouncedSearch.toLowerCase().trim();

    // Helper to find match
    const findMatch = (options: { label: string, value: string }[]) =>
      options.find(o => o.label.toLowerCase() === term || o.value.toLowerCase() === term);

    const funcMatch = findMatch(FILTER_OPTIONS.functions);
    if (funcMatch) {
      setJobFunction([funcMatch.value]);
      setTextSearch(''); // Clear text input as it's now a filter
      return;
    }

    const senMatch = findMatch(FILTER_OPTIONS.seniority);
    if (senMatch) {
      setSeniority([senMatch.value]);
      setTextSearch('');
      return;
    }

    const remMatch = findMatch(FILTER_OPTIONS.remote);
    if (remMatch) {
      setRemoteType([remMatch.value]);
      setTextSearch('');
      return;
    }

  }, [debouncedSearch]);

  const clearFilters = () => {
    setSeniority([]);
    setJobFunction([]);
    setRemoteType([]);
    setLocation('');
    setSalaryMin('');
    setSalaryMax('');
    setSelectedSkills([]);
    setTextSearch('');
    setNaturalQuery('');
    setParseExplanation('');
    setPage(1);
  };

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 mb-1">Job Explorer</h1>
          <p className="text-slate-500">{total} jobs found</p>
        </div>
      </div>

      {/* NLP Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm relative overflow-hidden group focus-within:ring-2 focus-within:ring-[#E07A5F]/20 transition-all">
        <div className="relative flex gap-3">
          <div className={`p-3 rounded-lg flex items-center justify-center transition-colors ${isParsing ? 'bg-[#E07A5F]/10 text-[#E07A5F] animate-pulse' : 'bg-slate-100 text-slate-500'}`}>
            {isParsing ? <Zap size={20} /> : <Sparkles size={20} />}
          </div>
          <input
            type="text"
            value={naturalQuery}
            onChange={(e) => setNaturalQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleNaturalSearch()}
            placeholder="Try: 'Senior engineering roles in NYC paying over $200k'"
            className="flex-1 bg-transparent border-none text-slate-900 placeholder-slate-400 focus:ring-0 text-lg outline-none"
          />
          <button
            onClick={handleNaturalSearch}
            disabled={isParsing}
            className="btn-primary"
            style={{ backgroundColor: '#0F172A' }}
          >
            Search
          </button>
        </div>
        {parseExplanation && (
          <div className="mt-3 text-sm text-[#84A98C] flex items-center gap-2 px-1 font-medium">
            <div className="w-1.5 h-1.5 rounded-full bg-[#84A98C]" />
            {parseExplanation}
          </div>
        )}
      </div>

      {/* Filters Row */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[300px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
          <input
            type="text"
            placeholder="Search matching keywords (e.g. 'Sales', 'Remote')..."
            value={textSearch}
            onChange={(e) => setTextSearch(e.target.value)}
            className="input-base !pl-12"
          />
        </div>

        <FilterSelect
          label="Seniority"
          value={seniority[0] || ''}
          options={FILTER_OPTIONS.seniority}
          onChange={(v) => setSeniority(v ? [v] : [])}
        />

        <FilterSelect
          label="Department"
          value={jobFunction[0] || ''}
          options={FILTER_OPTIONS.functions}
          onChange={(v) => setJobFunction(v ? [v] : [])}
        />

        <FilterSelect
          label="Work Type"
          value={remoteType[0] || ''}
          options={FILTER_OPTIONS.remote}
          onChange={(v) => setRemoteType(v ? [v] : [])}
        />
        <FilterSelect
          label="Location"
          value={location}
          options={locationOptions}
          onChange={(v) => setLocation(v)}
          align="right"
        />

        {(seniority.length > 0 || jobFunction.length > 0 || remoteType.length > 0 || location || naturalQuery) && (
          <button onClick={clearFilters} className="text-sm text-[#E07A5F] hover:text-[#D06A4F] flex items-center gap-1 px-2">
            <X size={14} /> Clear
          </button>
        )}
      </div>

      {/* Results */}
      {loading ? (
        <div className="py-20 text-center text-slate-500">Finding opportunities...</div>
      ) : (
        <div className="grid gap-4">
          {jobs.map((job) => (
            <Link href={`/jobs/${job.id}`} key={job.id}>
              <div className="bg-white hover:shadow-md group cursor-pointer border border-slate-200 rounded-xl p-5 transition-all duration-200 hover:border-[#E07A5F]/30">
                <div className="flex justify-between items-start">
                  <div className="flex gap-4">
                    <div className="w-12 h-12 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-400 group-hover:text-[#E07A5F] group-hover:bg-[#E07A5F]/5 transition-all">
                      <Building2 size={24} />
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-slate-900 group-hover:text-[#E07A5F] transition-colors">{job.role_title}</h3>
                      <p className="text-slate-500 font-medium">{job.company_name}</p>

                      <div className="flex flex-wrap gap-2 mt-3">
                        <Badge icon={Clock} text={formatSeniority(job.seniority_level)} color="sage" />
                        <Badge icon={MapPin} text={formatLocation(job)} color="slate" />
                        {job.salary_max_usd && (
                          <Badge icon={DollarSign} text={formatSalary(job.salary_min_usd, job.salary_max_usd)} color="terra" />
                        )}
                        {job.remote_type === 'remote' && <Badge icon={Zap} text="Remote" color="darkSage" />}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-slate-400">
                    Posted recently
                  </div>
                </div>
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
            const totalPages = Math.ceil(total / 20);
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
          disabled={page >= Math.ceil(total / 20)}
          onClick={() => setPage(p => p + 1)}
          className="p-2 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ArrowRight size={16} />
        </button>
      </div>
    </div>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-gray-500">Loading Explorer...</div>}>
      <JobsPageContent />
    </Suspense>
  );
}

// Helpers
function Badge({ icon: Icon, text, color }: any) {
  const colors: any = {
    sage: 'bg-[#84A98C]/10 text-[#84A98C] border-[#84A98C]/20',
    terra: 'bg-[#E07A5F]/10 text-[#E07A5F] border-[#E07A5F]/20',
    darkSage: 'bg-[#52796F]/10 text-[#52796F] border-[#52796F]/20',
    slate: 'bg-slate-100 text-slate-500 border-slate-200',
  };

  return (
    <span className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${colors[color] || colors.slate}`}>
      {Icon && <Icon size={12} />}
      {text}
    </span>
  );
}

function formatSeniority(s: string) {
  if (!s) return 'Unknown';
  return s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ');
}

function formatLocation(job: Job) {
  if (job.remote_type === 'remote') return 'Remote';
  const parts = [job.location_city, job.location_state].filter(Boolean);
  return parts.length ? parts.join(', ') : 'Location unspecified';
}

function formatSalary(min: number | null, max: number | null) {
  if (!min && !max) return '';
  const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
  if (min && max) return `${fmt(min)} - ${fmt(max)}`;
  return fmt(min || max || 0);
}
