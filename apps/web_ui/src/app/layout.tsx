import React from 'react';
import type { Metadata } from 'next';
import './globals.css';

import { Sidebar } from '@/components/Sidebar';

export const metadata: Metadata = {
    title: 'GTM Signal',
    description: 'AI-powered job market intelligence platform',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}): React.ReactElement {
    return (
        <html lang="en">
            <body className="flex min-h-screen bg-[var(--bg-app)]">
                <Sidebar />
                <main className="flex-1 ml-64 min-h-screen pl-10">
                    {children}
                </main>
            </body>
        </html>
    );
}
