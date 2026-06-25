'use client';

import React, { useState } from 'react';
import { useChatStore } from '@/store/useChatStore';
import { Button } from '@/components/ui/button';
import { Menu, RefreshCw, Cpu, ChevronDown, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useSession } from 'next-auth/react';
import { Avatar } from '@/components/ui/avatar';

export function TopNavbar() {
  const { data: session } = useSession();
  const user = session?.user;
  
  const { isSidebarOpen, toggleSidebar, activeSessionId, sessions, clearSessionMessages } = useChatStore();
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [currentModel, setCurrentModel] = useState('AgriGPT 3.5 (Core)');

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const title = activeSession ? activeSession.title : 'AgriGPT Assistant';

  const handleReset = () => {
    if (activeSessionId) {
      clearSessionMessages(activeSessionId);
    }
  };

  const userDisplayName = user?.name || 'Aakash Lagisetti';
  const userInitials = userDisplayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();

  const modelsList = [
    { name: 'AgriGPT 3.5 (Core)', desc: 'Fast, optimized for general farming advice' },
    { name: 'AgriGPT 4.0 (Pro)', desc: 'Advanced diagnostics & crop analysis' },
    { name: 'AgriGPT SoilVision', desc: 'Optimized for leaf disease & soil reports' }
  ];

  return (
    <header className="h-16 border-b border-border flex items-center justify-between px-4 bg-background/80 backdrop-blur-md shrink-0 relative z-30 select-none">
      <div className="flex items-center gap-2 min-w-0">
        {!isSidebarOpen && (
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleSidebar}
            className="text-muted-foreground hover:text-foreground hover:bg-secondary/60 cursor-pointer"
          >
            <Menu className="h-5 w-5" />
          </Button>
        )}
        <span className="text-xs sm:text-sm font-semibold text-foreground truncate pr-2">
          {title}
        </span>
      </div>

      <div className="flex items-center gap-3">
        {/* Connection status light */}
        <div className="flex items-center gap-1.5 px-2.5 py-1.5 bg-[#40916C]/10 border border-[#40916C]/20 rounded-full text-[10px] text-[#1B4332] font-semibold select-none">
          <span className="relative flex h-1.5 w-1.5 shrink-0">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#40916C] opacity-75"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-[#1B4332]"></span>
          </span>
          <span className="hidden sm:inline">API Connected</span>
        </div>



        {user && (
          <Avatar
            src={user.image || undefined}
            fallback={userInitials}
            className="h-8 w-8 rounded-xl border border-border shadow-sm shrink-0 bg-primary/10 text-primary ml-1"
          />
        )}
      </div>
    </header>
  );
}
