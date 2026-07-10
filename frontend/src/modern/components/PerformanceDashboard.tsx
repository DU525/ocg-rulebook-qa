import React, { useState, useEffect, useCallback } from 'react';
import { FiActivity, FiRefreshCw, FiTrash2, FiInfo } from 'react-icons/fi';
import { getWebVitalsMonitor } from '../services/webVitalsMonitor';

interface MetricCardProps {
  name: string;
  value: number | null | undefined;
  unit: string;
  status: 'good' | 'needs-improvement' | 'poor' | 'unknown';
  description: string;
  goodThreshold: number;
  poorThreshold: number;
}

const MetricCard: React.FC<MetricCardProps> = ({
  name,
  value,
  unit,
  status,
  description,
  goodThreshold,
  poorThreshold,
}) => {
  const getStatusColor = () => {
    switch (status) {
      case 'good':
        return 'bg-green-100 text-green-800 border-green-300';
      case 'needs-improvement':
        return 'bg-yellow-100 text-yellow-800 border-yellow-300';
      case 'poor':
        return 'bg-red-100 text-red-800 border-red-300';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-300';
    }
  };

  const getProgressWidth = () => {
    if (value == null) return '0%';
    if (value <= goodThreshold) return '100%';
    if (value <= poorThreshold) return '50%';
    return '25%';
  };

  return (
    <div className={`p-4 rounded-lg border-2 transition-all duration-300 ${getStatusColor()}`}>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm">{name}</h3>
        <span className={`text-xs px-2 py-1 rounded-full ${
          status === 'good' ? 'bg-green-200' :
          status === 'needs-improvement' ? 'bg-yellow-200' :
          status === 'poor' ? 'bg-red-200' : 'bg-gray-200'
        }`}>
          {status === 'good' ? '优秀' :
           status === 'needs-improvement' ? '需改进' :
           status === 'poor' ? '较差' : '未知'}
        </span>
      </div>
      
      <div className="text-2xl font-bold mb-2">
        {value != null ? `${value.toFixed(1)} ${unit}` : '--'}
      </div>
      
      <div className="h-2 bg-gray-300 rounded-full mb-2 overflow-hidden">
        <div 
          className={`h-full transition-all duration-500 ${
            status === 'good' ? 'bg-green-500' :
            status === 'needs-improvement' ? 'bg-yellow-500' :
            status === 'poor' ? 'bg-red-500' : 'bg-gray-500'
          }`}
          style={{ width: getProgressWidth() }}
        />
      </div>
      
      <p className="text-xs opacity-75">{description}</p>
    </div>
  );
};

export const PerformanceDashboard: React.FC = () => {
  const [isVisible, setIsVisible] = useState(false);
  const [metrics, setMetrics] = useState(getWebVitalsMonitor().getMetrics());
  const [score, setScore] = useState(getWebVitalsMonitor().getScore());

  useEffect(() => {
    const monitor = getWebVitalsMonitor();
    
    const updateCallback = (newMetrics: any) => {
      setMetrics(newMetrics);
      setScore(monitor.getScore());
    };
    
    monitor.setMetricUpdateCallback(updateCallback);
    
    return () => {
      monitor.setMetricUpdateCallback(null);
    };
  }, []);

  const handleReset = useCallback(() => {
    const monitor = getWebVitalsMonitor();
    monitor.reset();
    setMetrics(monitor.getMetrics());
    setScore(monitor.getScore());
  }, []);

  const metricsConfig = [
    {
      key: 'lcp' as const,
      name: 'LCP (最大内容渲染)',
      unit: 'ms',
      description: '页面内容加载速度',
      goodThreshold: 2500,
      poorThreshold: 4000,
    },
    {
      key: 'fcp' as const,
      name: 'FCP (首次内容渲染)',
      unit: 'ms',
      description: '首次可见内容出现时间',
      goodThreshold: 1800,
      poorThreshold: 3000,
    },
    {
      key: 'cls' as const,
      name: 'CLS (累积布局偏移)',
      unit: '',
      description: '页面布局稳定性',
      goodThreshold: 0.1,
      poorThreshold: 0.25,
    },
    {
      key: 'inp' as const,
      name: 'INP (交互响应)',
      unit: 'ms',
      description: '用户交互响应速度',
      goodThreshold: 200,
      poorThreshold: 500,
    },
    {
      key: 'ttfb' as const,
      name: 'TTFB (首字节时间)',
      unit: 'ms',
      description: '服务器响应速度',
      goodThreshold: 800,
      poorThreshold: 1800,
    },
  ];

  const getScoreColor = (scoreValue: number) => {
    if (scoreValue >= 90) return 'text-green-600';
    if (scoreValue >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <>
      {/* 浮动按钮 */}
      <button
        onClick={() => setIsVisible(!isVisible)}
        className="fixed bottom-4 right-4 z-50 bg-gradient-to-r from-blue-500 to-purple-600 text-white p-3 rounded-full shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105"
        title="性能仪表板"
      >
        <FiActivity className="w-6 h-6" />
      </button>

      {/* 仪表板弹窗 */}
      {isVisible && (
        <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center sm:justify-center">
          {/* 背景遮罩 */}
          <div 
            className="absolute inset-0 bg-black/50"
            onClick={() => setIsVisible(false)}
          />
          
          {/* 面板内容 */}
          <div className="relative bg-white dark:bg-gray-800 rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-4xl sm:max-h-[80vh] overflow-hidden animate-slide-up">
            {/* 头部 */}
            <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/30 dark:to-purple-900/30">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-2 rounded-lg">
                    <FiActivity className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">性能仪表板</h2>
                    <p className="text-sm text-gray-600 dark:text-gray-400">监控应用性能指标</p>
                  </div>
                </div>
                <button
                  onClick={() => setIsVisible(false)}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              {/* 总分 */}
              <div className="flex items-center gap-6">
                <div className="text-center">
                  <div className="text-5xl font-bold mb-1">
                    <span className={getScoreColor(score.overall)}>{score.overall}</span>
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">总得分</div>
                </div>
                
                <div className="flex-1" />
                
                <div className="flex gap-2">
                  <button
                    onClick={handleReset}
                    className="flex items-center gap-2 px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg transition-colors"
                  >
                    <FiTrash2 className="w-4 h-4" />
                    重置
                  </button>
                  <button
                    onClick={() => {
                      setMetrics(getWebVitalsMonitor().getMetrics());
                      setScore(getWebVitalsMonitor().getScore());
                    }}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-100 hover:bg-blue-200 text-blue-700 rounded-lg transition-colors"
                  >
                    <FiRefreshCw className="w-4 h-4" />
                    刷新
                  </button>
                </div>
              </div>
            </div>
            
            {/* 指标网格 */}
            <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[60vh] overflow-y-auto">
              {metricsConfig.map((config) => (
                <MetricCard
                  key={config.key}
                  name={config.name}
                  value={metrics[config.key]}
                  unit={config.unit}
                  status={score.metrics[config.key] || 'unknown'}
                  description={config.description}
                  goodThreshold={config.goodThreshold}
                  poorThreshold={config.poorThreshold}
                />
              ))}
            </div>
            
            {/* 底部信息 */}
            <div className="p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900">
              <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <FiInfo className="w-4 h-4" />
                <span>数据会在浏览器会话期间保存，关闭浏览器后重置</span>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {/* 动画样式 */}
      <style>{`
        @keyframes slide-up {
          from {
            transform: translateY(100%);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }
        .animate-slide-up {
          animation: slide-up 0.3s ease-out;
        }
      `}</style>
    </>
  );
};
