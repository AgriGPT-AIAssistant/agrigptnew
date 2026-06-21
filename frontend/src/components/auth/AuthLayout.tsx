'use client';

import React from 'react';
import { AnimatedBackground } from './AnimatedBackground';
import { AuthHero } from './AuthHero';

interface AuthLayoutProps {
  children: React.ReactNode;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({ children }) => {
  return (
    <div className="relative w-screen h-screen min-h-[600px] flex flex-col lg:flex-row bg-bg-luxury overflow-hidden">
      {/* Background Layer */}
      <AnimatedBackground />

      {/* Left Column: Branding Experience (Visible on Large/Desktop Screens) */}
      <div className="hidden lg:flex lg:w-[50%] xl:w-[55%] h-full border-r border-border bg-card/5 backdrop-blur-[2px] relative items-center justify-center">
        <AuthHero />
      </div>

      {/* Tablet Header (Visible on Medium/Tablet stacked screens, Hidden on Mobile/Desktop) */}
      <div className="hidden md:flex lg:hidden w-full py-10 px-8 items-center justify-between border-b border-border bg-card/5">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-primary/10 border border-primary/20 text-primary">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className="text-lg font-bold tracking-tight text-foreground font-mono">
            Agri<span className="text-primary">GPT</span>
          </span>
        </div>
        <p className="text-xs text-muted-foreground font-medium">AI-Powered Agricultural Intelligence</p>
      </div>

      {/* Right Column: Authentication Panel (All screen resolutions) */}
      <div className="flex-1 h-full flex items-center justify-center p-6 sm:p-12 z-10 relative overflow-y-auto">
        {/* Mobile Header (Hidden on Tablet/Desktop, Centered on top of Mobile viewport) */}
        <div className="absolute top-8 left-0 right-0 flex flex-col items-center justify-center gap-2 md:hidden">
          <div className="flex items-center gap-2.5">
            <div className="flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10 border border-primary/20 text-primary">
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className="text-base font-bold tracking-tight text-foreground font-mono">
              Agri<span className="text-primary">GPT</span>
            </span>
          </div>
        </div>

        {/* The Auth Card Component */}
        <div className="w-full flex justify-center py-12 md:py-0">
          {children}
        </div>
      </div>
    </div>
  );
};
