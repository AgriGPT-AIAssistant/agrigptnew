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
}

export const useChatStore = create<ChatState>((set) => ({
  sessions: [],
  activeSessionId: null,
  isSidebarOpen: true,
  isLoading: false,
  error: null,

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
}));

