'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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

interface JobsResponse {
  jobs: Job[];
  total: number;
  page: number;
  page_size: number;
}

interface ParsedFilters {
  q?: string;
  seniority?: string[];
  job_function?: string[];
  remote_type?: string[];
  city?: string;
  state?: string;
  country?: string;
  salary_min?: number;
  salary_max?: number;
  company?: string;
}

const SENIORITY_OPTIONS = ['intern', 'junior', 'mid', 'senior', 'staff', 'principal', 'manager', 'director', 'vp', 'cxo'];
const FUNCTION_OPTIONS = ['sales', 'marketing', 'engineering', 'data', 'product_marketing', 'customer_success', 'hr', 'finance', 'operations', 'other'];
const REMOTE_OPTIONS = ['remote', 'hybrid', 'onsite'];

export default function JobsPage(): React.ReactElement {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [parsing, setParsing] = useState(false);

  // Natural language search
  const [naturalQuery, setNaturalQuery] = useState('');
  const [parseExplanation, setParseExplanation] = useState('');

  // Filters
  const [textSearch, setTextSearch] = useState('');
  const [seniority, setSeniority] = useState<string[]>([]);
  const [jobFunction, setJobFunction] = useState<string[]>([]);
  const [remoteType, setRemoteType] = useState<string[]>([]);
  const [salaryMin, setSalaryMin] = useState<string>('');
  const [salaryMax, setSalaryMax] = useState<string>('');
  const [city, setCity] = useState('');
  const [country, setCountry] = useState('');

  const pageSize = 20;

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(pageSize));

    if (textSearch) params.set('q', textSearch);
    seniority.forEach(s => params.append('seniority', s));
    jobFunction.forEach(f => params.append('function', f));
    remoteType.forEach(r => params.append('remote_type', r));
    if (salaryMin) params.set('salary_min', salaryMin);
    if (salaryMax) params.set('salary_max', salaryMax);
    if (city) params.set('city', city);
    if (country) params.set('country', country);

    try {
      const res = await fetch(`${API_BASE}/jobs?${params.toString()}`);
      const data: JobsResponse = await res.json();
      setJobs(data.jobs);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to fetch jobs:', err);
    } finally {
      setLoading(false);
    }
  }, [page, textSearch, seniority, jobFunction, remoteType, salaryMin, salaryMax, city, country]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handleNaturalSearch = async () => {
    if (!naturalQuery.trim()) return;

    setParsing(true);
    setParseExplanation('');

    try {
      const res = await fetch(`${API_BASE}/search/parse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: naturalQuery }),
      });

      const data = await res.json();
      const filters: ParsedFilters = data.filters;

      // Clear all existing filters first
      setTextSearch('');
      setSeniority([]);
      setJobFunction([]);
      setRemoteType([]);
      setSalaryMin('');
      setSalaryMax('');
      setCity('');
      setCountry('');

      // Apply only the structured filters (not the raw query text)
      // Only use q for text search if no structured filters were extracted
      const hasStructuredFilters =
        (filters.seniority?.length ?? 0) > 0 ||
        (filters.job_function?.length ?? 0) > 0 ||
        (filters.remote_type?.length ?? 0) > 0 ||
        filters.salary_min ||
        filters.salary_max ||
        filters.city ||
        filters.country;

      if (!hasStructuredFilters && filters.q) {
        // No structured filters, use as text search
        setTextSearch(filters.q);
      }

      // Apply structured filters
      if (filters.seniority?.length) setSeniority(filters.seniority);
      if (filters.job_function?.length) setJobFunction(filters.job_function);
      if (filters.remote_type?.length) setRemoteType(filters.remote_type);
      if (filters.salary_min) setSalaryMin(String(filters.salary_min));
      if (filters.salary_max) setSalaryMax(String(filters.salary_max));
      if (filters.city) setCity(filters.city);
      if (filters.country) setCountry(filters.country);

      setParseExplanation(data.explanation || 'Query parsed successfully');
      setPage(1);
    } catch (err) {
      console.error('Failed to parse query:', err);
      setParseExplanation('Failed to parse query');
    } finally {
      setParsing(false);
    }
  };

  const clearAllFilters = () => {
    setTextSearch('');
    setSeniority([]);
    setJobFunction([]);
    setRemoteType([]);
    setSalaryMin('');
    setSalaryMax('');
    setCity('');
    setCountry('');
    setNaturalQuery('');
    setParseExplanation('');
    setPage(1);
  };

  const toggleFilter = (
    value: string,
    current: string[],
    setter: React.Dispatch<React.SetStateAction<string[]>>
  ) => {
    if (current.includes(value)) {
      setter(current.filter(v => v !== value));
    } else {
      setter([...current, value]);
    }
    setPage(1);
  };

  const formatSalary = (min: number | null, max: number | null) => {
    if (!min && !max) return '—';
    const fmt = (n: number) => `$${Math.round(n / 1000)}k`;
    if (min && max) return `${fmt(min)} - ${fmt(max)}`;
    if (min) return `${fmt(min)}+`;
    return `Up to ${fmt(max!)}`;
  };

  const formatLocation = (job: Job) => {
    const parts = [job.location_city, job.location_state, job.location_country].filter(Boolean);
    if (parts.length === 0) return job.remote_type === 'remote' ? 'Remote' : '—';
    return parts.slice(0, 2).join(', ');
  };

  const totalPages = Math.ceil(total / pageSize);
  const hasActiveFilters = seniority.length > 0 || jobFunction.length > 0 || remoteType.length > 0 ||
    salaryMin || salaryMax || city || country || textSearch;

  return (
    <main className="jobs-page">
      <style jsx>{`
        .jobs-page {
          min-height: 100vh;
          background: var(--background);
        }
        .container {
          max-width: 1400px;
          margin: 0 auto;
          padding: 2rem;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 2rem;
        }
        .header h1 {
          font-size: 1.5rem;
          font-weight: 600;
          color: var(--text-primary);
        }
        .back-link {
          color: var(--text-secondary);
          font-size: 0.875rem;
          margin-bottom: 0.5rem;
          display: inline-block;
        }
        .back-link:hover {
          color: var(--accent);
          text-decoration: none;
        }
        
        /* Natural Search */
        .natural-search {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 1.5rem;
          margin-bottom: 2rem;
        }
        .natural-search label {
          display: block;
          font-size: 0.875rem;
          color: var(--text-secondary);
          margin-bottom: 0.75rem;
          font-weight: 500;
        }
        .search-row {
          display: flex;
          gap: 0.75rem;
        }
        .nl-input {
          flex: 1;
          height: 48px;
        }
        .search-btn {
          height: 48px;
          padding: 0 2rem;
          font-size: 1rem;
        }
        .parse-explanation {
          margin-top: 1rem;
          padding: 0.75rem 1rem;
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.2);
          border-radius: var(--radius);
          font-size: 0.875rem;
          color: #93c5fd;
          display: flex;
          align-items: flex-start;
          gap: 0.5rem;
          word-wrap: break-word;
          white-space: normal;
          overflow-wrap: break-word;
        }
        .parse-explanation span:last-child {
          flex: 1;
        }
        
        /* Layout Grid */
        .content-grid {
          display: grid;
          grid-template-columns: 280px 1fr;
          gap: 2rem;
          align-items: start;
        }
        
        /* Filters */
        .filters-panel {
          position: sticky;
          top: 1rem;
        }
        .filter-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 1.5rem;
        }
        .filter-header h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary);
        }
        .clear-btn {
          font-size: 0.75rem;
          color: var(--accent);
          background: none;
          border: none;
          cursor: pointer;
          font-weight: 500;
        }
        .clear-btn:hover {
            text-decoration: underline;
        }
        .filter-section {
          margin-bottom: 2rem;
        }
        .filter-label {
          font-size: 0.75rem;
          font-weight: 600;
          color: var(--text-tertiary);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.75rem;
          display: block;
        }
        .filter-option {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          padding: 0.375rem 0;
          cursor: pointer;
          font-size: 0.875rem;
          color: var(--text-secondary);
          transition: color 0.2s;
        }
        .filter-option:hover {
          color: var(--text-primary);
        }
        .checkbox-custom {
          width: 16px;
          height: 16px;
          border: 1px solid var(--border);
          border-radius: 4px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: var(--surface);
          flex-shrink: 0;
        }
        input[type="checkbox"]:checked + .checkbox-custom {
          background: var(--accent);
          border-color: var(--accent);
        }
        .filter-input {
          width: 100%;
          margin-bottom: 0.5rem;
        }
        .salary-row {
          display: flex;
          gap: 0.5rem;
        }
        
        /* Results Table */
        .results-header {
            margin-bottom: 1rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .total-count {
            color: var(--text-secondary);
            font-size: 0.875rem;
        }
        .job-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            margin-bottom: 0.75rem;
            transition: all 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .job-card:hover {
            border-color: var(--accent);
            transform: translateX(4px);
        }
        .job-main {
            flex: 1;
        }
        .role-title {
            font-size: 1.125rem;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 0.25rem;
            display: block;
        }
        .company-name {
            color: var(--text-primary);
            font-weight: 500;
            font-size: 0.95rem;
        }
        .job-meta {
            margin-top: 0.5rem;
            display: flex;
            gap: 1rem;
            font-size: 0.875rem;
            color: var(--text-secondary);
        }
        .job-right {
            text-align: right;
            min-width: 150px;
        }
        .salary-tag {
            font-weight: 600;
            color: var(--success);
            font-size: 1rem;
            display: block;
            margin-bottom: 0.25rem;
        }
        .date-posted {
            font-size: 0.75rem;
            color: var(--text-tertiary);
        }
        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 1rem;
          margin-top: 2rem;
          color: var(--text-secondary);
          font-size: 0.875rem;
        }
        
        .loading, .empty {
          text-align: center;
          padding: 4rem;
          color: var(--text-secondary);
          background: var(--surface);
          border-radius: 12px;
          border: 1px dashed var(--border);
        }

        @media (max-width: 900px) {
          .content-grid {
            grid-template-columns: 1fr;
          }
          .filters-panel {
            position: static;
            margin-bottom: 2rem;
          }
          .job-card {
             flex-direction: column;
             align-items: flex-start;
          }
          .job-right {
             text-align: left;
             margin-top: 1rem;
          }
        }
      `}</style>

      <div className="container">
        <div>
          <Link href="/" className="back-link">← Back to Home</Link>
          <div className="header">
            <h1>Jobs Search</h1>
          </div>
        </div>

        {/* Natural Language Search */}
        <section className="natural-search">
          <label>Natural Language Search</label>
          <div className="search-row">
            <input
              type="text"
              className="input-base nl-input"
              value={naturalQuery}
              onChange={(e) => setNaturalQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleNaturalSearch()}
              placeholder='e.g., "Staff roles paying over $200k in NYC" or "Remote engineering at Stripe"'
            />
            <button
              className="btn-primary search-btn"
              onClick={handleNaturalSearch}
              disabled={parsing || !naturalQuery.trim()}
            >
              {parsing ? 'Parsing...' : 'Search'}
            </button>
          </div>
          {parseExplanation && (
            <div className="parse-explanation">
              <span>✨</span>
              <span>Explanation: {parseExplanation}</span>
            </div>
          )}
        </section>

        <div className="content-grid">
          {/* Filters Panel */}
          <aside className="filters-panel">
            <div className="filter-header">
              <h3>Filters</h3>
              {hasActiveFilters && (
                <button className="clear-btn" onClick={clearAllFilters}>Clear all</button>
              )}
            </div>

            {/* Text Search */}
            <div className="filter-section">
              <span className="filter-label">Keywords</span>
              <input
                type="text"
                className="input-base filter-input"
                value={textSearch}
                onChange={(e) => { setTextSearch(e.target.value); setPage(1); }}
                placeholder="Search titles..."
              />
            </div>

            {/* Salary Range */}
            <div className="filter-section">
              <span className="filter-label">Salary (USD)</span>
              <div className="salary-row">
                <input
                  type="number"
                  className="input-base"
                  value={salaryMin}
                  onChange={(e) => { setSalaryMin(e.target.value); setPage(1); }}
                  placeholder="Min"
                />
                <input
                  type="number"
                  className="input-base"
                  value={salaryMax}
                  onChange={(e) => { setSalaryMax(e.target.value); setPage(1); }}
                  placeholder="Max"
                />
              </div>
            </div>

            {/* Location */}
            <div className="filter-section">
              <span className="filter-label">Location</span>
              <input
                type="text"
                className="input-base filter-input"
                value={city}
                onChange={(e) => { setCity(e.target.value); setPage(1); }}
                placeholder="City"
              />
              <input
                type="text"
                className="input-base filter-input"
                value={country}
                onChange={(e) => { setCountry(e.target.value); setPage(1); }}
                placeholder="Country"
              />
            </div>

            {/* Seniority */}
            <div className="filter-section">
              <span className="filter-label">Seniority</span>
              {SENIORITY_OPTIONS.map(opt => (
                <label key={opt} className="filter-option">
                  <input
                    type="checkbox"
                    checked={seniority.includes(opt)}
                    onChange={() => toggleFilter(opt, seniority, setSeniority)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </label>
              ))}
            </div>

            {/* Function */}
            <div className="filter-section">
              <span className="filter-label">Function</span>
              {FUNCTION_OPTIONS.map(opt => (
                <label key={opt} className="filter-option">
                  <input
                    type="checkbox"
                    checked={jobFunction.includes(opt)}
                    onChange={() => toggleFilter(opt, jobFunction, setJobFunction)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                  {opt.replace('_', ' ').charAt(0).toUpperCase() + opt.replace('_', ' ').slice(1)}
                </label>
              ))}
            </div>

            {/* Remote */}
            <div className="filter-section">
              <span className="filter-label">Work Type</span>
              {REMOTE_OPTIONS.map(opt => (
                <label key={opt} className="filter-option">
                  <input
                    type="checkbox"
                    checked={remoteType.includes(opt)}
                    onChange={() => toggleFilter(opt, remoteType, setRemoteType)}
                    style={{ accentColor: 'var(--accent)' }}
                  />
                  {opt.charAt(0).toUpperCase() + opt.slice(1)}
                </label>
              ))}
            </div>
          </aside>

          {/* Results */}
          <section>
            <div className="results-header">
              <span className="total-count">{total.toLocaleString()} jobs found</span>
            </div>

            {loading ? (
              <div className="loading">Loading jobs...</div>
            ) : jobs.length === 0 ? (
              <div className="empty">No jobs found matching your criteria.</div>
            ) : (
              <>
                {jobs.map(job => (
                  <Link href={`/jobs/${job.id}`} key={job.id} style={{ textDecoration: 'none' }}>
                    <div className="job-card">
                      <div className="job-main">
                        <span className="role-title">
                          {job.role_title}
                        </span>
                        <div className="company-name">{job.company_name}</div>
                        <div className="job-meta">
                          <span>{formatLocation(job)}</span>
                          <span>•</span>
                          <span>{job.seniority_level}</span>
                          <span>•</span>
                          <span>{job.job_function.replace('_', ' ')}</span>
                        </div>
                      </div>
                      <div className="job-right">
                        <span className="salary-tag">{formatSalary(job.salary_min_usd, job.salary_max_usd)}</span>
                        <div className="badge">{job.remote_type}</div>
                      </div>
                    </div>
                  </Link>
                ))}

                {totalPages > 1 && (
                  <div className="pagination">
                    <button
                      className="btn-primary"
                      style={{ padding: '0.5rem 1rem', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page <= 1}
                    >
                      Previous
                    </button>
                    <span>Page {page} of {totalPages}</span>
                    <button
                      className="btn-primary"
                      style={{ padding: '0.5rem 1rem', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
