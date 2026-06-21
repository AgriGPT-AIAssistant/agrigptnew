'use client';

import React, { useRef, useEffect } from 'react';
import { useChatStore } from '@/store/useChatStore';
import { ChatMessage } from './chat-message';
import { Sprout, ShieldCheck, Droplet, HelpCircle, ArrowRight } from 'lucide-react';

interface ChatWindowProps {
  onSend: (message: string) => void;
  statusText?: string;
  onRegenerate?: (messageId: string) => void;
}

export function ChatWindow({ onSend, statusText, onRegenerate }: ChatWindowProps) {
  const { activeSessionId, sessions, isLoading } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const messages = activeSession ? activeSession.messages : [];

  // Scroll to bottom on message update or loading trigger
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const suggestionChips = [
    { 
      label: "Crop Diagnosis", 
      text: "What organic remedies can treat late blight in tomato plants?", 
      icon: Sprout,
      color: "text-primary bg-primary/5 border-primary/10"
    },
    { 
      label: "Soil & Nutrients", 
      text: "How do I balance nitrogen levels in sandy loam soil before sowing corn?", 
      icon: HelpCircle,
      color: "text-muted-foreground bg-secondary/50 border-border"
    },
    { 
      label: "Water Scheduling", 
      text: "What is the optimal drip irrigation schedule for olive orchards in dry summers?", 
      icon: Droplet,
      color: "text-[#708D81] bg-[#708D81]/5 border-[#708D81]/10"
    },
    { 
      label: "Pest Management", 
      text: "Identify sustainable methods to control aphid infestations on wheat crops.", 
      icon: ShieldCheck,
      color: "text-[#40916C] bg-[#40916C]/5 border-[#40916C]/10"
    },
  ];

  if (!activeSessionId) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-background relative select-none">
        {/* Glow backing */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-72 h-72 rounded-full bg-primary/5 blur-[100px] pointer-events-none" />
        
        <div className="h-16 w-16 rounded-2xl bg-gradient-to-tr from-primary/10 to-primary/5 border border-primary/20 flex items-center justify-center text-primary mb-6 shadow-md relative animate-fade-in">
          <Sprout className="h-8 w-8" />
        </div>
        <h2 className="text-xl font-bold text-foreground animate-fade-in">Welcome to AgriGPT</h2>
        <p className="text-muted-foreground text-sm max-w-sm mt-2.5 leading-relaxed animate-fade-in">
          Your specialized agronomic assistant. Choose a conversation from history or start a new chat session to continue.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto flex flex-col bg-background scroll-smooth">
      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col justify-center items-center px-4 max-w-2xl mx-auto w-full py-12 relative select-none">
          {/* Decorative glowing gradient backing */}
          <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-64 h-64 rounded-full bg-primary/5 blur-[80px] pointer-events-none" />

          <div className="text-center mb-8 animate-fade-in relative z-10">
            <div className="inline-flex h-14 w-14 rounded-2xl bg-gradient-to-tr from-primary/10 to-primary/5 border border-primary/20 items-center justify-center text-primary mb-4 shadow-sm">
              <Sprout className="h-7 w-7" />
            </div>
            <h3 className="text-xl font-extrabold text-foreground">AgriGPT Farmer Support</h3>
            <p className="text-xs text-muted-foreground mt-2 max-w-md leading-relaxed">
              Ask about disease diagnostics, soil nutrients, weather impacts, or select a recommendation chip below.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 w-full relative z-10">
            {suggestionChips.map((chip, idx) => (
              <button
                key={idx}
                onClick={() => onSend(chip.text)}
                className="text-left p-4.5 rounded-xl border border-border bg-card hover:bg-secondary/40 hover:border-primary/25 hover:shadow-sm group transition-all duration-200 cursor-pointer active:scale-[0.98] select-none"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className={`flex items-center gap-2 px-2.5 py-1 rounded-lg border text-[10px] font-bold tracking-wider uppercase ${chip.color}`}>
                    <chip.icon className="h-3 w-3 shrink-0" />
                    <span>{chip.label}</span>
                  </div>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground/60 group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                </div>
                <p className="text-xs text-foreground/80 group-hover:text-foreground line-clamp-2 leading-relaxed">
                  {chip.text}
                </p>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex-1">
          {messages.map((msg) => (
            <ChatMessage 
              key={msg.id} 
              message={msg} 
              onRegenerate={onRegenerate ? () => onRegenerate(msg.id) : undefined}
            />
          ))}

          {/* Typing & Reasoning Activity Indicator */}
          {isLoading && statusText && (
            <div className="flex w-full items-start gap-4 py-6 px-4 md:px-6 bg-secondary/20 border-b border-border/50">
              <div className="flex max-w-3xl mx-auto gap-4 w-full items-start">
                <div className="h-8 w-8 shrink-0 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-sm">
                  <Sprout className="h-4.5 w-4.5" />
                </div>
                <div className="flex-1 space-y-1.5 overflow-hidden text-left">
                  <span className="text-[11px] font-bold tracking-wider text-muted-foreground uppercase select-none">
                    AgriGPT Assistant
                  </span>
                  <div>
                    <div className="inline-flex items-center gap-2.5 py-3 px-4.5 border border-border bg-card rounded-2xl shadow-sm relative min-w-[200px] text-foreground select-none">
                      <div className="h-3.5 w-3.5 rounded-full border-2 border-primary border-t-transparent animate-spin shrink-0" />
                      <span className="text-xs font-semibold tracking-wide">{statusText}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} className="h-10 shrink-0" />
        </div>
      )}
    </div>
  );
}
