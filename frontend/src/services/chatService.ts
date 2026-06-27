import api from './api';
import { ChatResponsePayload, ChatRequestPayload } from '../types/chat';

export const chatService = {
  /**
   * Standard single-turn chat response
   */
  async sendMessage(message: string, sessionId?: string): Promise<ChatResponsePayload> {
    const payload: ChatRequestPayload = { message, session_id: sessionId };
    const response = await api.post<ChatResponsePayload>('/chat', payload);
    return response.data;
  },

  async getSessions(): Promise<any> {
    const response = await api.get('/chat/sessions');
    return response.data;
  },

  async getHistory(sessionId: string): Promise<any> {
    const response = await api.get(`/chat/history/${sessionId}`);
    return response.data;
  },

  /**
   * SSE Stream connection that reads chunked response buffers in real time
   */
  async sendMessageStream(
    message: string,
    sessionId: string | undefined,
    token: string,
    onChunk: (chunk: string) => void,
    onEvent?: (event: string, data: any) => void,
    onDone?: () => void,
    onError?: (err: Error) => void
  ): Promise<void> {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      } else if (process.env.NODE_ENV === 'development') {
        headers['Authorization'] = 'Bearer mock-dev-token';
      }

      const response = await fetch(`${baseUrl}/chat/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message, session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error(`Streaming failed: ${response.status} ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response stream reader unavailable.');
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        
        // Keep the last partial line in buffer
        buffer = lines.pop() || '';

        for (const line of lines) {
          const cleanLine = line.trim();
          if (cleanLine.startsWith('event:')) {
            currentEvent = cleanLine.slice(6).trim();
          } else if (cleanLine.startsWith('data:')) {
            const dataContent = cleanLine.slice(5).trim();
            if (dataContent === '[DONE]') {
              if (onDone) onDone();
              return;
            }
            if (dataContent) {
              // Convert protected spaces and carriage returns back to normal formatting
              const cleanData = dataContent.replace(/&nbsp;/g, ' ').replace(/\r/g, '\n');
              if (currentEvent && currentEvent !== 'token' && onEvent) {
                try {
                  const parsed = JSON.parse(cleanData);
                  onEvent(currentEvent, parsed);
                } catch (e) {
                  onEvent(currentEvent, cleanData);
                }
              } else {
                onChunk(cleanData);
              }
            }
            // Reset event name for the next block
            currentEvent = '';
          }
        }
      }

      // Process any remaining buffer
      const finalClean = buffer.trim();
      if (finalClean.startsWith('data:')) {
        const dataContent = finalClean.slice(5).trim();
        if (dataContent && dataContent !== '[DONE]') {
          const cleanData = dataContent.replace(/&nbsp;/g, ' ').replace(/\r/g, '\n');
          if (currentEvent && currentEvent !== 'token' && onEvent) {
            try {
              onEvent(currentEvent, JSON.parse(cleanData));
            } catch (e) {
              onEvent(currentEvent, cleanData);
            }
          } else {
            onChunk(cleanData);
          }
        }
      }
      
      if (onDone) onDone();
    } catch (error) {
      if (onError) {
        onError(error as Error);
      } else {
        throw error;
      }
    }
  },

};
