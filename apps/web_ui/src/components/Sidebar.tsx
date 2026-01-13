"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
    BarChart2,
    Briefcase,
    Building2,
    LayoutDashboard,
    Settings,
    LogOut,
    Bookmark
} from 'lucide-react';

const MENU_ITEMS = [
    { name: 'Dashboard', icon: LayoutDashboard, path: '/' },
    { name: 'Job Explorer', icon: Briefcase, path: '/jobs' },
    { name: 'Companies', icon: Building2, path: '/companies' },
    { name: 'Analytics', icon: BarChart2, path: '/analytics' },
    { name: 'Saved', icon: Bookmark, path: '/saved-searches' },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <aside className="w-64 fixed h-screen top-0 left-0 border-r border-slate-200 bg-white flex flex-col z-50">

            {/* Brand */}
            <div className="p-6 border-b border-slate-100 mb-2">
                <h1 className="text-2xl font-bold brand-font text-slate-900">
                    GTM Signal
                </h1>
                <p className="text-xs text-slate-500 mt-1 font-medium tracking-wide">INTELLIGENCE PLATFORM</p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 space-y-1">
                {MENU_ITEMS.map((item) => {
                    const isActive = pathname === item.path || (item.path !== '/' && pathname.startsWith(item.path));

                    return (
                        <Link
                            key={item.path}
                            href={item.path}
                            className={`
                flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-200 group
                ${isActive
                                    ? 'bg-[#E07A5F]/10 text-[#E07A5F] border border-[#E07A5F]/20'
                                    : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900 border border-transparent'
                                }
              `}
                        >
                            <item.icon
                                size={18}
                                className={`transition-colors duration-200 ${isActive ? 'text-[#E07A5F]' : 'text-slate-400 group-hover:text-slate-900'}`}
                            />
                            {item.name}
                        </Link>
                    );
                })}
            </nav>
        </aside>
    );
}
