import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const maintenanceApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

export interface DataSource {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  priority: number;
  status: string;
  health_score: number;
  last_check_time: string | null;
  last_success_time: string | null;
}

export interface DataSourcesResponse {
  success: boolean;
  total: number;
  sources: DataSource[];
}

export interface MaintenanceStatus {
  success: boolean;
  is_running: boolean;
  scheduler_status: string;
  data_source_health: {
    total_sources: number;
    enabled_sources: number;
    healthy_sources: number;
    health_rate: number;
  };
  last_sync: {
    version_id: string;
    timestamp: string;
    cards_added: number;
    cards_updated: number;
    status: string;
  } | null;
  active_tasks: number;
  cards_in_kb: number;
  timestamp: string;
}

export interface SyncRequest {
  sync_type: 'full' | 'incremental' | 'emergency';
  priority?: number;
}

export interface SyncResponse {
  success: boolean;
  task_id: string;
  message: string;
  timestamp: string;
}

export interface Task {
  task_id: string;
  task_type: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration: number;
  error: string | null;
}

export interface TaskHistoryResponse {
  success: boolean;
  total: number;
  tasks: Task[];
}

export interface ScheduledJob {
  id: string;
  name: string;
  next_run_time: string | null;
}

export interface ScheduledJobsResponse {
  success: boolean;
  total: number;
  jobs: ScheduledJob[];
}

export interface CardInfo {
  card_id: string;
  name: string;
  type: string;
  effect_text: string;
  image_url?: string;
  source: string;
  last_updated: string;
}

export interface CardsResponse {
  success: boolean;
  total: number;
  limit: number;
  offset: number;
  cards: CardInfo[];
}

export interface SyncVersion {
  version_id: string;
  timestamp: string;
  cards_added: number;
  cards_updated: number;
  status: string;
  error: string | null;
}

export interface VersionsResponse {
  success: boolean;
  total: number;
  versions: SyncVersion[];
}

export interface MaintenanceStatistics {
  success: boolean;
  statistics: {
    system: {
      is_running: boolean;
      uptime: string;
    };
    data_sources: Record<string, any>;
    card_fetcher: {
      total_cards: number;
      by_type: Record<string, number>;
      with_banlist: number;
      recently_updated: number;
      sources_used: string[];
    };
    scheduler: Record<string, any>;
    knowledge_base_sync: {
      total_syncs: number;
      successful_syncs: number;
      success_rate: number;
      last_sync?: any;
      current_cards: number;
      total_cards_synced: number;
    };
  };
}

export const maintenanceApiService = {
  getStatus: async (): Promise<MaintenanceStatus> => {
    const response = await maintenanceApi.get('/maintenance/status');
    return response.data;
  },

  getStatistics: async (): Promise<MaintenanceStatistics> => {
    const response = await maintenanceApi.get('/maintenance/statistics');
    return response.data;
  },

  triggerSync: async (data: SyncRequest): Promise<SyncResponse> => {
    const response = await maintenanceApi.post('/maintenance/sync', data);
    return response.data;
  },

  getDataSources: async (): Promise<DataSourcesResponse> => {
    const response = await maintenanceApi.get('/maintenance/data-sources');
    return response.data;
  },

  checkSourceHealth: async (sourceId: string): Promise<any> => {
    const response = await maintenanceApi.post(`/maintenance/data-sources/${sourceId}/health-check`);
    return response.data;
  },

  removeDataSource: async (sourceId: string): Promise<any> => {
    const response = await maintenanceApi.delete(`/maintenance/data-sources/${sourceId}`);
    return response.data;
  },

  startScheduler: async (): Promise<{ success: boolean; message: string }> => {
    const response = await maintenanceApi.post('/maintenance/scheduler/start');
    return response.data;
  },

  stopScheduler: async (): Promise<{ success: boolean; message: string }> => {
    const response = await maintenanceApi.post('/maintenance/scheduler/stop');
    return response.data;
  },

  getScheduledJobs: async (): Promise<ScheduledJobsResponse> => {
    const response = await maintenanceApi.get('/maintenance/scheduler/jobs');
    return response.data;
  },

  getTaskHistory: async (limit = 20): Promise<TaskHistoryResponse> => {
    const response = await maintenanceApi.get(`/maintenance/scheduler/history?limit=${limit}`);
    return response.data;
  },

  getCards: async (limit = 50, offset = 0): Promise<CardsResponse> => {
    const response = await maintenanceApi.get(`/maintenance/knowledge-base/cards?limit=${limit}&offset=${offset}`);
    return response.data;
  },

  getVersions: async (limit = 10): Promise<VersionsResponse> => {
    const response = await maintenanceApi.get(`/maintenance/knowledge-base/versions?limit=${limit}`);
    return response.data;
  },
};

export default maintenanceApiService;
