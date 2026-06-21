'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Leaf, Mic, Paperclip, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  const MAX_CHARS = 2000;
  const isOverflowing = input.length > MAX_CHARS;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || disabled || isOverflowing) return;
    onSend(input.trim());
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Adjust height automatically as user types
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`;
  }, [input]);

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-3xl mx-auto px-4 md:px-6 pb-6 shrink-0 relative z-20">
      <div className="relative rounded-2xl border border-border bg-card shadow-md hover:shadow-lg focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10 transition-all duration-200">
        <textarea
          ref={textareaRef}
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask AgriGPT about crops, pests, soil or weather..."
          disabled={disabled}
          className="w-full resize-none bg-transparent py-4 pl-4 pr-32 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50 min-h-[56px] max-h-[180px] overflow-y-auto block leading-relaxed"
        />

        {/* Input Controls (Paperclip, Mic, Send) */}
        <div className="absolute right-3 bottom-2.5 flex items-center gap-1.5 select-none">
          <button
            type="button"
            className="p-2 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary"
            title="Attach images or soil reports (Placeholder)"
          >
            <Paperclip className="h-4 w-4" />
          </button>
          
          <button
            type="button"
            className="p-2 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary"
            title="Voice input (Placeholder)"
          >
            <Mic className="h-4 w-4" />
          </button>

          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || disabled || isOverflowing}
            className="h-8.5 w-8.5 rounded-lg bg-primary hover:bg-primary/95 text-white disabled:bg-secondary disabled:text-muted-foreground/30 transition-all shrink-0 cursor-pointer active:scale-90"
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Warning/Counter Bar */}
      <div className="mt-2.5 flex items-center justify-between px-1 text-[11px]">
        <div className="flex items-center gap-1.5 text-muted-foreground">
          <Leaf className="h-3 w-3 text-primary/70 shrink-0" />
          <span className="truncate pr-4">AgriGPT can formulate crop recommendations. Verify local regulations.</span>
        </div>
        
        {/* Character Count */}
        <div className="shrink-0 flex items-center gap-1">
          {isOverflowing ? (
            <span className="text-red-500 flex items-center gap-0.5 font-medium">
              <AlertCircle className="h-3 w-3" />
              {input.length}/{MAX_CHARS}
            </span>
          ) : (
            input.length > MAX_CHARS - 200 && (
              <span className="text-muted-foreground">
                {input.length}/{MAX_CHARS}
              </span>
            )
          )}
        </div>
      </div>
    </form>
  );
}
