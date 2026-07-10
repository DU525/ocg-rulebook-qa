import { useState, useEffect, useCallback } from 'react';
import { 
  FiDatabase, FiRefreshCw, FiActivity, FiClock, FiCheckCircle, 
  FiAlertCircle, FiPlay, FiSquare, FiTrendingUp, FiServer,
  FiSettings, FiCode, FiTerminal, FiList, FiCalendar, FiArrowLeft
} from 'react-icons/fi';
import maintenanceApiService, { 
  MaintenanceStatus, DataSource, Task, CardInfo, SyncVersion
} from '../services/maintenanceApi';

interface MaintenanceDashboardProps {
  gameType?: 'ocg' | 'dm';
  onBack?: () => void;
}

type TabType = 'overview' | 'sources' | 'tasks' | 'cards' | 'versions';

const MaintenanceDashboard: React.FC<MaintenanceDashboardProps> = ({ onBack }) => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [status, setStatus] = useState<MaintenanceStatus | null>(null);
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [cards, setCards] = useState<CardInfo[]>([]);
  const [versions, setVersions] = useState<SyncVersion[]>([]);
  const [loading, setLoading] = useState<Record<string, boolean>>({
    status: false,
    sources: false,
    tasks: false,
    cards: false,
    versions: false
  });
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' } | null>(null);
  
  const showMessage = useCallback((text: string, type: 'success' | 'error' | 'info' = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  }, []);

  const loadStatus = useCallback(async () => {
    setLoading(p => ({ ...p, status: true }));
    try {
      const data = await maintenanceApiService.getStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to load status:', err);
    } finally {
      setLoading(p => ({ ...p, status: false }));
    }
  }, []);

  const loadDataSources = useCallback(async () => {
    setLoading(p => ({ ...p, sources: true }));
    try {
      const data = await maintenanceApiService.getDataSources();
      setDataSources(data.sources);
    } catch (err) {
      console.error('Failed to load data sources:', err);
    } finally {
      setLoading(p => ({ ...p, sources: false }));
    }
  }, []);

  const loadTasks = useCallback(async () => {
    setLoading(p => ({ ...p, tasks: true }));
    try {
      const data = await maintenanceApiService.getTaskHistory(20);
      setTasks(data.tasks);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    } finally {
      setLoading(p => ({ ...p, tasks: false }));
    }
  }, []);

  const loadCards = useCallback(async () => {
    setLoading(p => ({ ...p, cards: true }));
    try {
      const data = await maintenanceApiService.getCards(50, 0);
      setCards(data.cards);
    } catch (err) {
      console.error('Failed to load cards:', err);
    } finally {
      setLoading(p => ({ ...p, cards: false }));
    }
  }, []);

  const loadVersions = useCallback(async () => {
    setLoading(p => ({ ...p, versions: true }));
    try {
      const data = await maintenanceApiService.getVersions(10);
      setVersions(data.versions);
    } catch (err) {
      console.error('Failed to load versions:', err);
    } finally {
      setLoading(p => ({ ...p, versions: false }));
    }
  }, []);

  const triggerSync = useCallback(async (type: 'full' | 'incremental' | 'emergency') => {
    try {
      const result = await maintenanceApiService.triggerSync({ sync_type: type });
      showMessage(`${result.message} (任务ID: ${result.task_id})`, 'success');
      loadStatus();
      loadTasks();
    } catch (err: any) {
      showMessage(err.response?.data?.error || '触发同步失败', 'error');
    }
  }, [loadStatus, loadTasks, showMessage]);

  const handleSchedulerControl = useCallback(async (action: 'start' | 'stop') => {
    try {
      const result = action === 'start' 
        ? await maintenanceApiService.startScheduler()
        : await maintenanceApiService.stopScheduler();
      showMessage(result.message, 'success');
      loadStatus();
    } catch (err: any) {
      showMessage(err.response?.data?.error || '操作失败', 'error');
    }
  }, [loadStatus, showMessage]);

  const handleCheckSourceHealth = useCallback(async (sourceId: string) => {
    try {
      await maintenanceApiService.checkSourceHealth(sourceId);
      showMessage('健康检查完成', 'success');
      loadDataSources();
      loadStatus();
    } catch (err: any) {
      showMessage(err.response?.data?.error || '检查失败', 'error');
    }
  }, [loadDataSources, loadStatus, showMessage]);

  useEffect(() => {
    loadStatus();
    if (activeTab === 'sources') loadDataSources();
    if (activeTab === 'tasks') loadTasks();
    if (activeTab === 'cards') loadCards();
    if (activeTab === 'versions') loadVersions();
  }, [activeTab]);

  useEffect(() => {
    const interval = setInterval(() => {
      loadStatus();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy': return 'text-green-600 bg-green-100';
      case 'degraded': return 'text-yellow-600 bg-yellow-100';
      case 'unhealthy': return 'text-red-600 bg-red-100';
      case 'running': return 'text-blue-600 bg-blue-100';
      case 'success': return 'text-green-600 bg-green-100';
      case 'failed': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy': case 'success': return <FiCheckCircle />;
      case 'degraded': case 'unhealthy': case 'failed': return <FiAlertCircle />;
      case 'running': return <FiActivity />;
      default: return <FiClock />;
    }
  };

  const formatTime = (timeStr: string | null) => {
    if (!timeStr) return '-';
    return new Date(timeStr).toLocaleString('zh-CN');
  };

  return (
    <div className="h-full bg-gray-50 overflow-hidden flex flex-col">
      {message && (
        <div className={`p-4 border-b ${message.type === 'success' ? 'bg-green-50 border-green-200' : message.type === 'error' ? 'bg-red-50 border-red-200' : 'bg-blue-50 border-blue-200'}`}>
          <div className="flex items-center justify-between">
            <span className={message.type === 'success' ? 'text-green-800' : message.type === 'error' ? 'text-red-800' : 'text-blue-800'}>
              {message.text}
            </span>
            <button onClick={() => setMessage(null)} className="text-gray-500 hover:text-gray-700">×</button>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6">
          <div className="mb-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {onBack && (
                  <button
                    onClick={onBack}
                    className="p-2 rounded-lg bg-white shadow hover:bg-gray-50 text-gray-600"
                  >
                    <FiArrowLeft className="w-5 h-5" />
                  </button>
                )}
                <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
                  <FiDatabase className="text-blue-600" />
                  维护系统
                </h1>
              </div>
              <div className="flex gap-2">
                {status?.is_running && (
                  <button
                    onClick={() => handleSchedulerControl('stop')}
                    className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                  >
                    <FiSquare />
                    停止调度器
                  </button>
                )}
                {!status?.is_running && (
                  <button
                    onClick={() => handleSchedulerControl('start')}
                    className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
                  >
                    <FiPlay />
                    启动调度器
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">调度器状态</span>
                  <FiActivity className="text-blue-600" />
                </div>
                <div className="text-2xl font-bold">
                  {loading.status ? (
                    <span className="animate-pulse">...</span>
                  ) : (
                    <span className={status?.scheduler_status === 'running' ? 'text-green-600' : 'text-gray-500'}>
                      {status?.scheduler_status === 'running' ? '运行中' : '已停止'}
                    </span>
                  )}
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">健康源</span>
                  <FiCheckCircle className="text-green-600" />
                </div>
                <div className="text-2xl font-bold">
                  {loading.status ? (
                    <span className="animate-pulse">...</span>
                  ) : (
                    <span>{status?.data_source_health.healthy_sources}/{status?.data_source_health.total_sources}</span>
                  )}
                </div>
                <div className="text-xs text-gray-500">
                  健康率: {status?.data_source_health.health_rate.toFixed(0)}%
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">卡片数量</span>
                  <FiList className="text-purple-600" />
                </div>
                <div className="text-2xl font-bold">
                  {loading.status ? (
                    <span className="animate-pulse">...</span>
                  ) : (
                    <span>{status?.cards_in_kb.toLocaleString()}</span>
                  )}
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-600">活动任务</span>
                  <FiClock className="text-orange-600" />
                </div>
                <div className="text-2xl font-bold">
                  {loading.status ? (
                    <span className="animate-pulse">...</span>
                  ) : (
                    <span>{status?.active_tasks}</span>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-4 mb-6">
              <h3 className="font-semibold mb-3 text-gray-800">快速操作</h3>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => triggerSync('incremental')}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"
                >
                  <FiRefreshCw />
                  增量同步
                </button>
                <button
                  onClick={() => triggerSync('full')}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 flex items-center gap-2"
                >
                  <FiRefreshCw />
                  全量同步
                </button>
                <button
                  onClick={() => triggerSync('emergency')}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 flex items-center gap-2"
                >
                  <FiAlertCircle />
                  紧急更新
                </button>
                <button
                  onClick={() => { loadStatus(); if (activeTab === 'sources') loadDataSources(); if (activeTab === 'tasks') loadTasks(); }}
                  className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 flex items-center gap-2"
                >
                  <FiRefreshCw />
                  刷新
                </button>
              </div>
            </div>
          </div>

          <div className="border-b border-gray-200 mb-6">
            <nav className="flex gap-6">
              {[
                { id: 'overview' as TabType, label: '概览', icon: <FiTrendingUp /> },
                { id: 'sources' as TabType, label: '数据源', icon: <FiServer /> },
                { id: 'tasks' as TabType, label: '任务历史', icon: <FiCalendar /> },
                { id: 'cards' as TabType, label: '卡片库', icon: <FiDatabase /> },
                { id: 'versions' as TabType, label: '版本记录', icon: <FiCode /> },
              ].map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`py-3 px-4 border-b-2 -mb-[1px] transition-colors flex items-center gap-2 ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          <div className="min-h-[400px]">
            {activeTab === 'overview' && (
              <div className="space-y-6">
                {status?.last_sync && (
                  <div className="bg-white rounded-lg shadow p-4">
                    <h3 className="font-semibold mb-3 text-gray-800">上次同步</h3>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                      <div>
                        <span className="text-xs text-gray-500">版本</span>
                        <div className="font-mono text-sm">{status.last_sync.version_id}</div>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500">时间</span>
                        <div>{formatTime(status.last_sync.timestamp)}</div>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500">新增卡片</span>
                        <div className="text-green-600 font-semibold">+{status.last_sync.cards_added}</div>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500">更新卡片</span>
                        <div className="text-blue-600 font-semibold">~{status.last_sync.cards_updated}</div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="bg-white rounded-lg shadow p-4">
                  <h3 className="font-semibold mb-3 text-gray-800">快速统计</h3>
                  <button
                    onClick={() => setActiveTab('tasks')}
                    className="text-blue-600 hover:underline"
                  >
                    查看最近任务 →
                  </button>
                </div>
              </div>
            )}

            {activeTab === 'sources' && (
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-800">数据源列表</h3>
                  <button onClick={loadDataSources} className="text-blue-600 hover:underline text-sm flex items-center gap-1">
                    <FiRefreshCw />
                    刷新
                  </button>
                </div>
                {loading.sources ? (
                  <div className="p-8 text-center text-gray-500">加载中...</div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {dataSources.map(source => (
                      <div key={source.id} className="p-4 hover:bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <h4 className="font-medium text-gray-900">{source.name}</h4>
                              <span className={`px-2 py-0.5 rounded-full text-xs ${getStatusColor(source.status)} flex items-center gap-1`}>
                                {getStatusIcon(source.status)}
                                {source.status}
                              </span>
                              <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">
                                优先级 {source.priority}
                              </span>
                            </div>
                            <p className="text-sm text-gray-500 mt-1 truncate">{source.url}</p>
                            <div className="flex gap-4 mt-2 text-xs text-gray-500">
                              <span>健康评分: {source.health_score}%</span>
                              <span>最后检查: {formatTime(source.last_check_time)}</span>
                              <span>最后成功: {formatTime(source.last_success_time)}</span>
                            </div>
                          </div>
                          <div className="flex gap-2 ml-4">
                            <button
                              onClick={() => handleCheckSourceHealth(source.id)}
                              className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded hover:bg-blue-200"
                            >
                              检查
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'tasks' && (
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-800">任务历史</h3>
                  <button onClick={loadTasks} className="text-blue-600 hover:underline text-sm flex items-center gap-1">
                    <FiRefreshCw />
                    刷新
                  </button>
                </div>
                {loading.tasks ? (
                  <div className="p-8 text-center text-gray-500">加载中...</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">任务类型</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">状态</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">创建时间</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">完成时间</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">耗时</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {tasks.map(task => (
                          <tr key={task.task_id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm text-gray-900">{task.task_type}</td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-1 rounded-full text-xs ${getStatusColor(task.status)} flex items-center gap-1 inline-flex`}>
                                {getStatusIcon(task.status)}
                                {task.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">{formatTime(task.created_at)}</td>
                            <td className="px-4 py-3 text-sm text-gray-600">{formatTime(task.completed_at)}</td>
                            <td className="px-4 py-3 text-sm text-gray-600">{task.duration}s</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'cards' && (
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-800">卡片库</h3>
                  <button onClick={loadCards} className="text-blue-600 hover:underline text-sm flex items-center gap-1">
                    <FiRefreshCw />
                    刷新
                  </button>
                </div>
                {loading.cards ? (
                  <div className="p-8 text-center text-gray-500">加载中...</div>
                ) : (
                  <div className="divide-y divide-gray-200 max-h-[500px] overflow-auto">
                    {cards.map(card => (
                      <div key={card.card_id} className="p-4 hover:bg-gray-50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-900">{card.name}</h4>
                            <p className="text-sm text-gray-500 mt-1">{card.type}</p>
                            <p className="text-xs text-gray-400 mt-1 line-clamp-2">{card.effect_text}</p>
                            <div className="flex gap-4 mt-2 text-xs text-gray-500">
                              <span>来源: {card.source}</span>
                              <span>更新: {formatTime(card.last_updated)}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'versions' && (
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
                  <h3 className="font-semibold text-gray-800">同步版本</h3>
                  <button onClick={loadVersions} className="text-blue-600 hover:underline text-sm flex items-center gap-1">
                    <FiRefreshCw />
                    刷新
                  </button>
                </div>
                {loading.versions ? (
                  <div className="p-8 text-center text-gray-500">加载中...</div>
                ) : (
                  <div className="divide-y divide-gray-200">
                    {versions.map(version => (
                      <div key={version.version_id} className="p-4 hover:bg-gray-50">
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <h4 className="font-mono font-medium text-gray-900">{version.version_id}</h4>
                              <span className={`px-2 py-0.5 rounded-full text-xs ${getStatusColor(version.status)} flex items-center gap-1`}>
                                {getStatusIcon(version.status)}
                                {version.status}
                              </span>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-2 text-sm">
                              <div>
                                <span className="text-xs text-gray-500">时间</span>
                                <div>{formatTime(version.timestamp)}</div>
                              </div>
                              <div>
                                <span className="text-xs text-gray-500">新增卡片</span>
                                <div className="text-green-600 font-medium">+{version.cards_added}</div>
                              </div>
                              <div>
                                <span className="text-xs text-gray-500">更新卡片</span>
                                <div className="text-blue-600 font-medium">~{version.cards_updated}</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MaintenanceDashboard;
