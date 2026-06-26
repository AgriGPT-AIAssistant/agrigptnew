'use client';

import React, { useState } from 'react';
import { useChatStore } from '@/store/useChatStore';
import { Button } from '@/components/ui/button';
import { useSession, signOut } from 'next-auth/react';
import { 
  Plus, MessageSquare, Trash2, Sprout, Search, ChevronLeft, 
  User, Settings as SettingsIcon, BarChart3, LogOut, X, ShieldCheck, Cpu
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { Avatar } from '@/components/ui/avatar';

export function Sidebar() {
  const { data: session } = useSession();
  const user = session?.user;

  const {
    sessions,
    activeSessionId,
    isSidebarOpen,
    createSession,
    deleteSession,
    setActiveSessionId,
    toggleSidebar,
  } = useChatStore();

  const [searchQuery, setSearchQuery] = useState('');
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [usageModalOpen, setUsageModalOpen] = useState(false);

  // General App settings states (configured in Settings modal)
  const [selectedRegion, setSelectedRegion] = useState('Telangana (Kharif/Rabi)');
  const [selectedLanguage, setSelectedLanguage] = useState('English / Telugu');

  const handleNewChat = () => {
    createSession('New Conversation');
  };

  const handleLogout = () => {
    useChatStore.getState().resetStore();
    signOut({ callbackUrl: '/auth' });
  };

  // Filter sessions based on search
  const filteredSessions = sessions.filter(session => 
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Fallback defaults if no active Google session is found
  const userDisplayName = user?.name || 'Guest User';
  const userDisplayEmail = user?.email || 'Not logged in';
  const userInitials = userDisplayName
    .split(' ')
    .map(n => n[0])
    .join('')
    .substring(0, 2)
    .toUpperCase();

  return (
    <>
      <aside
        className={cn(
          "fixed md:static inset-y-0 left-0 z-40 bg-gradient-to-b from-[#FAF9F6] to-[#F4F2EB] border-r border-border flex flex-col transition-all duration-300 ease-in-out select-none",
          isSidebarOpen 
            ? "w-72 translate-x-0" 
            : "w-0 -translate-x-full md:translate-x-0 md:w-0 md:border-r-0 overflow-hidden"
        )}
      >
        {/* Header / Brand */}
        <div className="h-16 shrink-0 border-b border-border flex items-center justify-between px-4">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-primary/10 rounded-xl text-primary border border-primary/20">
              <Sprout className="h-5 w-5" />
            </div>
            <span className="font-bold text-base text-foreground font-mono tracking-tight">
              Agri<span className="text-primary font-bold">GPT</span>
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="text-muted-foreground hover:text-foreground hover:bg-secondary/60 cursor-pointer"
            onClick={toggleSidebar}
          >
            <ChevronLeft className="h-4.5 w-4.5" />
          </Button>
        </div>

        {/* Action / New Chat Button */}
        <div className="p-3 shrink-0">
          <Button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 border border-primary/20 hover:border-primary/40 bg-primary/5 hover:bg-primary/10 text-primary hover:text-primary/95 transition-all font-medium py-5.5 rounded-xl shadow-sm hover:shadow group cursor-pointer"
            variant="outline"
          >
            <Plus className="h-4 w-4 group-hover:rotate-90 transition-transform duration-200" />
            New Chat
          </Button>
        </div>

        {/* Search Bar */}
        <div className="px-3 pb-2 shrink-0">
          <div className="relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search conversations..."
              className="w-full bg-card border border-border focus:border-primary/50 text-xs text-foreground rounded-lg pl-9 pr-4 py-2.5 focus:outline-none transition-all placeholder:text-muted-foreground/70"
            />
          </div>
        </div>

        {/* History Lists */}
        <div className="flex-1 overflow-y-auto px-2 space-y-0.5 py-2">
          <p className="px-3 text-[10px] font-bold text-muted-foreground uppercase tracking-wider mb-2 font-mono">
            Chat History
          </p>
          
          {filteredSessions.length === 0 ? (
            <div className="text-center py-8 px-3">
              <p className="text-xs text-muted-foreground/60">No conversations found.</p>
            </div>
          ) : (
            filteredSessions.map((session) => {
              const isActive = session.id === activeSessionId;
              const lastMsg = session.messages[session.messages.length - 1];
              const activityTime = lastMsg ? lastMsg.createdAt : session.createdAt;
              const formattedTime = new Date(activityTime).toLocaleDateString([], {
                month: 'short',
                day: 'numeric'
              });

              return (
                <div
                  key={session.id}
                  onClick={() => setActiveSessionId(session.id)}
                  className={cn(
                    "group relative flex items-center justify-between gap-3 px-3 py-2.5 rounded-xl cursor-pointer text-xs transition-all duration-150 select-none border border-transparent",
                    isActive
                      ? "bg-secondary border-border text-primary font-semibold shadow-sm"
                      : "text-slate-700 hover:bg-secondary/40 hover:text-foreground"
                  )}
                >
                  <div className="flex items-center gap-2.5 min-w-0 flex-1">
                    <MessageSquare className={cn("h-4 w-4 shrink-0", isActive ? "text-primary" : "text-muted-foreground")} />
                    <div className="flex-1 flex flex-col min-w-0 text-left">
                      <div className="flex items-center justify-between gap-1.5 w-full">
                        <span className={cn("truncate pr-1 font-medium", isActive ? "text-primary" : "text-slate-800 group-hover:text-foreground")}>
                          {session.title}
                        </span>
                        <span className="text-[9px] text-muted-foreground/80 shrink-0 font-medium font-sans">
                          {formattedTime}
                        </span>
                      </div>
                      <span className="text-[10px] text-muted-foreground truncate mt-0.5 font-sans leading-normal">
                        {lastMsg ? lastMsg.content.replace(/[\*\#\`\_]+/g, '').substring(0, 45) : "No advice requested yet"}
                      </span>
                    </div>
                  </div>
                  
                  {/* Delete button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSession(session.id);
                    }}
                    className={cn(
                      "p-1.5 rounded text-muted-foreground/60 hover:bg-white hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity duration-150 cursor-pointer shrink-0 ml-1 border border-transparent hover:border-border shadow-sm",
                      isActive && "opacity-100 md:opacity-0"
                    )}
                    title="Delete Conversation"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>

        {/* Footer User Profile Summary */}
        <div className="p-3 shrink-0 border-t border-border bg-[#F4F2EB]/40 relative">
          {/* User Account Popover Dropdown Menu */}
          <AnimatePresence>
            {userMenuOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setUserMenuOpen(false)} />
                <motion.div
                  initial={{ opacity: 0, y: 15, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 10, scale: 0.95 }}
                  transition={{ duration: 0.2, ease: 'easeOut' }}
                  className="absolute bottom-[72px] left-3 right-3 bg-card border border-border rounded-2xl shadow-2xl p-1.5 z-40 flex flex-col font-medium"
                >
                  <button
                    onClick={() => { setUserMenuOpen(false); setProfileModalOpen(true); }}
                    className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-xs text-slate-700 hover:bg-secondary hover:text-foreground text-left cursor-pointer transition-colors"
                  >
                    <User className="w-4 h-4 text-muted-foreground" />
                    👤 My Profile
                  </button>

                  <div className="h-[1px] bg-border my-1 mx-2" />
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700 text-left cursor-pointer transition-colors"
                  >
                    <LogOut className="w-4 h-4 text-rose-500" />
                    🚪 Logout
                  </button>
                </motion.div>
              </>
            )}
          </AnimatePresence>

          {/* Core Footer Trigger */}
          <div 
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center justify-between gap-3 p-1.5 rounded-xl hover:bg-white/40 border border-transparent hover:border-border transition-all cursor-pointer shadow-sm hover:shadow"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <Avatar
                src={user?.image || undefined}
                fallback={userInitials}
                className="h-8.5 w-8.5 rounded-xl border border-border shadow-sm shrink-0 bg-primary/10 text-primary"
              />
              <div className="min-w-0 flex-col text-left">
                <p className="text-xs font-bold text-foreground truncate">{userDisplayName}</p>
                <p className="text-[10px] text-muted-foreground truncate leading-none mt-0.5">{userDisplayEmail}</p>
              </div>
            </div>
            <div className="flex flex-col gap-0.5 shrink-0 text-slate-400">
              <span className="block w-1.5 h-1.5 rounded-full bg-primary/40" />
              <span className="block w-1.5 h-1.5 rounded-full bg-primary/40" />
            </div>
          </div>
        </div>
      </aside>

      {/* ──────────────────────────────────────────────────────────────────────── */}
      {/* PROFILE DIALOG MODAL */}
      <AnimatePresence>
        {profileModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 backdrop-blur-sm"
              onClick={() => setProfileModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              className="relative w-full max-w-md bg-card border border-border rounded-3xl p-6 shadow-2xl z-50 text-left space-y-6"
            >
              <button 
                onClick={() => setProfileModalOpen(false)}
                className="absolute top-4 right-4 p-1.5 rounded-lg border border-border hover:bg-secondary text-muted-foreground hover:text-foreground cursor-pointer transition-colors shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-4">
                <Avatar
                  src={user?.image || undefined}
                  fallback={userInitials}
                  className="h-16 w-16 rounded-2xl border border-border bg-primary/10 text-primary text-xl font-bold"
                />
                <div className="space-y-1">
                  <h3 className="text-lg font-bold text-foreground">{userDisplayName}</h3>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg border border-primary/20 bg-primary/5 text-[9px] font-extrabold tracking-wider uppercase text-primary font-mono select-none">
                    <ShieldCheck className="w-3 h-3 text-primary" /> Google Account Verified
                  </span>
                </div>
              </div>

              <div className="border-t border-border pt-4 space-y-3 text-xs leading-normal">
                <div className="flex justify-between py-1 border-b border-border/50">
                  <span className="text-muted-foreground font-medium">Email Address</span>
                  <span className="text-foreground font-semibold font-mono">{userDisplayEmail}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-border/50">
                  <span className="text-muted-foreground font-medium">Authentication Authority</span>
                  <span className="text-foreground font-semibold">Auth.js / OAuth2</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-muted-foreground font-medium">Status</span>
                  <span className="text-primary font-bold">Active Session</span>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ──────────────────────────────────────────────────────────────────────── */}
      {/* SETTINGS DIALOG MODAL */}
      <AnimatePresence>
        {settingsModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 backdrop-blur-sm"
              onClick={() => setSettingsModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              className="relative w-full max-w-md bg-card border border-border rounded-3xl p-6 shadow-2xl z-50 text-left space-y-6"
            >
              <button 
                onClick={() => setSettingsModalOpen(false)}
                className="absolute top-4 right-4 p-1.5 rounded-lg border border-border hover:bg-secondary text-muted-foreground hover:text-foreground cursor-pointer transition-colors shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="space-y-1">
                <h3 className="text-lg font-bold text-foreground">Redesign Settings</h3>
                <p className="text-xs text-muted-luxury leading-relaxed">Customize your agricultural workspace parameters.</p>
              </div>

              <div className="space-y-4 pt-2 text-xs">
                {/* Region Select */}
                <div className="space-y-2">
                  <label className="text-foreground font-semibold block">Target Farming Region</label>
                  <select 
                    value={selectedRegion}
                    onChange={(e) => setSelectedRegion(e.target.value)}
                    className="w-full h-10 px-3 border border-border rounded-xl bg-secondary/35 text-foreground focus:outline-none focus:border-primary/50 font-medium"
                  >
                    <option>Telangana (Kharif/Rabi)</option>
                    <option>Andhra Pradesh (Coastal/Rayalaseema)</option>
                    <option>Karnataka (Deccan Plateau)</option>
                    <option>Maharashtra (Vidarbha/Marathwada)</option>
                  </select>
                </div>

                {/* Language Select */}
                <div className="space-y-2">
                  <label className="text-foreground font-semibold block">Preferred Language</label>
                  <select 
                    value={selectedLanguage}
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                    className="w-full h-10 px-3 border border-border rounded-xl bg-secondary/35 text-foreground focus:outline-none focus:border-primary/50 font-medium"
                  >
                    <option>English / Telugu</option>
                    <option>English / Kannada</option>
                    <option>English / Marathi</option>
                    <option>English Only</option>
                  </select>
                </div>

                {/* LLM Engine Display */}
                <div className="p-3 bg-secondary/40 border border-border rounded-xl flex items-start gap-2.5 leading-normal text-[11px] text-muted-foreground">
                  <Cpu className="w-4.5 h-4.5 text-primary shrink-0 mt-0.5" />
                  <div>
                    <span className="text-foreground font-bold block mb-0.5">Generative AI Provider</span>
                    NextAuth session coordinates LLM calls securely with the backend retrieve engine.
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ──────────────────────────────────────────────────────────────────────── */}
      {/* USAGE DIALOG MODAL */}
      <AnimatePresence>
        {usageModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 backdrop-blur-sm"
              onClick={() => setUsageModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 15 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 15 }}
              className="relative w-full max-w-md bg-card border border-border rounded-3xl p-6 shadow-2xl z-50 text-left space-y-6"
            >
              <button 
                onClick={() => setUsageModalOpen(false)}
                className="absolute top-4 right-4 p-1.5 rounded-lg border border-border hover:bg-secondary text-muted-foreground hover:text-foreground cursor-pointer transition-colors shadow-sm"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="space-y-1">
                <h3 className="text-lg font-bold text-foreground">Usage Telemetry</h3>
                <p className="text-xs text-muted-luxury leading-relaxed">Telemetry metrics bound to your agricultural profile session.</p>
              </div>

              <div className="space-y-4 pt-2 text-xs leading-normal">
                {/* Metric 1 */}
                <div className="space-y-1.5">
                  <div className="flex justify-between font-semibold">
                    <span className="text-foreground">AI Queries Sent</span>
                    <span className="text-primary">12 / 100</span>
                  </div>
                  <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-[12%] rounded-full" />
                  </div>
                </div>

                {/* Metric 2 */}
                <div className="space-y-1.5">
                  <div className="flex justify-between font-semibold">
                    <span className="text-foreground">Weather Diagnostics Checks</span>
                    <span className="text-primary">8 / 50</span>
                  </div>
                  <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                    <div className="h-full bg-accent w-[16%] rounded-full" />
                  </div>
                </div>

                {/* Metric 3 */}
                <div className="space-y-1.5">
                  <div className="flex justify-between font-semibold">
                    <span className="text-foreground">Vector RAG Database Lookups</span>
                    <span className="text-primary">24 / 200</span>
                  </div>
                  <div className="h-1.5 w-full bg-secondary rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-[12%] rounded-full" />
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
