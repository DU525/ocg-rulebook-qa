import React from 'react';

// 卡片骨架屏
export const CardSkeleton: React.FC = () => {
  return (
    <div className="animate-pulse">
      <div className="bg-gray-200 rounded-lg p-4 space-y-4">
        <div className="h-4 bg-gray-300 rounded w-3/4"></div>
        <div className="h-4 bg-gray-300 rounded w-1/2"></div>
        <div className="space-y-2">
          <div className="h-3 bg-gray-300 rounded w-full"></div>
          <div className="h-3 bg-gray-300 rounded w-5/6"></div>
          <div className="h-3 bg-gray-300 rounded w-4/6"></div>
        </div>
      </div>
    </div>
  );
};

// 消息气泡骨架屏
export const MessageSkeleton: React.FC = () => {
  return (
    <div className="animate-pulse space-y-4">
      <div className="flex items-start space-x-3">
        <div className="flex-shrink-0 w-10 h-10 bg-gray-300 rounded-xl"></div>
        <div className="flex-1 space-y-2">
          <div className="h-4 bg-gray-300 rounded w-1/4"></div>
          <div className="h-24 bg-gray-300 rounded-lg"></div>
        </div>
      </div>
      
      <div className="flex items-start space-x-3 flex-row-reverse">
        <div className="flex-shrink-0 w-10 h-10 bg-blue-400 rounded-xl"></div>
        <div className="flex-1 space-y-2">
          <div className="h-20 bg-blue-200 rounded-lg"></div>
        </div>
      </div>
    </div>
  );
};

// 欢迎页面骨架屏
export const WelcomeSkeleton: React.FC = () => {
  return (
    <div className="animate-pulse min-h-screen flex items-center justify-center">
      <div className="text-center space-y-8">
        <div className="w-24 h-24 bg-gradient-to-br from-gray-300 to-gray-400 rounded-2xl mx-auto"></div>
        
        <div className="space-y-4">
          <div className="h-8 bg-gray-300 rounded w-64 mx-auto"></div>
          <div className="h-4 bg-gray-300 rounded w-80 mx-auto"></div>
          <div className="h-4 bg-gray-300 rounded w-72 mx-auto"></div>
        </div>
        
        <div className="space-y-3 pt-8">
          <div className="h-10 bg-gray-300 rounded-lg w-64 mx-auto"></div>
          <div className="h-10 bg-gray-300 rounded-lg w-56 mx-auto"></div>
        </div>
      </div>
    </div>
  );
};

// 列表骨架屏
export const ListSkeleton: React.FC<{ count?: number }> = ({ count = 5 }) => {
  return (
    <div className="space-y-3">
      {[...Array(count)].map((_, index) => (
        <div key={index} className="animate-pulse">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gray-300 rounded-full"></div>
              <div className="flex-1 space-y-2">
                <div className="h-4 bg-gray-300 rounded w-1/2"></div>
                <div className="h-3 bg-gray-300 rounded w-3/4"></div>
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

// 按钮骨架屏
export const ButtonSkeleton: React.FC<{ width?: string }> = ({ width = 'w-32' }) => {
  return (
    <div className={`animate-pulse h-10 ${width} bg-gray-300 rounded-lg`}></div>
  );
};

// 输入框骨架屏
export const InputSkeleton: React.FC = () => {
  return (
    <div className="animate-pulse">
      <div className="h-12 bg-gray-300 rounded-lg border border-gray-200"></div>
    </div>
  );
};

export default {
  CardSkeleton,
  MessageSkeleton,
  WelcomeSkeleton,
  ListSkeleton,
  ButtonSkeleton,
  InputSkeleton
};
