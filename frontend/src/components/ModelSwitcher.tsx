import { useState, useEffect } from 'react';
import { modelApi } from '../services/api';
import type { ModelInfo } from '../types';

interface ModelSwitcherProps {
  isDm: boolean;
  onModelChange?: (modelId: string) => void;
}

export default function ModelSwitcher({ isDm, onModelChange }: ModelSwitcherProps) {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [currentModel, setCurrentModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [switching, setSwitching] = useState(false);

  const selectBg = isDm ? 'bg-dm-800 border-dm-600 text-dm-100' : 'bg-white border-gray-300 text-gray-900';
  const labelColor = isDm ? 'text-dm-300' : 'text-gray-600';

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const res = await modelApi.getAvailableModels();
        if (res.success && res.data) {
          setModels(res.data.available_models.filter(m => m.enabled));
          setCurrentModel(res.data.current_model);
        }
      } catch (err) {
        console.error('Failed to fetch models:', err);
      }
    };

    fetchModels();
  }, []);

  const handleSwitch = async (modelId: string) => {
    if (modelId === currentModel) return;
    
    setSwitching(true);
    try {
      const res = await modelApi.switchModel(modelId);
      if (res.success) {
        setCurrentModel(modelId);
        onModelChange?.(modelId);
      }
    } catch (err) {
      console.error('Failed to switch model:', err);
    } finally {
      setSwitching(false);
    }
  };

  if (models.length === 0) return null;

  return (
    <div className="space-y-2">
      <label className={`text-xs font-medium ${labelColor}`}>
        当前模型
      </label>
      <select
        value={currentModel}
        onChange={(e) => handleSwitch(e.target.value)}
        disabled={switching}
        className={`w-full px-3 py-2 text-sm rounded border focus:outline-none focus:ring-2 ${isDm ? 'focus:ring-dm-500' : 'focus:ring-primary-500'} ${selectBg}`}
      >
        {models.map((model) => (
          <option key={model.id} value={model.id}>
            {model.name} ({model.model_name})
          </option>
        ))}
      </select>
      {switching && (
        <div className={`text-xs ${isDm ? 'text-dm-400' : 'text-gray-500'}`}>
          模型切换中...
        </div>
      )}
    </div>
  );
}
