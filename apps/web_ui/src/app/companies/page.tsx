'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Company {
  id: string;
  name: string;
  domain: string | null;
  job_count: number;
}

interface CompaniesResponse {
  companies: Company[];
  total: number;
  page: number;
  page_size: number;
}

export default function CompaniesPage(): React.ReactElement {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

  const pageSize = 24;

  useEffect(() => {
    fetchCompanies();
  }, [page]);

  const fetchCompanies = async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('page_size', String(pageSize));
    if (query) params.set('q', query);

    try {
      const res = await fetch(`${API_BASE}/companies?${params.toString()}`);
      const data: CompaniesResponse = await res.json();
      setCompanies(data.companies);
      setTotal(data.total);
    } catch (err) {
      console.error('Failed to fetch companies:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchCompanies();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <main className="companies-page">
      <style jsx>{`
        .companies-page {
          min-height: 100vh;
          background: var(--background);
        }
        .container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 2rem;
        }
        .header {
          margin-bottom: 2rem;
        }
        .back-link {
          color: var(--text-secondary);
          text-decoration: none;
          font-size: 0.875rem;
          margin-bottom: 0.5rem;
          display: inline-block;
        }
        .back-link:hover {
          color: var(--accent);
          text-decoration: none;
        }
        .header h1 {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 0.5rem;
        }
        .stats {
          color: var(--text-secondary);
          font-size: 0.875rem;
        }
        .search-form {
          display: flex;
          gap: 0.75rem;
          margin-bottom: 2rem;
          max-width: 500px;
        }
        .companies-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 1.5rem;
        }
        .company-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 1.5rem;
          text-decoration: none;
          color: inherit;
          transition: all 0.2s;
          display: block;
        }
        .company-card:hover {
          border-color: var(--accent);
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        .company-name {
          font-size: 1.125rem;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 0.5rem;
        }
        .job-count {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
          color: var(--accent);
          font-weight: 500;
        }
        .company-domain {
          font-size: 0.8rem;
          color: var(--text-tertiary);
          margin-top: 0.75rem;
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
      `}</style>

      <div className="container">
        <header className="header">
          <Link href="/" className="back-link">← Back to Home</Link>
          <h1>Companies</h1>
          <p className="stats">{total} companies hiring now</p>
        </header>

        <form className="search-form" onSubmit={handleSearch}>
          <input
            type="text"
            className="input-base"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search companies..."
          />
          <button type="submit" className="btn-primary">Search</button>
        </form>

        {loading ? (
          <div className="loading">Loading companies...</div>
        ) : companies.length === 0 ? (
          <div className="empty">No companies found.</div>
        ) : (
          <>
            <div className="companies-grid">
              {companies.map(company => (
                <Link
                  key={company.id}
                  href={`/companies/${company.id}`}
                  className="company-card"
                >
                  <div className="company-name">{company.name}</div>
                  <div className="job-count">
                    <span>{company.job_count} open jobs</span>
                  </div>
                  {company.domain && (
                    <div className="company-domain">{company.domain}</div>
                  )}
                </Link>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  className="btn-outline"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                >
                  ← Previous
                </button>
                <span className="page-info">Page {page} of {totalPages}</span>
                <button
                  className="btn-outline"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
