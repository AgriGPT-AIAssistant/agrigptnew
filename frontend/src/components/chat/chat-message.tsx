'use client';

import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useSession } from 'next-auth/react';
import remarkGfm from 'remark-gfm';
import { Message } from '@/types/chat';
import { Avatar } from '@/components/ui/avatar';
import { useChatStore } from '@/store/useChatStore';
import { 
  Sprout, Copy, Check, ThumbsUp, ThumbsDown, RotateCcw, 
  ChevronDown, ChevronUp, FileText, ExternalLink, Globe, 
  CloudSun, Cpu, Share2 
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ChatMessageProps {
  message: Message;
  onRegenerate?: () => void;
}

export function ChatMessage({ message, onRegenerate }: ChatMessageProps) {
  const { data: session } = useSession();
  const user = session?.user;

  const isUser = message.role === 'user';
  const [copiedMessage, setCopiedMessage] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);
  const [isSourcesOpen, setIsSourcesOpen] = useState(false);
  const [isThinkingExpanded, setIsThinkingExpanded] = useState(true);

  const { activeSessionId, updateMessageFeedback } = useChatStore();

  const userDisplayName = user?.name || 'Aakash Lagisetti';
  const userInitials = userDisplayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();

  const handleCopyMessage = () => {
    if (!message.content) return;
    navigator.clipboard.writeText(message.content);
    setCopiedMessage(true);
    setTimeout(() => setCopiedMessage(false), 2000);
  };

  const handleShare = () => {
    if (!message.content) return;
    const shareText = `🌾 AgriGPT Agricultural Advice:\n\n${message.content}\n\nTools used: ${message.toolsUsed?.join(', ') || 'Generative Model'}\nTime taken: ${message.thoughtDuration}s`;
    navigator.clipboard.writeText(shareText);
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 2000);
  };

  const handleFeedback = (type: 'up' | 'down') => {
    if (!activeSessionId) return;
    const current = message.feedback === type ? null : type;
    updateMessageFeedback(activeSessionId, message.id, current);
  };

  // Custom components to override default Markdown element rendering
  const MarkdownComponents = {
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      const [copiedCode, setCopiedCode] = useState(false);
      const codeString = String(children).replace(/\n$/, '');

      const handleCopyCode = () => {
        navigator.clipboard.writeText(codeString);
        setCopiedCode(true);
        setTimeout(() => setCopiedCode(false), 1500);
      };

      if (!inline && match) {
        return (
          <div className="relative border border-border rounded-xl overflow-hidden my-3 w-full bg-[#FAF9F6] shadow-sm">
            <div className="flex items-center justify-between px-4 py-2 bg-[#F2EFE9] border-b border-border text-[10px] text-muted-foreground font-mono select-none">
              <span>{match[1]}</span>
              <button
                onClick={handleCopyCode}
                className="hover:text-primary flex items-center gap-1 transition-colors font-semibold cursor-pointer"
              >
                {copiedCode ? (
                  <>
                    <Check className="h-3 w-3 text-primary" /> Copied!
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" /> Copy code
                  </>
                )}
              </button>
            </div>
            <pre className="p-4 overflow-x-auto font-mono text-xs leading-relaxed text-foreground">
              <code>{children}</code>
            </pre>
          </div>
        );
      }

      return (
        <code className={cn("bg-[#F2EFE9] text-primary px-1.5 py-0.5 rounded text-xs font-mono font-semibold border border-border/40", className)} {...props}>
          {children}
        </code>
      );
    },
    
    a({ href, children }: any) {
      return (
        <a 
          href={href} 
          target="_blank" 
          rel="noopener noreferrer" 
          className="text-primary hover:underline font-semibold transition-colors"
        >
          {children}
        </a>
      );
    },

    blockquote({ node, children }: any) {
      const text = React.Children.toArray(children)
        .map((child: any) => {
          if (typeof child === 'string') return child;
          if (child.props && child.props.children) {
            return React.Children.toArray(child.props.children).join('');
          }
          return '';
        })
        .join('');
      
      const match = text.match(/^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]/i);
      
      if (match) {
        const type = match[1].toUpperCase();
        const cleanChildren = React.Children.map(children, (child: any) => {
          if (child.props && child.props.children) {
            const innerChildren = React.Children.toArray(child.props.children);
            const firstInner = innerChildren[0];
            if (typeof firstInner === 'string') {
              const cleaned = firstInner.replace(/^\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]\s*/i, '');
              if (cleaned === '') {
                return innerChildren.slice(1);
              }
              return [cleaned, ...innerChildren.slice(1)];
            }
          }
          return child;
        });

        let borderClass = 'border-l-4 border-primary';
        let bgClass = 'bg-[#FAF9F6]';
        let titleColor = 'text-primary';
        let icon = '💡';
        let titleLabel = 'TIP';

        if (type === 'WARNING' || type === 'CAUTION') {
          borderClass = 'border-l-4 border-amber-600';
          bgClass = 'bg-amber-50/70';
          titleColor = 'text-amber-800';
          icon = '⚠️';
          titleLabel = type;
        } else if (type === 'IMPORTANT') {
          borderClass = 'border-l-4 border-blue-600';
          bgClass = 'bg-blue-50/70';
          titleColor = 'text-blue-800';
          icon = '📌';
          titleLabel = 'IMPORTANT';
        } else if (type === 'NOTE') {
          borderClass = 'border-l-4 border-slate-400';
          bgClass = 'bg-slate-50';
          titleColor = 'text-slate-700';
          icon = 'ℹ️';
          titleLabel = 'NOTE';
        }

        return (
          <div className={cn("my-4.5 p-4.5 rounded-r-xl border border-border", borderClass, bgClass)}>
            <div className="flex items-center gap-2 mb-2 select-none">
              <span className="text-sm">{icon}</span>
              <span className={cn("text-[10px] font-extrabold tracking-wider uppercase", titleColor)}>{titleLabel}</span>
            </div>
            <div className="text-xs leading-relaxed text-foreground/80">
              {cleanChildren}
            </div>
          </div>
        );
      }
      
      return (
        <blockquote className="border-l-4 border-slate-300 pl-4 py-1.5 my-4.5 text-muted-foreground italic bg-secondary/30 rounded-r-lg pr-4">
          {children}
        </blockquote>
      );
    },

    table({ children }: any) {
      return (
        <div className="overflow-x-auto my-4.5 border border-border rounded-xl shadow-sm">
          <table className="min-w-full divide-y divide-border text-xs leading-normal">
            {children}
          </table>
        </div>
      );
    },

    thead({ children }: any) {
      return <thead className="bg-[#F2EFE9] text-primary">{children}</thead>;
    },

    tbody({ children }: any) {
      return <tbody className="divide-y divide-border/60 bg-white">{children}</tbody>;
    },

    tr({ children, ...props }: any) {
      return <tr className="hover:bg-secondary/20 transition-colors odd:bg-white even:bg-secondary/15" {...props}>{children}</tr>;
    },

    th({ children }: any) {
      return <th className="px-4 py-3 text-left font-bold tracking-wider text-[10px] uppercase">{children}</th>;
    },

    td({ children }: any) {
      return <td className="px-4 py-2.5 text-foreground leading-normal">{children}</td>;
    }
  };

  return (
    <div
      className={cn(
        "flex w-full items-start gap-4 py-6 px-4 md:px-6 transition-colors duration-200 border-b border-border/50 group",
        isUser ? "bg-[#FAF9F6]/20" : "bg-background"
      )}
    >
      <div className={cn("flex max-w-[800px] mx-auto gap-4 w-full items-start", isUser ? "flex-row-reverse" : "")}>
        {isUser ? (
          <Avatar
            src={user?.image || undefined}
            fallback={userInitials}
            className="h-8.5 w-8.5 rounded-xl border border-border shrink-0 bg-primary/10 text-primary"
          />
        ) : (
          <div className="h-8 w-8 shrink-0 rounded-lg bg-primary/10 border border-primary/20 flex items-center justify-center text-primary shadow-sm">
            <Sprout className="h-4.5 w-4.5" />
          </div>
        )}

        <div className="flex-1 space-y-1.5 overflow-hidden">
          {/* Header Metadata */}
          <div className={cn("flex items-center gap-2.5 justify-start", isUser ? "flex-row-reverse" : "")}>
            <span className="text-[11px] font-bold tracking-wider text-muted-foreground uppercase select-none font-mono">
              {isUser ? userDisplayName : 'AgriGPT Assistant'}
            </span>
            <span className="text-[10px] text-muted-foreground/75 select-none font-sans">
              {new Date(message.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          {/* Message Text Panel */}
          <div className={cn(
            "p-4.5 rounded-2xl inline-block max-w-full text-left shadow-sm relative border font-sans text-sm leading-relaxed",
            isUser 
              ? "chat-bubble-user text-foreground border-border bg-[#F2EFE9]" 
              : "chat-bubble-ai text-foreground border-border bg-card"
          )}>
            {/* Collapsible Thinking Steps */}
            {!isUser && message.steps && message.steps.length > 0 && (
              <div className="mb-4.5 border border-border bg-[#FAF9F6] rounded-xl overflow-hidden shadow-sm">
                <button
                  onClick={() => setIsThinkingExpanded(!isThinkingExpanded)}
                  className="w-full flex items-center justify-between px-4 py-2.5 bg-secondary/40 hover:bg-secondary/70 transition-colors cursor-pointer select-none text-left"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-muted-foreground flex items-center gap-1.5 font-bold uppercase tracking-wider font-mono">
                      🧠 reasoning pipeline
                    </span>
                    {message.isGenerating && (
                      <span className="flex h-1.5 w-1.5 relative">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-accent"></span>
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 text-[9px] text-muted-foreground/80 font-semibold uppercase tracking-wider">
                    <span>{isThinkingExpanded ? 'Hide' : 'Show'}</span>
                    {isThinkingExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3.5 w-3.5" />}
                  </div>
                </button>
                
                {isThinkingExpanded && (
                  <div className="px-4.5 py-3 border-t border-border/40 space-y-2 bg-[#FAF9F6]/50 select-none">
                    {message.steps.map((step) => {
                      let icon = <div className="h-3 w-3 rounded-full border border-border bg-card shrink-0" />;
                      let labelClass = 'text-muted-foreground/70 font-medium';
                      
                      if (step.status === 'completed') {
                        icon = <Check className="h-3 w-3 text-primary shrink-0" />;
                        labelClass = 'text-muted-foreground/50 font-semibold line-through decoration-border decoration-1';
                      } else if (step.status === 'active') {
                        icon = <div className="h-3 w-3 rounded-full border-2 border-primary border-t-transparent animate-spin shrink-0" />;
                        labelClass = 'text-primary font-bold';
                      } else if (step.status === 'skipped') {
                        icon = <span className="text-[10px] text-muted-foreground/40 shrink-0 font-extrabold select-none leading-none">-</span>;
                        labelClass = 'text-muted-foreground/40 font-normal italic';
                      }
                      
                      return (
                        <div key={step.id} className="flex items-center gap-2.5 text-[11px]">
                          {icon}
                          <span className={labelClass}>
                            {step.label} {step.status === 'skipped' && <span className="text-[8px] text-muted-foreground/30 not-italic uppercase font-extrabold tracking-wider ml-1">(skipped)</span>}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            <div className={cn("markdown-body leading-relaxed prose max-w-none text-foreground/90 font-sans", !isUser && message.isGenerating ? "streaming-active" : "")}>
              <ReactMarkdown 
                remarkPlugins={[remarkGfm]}
                components={MarkdownComponents}
              >
                {message.content}
              </ReactMarkdown>
            </div>

            {/* Collapsible Grounded Sources Panel */}
            {!isUser && message.sources && message.sources.length > 0 && (
              <div className="mt-4 border-t border-border pt-3 text-left">
                <button
                  onClick={() => setIsSourcesOpen(!isSourcesOpen)}
                  className="flex items-center gap-1.5 text-[11px] font-bold text-muted-foreground hover:text-primary cursor-pointer select-none transition-colors"
                >
                  <span>Grounded Sources ({message.sources.length})</span>
                  {isSourcesOpen ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>

                {isSourcesOpen && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2.5 select-none animate-fade-in">
                    {message.sources.map((src, idx) => {
                      const isWeb = !!src.url;
                      return isWeb ? (
                        <a
                          key={idx}
                          href={src.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="p-2.5 rounded-xl border border-border bg-card hover:bg-secondary/40 hover:border-primary/25 flex flex-col gap-1 transition-all group cursor-pointer shadow-sm"
                        >
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1 text-[9px] font-extrabold text-[#708D81] uppercase tracking-wide">
                              <Globe className="h-3 w-3" /> Web [{idx + 1}]
                            </span>
                            <ExternalLink className="h-3 w-3 text-muted-foreground/50 group-hover:text-primary transition-colors" />
                          </div>
                          <p className="text-[11px] font-semibold text-foreground line-clamp-1 group-hover:text-primary transition-colors">
                            {src.title || "Live Web Update"}
                          </p>
                          {src.date && (
                            <span className="text-[9px] text-muted-foreground/60">{src.date}</span>
                          )}
                        </a>
                      ) : (
                        <div
                          key={idx}
                          className="p-2.5 rounded-xl border border-border bg-card hover:bg-secondary/30 flex flex-col gap-1 transition-all shadow-sm"
                        >
                          <div className="flex items-center justify-between">
                            <span className="flex items-center gap-1 text-[9px] font-extrabold text-primary uppercase tracking-wide">
                              <FileText className="h-3 w-3" /> RAG [{idx + 1}]
                            </span>
                            {src.score !== undefined && (
                              <span className="text-[9px] text-muted-foreground/60 font-mono">
                                score: {Number(src.score).toFixed(3)}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] font-semibold text-foreground line-clamp-1">
                            {src.document || "Telangana Agri Manual"}
                          </p>
                          {src.section && (
                            <span className="text-[9px] text-muted-foreground/80 line-clamp-1">
                              {src.section}
                            </span>
                          )}
                          {src.pages && (
                            <span className="text-[9px] text-muted-foreground/60 font-mono">
                              Pages: {src.pages}
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Premium Metadata Footer */}
          {!isUser && !message.isGenerating && (message.thoughtDuration || message.model || (message.toolsUsed && message.toolsUsed.length > 0)) && (
            <div className="flex flex-wrap items-center gap-3 mt-3 px-3 py-2 border border-border bg-secondary/35 rounded-xl max-w-fit select-none text-[10px] text-muted-foreground shadow-sm">
              {message.thoughtDuration !== undefined && (
                <span className="text-muted-foreground/85 font-semibold flex items-center gap-1">
                  ⏱️ Thought for <span className="font-mono text-foreground">{message.thoughtDuration}s</span>
                </span>
              )}
              
              {message.thoughtDuration !== undefined && (message.model || (message.toolsUsed && message.toolsUsed.length > 0)) && (
                <span className="text-border">|</span>
              )}

              {message.toolsUsed && message.toolsUsed.length > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="text-muted-foreground/70">🛠️ Tools:</span>
                  {message.toolsUsed.map((tool, idx) => {
                    let icon = Sprout;
                    let label = "RAG";
                    let color = "text-primary bg-primary/5 border-primary/10";
                    
                    if (tool === "weather") {
                      icon = CloudSun;
                      label = "Weather";
                      color = "text-[#708D81] bg-[#708D81]/5 border-[#708D81]/15";
                    } else if (tool === "web_search" || tool === "web") {
                      icon = Globe;
                      label = "Web Search";
                      color = "text-[#40916C] bg-[#40916C]/5 border-[#40916C]/15";
                    } else if (tool === "direct_llm") {
                      icon = Cpu;
                      label = "Direct LLM";
                      color = "text-slate-600 bg-slate-100 border-slate-200";
                    }
                    
                    const IconComponent = icon;
                    return (
                      <span key={idx} className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-lg border text-[9px] font-extrabold tracking-wide uppercase font-mono", color)}>
                        <IconComponent className="h-2.5 w-2.5 shrink-0" />
                        {label}
                      </span>
                    );
                  })}
                </span>
              )}

              {(message.model || (message.toolsUsed && message.toolsUsed.length > 0)) && message.model && (
                <>
                  <span className="text-border">|</span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg border border-border bg-card text-[9px] font-mono font-bold text-muted-foreground uppercase tracking-wide">
                    🤖 {message.model.split('/').pop()?.split(':')[0] || message.model}
                  </span>
                </>
              )}
            </div>
          )}

          {/* Action Row */}
          {!isUser && message.content && (
            <div className="flex items-center gap-1.5 mt-1 md:opacity-0 group-hover:opacity-100 transition-opacity duration-300 select-none">
              <button
                onClick={handleCopyMessage}
                className="p-1.5 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary"
                title="Copy response"
              >
                {copiedMessage ? <Check className="h-3.5 w-3.5 text-primary" /> : <Copy className="h-3.5 w-3.5" />}
              </button>

              <button
                onClick={handleShare}
                className="p-1.5 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary"
                title="Share advice"
              >
                {copiedShare ? <Check className="h-3.5 w-3.5 text-primary" /> : <Share2 className="h-3.5 w-3.5" />}
              </button>
              
              <button
                onClick={() => handleFeedback('up')}
                className={cn(
                  "p-1.5 rounded-lg text-muted-foreground hover:bg-secondary transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary",
                  message.feedback === 'up' ? "text-primary bg-primary/10" : "hover:text-foreground"
                )}
                title="Good response"
              >
                <ThumbsUp className="h-3.5 w-3.5" />
              </button>

              <button
                onClick={() => handleFeedback('down')}
                className={cn(
                  "p-1.5 rounded-lg text-muted-foreground hover:bg-secondary transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary",
                  message.feedback === 'down' ? "text-rose-600 bg-rose-50" : "hover:text-foreground"
                )}
                title="Bad response"
              >
                <ThumbsDown className="h-3.5 w-3.5" />
              </button>

              {onRegenerate && (
                <button
                  onClick={onRegenerate}
                  className="p-1.5 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors cursor-pointer outline-none focus-visible:ring-1 focus-visible:ring-primary"
                  title="Regenerate response"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
