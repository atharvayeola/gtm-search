import React from 'react';
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
    title: 'GTM Engine - Job Intelligence Platform',
    description: 'Search and analyze 50,000+ job postings with AI-powered extraction',
};

export default function RootLayout({
    children,
}: {
    children: React.ReactNode;
}): React.ReactElement {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    );
}
