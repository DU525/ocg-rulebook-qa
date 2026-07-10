import React, { useState, useEffect, useCallback } from 'react';

interface LoadingProgressBarProps {
  isLoading: boolean;
  duration?: number;
  color?: string;
  height?: string;
}

export const LoadingProgressBar: React.FC<LoadingProgressBarProps> = ({
  isLoading,
  duration = 3000,
  color = 'bg-gradient-to-r from-blue-500 to-purple-600',
  height = 'h-1',
}) => {
  const [progress, setProgress] = useState(0);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isLoading) {
      setIsVisible(true);
      setProgress(0);
      
      let startTime = Date.now();
      
      const animate = () => {
        const elapsed = Date.now() - startTime;
        const progressPercent = Math.min((elapsed / duration) * 90, 90);
        setProgress(progressPercent);
        
        if (elapsed < duration) {
          requestAnimationFrame(animate);
        }
      };
      
      requestAnimationFrame(animate);
    } else {
      setProgress(100);
      const timer = setTimeout(() => {
        setIsVisible(false);
        setProgress(0);
      }, 500);
      
      return () => clearTimeout(timer);
    }
  }, [isLoading, duration]);

  if (!isVisible) return null;

  return (
    <div className={`fixed top-0 left-0 right-0 z-50 ${height} bg-gray-200 dark:bg-gray-700`}>
      <div
        className={`h-full ${color} transition-all duration-150 ease-out shadow-lg`}
        style={{
          width: `${progress}%`,
          transformOrigin: 'left',
        }}
      >
        <div 
          className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-white/30 to-transparent"
          style={{
            animation: 'shimmer 1.5s infinite',
          }}
        />
      </div>
      
      {/* CSS 动画 */}
      <style>{`
        @keyframes shimmer {
          0% { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
      `}</style>
    </div>
  );
};

// Hook 用于管理全局加载状态
export const useGlobalLoading = () => {
  const [isLoading, setIsLoading] = useState(false);

  const startLoading = useCallback(() => setIsLoading(true), []);
  const stopLoading = useCallback(() => setIsLoading(false), []);

  return { isLoading, startLoading, stopLoading };
};
