import React from 'react';
import type { AgentEvent } from '../types/chat';
import { 
  Brain, 
  Wrench, 
  CheckCircle, 
  AlertCircle, 
  MessageSquare, 
  HelpCircle,
  Settings
} from 'lucide-react';

interface EventDisplayProps {
  events: AgentEvent[];
}

export const EventDisplay: React.FC<EventDisplayProps> = ({ events }) => {
  if (events.length === 0) return null;

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'agent_thinking':
        return <Brain className="w-4 h-4 text-purple-500" />;
      case 'agent_tool_call':
        return <Wrench className="w-4 h-4 text-blue-500" />;
      case 'agent_tool_result':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'agent_clarification':
        return <HelpCircle className="w-4 h-4 text-yellow-500" />;
      case 'agent_message':
        return <MessageSquare className="w-4 h-4 text-gray-500" />;
      case 'agent_error':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      case 'agent_completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />;
      default:
        return <Settings className="w-4 h-4 text-gray-400" />;
    }
  };

  const getEventColor = (type: string) => {
    switch (type) {
      case 'agent_thinking':
        return 'bg-purple-50 border-purple-200 text-purple-800';
      case 'agent_tool_call':
        return 'bg-blue-50 border-blue-200 text-blue-800';
      case 'agent_tool_result':
        return 'bg-green-50 border-green-200 text-green-800';
      case 'agent_clarification':
        return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'agent_message':
        return 'bg-gray-50 border-gray-200 text-gray-800';
      case 'agent_error':
        return 'bg-red-50 border-red-200 text-red-800';
      case 'agent_completed':
        return 'bg-green-50 border-green-200 text-green-800';
      default:
        return 'bg-gray-50 border-gray-200 text-gray-600';
    }
  };

  const formatEventData = (event: AgentEvent) => {
    if (!event.data) return null;

    // Show specific data based on event type
    switch (event.type) {
      case 'agent_thinking':
        return event.data.reasoning ? (
          <div className="mt-1 text-xs opacity-75">
            Reasoning: {event.data.reasoning}
          </div>
        ) : null;
      
      case 'agent_tool_call':
        return (
          <div className="mt-1 text-xs opacity-75">
            Tool: {event.data.tool_name}
            {event.data.parameters && Object.keys(event.data.parameters).length > 0 && (
              <div>Params: {JSON.stringify(event.data.parameters, null, 2)}</div>
            )}
          </div>
        );
      
      case 'agent_tool_result':
        return (
          <div className="mt-1 text-xs opacity-75">
            {event.data.success ? '✓' : '✗'} {event.data.tool_name}
            {event.data.error && <div className="text-red-600">Error: {event.data.error}</div>}
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
      <h3 className="text-sm font-medium text-gray-900 mb-3">Agent Activity</h3>
      <div className="space-y-2 max-h-48 overflow-y-auto">
        {events.slice(-10).map((event, index) => (
          <div
            key={event.id || index}
            className={`flex items-start gap-2 p-2 rounded border ${getEventColor(event.type)}`}
          >
            {getEventIcon(event.type)}
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium truncate">
                {event.message}
              </div>
              {formatEventData(event)}
              <div className="text-xs opacity-50 mt-1">
                {new Date(event.timestamp * 1000).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};