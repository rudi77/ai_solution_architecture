import React, { useState } from 'react';
import type { ClarificationRequest } from '../types/chat';
import { HelpCircle, Send } from 'lucide-react';

interface ClarificationDialogProps {
  clarification: ClarificationRequest;
  onResponse: (response: string) => void;
  onCancel: () => void;
}

export const ClarificationDialog: React.FC<ClarificationDialogProps> = ({
  clarification,
  onResponse,
  onCancel,
}) => {
  const [response, setResponse] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (response.trim()) {
      onResponse(response.trim());
      setResponse('');
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-md w-full p-6">
        <div className="flex items-center gap-2 mb-4">
          <HelpCircle className="w-5 h-5 text-blue-500" />
          <h3 className="text-lg font-medium text-gray-900">
            Additional Information Needed
          </h3>
        </div>
        
        <div className="mb-4">
          <p className="text-gray-700 mb-3">{clarification.question}</p>
          
          {clarification.required_fields.length > 0 && (
            <div className="mb-3">
              <p className="text-sm font-medium text-gray-900 mb-1">
                Required fields:
              </p>
              <ul className="text-sm text-gray-600 list-disc list-inside">
                {clarification.required_fields.map((field, index) => (
                  <li key={index}>{field.replace('_', ' ')}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            placeholder="Please provide the missing information..."
            className="w-full p-3 border border-gray-300 rounded-md resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows={3}
            autoFocus
          />
          
          <div className="flex gap-2 justify-end">
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!response.trim()}
              className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Send className="w-4 h-4" />
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};