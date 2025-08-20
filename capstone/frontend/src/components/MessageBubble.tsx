import React from 'react';
import type { ChatMessage } from '../types/chat';
import { User, Bot, Settings } from 'lucide-react';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  const getIcon = () => {
    if (isUser) return <User className="w-4 h-4" />;
    if (isSystem) return <Settings className="w-4 h-4" />;
    return <Bot className="w-4 h-4" />;
  };

  const getBubbleClasses = () => {
    if (isUser) {
      return 'bg-blue-500 text-white ml-auto';
    }
    if (isSystem) {
      return 'bg-gray-200 text-gray-800 mx-auto';
    }
    return 'bg-white text-gray-900 mr-auto border border-gray-200';
  };

  const getContainerClasses = () => {
    if (isUser) return 'flex justify-end';
    if (isSystem) return 'flex justify-center';
    return 'flex justify-start';
  };

  return (
    <div className={`mb-4 ${getContainerClasses()}`}>
      <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg shadow-sm ${getBubbleClasses()}`}>
        <div className="flex items-center gap-2 mb-1">
          {getIcon()}
          <span className="text-xs font-medium capitalize">
            {message.role}
          </span>
          {message.timestamp && (
            <span className="text-xs opacity-75">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="text-sm whitespace-pre-wrap">
          {message.content}
        </div>
      </div>
    </div>
  );
};