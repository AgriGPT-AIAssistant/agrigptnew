import { create } from 'zustand';
import { ChatSession, Message } from '../types/chat';

interface ChatState {
  sessions: ChatSession[];
  activeSessionId: string | null;
  isSidebarOpen: boolean;
  isLoading: boolean;
  error: string | null;
  
  createSession: (title?: string) => string;
  deleteSession: (id: string) => void;
  addMessage: (sessionId: string, message: Message) => void;
  updateMessageContent: (sessionId: string, messageId: string, content: string) => void;
  updateMessageMetadata: (sessionId: string, messageId: string, metadata: Partial<Message>) => void;
  updateMessageFeedback: (sessionId: string, messageId: string, feedback: 'up' | 'down' | null) => void;
  setActiveSessionId: (id: string | null) => void;
  toggleSidebar: () => void;
  setIsLoading: (loading: boolean) => void;
  setError: (err: string | null) => void;
  clearSessionMessages: (sessionId: string) => void;
  resetStore: () => void;
  
  // Backend Integration
  loadBackendSessions: () => Promise<void>;
  loadSessionHistory: (sessionId: string) => Promise<void>;
}

import { chatService } from '../services/chatService';

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  activeSessionId: null,
  isSidebarOpen: true,
  isLoading: false,
  error: null,

  loadBackendSessions: async () => {
    try {
      const data = await chatService.getSessions();
      if (data && data.sessions) {
        set((state) => {
          // Merge backend sessions with existing local sessions
          const existingIds = new Set(state.sessions.map(s => s.id));
          const newSessions = data.sessions
            .filter((s: any) => !existingIds.has(s.session_id))
            .map((s: any) => ({
              id: s.session_id,
              title: s.title || 'New Conversation',
              messages: [],
              createdAt: new Date().toISOString()
            }));
          
          if (newSessions.length === 0) return state;
          
          const combined = [...state.sessions, ...newSessions];
          return {
            sessions: combined,
            activeSessionId: state.activeSessionId || (combined.length > 0 ? combined[0].id : null)
          };
        });
      }
    } catch (err) {
      console.error("Failed to load backend sessions:", err);
    }
  },

  loadSessionHistory: async (sessionId: string) => {
    try {
      const data = await chatService.getHistory(sessionId);
      if (data && data.history) {
        set((state) => ({
          sessions: state.sessions.map((s) => {
            if (s.id !== sessionId) return s;
            // Only load history if we don't have local messages yet
            if (s.messages.length > 0) return s;
            
            const messages = data.history.map((m: any, idx: number) => ({
              id: `msg_${idx}`,
              role: m.role,
              content: m.content,
              createdAt: new Date().toISOString()
            }));
            
            return { ...s, messages };
          })
        }));
      }
    } catch (err) {
      console.error(`Failed to load history for ${sessionId}:`, err);
    }
  },

  createSession: (title) => {
    const id = `sess_${Math.random().toString(36).substring(2, 15)}`;
    const newSession: ChatSession = {
      id,
      title: title || 'New Conversation',
      messages: [],
      createdAt: new Date().toISOString(),
    };
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      activeSessionId: id,
    }));
    return id;
  },

  deleteSession: (id) => {
    set((state) => {
      const nextSessions = state.sessions.filter((s) => s.id !== id);
      let nextActiveId = state.activeSessionId;
      if (nextActiveId === id) {
        nextActiveId = nextSessions.length > 0 ? nextSessions[0].id : null;
      }
      return {
        sessions: nextSessions,
        activeSessionId: nextActiveId,
      };
    });
  },

  addMessage: (sessionId, message) => {
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        
        // Auto-update session title based on the first user message
        let title = s.title;
        if (s.messages.length === 0 && message.role === 'user') {
          title = message.content.length > 30 
            ? message.content.substring(0, 30) + '...' 
            : message.content;
        }
        
        return {
          ...s,
          title,
          messages: [...s.messages, message],
        };
      }),
    }));
  },

  updateMessageContent: (sessionId, messageId, content) => {
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => {
            if (m.id !== messageId) return m;
            return { ...m, content };
          }),
        };
      }),
    }));
  },

  updateMessageMetadata: (sessionId, messageId, metadata) => {
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => {
            if (m.id !== messageId) return m;
            return { ...m, ...metadata };
          }),
        };
      }),
    }));
  },

  updateMessageFeedback: (sessionId, messageId, feedback) => {
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => {
            if (m.id !== messageId) return m;
            return { ...m, feedback };
          }),
        };
      }),
    }));
  },

  setActiveSessionId: (id) => set({ activeSessionId: id }),
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setIsLoading: (loading) => set({ isLoading: loading }),
  setError: (err) => set({ error: err }),
  clearSessionMessages: (sessionId) => {
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return { ...s, messages: [] };
      }),
    }));
  },
  resetStore: () => set({ sessions: [], activeSessionId: null, error: null, isLoading: false }),
}));

