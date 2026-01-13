"use client";

import { Bookmark } from 'lucide-react';
import Link from 'next/link';

export default function SavedSearchesPage() {
    return (
        <div className="p-8 h-[calc(100vh-64px)] flex flex-col">
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-white mb-2">Saved Searches</h1>
                <p className="text-[var(--text-secondary)]">0 saved searches</p>
            </div>

            <div className="flex-1 card flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-2xl bg-[var(--bg-app)] border border-[var(--border)] flex items-center justify-center text-[var(--text-tertiary)] mb-6">
                    <Bookmark size={32} />
                </div>
                <h2 className="text-xl font-semibold text-white mb-2">No saved searches yet</h2>
                <p className="text-[var(--text-secondary)] max-w-sm mb-8">
                    Save your frequently used search filters to quickly access them later.
                </p>
                <Link href="/jobs" className="btn-primary">
                    Start Searching
                </Link>
            </div>
        </div>
    );
}
