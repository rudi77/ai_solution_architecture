export type Role = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  role: Role;
  content: string;
  timestamp?: number;
}

export interface AgentEvent {
  id: string;
  type: string;
  message: string;
  timestamp: number;
  run_id?: string;
  conversation_id?: string;
  data?: any;
}

export interface TaskProgress {
  id: string;
  title: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
}

export interface ClarificationRequest {
  question: string;
  required_fields: string[];
  context: Record<string, any>;
}

export interface ChatState {
  messages: ChatMessage[];
  events: AgentEvent[];
  tasks: TaskProgress[];
  isLoading: boolean;
  clarificationRequest?: ClarificationRequest;
  conversationId?: string;
}