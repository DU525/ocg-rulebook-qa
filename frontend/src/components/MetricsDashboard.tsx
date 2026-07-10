import { useEffect, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { metricsApi, alertApi, searchQualityApi } from '../services/api';
import type { TrendData, Alert, SearchQualityMetrics } from '../types';

interface MetricsDashboardProps {
  onRefresh?: () => void;
  isDm?: boolean;
}

export default function MetricsDashboard({ onRefresh, isDm = false }: MetricsDashboardProps = {}) {
  const { metrics } = useAppStore();
  const [trendData, setTrendData] = useState<TrendData[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [loading, setLoading] = useState(false);
  const [trendDays, setTrendDays] = useState(7);
  const [qualityData, setQualityData] = useState<SearchQualityMetrics | null>(null);

  const loadTrend = async (days: number = 7) => {
    setLoading(true);
    const response = await metricsApi.getTrend(days);
    if (response.success && response.data) {
      setTrendData(response.data.data);
    }
    setLoading(false);
  };

  const loadAlerts = async () => {
    const response = await alertApi.getUnread();
    if (response.success && response.data) {
      setAlerts(response.data);
    }
  };

  const loadQuality = async (days: number = 7) => {
    try {
      const response = await searchQualityApi.get(days);
      if (response.success && response.data) {
        setQualityData(response.data);
      }
    } catch (err) {
      console.error('加载质量数据失败:', err);
    }
  };

  useEffect(() => {
    loadTrend(trendDays);
    loadAlerts();
    loadQuality(trendDays);
  }, [trendDays]);

  const handleRefresh = () => {
    onRefresh?.();
    loadTrend(trendDays);
    loadAlerts();
    loadQuality(trendDays);
  };

  const handleMarkAsRead = async (alertId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setLoading(true);
    try {
      await alertApi.markRead(alertId);
      await loadAlerts();
      if (onRefresh) onRefresh();
    } catch (error) {
      console.error('标记已读失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const maxMessages = Math.max(...trendData.map(d => d.messages), 1);

  const cardBg = isDm ? 'bg-gray-800' : 'bg-gray-50';
  const textPrimary = isDm ? 'text-gray-100' : 'text-gray-700';
  const textSecondary = isDm ? 'text-gray-400' : 'text-gray-500';

  const dateOptions = [
    { value: 7, label: '7天' },
    { value: 14, label: '14天' },
    { value: 30, label: '30天' },
  ];

  const totalDistribution = qualityData?.response_distribution
    ? qualityData.response_distribution.fast + qualityData.response_distribution.medium + qualityData.response_distribution.slow
    : 0;

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <div />
        <button
          onClick={handleRefresh}
          disabled={loading}
          className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg hover:opacity-80 disabled:opacity-50 ${
            isDm ? 'bg-gray-700 text-gray-200 hover:bg-gray-600' : 'bg-primary-50 text-primary-600 hover:bg-primary-100'
          }`}
        >
          <svg className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          刷新
        </button>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-primary-50 rounded-lg p-3">
          <p className="text-xs text-primary-600">知识库</p>
          <p className="text-xl font-bold text-primary-700">
            {metrics?.knowledgeBaseSize || 0}
          </p>
          <p className="text-xs text-primary-500">文档块</p>
        </div>

        <div className="bg-green-50 rounded-lg p-3">
          <p className="text-xs text-green-600">总对话数</p>
          <p className="text-xl font-bold text-green-700">
            {metrics?.totalConversations || 0}
          </p>
        </div>

        <div className="bg-blue-50 rounded-lg p-3">
          <p className="text-xs text-blue-600">今日消息</p>
          <p className="text-xl font-bold text-blue-700">
            {metrics?.messagesToday || 0}
          </p>
        </div>

        <div className="bg-purple-50 rounded-lg p-3">
          <p className="text-xs text-purple-600">本周对话</p>
          <p className="text-xl font-bold text-purple-700">
            {metrics?.conversationsThisWeek || 0}
          </p>
        </div>
      </div>

      <div className="bg-orange-50 rounded-lg p-3">
        <p className="text-xs text-orange-600">平均响应时间</p>
        <p className="text-xl font-bold text-orange-700">
          {metrics?.avgResponseTimeMs || 0}
          <span className="text-sm font-normal ml-1">ms</span>
        </p>
      </div>

      <div className={`${cardBg} rounded-lg p-3`}>
        <div className="flex items-center justify-between mb-3">
          <p className={`text-sm font-medium ${textPrimary}`}>趋势</p>
          <div className="flex gap-1">
            {dateOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTrendDays(opt.value)}
                className={`px-2 py-0.5 text-xs rounded transition-colors ${
                  trendDays === opt.value
                    ? (isDm ? 'bg-indigo-600 text-white' : 'bg-primary-500 text-white')
                    : (isDm ? 'bg-gray-700 text-gray-300 hover:bg-gray-600' : 'bg-gray-100 text-gray-500 hover:bg-gray-200')
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        {trendData.length > 0 ? (
          <div className="flex items-end gap-1 h-24">
            {trendData.map((item, index) => (
              <div key={index} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className={`w-full rounded-t transition-all ${isDm ? 'bg-blue-600 hover:bg-blue-500' : 'bg-blue-400 hover:bg-blue-500'}`}
                  style={{ height: `${Math.max((item.messages / maxMessages) * 80, 4)}px` }}
                  title={`${item.date}: ${item.messages} 条消息`}
                />
                <span className={`text-xs ${textSecondary} transform -rotate-45 origin-center whitespace-nowrap`}>
                  {item.date.slice(5)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="h-24 flex items-center justify-center text-gray-400 text-sm">
            {loading ? '加载中...' : '暂无数据'}
          </div>
        )}
      </div>

      {qualityData && (
        <div className="space-y-4">
          <div className={`${cardBg} rounded-lg p-3`}>
            <p className={`text-sm font-medium ${textPrimary} mb-3`}>检索质量</p>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs ${textSecondary}`}>好评率</span>
                  <span className={`text-xs font-bold ${qualityData.positive_rate >= 0.7 ? 'text-green-500' : qualityData.positive_rate >= 0.4 ? 'text-yellow-500' : 'text-red-500'}`}>
                    {(qualityData.positive_rate * 100).toFixed(0)}%
                  </span>
                </div>
                <div className={`w-full h-2 rounded-full ${isDm ? 'bg-gray-700' : 'bg-gray-200'}`}>
                  <div
                    className={`h-2 rounded-full transition-all ${qualityData.positive_rate >= 0.7 ? 'bg-green-500' : qualityData.positive_rate >= 0.4 ? 'bg-yellow-500' : 'bg-red-500'}`}
                    style={{ width: `${qualityData.positive_rate * 100}%` }}
                  />
                </div>
                <div className="flex justify-between mt-1">
                  <span className={`text-xs ${textSecondary}`}>好评 {qualityData.positive_count}</span>
                  <span className={`text-xs ${textSecondary}`}>差评 {qualityData.negative_count}</span>
                </div>
              </div>

              {qualityData.daily_quality && qualityData.daily_quality.length > 0 && (
                <div>
                  <p className={`text-xs ${textSecondary} mb-2`}>每日质量趋势</p>
                  <div className="flex items-end gap-1 h-16">
                    {qualityData.daily_quality.map((item, index) => {
                      const total = item.positive + item.negative;
                      const maxBar = Math.max(...qualityData.daily_quality.map(d => d.positive + d.negative), 1);
                      const height = total > 0 ? Math.max((total / maxBar) * 60, 2) : 0;
                      const posHeight = total > 0 ? (item.positive / total) * height : 0;
                      return (
                        <div key={index} className="flex-1 flex flex-col items-center gap-0.5">
                          <div className="w-full relative" style={{ height: `${height}px` }}>
                            <div className="absolute bottom-0 w-full bg-green-400 rounded-t-sm" style={{ height: `${posHeight}px` }} />
                            <div className="absolute bottom-0 w-full bg-red-400 rounded-b-sm opacity-60" style={{ height: `${height - posHeight}px` }} />
                          </div>
                          <span className={`text-xs ${textSecondary}`} style={{ fontSize: '0.5rem' }}>
                            {item.date.slice(5)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="flex items-center gap-1 text-xs">
                      <span className="w-2 h-2 rounded-sm bg-green-400" />
                      <span className={textSecondary}>好评</span>
                    </span>
                    <span className="flex items-center gap-1 text-xs">
                      <span className="w-2 h-2 rounded-sm bg-red-400 opacity-60" />
                      <span className={textSecondary}>差评</span>
                    </span>
                  </div>
                </div>
              )}

              {qualityData.top_negative_reasons && qualityData.top_negative_reasons.length > 0 && (
                <div>
                  <p className={`text-xs ${textSecondary} mb-2`}>差评原因 Top {qualityData.top_negative_reasons.length}</p>
                  <div className="space-y-1.5">
                    {qualityData.top_negative_reasons.map((item, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <span className={`w-4 h-4 rounded text-xs flex items-center justify-center font-medium ${
                          isDm ? 'bg-red-900/50 text-red-300' : 'bg-red-100 text-red-600'
                        }`}>
                          {index + 1}
                        </span>
                        <span className={`flex-1 text-xs truncate ${textPrimary}`}>{item.reason}</span>
                        <span className={`text-xs ${textSecondary}`}>{item.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className={`${cardBg} rounded-lg p-3`}>
            <p className={`text-sm font-medium ${textPrimary} mb-3`}>模型性能</p>
            <div className="space-y-3">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className={`text-xs ${textSecondary}`}>平均响应时间</span>
                  <span className={`text-xs font-mono ${textPrimary}`}>{qualityData.avg_response_time_ms} ms</span>
                </div>
              </div>

              {totalDistribution > 0 && (
                <div>
                  <p className={`text-xs ${textSecondary} mb-2`}>响应时间分布</p>
                  <div className="space-y-2">
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className={`text-xs ${textSecondary}`}>快速 (&lt;1s)</span>
                        <span className={`text-xs font-mono ${textPrimary}`}>{qualityData.response_distribution.fast}</span>
                      </div>
                      <div className={`w-full h-1.5 rounded-full ${isDm ? 'bg-gray-700' : 'bg-gray-200'}`}>
                        <div
                          className="h-1.5 rounded-full bg-green-500 transition-all"
                          style={{ width: `${(qualityData.response_distribution.fast / totalDistribution) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className={`text-xs ${textSecondary}`}>中等 (1-3s)</span>
                        <span className={`text-xs font-mono ${textPrimary}`}>{qualityData.response_distribution.medium}</span>
                      </div>
                      <div className={`w-full h-1.5 rounded-full ${isDm ? 'bg-gray-700' : 'bg-gray-200'}`}>
                        <div
                          className="h-1.5 rounded-full bg-yellow-500 transition-all"
                          style={{ width: `${(qualityData.response_distribution.medium / totalDistribution) * 100}%` }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-0.5">
                        <span className={`text-xs ${textSecondary}`}>慢速 (&gt;3s)</span>
                        <span className={`text-xs font-mono ${textPrimary}`}>{qualityData.response_distribution.slow}</span>
                      </div>
                      <div className={`w-full h-1.5 rounded-full ${isDm ? 'bg-gray-700' : 'bg-gray-200'}`}>
                        <div
                          className="h-1.5 rounded-full bg-red-500 transition-all"
                          style={{ width: `${(qualityData.response_distribution.slow / totalDistribution) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {totalDistribution === 0 && (
                <p className={`text-xs ${textSecondary} text-center py-2`}>暂无性能数据</p>
              )}
            </div>
          </div>
        </div>
      )}

      <div className={`${cardBg} rounded-lg p-3`}>
        <p className={`text-sm font-medium ${textPrimary} mb-3`}>热词 Top 10</p>
        {metrics?.topKeywords && metrics.topKeywords.length > 0 ? (
          <div className="space-y-2">
            {metrics.topKeywords.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <span className={`w-5 h-5 rounded text-xs flex items-center justify-center font-medium ${
                  index < 3 ? 'bg-red-100 text-red-600' : 'bg-gray-200 text-gray-600'
                }`}>
                  {index + 1}
                </span>
                <span className={`flex-1 text-sm ${textPrimary}`}>{item.keyword}</span>
                <span className={`text-xs ${textSecondary}`}>{item.count}次</span>
              </div>
            ))}
          </div>
        ) : (
          <div className={`text-center ${textSecondary} text-sm py-4`}>
            暂无热词数据
          </div>
        )}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className={`text-sm font-medium ${textPrimary} flex items-center gap-2`}>
            <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            告警 ({alerts.length})
          </h3>
          <button
            onClick={loadAlerts}
            className={`text-xs ${textSecondary} hover:${textPrimary}`}
          >
            刷新
          </button>
        </div>

        {alerts.length === 0 ? (
          <div className={`${isDm ? 'bg-green-900/30 border border-green-700' : 'bg-green-50 border border-green-200'} rounded-lg p-4 text-center`}>
            <svg className={`w-8 h-8 mx-auto mb-2 ${isDm ? 'text-green-400' : 'text-green-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className={`text-sm ${isDm ? 'text-green-400' : 'text-green-600'}`}>暂无未读告警</p>
          </div>
        ) : (
          <div className="space-y-2">
            {alerts.map(alert => (
              <div
                key={alert.id}
                onClick={() => setSelectedAlert(selectedAlert?.id === alert.id ? null : alert)}
                className={`${isDm ? 'bg-red-900/30 border border-red-700' : 'bg-red-50 border border-red-200'} rounded-lg p-3 cursor-pointer hover:${isDm ? 'bg-red-900/50' : 'bg-red-100'} transition-colors`}
              >
                <div className="flex items-start gap-3">
                  <div className="text-red-500 mt-0.5">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-sm font-medium line-clamp-2 ${isDm ? 'text-red-300' : 'text-red-800'}`}>
                      {alert.message}
                    </p>
                    <p className={`text-xs ${isDm ? 'text-red-400' : 'text-red-500'} mt-1`}>
                      {formatTime(alert.createdAt)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleMarkAsRead(alert.id, e)}
                    disabled={loading}
                    className={`px-2 py-1 text-xs rounded disabled:opacity-50 ${
                      isDm ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-red-500 text-white hover:bg-red-600'
                    }`}
                  >
                    已读
                  </button>
                </div>

                {selectedAlert?.id === alert.id && (
                  <div className={`mt-3 pt-3 border-t ${isDm ? 'border-red-700 text-red-300' : 'border-red-200 text-red-600'}`}>
                    <div className="text-xs space-y-1">
                      <p><span className="font-medium">规则类型：</span>{alert.ruleType}</p>
                      <p><span className="font-medium">创建时间：</span>{formatTime(alert.createdAt)}</p>
                    </div>
                    <button
                      onClick={(e) => handleMarkAsRead(alert.id, e)}
                      disabled={loading}
                      className={`mt-2 w-full px-3 py-1.5 text-xs rounded disabled:opacity-50 ${
                        isDm ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-red-500 text-white hover:bg-red-600'
                      }`}
                    >
                      确认已读
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
