import type { ChatMessage, AgentEvent } from '../types/chat';

const API_BASE_URL = 'http://127.0.0.1:8001';

export class ChatService {
  constructor() {
    // Using Server-Sent Events and fetch API for communication
  }

  async sendMessage(messages: ChatMessage[], conversationId?: string): Promise<string> {
    const response = await fetch(`${API_BASE_URL}/api/chat/v2/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages,
        conversation_id: conversationId,
        stream: false
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.conversation_id;
  }

  async *streamMessage(messages: ChatMessage[], conversationId?: string): AsyncGenerator<AgentEvent> {
    const response = await fetch(`${API_BASE_URL}/api/chat/v2/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages,
        conversation_id: conversationId,
        stream: true
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const eventData = JSON.parse(line.slice(6));
              
              // Check for completion event
              if (eventData.type === 'stream_complete') {
                return;
              }

              yield eventData as AgentEvent;
            } catch (e) {
              console.warn('Failed to parse SSE data:', line);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  }

  async sendClarification(
    conversationId: string, 
    response: string, 
    originalMessage: string,
    runId?: string
  ): Promise<void> {
    const apiResponse = await fetch(`${API_BASE_URL}/api/chat/v2/clarification`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        conversation_id: conversationId,
        response,
        original_message: originalMessage,
        run_id: runId
      }),
    });

    if (!apiResponse.ok) {
      throw new Error(`HTTP error! status: ${apiResponse.status}`);
    }
  }

  async getConversationHistory(conversationId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/chat/v2/conversation/${conversationId}/history`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async clearConversation(conversationId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/chat/v2/conversation/${conversationId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  disconnect() {
    // No persistent connection to disconnect
  }
}