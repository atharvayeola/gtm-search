'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Skill {
  id: string;
  name: string;
  type: string | null;
}

interface JobDetail {
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
  department: string | null;
  employment_type: string;
  salary_min_usd: number | null;
  salary_max_usd: number | null;
  job_summary: string | null;
  clean_text: string | null;
  skills: Skill[];
  confidence: number;
}

export default function JobDetailPage(): React.ReactElement {
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (jobId) {
      fetchJob();
    }
  }, [jobId]);

  const fetchJob = async () => {
    try {
      const res = await fetch(`${API_BASE}/jobs/${jobId}`);
      if (!res.ok) {
        throw new Error('Job not found');
      }
      const data: JobDetail = await res.json();
      setJob(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load job');
    } finally {
      setLoading(false);
    }
  };

  const formatSalary = (min: number | null, max: number | null) => {
    if (!min && !max) return 'Not disclosed';
    const fmt = (n: number) => `$${n.toLocaleString()}`;
    if (min && max) return `${fmt(min)} - ${fmt(max)}`;
    if (min) return `${fmt(min)}+`;
    return `Up to ${fmt(max!)}`;
  };

  const formatLocation = () => {
    if (!job) return '';
    const parts = [job.location_city, job.location_state, job.location_country].filter(Boolean);
    return parts.length > 0 ? parts.join(', ') : 'Location not specified';
  };

  // Highlight key terms in the job description using new design colors
  const highlightKeyTerms = (text: string): string => {
    const keyTerms = [
      'required', 'requirements', 'qualifications', 'responsibilities',
      'experience', 'skills', 'you will', 'what you', 'benefits',
      'salary', 'compensation', 'bonus', 'equity', 'remote',
    ];

    let highlighted = text;
    keyTerms.forEach(term => {
      const regex = new RegExp(`\\b(${term})\\b`, 'gi');
      highlighted = highlighted.replace(regex, '<mark>$1</mark>');
    });

    return highlighted;
  };

  if (loading) {
    return (
      <main className="job-detail-page">
        <style jsx>{`
          .job-detail-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; color: var(--text-secondary); }
        `}</style>
        <div>Loading...</div>
      </main>
    );
  }

  if (error || !job) {
    return (
      <main className="job-detail-page">
        <div className="container" style={{ padding: '4rem 1.5rem' }}>
          <Link href="/jobs" className="btn-primary" style={{ display: 'inline-block', marginBottom: '1rem' }}>← Back to Jobs</Link>
          <h1>Job Not Found</h1>
          <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="job-detail-page">
      <style jsx>{`
        .job-detail-page {
          min-height: 100vh;
          background: var(--background);
          padding-bottom: 4rem;
        }
        .header-bg {
          background: var(--surface);
          border-bottom: 1px solid var(--border);
          padding: 2rem 0;
        }
        .top-nav {
          margin-bottom: 1.5rem;
        }
        .back-link {
          color: var(--text-secondary);
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
        }
        .back-link:hover {
          color: var(--text-primary);
        }
        .title-section h1 {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 0.5rem;
        }
        .company-link {
          color: var(--accent);
          font-size: 1.125rem;
          font-weight: 500;
        }
        .company-link:hover {
          text-decoration: underline;
        }

        .meta-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 1rem;
          margin-top: 2rem;
          margin-bottom: 3rem;
        }
        .meta-card {
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: var(--radius);
          padding: 1.25rem;
        }
        .meta-label {
          font-size: 0.75rem;
          color: var(--text-tertiary);
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 0.5rem;
          font-weight: 600;
        }
        .meta-value {
          font-size: 1rem;
          font-weight: 500;
          color: var(--text-primary);
        }
        .salary-value {
          color: var(--success);
          font-weight: 600;
        }
        
        .main-grid {
          display: grid;
          grid-template-columns: 2fr 1fr;
          gap: 3rem;
        }
        
        .section-title {
          font-size: 1.5rem; /* Larger */
          font-weight: 800; /* Bolder */
          color: var(--text-primary);
          margin-bottom: 1.25rem;
          padding-bottom: 0.75rem;
          border-bottom: 1px solid var(--border);
          letter-spacing: -0.02em;
        }
        
        .skills-container {
          display: flex;
          flex-wrap: wrap;
          gap: 0.75rem;
          margin-bottom: 2rem;
        }
        .skill-tag {
          padding: 0.5rem 1rem;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 9999px;
          color: var(--text-primary);
          font-size: 0.875rem;
          transition: all 0.2s;
        }
        .skill-tag:hover {
          border-color: var(--accent);
          color: var(--accent);
        }
        
        .summary-box {
          background: rgba(224, 122, 95, 0.05); /* Terra Cotta tint */
          border: 1px solid rgba(224, 122, 95, 0.2);
          border-radius: var(--radius);
          padding: 1.5rem;
          margin-bottom: 2rem;
        }
        .summary-text {
          font-size: 1.05rem;
          line-height: 1.7;
          color: var(--text-primary);
        }
        
        .description-content {
          font-size: 1rem;
          line-height: 1.8;
          color: var(--text-secondary);
        }
        .description-content :global(mark) {
          background: rgba(224, 122, 95, 0.2); /* Terra Cotta highlight */
          color: #0F172A; /* Slate 900 - High Contrast */
          font-weight: 600;
          padding: 0 0.25rem;
          border-radius: 4px;
        }
        
        .sidebar-card {
           background: var(--surface);
           border: 1px solid var(--border);
           border-radius: var(--radius);
           padding: 1.5rem;
           margin-bottom: 1.5rem;
        }
        
        .confidence-bar {
          margin-top: 1rem;
          height: 6px;
          background: var(--border);
          border-radius: 3px;
          overflow: hidden;
        }
        .confidence-fill {
          height: 100%;
          background: var(--accent);
          border-radius: 3px;
        }
        .confidence-label {
          display: flex;
          justify-content: space-between;
          font-size: 0.875rem;
          color: var(--text-secondary);
          margin-bottom: 0.5rem;
        }

        @media (max-width: 900px) {
          .main-grid { grid-template-columns: 1fr; }
        }
      `}</style>

      <header className="header-bg">
        <div className="container">
          <div className="top-nav">
            <Link href="/jobs" className="back-link">← Back to Jobs</Link>
          </div>
          <div className="title-section">
            <h1>{job.role_title}</h1>
            <Link href={`/companies/${job.company_id}`} className="company-link">
              {job.company_name}
            </Link>
          </div>
        </div>
      </header>

      <div className="container">
        {/* Meta Cards */}
        <div className="meta-grid">
          <div className="meta-card">
            <div className="meta-label">Salary</div>
            <div className="meta-value salary-value">{formatSalary(job.salary_min_usd, job.salary_max_usd)}</div>
          </div>
          <div className="meta-card">
            <div className="meta-label">Location</div>
            <div className="meta-value">{formatLocation()}</div>
          </div>
          <div className="meta-card">
            <div className="meta-label">Work Type</div>
            <div className="meta-value">{job.remote_type}</div>
          </div>
          <div className="meta-card">
            <div className="meta-label">Seniority</div>
            <div className="meta-value">{job.seniority_level}</div>
          </div>
        </div>

        <div className="main-grid">
          <div className="left-col">
            {/* Summary */}
            {job.job_summary && (
              <section>
                <h2 className="section-title">AI Summary</h2>
                <div className="summary-box">
                  <p className="summary-text">{job.job_summary}</p>
                </div>
              </section>
            )}

            {/* Skills */}
            {job.skills.length > 0 && (
              <section>
                <h2 className="section-title">Skills & Tech Stack</h2>
                <div className="skills-container">
                  {job.skills.map(skill => (
                    <span key={skill.id} className="skill-tag">
                      {skill.name}
                    </span>
                  ))}
                </div>
              </section>
            )}

            {/* Full Description */}
            {job.clean_text && (
              <section>
                <h2 className="section-title">Full Description</h2>
                <div className="description-content" dangerouslySetInnerHTML={{ __html: highlightKeyTerms(job.clean_text) }} />
              </section>
            )}
          </div>

          <aside className="right-col">
            <div className="sidebar-card">
              <h3 style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '1rem' }}>
                Job Details
              </h3>
              <div style={{ marginBottom: '1rem' }}>
                <div className="meta-label">Function</div>
                <div className="meta-value" style={{ fontSize: '0.95rem' }}>{job.job_function.replace('_', ' ')}</div>
              </div>
              <div style={{ marginBottom: '1rem' }}>
                <div className="meta-label">Department</div>
                <div className="meta-value" style={{ fontSize: '0.95rem' }}>{job.department || 'Not specified'}</div>
              </div>
              <div>
                <div className="meta-label">Employment</div>
                <div className="meta-value" style={{ fontSize: '0.95rem' }}>{job.employment_type.replace('_', ' ')}</div>
              </div>
            </div>

            <div className="sidebar-card">
              <div className="confidence-label">
                <span>AI Confidence Score</span>
                <span>{Math.round(job.confidence * 100)}%</span>
              </div>
              <div className="confidence-bar">
                <div className="confidence-fill" style={{ width: `${job.confidence * 100}%` }}></div>
              </div>
              <p style={{ marginTop: '0.75rem', fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>
                Based on data extraction quality and completeness.
              </p>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
