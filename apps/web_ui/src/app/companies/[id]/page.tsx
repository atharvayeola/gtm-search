'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface SkillRollup {
  skill_id: string;
  skill_name: string;
  job_count: number;
}

interface CompanyJob {
  id: string;
  role_title: string;
  seniority_level: string;
  job_function: string;
  location_city: string | null;
  remote_type: string;
}

interface CompanyDetail {
  id: string;
  name: string;
  domain: string | null;
  job_count: number;
  top_skills: SkillRollup[];
  recent_jobs: CompanyJob[];
}

export default function CompanyDetailPage(): React.ReactElement {
  const params = useParams();
  const companyId = params.id as string;

  const [company, setCompany] = useState<CompanyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (companyId) {
      fetchCompany();
    }
  }, [companyId]);

  const fetchCompany = async () => {
    try {
      const res = await fetch(`${API_BASE}/companies/${companyId}`);
      if (!res.ok) {
        throw new Error('Company not found');
      }
      const data: CompanyDetail = await res.json();
      setCompany(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load company');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <main className="company-page">
        <style jsx>{`
          .company-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); }
        `}</style>
        <div>Loading...</div>
      </main>
    );
  }

  if (error || !company) {
    return (
      <main className="company-page">
        <div className="container" style={{ padding: '4rem 1.5rem' }}>
          <Link href="/companies" className="back-link">← Back to Companies</Link>
          <h1 style={{ marginTop: '1rem', color: 'var(--text-primary)' }}>Company Not Found</h1>
          <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="company-detail-page">
      <style jsx>{`
        .company-detail-page {
          min-height: 100vh;
          background: var(--background);
          padding-bottom: 4rem;
        }
        .header-bg {
          background: var(--surface);
          border-bottom: 1px solid var(--border);
          padding: 3rem 0;
          text-align: center;
          margin-bottom: 2rem;
        }
        .container {
          max-width: 1100px;
          margin: 0 auto;
          padding: 0 1.5rem;
        }
        .back-link {
          color: var(--text-secondary);
          text-decoration: none;
          font-size: 0.875rem;
        }
        .back-link:hover {
          color: var(--accent);
          text-decoration: none;
        }
        
        .header h1 {
          font-size: 2.5rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 0.5rem;
          margin-top: 1rem;
        }
        .company-meta {
          color: var(--text-tertiary);
          font-size: 1rem;
          margin-bottom: 1.5rem;
        }
        .job-count-badge {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          background: rgba(59, 130, 246, 0.1);
          border: 1px solid rgba(59, 130, 246, 0.2);
          border-radius: 9999px;
          font-size: 1rem;
          color: var(--accent);
          font-weight: 500;
        }
        
        .content-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 2rem;
        }
        .panel {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 1.5rem;
          height: 100%;
        }
        .panel-title {
          font-size: 1.125rem;
          font-weight: 600;
          margin-bottom: 1.25rem;
          color: var(--text-primary);
          padding-bottom: 0.75rem;
          border-bottom: 1px solid var(--border);
        }
        
        /* Skill List */
        .skill-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }
        .skill-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.75rem 1rem;
          border-radius: var(--radius);
          border: 1px solid transparent;
          background: rgba(255, 255, 255, 0.02);
          transition: all 0.2s;
        }
        .skill-item:hover {
          background: rgba(255, 255, 255, 0.04);
          border-color: var(--border);
        }
        .skill-name {
          font-weight: 500;
          color: var(--text-primary);
        }
        .skill-count {
          font-size: 0.75rem;
          color: var(--text-secondary);
          background: rgba(255, 255, 255, 0.05);
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
        }
        
        /* Job List */
        .job-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }
        .job-item {
          display: block;
          padding: 1rem;
          background: rgba(255, 255, 255, 0.02);
          border: 1px solid transparent;
          border-radius: var(--radius);
          text-decoration: none;
          color: inherit;
          transition: all 0.2s;
        }
        .job-item:hover {
          background: rgba(255, 255, 255, 0.04);
          border-color: var(--border);
          transform: translateX(4px);
        }
        .job-title {
          font-weight: 500;
          color: var(--accent);
          margin-bottom: 0.25rem;
        }
        .job-meta {
          font-size: 0.8rem;
          color: var(--text-secondary);
        }
        
        .view-all-container {
             text-align: center;
             margin-top: 3rem;
        }
        .empty-message {
          color: var(--text-secondary);
          font-style: italic;
        }

        @media (max-width: 768px) {
          .content-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>

      <div className="header-bg">
        <div className="container">
          <Link href="/companies" className="back-link">← Back to Companies</Link>
          <h1>{company.name}</h1>
          {company.domain && <p className="company-meta">{company.domain}</p>}
          <div className="job-count-badge">
            {company.job_count} open positions
          </div>
        </div>
      </div>

      <div className="container">
        <div className="content-grid">
          {/* Top Skills Panel */}
          <div className="panel">
            <h2 className="panel-title">Top Skills Required</h2>
            {company.top_skills.length > 0 ? (
              <div className="skill-list">
                {company.top_skills.map(skill => (
                  <div key={skill.skill_id} className="skill-item">
                    <span className="skill-name">{skill.skill_name}</span>
                    <span className="skill-count">{skill.job_count} jobs</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="empty-message">No skill data available</p>
            )}
          </div>

          {/* Recent Jobs Panel */}
          <div className="panel">
            <h2 className="panel-title">Recent Jobs</h2>
            {company.recent_jobs.length > 0 ? (
              <div className="job-list">
                {company.recent_jobs.map(job => (
                  <Link
                    key={job.id}
                    href={`/jobs/${job.id}`}
                    className="job-item"
                  >
                    <div className="job-title">{job.role_title}</div>
                    <div className="job-meta">
                      {job.seniority_level} • {job.job_function.replace('_', ' ')} • {job.remote_type}
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <p className="empty-message">No jobs available</p>
            )}
          </div>
        </div>

        <div className="view-all-container">
          <Link href={`/jobs?company_id=${company.id}`} className="btn-primary" style={{ textDecoration: 'none' }}>
            View All {company.job_count} Jobs at {company.name} →
          </Link>
        </div>
      </div>
    </main>
  );
}
