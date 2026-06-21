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

        {/* Model dropdown */}
        <div className="relative">
          <button
            onClick={() => setModelDropdownOpen(!modelDropdownOpen)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-card hover:bg-secondary border border-border rounded-xl text-xs font-semibold text-foreground transition-colors select-none cursor-pointer shadow-sm"
          >
            <Cpu className="h-3.5 w-3.5 text-primary" />
            <span className="max-w-[120px] truncate">{currentModel}</span>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </button>

          {modelDropdownOpen && (
            <>
              {/* Overlay background to dismiss */}
              <div 
                className="fixed inset-0 z-40" 
                onClick={() => setModelDropdownOpen(false)}
              />
              <div className="absolute right-0 mt-2 w-64 bg-card border border-border rounded-2xl shadow-xl p-1.5 z-50 animate-fade-in">
                {modelsList.map((model) => (
                  <button
                    key={model.name}
                    onClick={() => {
                      setCurrentModel(model.name);
                      setModelDropdownOpen(false);
                    }}
                    className={cn(
                      "w-full flex flex-col items-start text-left px-3.5 py-2.5 rounded-xl cursor-pointer transition-colors select-none",
                      currentModel === model.name
                        ? "bg-primary/5 text-primary"
                        : "hover:bg-secondary text-slate-700 hover:text-foreground"
                    )}
                  >
                    <div className="flex items-center justify-between w-full font-bold text-xs">
                      <span>{model.name}</span>
                      {currentModel === model.name && <Check className="h-3.5 w-3.5 text-primary" />}
                    </div>
                    <span className={cn("text-[10px] mt-0.5 leading-normal", currentModel === model.name ? "text-primary/70" : "text-muted-foreground")}>{model.desc}</span>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {activeSessionId && (
          <Button
            variant="ghost"
            size="icon"
            onClick={handleReset}
            className="text-muted-foreground hover:text-foreground hover:bg-secondary/60 cursor-pointer"
            title="Reset Chat Messages"
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        )}

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
