import React, { useState, useRef, useEffect } from 'react';
import { Send, Trash2 } from 'lucide-react';
import type { ChatMessage, AgentEvent, TaskProgress, ChatState } from '../types/chat';
import { ChatService } from '../services/chatService';
import { MessageBubble } from './MessageBubble';
import { TaskProgress as TaskProgressComponent } from './TaskProgress';
import { EventDisplay } from './EventDisplay';
import { ClarificationDialog } from './ClarificationDialog';

export const ChatContainer: React.FC = () => {
  const [chatState, setChatState] = useState<ChatState>({
    messages: [],
    events: [],
    tasks: [],
    isLoading: false,
  });
  const [inputMessage, setInputMessage] = useState('');
  const chatService = useRef(new ChatService());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatState.messages, chatState.events]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || chatState.isLoading) return;

    const userMessage: ChatMessage = {
      role: 'user',
      content: inputMessage.trim(),
      timestamp: Date.now(),
    };

    const newMessages = [...chatState.messages, userMessage];
    
    setChatState(prev => ({
      ...prev,
      messages: newMessages,
      isLoading: true,
      clarificationRequest: undefined,
    }));
    
    setInputMessage('');

    try {
      // Stream the response
      const eventGenerator = chatService.current.streamMessage(newMessages, chatState.conversationId);
      
      let assistantMessage = '';
      const newEvents: AgentEvent[] = [];
      const newTasks: TaskProgress[] = [];

      for await (const event of eventGenerator) {
        newEvents.push(event);

        // Handle different event types
        switch (event.type) {
          case 'agent_message':
            if (event.data?.content) {
              assistantMessage = event.data.content;
            }
            break;
          
          case 'agent_clarification':
            setChatState(prev => ({
              ...prev,
              clarificationRequest: {
                question: event.data?.question || event.message,
                required_fields: event.data?.required_fields || [],
                context: event.data?.context || {},
              },
              isLoading: false,
            }));
            return; // Don't add assistant message yet
          
          case 'agent_plan_created':
            if (event.data?.tasks) {
              const tasks = event.data.tasks.map((task: any, index: number) => ({
                id: task.id || `task_${index}`,
                title: task.title || task,
                status: 'pending' as const,
              }));
              newTasks.push(...tasks);
            }
            break;
          
          case 'agent_tool_call':
            // Update task status to in_progress if we can match it
            const toolTaskIndex = newTasks.findIndex(task => 
              task.title.toLowerCase().includes(event.data?.tool_name?.toLowerCase() || '')
            );
            if (toolTaskIndex >= 0) {
              newTasks[toolTaskIndex].status = 'in_progress';
            }
            break;
          
          case 'agent_tool_result':
            // Update task status based on success
            const resultTaskIndex = newTasks.findIndex(task => 
              task.title.toLowerCase().includes(event.data?.tool_name?.toLowerCase() || '')
            );
            if (resultTaskIndex >= 0) {
              newTasks[resultTaskIndex].status = event.data?.success ? 'completed' : 'failed';
            }
            break;
        }

        // Update state with new events and tasks
        setChatState(prev => ({
          ...prev,
          events: [...prev.events, ...newEvents.slice(prev.events.length)],
          tasks: newTasks.length > 0 ? newTasks : prev.tasks,
          conversationId: event.conversation_id || prev.conversationId,
        }));
      }

      // Add final assistant message
      if (assistantMessage) {
        const assistantMsg: ChatMessage = {
          role: 'assistant',
          content: assistantMessage,
          timestamp: Date.now(),
        };
        
        setChatState(prev => ({
          ...prev,
          messages: [...prev.messages, assistantMsg],
          isLoading: false,
        }));
      } else {
        setChatState(prev => ({ ...prev, isLoading: false }));
      }

    } catch (error) {
      console.error('Error sending message:', error);
      
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}`,
        timestamp: Date.now(),
      };
      
      setChatState(prev => ({
        ...prev,
        messages: [...prev.messages, errorMessage],
        isLoading: false,
      }));
    }
  };

  const handleClarificationResponse = async (response: string) => {
    if (!chatState.conversationId || !chatState.clarificationRequest) return;

    // Add user's clarification as a message
    const clarificationMessage: ChatMessage = {
      role: 'user',
      content: response,
      timestamp: Date.now(),
    };

    setChatState(prev => ({
      ...prev,
      messages: [...prev.messages, clarificationMessage],
      clarificationRequest: undefined,
      isLoading: true,
    }));

    try {
      // Send clarification and continue the conversation
      await chatService.current.sendClarification(
        chatState.conversationId,
        response,
        chatState.messages[chatState.messages.length - 1]?.content || ''
      );
      
      // The agent will continue processing, we might want to listen for more events here
      setChatState(prev => ({ ...prev, isLoading: false }));
      
    } catch (error) {
      console.error('Error sending clarification:', error);
      setChatState(prev => ({ ...prev, isLoading: false }));
    }
  };

  const handleClearChat = async () => {
    if (chatState.conversationId) {
      try {
        await chatService.current.clearConversation(chatState.conversationId);
      } catch (error) {
        console.error('Error clearing conversation:', error);
      }
    }
    
    setChatState({
      messages: [],
      events: [],
      tasks: [],
      isLoading: false,
    });
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-gray-900">IDP Copilot</h1>
          <button
            onClick={handleClearChat}
            className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
            title="Clear chat"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-hidden">
        <div className="h-full flex">
          {/* Chat area */}
          <div className="flex-1 flex flex-col">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4">
              {chatState.messages.length === 0 && (
                <div className="text-center text-gray-500 mt-8">
                  <h2 className="text-lg font-medium mb-2">Welcome to IDP Copilot!</h2>
                  <p>Ask me to create a new service and I'll guide you through the process.</p>
                  <p className="text-sm mt-2">Try: "Create a new Go service called user-api"</p>
                </div>
              )}
              
              {chatState.messages.map((message, index) => (
                <MessageBubble key={index} message={message} />
              ))}
              
              {chatState.isLoading && (
                <div className="flex justify-start mb-4">
                  <div className="bg-white text-gray-900 px-4 py-2 rounded-lg border border-gray-200 max-w-xs">
                    <div className="flex items-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-500"></div>
                      <span className="text-sm">Agent is thinking...</span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div className="border-t border-gray-200 bg-white p-4">
              <div className="flex gap-2">
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message here..."
                  className="flex-1 p-3 border border-gray-300 rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  rows={1}
                  disabled={chatState.isLoading}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!inputMessage.trim() || chatState.isLoading}
                  className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                >
                  <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {/* Sidebar */}
          <div className="w-80 bg-gray-50 border-l border-gray-200 p-4 overflow-y-auto">
            <TaskProgressComponent tasks={chatState.tasks} />
            <EventDisplay events={chatState.events} />
          </div>
        </div>
      </div>

      {/* Clarification Dialog */}
      {chatState.clarificationRequest && (
        <ClarificationDialog
          clarification={chatState.clarificationRequest}
          onResponse={handleClarificationResponse}
          onCancel={() => setChatState(prev => ({ ...prev, clarificationRequest: undefined }))}
        />
      )}
    </div>
  );
};