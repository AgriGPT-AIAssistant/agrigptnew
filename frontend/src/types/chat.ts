export interface Source {
  title?: string;
  url?: string;
  score?: number;
  date?: string;
  document?: string;
  section?: string;
  pages?: string;
  method?: string;
}

export interface Step {
  id: string;
  label: string;
  status: 'pending' | 'active' | 'completed' | 'skipped';
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  thoughtDuration?: number; // e.g., 3.8 for 3.8 seconds
  model?: string;
  toolsUsed?: string[];
  sources?: Source[];
  feedback?: 'up' | 'down' | null;
  isGenerating?: boolean;
  steps?: Step[];
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
}


export interface ChatRequestPayload {
  message: string;
  session_id?: string;
}

export interface ChatMessageResponsePayload {
  id: string;
  role: 'assistant';
  content: string;
  created_at: string;
}

export interface ChatResponsePayload {
  session_id: string;
  message: ChatMessageResponsePayload;
}
