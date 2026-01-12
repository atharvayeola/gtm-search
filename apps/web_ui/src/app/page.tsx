'use client';

import React from 'react';
import Link from 'next/link';

export default function Home(): React.ReactElement {
  return (
    <main className="home-page">
      <style jsx>{`
        .home-page {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2rem;
        }
        .hero {
          text-align: center;
          max-width: 800px;
          margin-bottom: 4rem; /* Reduced from 5rem */
        }
        .section-label {
          color: var(--accent);
          font-size: 0.875rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          margin-bottom: 1rem;
          display: block;
        }
        .logo {
          font-size: 4.5rem; /* Slightly larger */
          font-weight: 800;
          letter-spacing: -0.02em;
          color: var(--text-primary);
          margin-bottom: 1.5rem;
          line-height: 1.1;
        }
        .logo span {
          color: var(--accent);
        }
        .tagline {
          font-size: 1.25rem;
          color: var(--text-secondary);
          margin-bottom: 2.5rem;
          font-weight: 400;
          max-width: 600px;
          margin-left: auto;
          margin-right: auto;
        }
        .cta-group {
          display: flex;
          gap: 1rem;
          justify-content: center;
          align-items: center;
        }
        .features-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 2rem;
          max-width: 1200px;
          width: 100%;
          margin-top: 2rem; /* Reduced margin */
        }
        .feature-item {
          text-align: center;
          padding: 2.5rem 2rem;
          background: var(--surface);
          border: 1px solid var(--border);
          border-radius: 16px;
          transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .feature-item:hover {
          transform: translateY(-4px);
          border-color: var(--accent); /* Highlight border on hover */
        }
        .feature-icon {
          font-size: 2.5rem; /* Larger icon */
          margin-bottom: 1.25rem;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          background: rgba(59, 130, 246, 0.1);
          width: 80px; /* Larger background */
          height: 80px;
          border-radius: 50%;
          color: var(--accent);
        }
        .feature-title {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 0.75rem;
          color: var(--text-primary);
        }
        .feature-desc {
          color: #cbd5e1; /* Lighter/brighter for better contrast */
          font-size: 1rem;
          line-height: 1.6;
        }
        .footer {
          margin-top: auto;
          padding-top: 4rem;
          color: var(--text-tertiary);
          font-size: 0.875rem;
        }
        @media (max-width: 768px) {
          .logo { font-size: 3rem; }
          .features-grid { grid-template-columns: 1fr; }
        }
      `}</style>

      <section className="hero">
        <span className="section-label">Job Intelligence Platform</span>
        <h1 className="logo">GTM <span>Engine</span></h1>
        <p className="tagline">
          The professional source for GTM talent intelligence. Search over 50,000 job postings with AI-powered insights.
        </p>

        <div className="cta-group">
          {/* Using global classes for buttons */}
          <Link href="/jobs" className="btn-primary" style={{ fontSize: '1.125rem', padding: '1rem 2.5rem' }}>
            Search Jobs
          </Link>
          <Link href="/companies" className="btn-outline" style={{ fontSize: '1.125rem', padding: '1rem 2.5rem' }}>
            Browse Companies
          </Link>
        </div>
      </section>

      <div className="features-grid">
        <div className="feature-item">
          <span className="feature-icon">🔍</span>
          <h3 className="feature-title">Natural Language Search</h3>
          <p className="feature-desc">
            Type exactly what you're looking for. "Staff Engineers in NYC paying over $200k" - our AI understands.
          </p>
        </div>
        <div className="feature-item">
          <span className="feature-icon">📊</span>
          <h3 className="feature-title">Data-Driven Insights</h3>
          <p className="feature-desc">
            Analyze market trends, salary ranges, and hiring patterns across thousands of companies.
          </p>
        </div>
        <div className="feature-item">
          <span className="feature-icon">⚡️</span>
          <h3 className="feature-title">Real-Time Extraction</h3>
          <p className="feature-desc">
            Direct integration with Greenhouse and Lever APIs ensures data is always fresh and accurate.
          </p>
        </div>
      </div>

      <footer className="footer">
        <p>Built for GTM Leaders • <a href="http://localhost:8000/docs">API Documentation</a></p>
      </footer>
    </main>
  );
}
