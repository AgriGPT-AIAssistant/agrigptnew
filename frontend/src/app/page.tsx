'use client';

import React, { useEffect, useState } from 'react';
import { useChatStore } from '@/store/useChatStore';
import { Sidebar } from '@/components/chat/sidebar';
import { TopNavbar } from '@/components/chat/top-navbar';
import { ChatWindow } from '@/components/chat/chat-window';
import { ChatInput } from '@/components/chat/chat-input';
import { chatService } from '@/services/chatService';
import api from '@/services/api';
import { useSession } from 'next-auth/react';
import { Message, Step } from '@/types/chat';
import { Sprout } from 'lucide-react';

export default function Home() {
  const [statusText, setStatusText] = useState<string>('');
  const [mounted, setMounted] = useState(false);
  const { data: session } = useSession();

  useEffect(() => {
    if (session?.id_token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${session.id_token}`;
    } else {
      const isDev = process.env.NODE_ENV === 'development';
      const hasGoogleKeys = !!(process.env.AUTH_GOOGLE_ID || process.env.GOOGLE_CLIENT_ID);
      if (isDev && !hasGoogleKeys) {
        api.defaults.headers.common['Authorization'] = 'Bearer mock-dev-token';
      } else {
        delete api.defaults.headers.common['Authorization'];
      }
    }
  }, [session]);
  
  const {
    activeSessionId,
    sessions,
    createSession,
    addMessage,
    updateMessageContent,
    updateMessageMetadata,
    isLoading,
    setIsLoading,
    setError,
    isSidebarOpen,
    toggleSidebar,
    loadBackendSessions,
    loadSessionHistory
  } = useChatStore();

  // Handle client-side mount and backend hydration
  useEffect(() => {
    setMounted(true);
    
    // Load sessions from SQLite via backend
    loadBackendSessions().then(() => {
      // Auto-create first session if list is empty after backend fetch
      if (useChatStore.getState().sessions.length === 0) {
        createSession('AgriGPT Session');
      }
    });
  }, [createSession, loadBackendSessions]);

  // Load history when activeSessionId changes
  useEffect(() => {
    if (activeSessionId) {
      loadSessionHistory(activeSessionId);
    }
  }, [activeSessionId, loadSessionHistory]);

  const handleSendMessage = async (content: string) => {
    let currentSessionId = activeSessionId;
    
    // Auto create session if it was deleted or is null
    if (!currentSessionId) {
      currentSessionId = createSession();
    }

    // 1. Dispatch User Message
    const userMessage: Message = {
      id: `msg_u_${Math.random().toString(36).substring(2, 11)}`,
      role: 'user',
      content,
      createdAt: new Date().toISOString(),
    };
    addMessage(currentSessionId, userMessage);

    // 2. Dispatch empty Assistant placeholder message to stream into
    const assistantMessageId = `msg_a_${Math.random().toString(36).substring(2, 11)}`;
    const initialSteps: Step[] = [
      { id: 'routing', label: 'Analyzing query & routing...', status: 'active' },
      { id: 'retrieval', label: 'Retrieving agricultural database...', status: 'pending' },
      { id: 'weather', label: 'Checking weather conditions...', status: 'pending' },
      { id: 'web_search', label: 'Searching web sources...', status: 'pending' },
      { id: 'generation', label: 'Generating agricultural advice...', status: 'pending' },
    ];
    
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      createdAt: new Date().toISOString(),
      isGenerating: true,
      steps: initialSteps,
    };
    addMessage(currentSessionId, assistantMessage);

    setIsLoading(true);
    setError(null);
    setStatusText('Thinking...');

    let accumulatedContent = '';
    let currentSteps = [...initialSteps];

    const updateStepStatus = (stepId: string, status: 'active' | 'completed' | 'skipped') => {
      currentSteps = currentSteps.map(step => {
        if (step.id === stepId) {
          return { ...step, status };
        }
        return step;
      });
      updateMessageMetadata(currentSessionId!, assistantMessageId, { steps: currentSteps });
    };

    try {
      // Connect to the backend stream
      await chatService.sendMessageStream(
        content,
        currentSessionId,
        (session?.id_token as string) || '',
        (token) => {
          accumulatedContent += token;
          updateMessageContent(currentSessionId!, assistantMessageId, accumulatedContent);
        },
        (event, data) => {
          if (event === 'thinking_started') {
            setStatusText('Understanding query...');
            updateStepStatus('routing', 'active');
          } else if (event === 'weather_started') {
            setStatusText('Checking weather conditions...');
            updateStepStatus('routing', 'completed');
            updateStepStatus('weather', 'active');
          } else if (event === 'retrieval_started') {
            setStatusText('Searching vector database...');
            updateStepStatus('routing', 'completed');
            updateStepStatus('retrieval', 'active');
          } else if (event === 'reranking_started') {
            setStatusText('Reranking documents...');
            updateStepStatus('retrieval', 'active');
          } else if (event === 'web_search_started') {
            setStatusText('Searching web sources...');
            updateStepStatus('routing', 'completed');
            updateStepStatus('web_search', 'active');
          } else if (event === 'generation_started') {
            setStatusText('Generating answer...');
            currentSteps = currentSteps.map(step => {
              if (step.id === 'routing') return { ...step, status: 'completed' as const };
              if (step.id === 'generation') return { ...step, status: 'active' as const };
              if (step.status === 'active') return { ...step, status: 'completed' as const };
              if (step.status === 'pending') return { ...step, status: 'skipped' as const };
              return step;
            });
            updateMessageMetadata(currentSessionId!, assistantMessageId, { steps: currentSteps });
          } else if (event === 'generation_completed') {
            setStatusText('');
            currentSteps = currentSteps.map(step => 
              step.id === 'generation' ? { ...step, status: 'completed' as const } : step
            );
            updateMessageMetadata(currentSessionId!, assistantMessageId, {
              isGenerating: false,
              steps: currentSteps,
              thoughtDuration: data.latency_s,
              model: data.model,
              toolsUsed: data.tools_used,
              sources: data.sources,
            });
          }
        },
        () => {
          // Stream completed
          setIsLoading(false);
          setStatusText('');
          updateMessageMetadata(currentSessionId!, assistantMessageId, { isGenerating: false });
        },
        async (error) => {
          console.warn('Streaming connection failed, falling back to standard POST:', error);
          setStatusText('Contacting server...');
          // Fallback to standard HTTP POST request on socket/stream error
          try {
            const response = await chatService.sendMessage(content, currentSessionId!);
            updateMessageContent(currentSessionId!, assistantMessageId, response.message.content);
            
            const fallbackSteps = [
              { id: 'routing', label: 'Analyzing query & routing...', status: 'completed' as const },
              { id: 'retrieval', label: 'Retrieving agricultural database...', status: 'completed' as const },
              { id: 'weather', label: 'Checking weather conditions...', status: 'skipped' as const },
              { id: 'web_search', label: 'Searching web sources...', status: 'skipped' as const },
              { id: 'generation', label: 'Generating agricultural advice...', status: 'completed' as const },
            ];

            updateMessageMetadata(currentSessionId!, assistantMessageId, {
              isGenerating: false,
              steps: fallbackSteps,
              thoughtDuration: 1.5,
              model: 'fallback-api',
              toolsUsed: ['RAG']
            });
          } catch (fallbackError) {
            const errorMsg = (fallbackError as Error).message || 'Failed to establish connection to AgriGPT servers.';
            setError(errorMsg);
            updateMessageContent(
              currentSessionId!,
              assistantMessageId,
              `**Connection Error**: ${errorMsg}\n\n*Please ensure the FastAPI backend is running on port 8000.*`
            );
            updateMessageMetadata(currentSessionId!, assistantMessageId, { isGenerating: false });
          } finally {
            setIsLoading(false);
            setStatusText('');
          }
        }
      );
    } catch (err) {
      setError((err as Error).message);
      setIsLoading(false);
      setStatusText('');
    }
  };

  const handleRegenerateMessage = async (messageId: string) => {
    const activeSession = sessions.find((s) => s.id === activeSessionId);
    if (!activeSession) return;
    
    // Find the message index
    const msgIndex = activeSession.messages.findIndex((m) => m.id === messageId);
    if (msgIndex === -1) return;
    
    // The user query is the message immediately before this assistant message
    const userMsg = activeSession.messages[msgIndex - 1];
    if (!userMsg || userMsg.role !== 'user') return;
    
    // Delete this assistant message and all subsequent messages in the session
    const updatedMessages = activeSession.messages.slice(0, msgIndex);
    useChatStore.setState({
      sessions: sessions.map((s) => {
        if (s.id !== activeSessionId) return s;
        return { ...s, messages: updatedMessages };
      })
    });
    
    // Resend the user query content
    await handleSendMessage(userMsg.content);
  };

  if (!mounted) {
    return (
      <div className="h-screen w-screen bg-background flex flex-col items-center justify-center gap-4">
        <div className="p-3 bg-primary/10 border border-primary/20 rounded-2xl text-primary animate-pulse">
          <Sprout className="h-10 w-10" />
        </div>
        <div className="h-1 w-24 bg-secondary rounded-full overflow-hidden relative">
          <div className="absolute inset-y-0 left-0 bg-primary w-1/2 rounded-full animate-[shimmer_1.5s_infinite_linear]" style={{
            animation: 'shimmer 1.5s infinite ease-in-out'
          }} />
        </div>
        <style jsx global>{`
          @keyframes shimmer {
            0% { left: -100%; width: 100%; }
            50% { left: 0%; width: 50%; }
            100% { left: 100%; width: 100%; }
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Sidebar History Panel */}
      <Sidebar />

      {/* Main chat column */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        <TopNavbar />

        {/* Message feed viewport */}
        <ChatWindow 
          onSend={handleSendMessage} 
          statusText={statusText} 
          onRegenerate={handleRegenerateMessage} 
        />

        {/* Message typing box */}
        <ChatInput onSend={handleSendMessage} disabled={isLoading} />

        {/* Responsive Drawer Backdrop overlay for mobile viewport */}
        {isSidebarOpen && (
          <div
            onClick={toggleSidebar}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 md:hidden cursor-pointer"
          />
        )}
      </div>
    </div>
  );
}

