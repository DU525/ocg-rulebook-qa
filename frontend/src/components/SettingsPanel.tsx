import { useEffect, useState } from 'react';
import { configApi } from '../services/api';
import { dmConfigApi } from '../dm/dmApi';
import type { RAGConfig, RAGTemplate } from '../types';
import ModelSwitcher from './ModelSwitcher';
import UrlImport from './UrlImport';

interface SettingsPanelProps {
  isDm?: boolean;
  onImportComplete?: () => void;
}

const DEFAULT_CONFIG: RAGConfig = {
  top_k: 5,
  temperature: 0.3,
  max_tokens: 1500,
  system_prompt_template: 'default',
  streaming_enabled: false,
  similarity_threshold: 0.5,
};

const DM_DEFAULT_CONFIG: RAGConfig = {
  top_k: 5,
  temperature: 0.3,
  max_tokens: 1500,
  system_prompt_template: 'dm_default',
  streaming_enabled: false,
  similarity_threshold: 0.5,
};

export default function SettingsPanel({ isDm = false, onImportComplete }: SettingsPanelProps = {}) {
  const [config, setConfig] = useState<RAGConfig>(isDm ? DM_DEFAULT_CONFIG : DEFAULT_CONFIG);
  const [templates, setTemplates] = useState<RAGTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const cfgApi = isDm ? dmConfigApi : configApi;

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const response = await cfgApi.getRAG();
      if (response.success && response.data) {
        setConfig(response.data.config);
        setTemplates(response.data.available_templates || []);
      }
    } catch (err) {
      console.error('加载配置失败:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const response = await cfgApi.updateRAG(config);
      if (response.success && response.data) {
        setConfig(response.data.config);
        setMessage({ text: '配置已保存', type: 'success' });
      } else {
        setMessage({ text: '保存失败', type: 'error' });
      }
    } catch (err) {
      setMessage({ text: '保存失败，请重试', type: 'error' });
    } finally {
      setSaving(false);
      setTimeout(() => setMessage(null), 3000);
    }
  };

  const handleReset = () => {
    const defaults = isDm ? DM_DEFAULT_CONFIG : DEFAULT_CONFIG;
    setConfig(defaults);
    setMessage({ text: '已重置为默认值（点击保存生效）', type: 'success' });
    setTimeout(() => setMessage(null), 3000);
  };

  const updateField = <K extends keyof RAGConfig>(key: K, value: RAGConfig[K]) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const bgCard = isDm ? 'bg-gray-800' : 'bg-white';
  const textPrimary = isDm ? 'text-gray-100' : 'text-gray-700';
  const textSecondary = isDm ? 'text-gray-400' : 'text-gray-500';
  const inputBg = isDm ? 'bg-gray-700 border-gray-600 text-gray-200' : 'border-gray-300 text-gray-900';
  const labelClass = isDm ? 'text-gray-300' : 'text-gray-700';
  const sliderTrack = isDm ? 'bg-gray-600' : 'bg-gray-200';
  const btnPrimary = isDm ? 'bg-indigo-600 hover:bg-indigo-500 text-white' : 'bg-primary-500 hover:bg-primary-600 text-white';
  const btnSecondary = isDm ? 'bg-gray-700 hover:bg-gray-600 text-gray-200' : 'bg-gray-100 hover:bg-gray-200 text-gray-600';
  const toggleBg = isDm ? 'bg-gray-600' : 'bg-gray-300';
  const toggleActive = isDm ? 'bg-indigo-500' : 'bg-primary-500';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className={`animate-spin rounded-full h-8 w-8 border-b-2 ${isDm ? 'border-indigo-400' : 'border-primary-500'}`} />
      </div>
    );
  }

  return (
    <div className="space-y-4 pb-4">
      <div className="flex items-center justify-between">
        <h3 className={`text-sm font-medium ${textPrimary}`}>
          RAG 配置中心
        </h3>
      </div>

      <ModelSwitcher isDm={isDm} />

      <UrlImport isDm={isDm} onImportComplete={onImportComplete} />

      {message && (
        <div className={`px-3 py-2 rounded-lg text-sm ${
          message.type === 'success'
            ? (isDm ? 'bg-green-900/30 text-green-300 border border-green-700' : 'bg-green-50 text-green-700 border border-green-200')
            : (isDm ? 'bg-red-900/30 text-red-300 border border-red-700' : 'bg-red-50 text-red-700 border border-red-200')
        }`}>
          {message.text}
        </div>
      )}

      <div className={`${bgCard} rounded-lg p-4 space-y-4`}>
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className={`text-xs font-medium ${labelClass}`}>
              检索数量 (Top K)
            </label>
            <span className={`text-xs font-mono ${textSecondary}`}>{config.top_k}</span>
          </div>
          <input
            type="range"
            min={1}
            max={20}
            value={config.top_k}
            onChange={(e) => updateField('top_k', parseInt(e.target.value))}
            className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${sliderTrack} [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-current [&::-webkit-slider-thumb]:cursor-pointer ${isDm ? 'text-indigo-500' : 'text-primary-500'}`}
          />
          <div className="flex justify-between mt-0.5">
            <span className={`text-xs ${textSecondary}`}>1</span>
            <span className={`text-xs ${textSecondary}`}>20</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className={`text-xs font-medium ${labelClass}`}>
              温度 (Temperature)
            </label>
            <span className={`text-xs font-mono ${textSecondary}`}>{config.temperature.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={config.temperature}
            onChange={(e) => updateField('temperature', parseFloat(e.target.value))}
            className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${sliderTrack} [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-current [&::-webkit-slider-thumb]:cursor-pointer ${isDm ? 'text-indigo-500' : 'text-primary-500'}`}
          />
          <div className="flex justify-between mt-0.5">
            <span className={`text-xs ${textSecondary}`}>0.0</span>
            <span className={`text-xs ${textSecondary}`}>1.0</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className={`text-xs font-medium ${labelClass}`}>
              最大 Token 数
            </label>
            <span className={`text-xs font-mono ${textSecondary}`}>{config.max_tokens}</span>
          </div>
          <input
            type="range"
            min={100}
            max={4000}
            step={100}
            value={config.max_tokens}
            onChange={(e) => updateField('max_tokens', parseInt(e.target.value))}
            className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${sliderTrack} [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-current [&::-webkit-slider-thumb]:cursor-pointer ${isDm ? 'text-indigo-500' : 'text-primary-500'}`}
          />
          <div className="flex justify-between mt-0.5">
            <span className={`text-xs ${textSecondary}`}>100</span>
            <span className={`text-xs ${textSecondary}`}>4000</span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1">
            <label className={`text-xs font-medium ${labelClass}`}>
              相似度阈值
            </label>
            <span className={`text-xs font-mono ${textSecondary}`}>{config.similarity_threshold.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={config.similarity_threshold}
            onChange={(e) => updateField('similarity_threshold', parseFloat(e.target.value))}
            className={`w-full h-2 rounded-lg appearance-none cursor-pointer ${sliderTrack} [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-current [&::-webkit-slider-thumb]:cursor-pointer ${isDm ? 'text-indigo-500' : 'text-primary-500'}`}
          />
          <div className="flex justify-between mt-0.5">
            <span className={`text-xs ${textSecondary}`}>0.0</span>
            <span className={`text-xs ${textSecondary}`}>1.0</span>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <label className={`text-xs font-medium ${labelClass}`}>
            启用流式输出
          </label>
          <button
            onClick={() => updateField('streaming_enabled', !config.streaming_enabled)}
            className={`relative w-10 h-5 rounded-full transition-colors ${
              config.streaming_enabled ? toggleActive : toggleBg
            }`}
          >
            <span
              className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                config.streaming_enabled ? 'translate-x-5' : ''
              }`}
            />
          </button>
        </div>

        <div>
          <label className={`text-xs font-medium ${labelClass} block mb-1`}>
            系统提示词模板
          </label>
          <select
            value={config.system_prompt_template}
            onChange={(e) => updateField('system_prompt_template', e.target.value)}
            className={`w-full px-3 py-2 text-sm rounded-lg border ${inputBg} focus:outline-none focus:ring-1 ${isDm ? 'focus:ring-indigo-500' : 'focus:ring-primary-500'}`}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
            {templates.length === 0 && (
              <>
                <option value="default">默认 (OCG)</option>
                <option value="concise">简洁模式</option>
                <option value="detailed">详细模式</option>
                <option value="dm_default">数码宝贝默认</option>
              </>
            )}
          </select>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={handleSave}
          disabled={saving}
          className={`flex-1 px-4 py-2 text-sm rounded-lg transition-colors disabled:opacity-50 ${btnPrimary}`}
        >
          {saving ? '保存中...' : '保存配置'}
        </button>
        <button
          onClick={handleReset}
          disabled={saving}
          className={`px-4 py-2 text-sm rounded-lg transition-colors ${btnSecondary}`}
        >
          重置默认
        </button>
      </div>
    </div>
  );
}