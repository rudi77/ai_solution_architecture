import React from 'react';
import type { TaskProgress as TaskProgressType } from '../types/chat';
import { CheckCircle, Clock, AlertCircle, Loader } from 'lucide-react';

interface TaskProgressProps {
  tasks: TaskProgressType[];
}

export const TaskProgress: React.FC<TaskProgressProps> = ({ tasks }) => {
  if (tasks.length === 0) return null;

  const getStatusIcon = (status: TaskProgressType['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'in_progress':
        return <Loader className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'failed':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  const getStatusColor = (status: TaskProgressType['status']) => {
    switch (status) {
      case 'completed':
        return 'text-green-700 bg-green-50 border-green-200';
      case 'in_progress':
        return 'text-blue-700 bg-blue-50 border-blue-200';
      case 'failed':
        return 'text-red-700 bg-red-50 border-red-200';
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200';
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4 mb-4">
      <h3 className="text-sm font-medium text-gray-900 mb-3">Task Progress</h3>
      <div className="space-y-2">
        {tasks.map((task) => (
          <div
            key={task.id}
            className={`flex items-center gap-3 p-2 rounded border ${getStatusColor(task.status)}`}
          >
            {getStatusIcon(task.status)}
            <span className="text-sm font-medium">{task.title}</span>
            <span className="text-xs capitalize ml-auto">
              {task.status.replace('_', ' ')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};