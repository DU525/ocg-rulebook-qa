import { useState } from 'react';
import { documentApi } from '../services/api';
import type { ImportStatus } from '../types';

interface UrlImportProps {
  isDm: boolean;
  onImportComplete?: (status: ImportStatus) => void;
}

export default function UrlImport({ isDm, onImportComplete }: UrlImportProps) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [status, setStatus] = useState<ImportStatus | null>(null);
  const [error, setError] = useState('');

  const inputBg = isDm ? 'bg-dm-800 border-dm-600 text-dm-100 placeholder-dm-400' : 'bg-white border-gray-300 text-gray-900 placeholder-gray-400';
  const btnPrimary = isDm ? 'bg-dm-600 hover:bg-dm-500 text-white' : 'bg-primary-600 hover:bg-primary-700 text-white';

  const handleImport = async () => {
    if (!url.trim()) {
      setError('请输入URL');
      return;
    }
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setError('URL必须以http://或https://开头');
      return;
    }

    setIsImporting(true);
    setError('');
    setStatus(null);

    try {
      const res = await documentApi.importUrl(url.trim(), title || undefined);
      if (res.success && res.data) {
        setStatus({
          id: res.data.id,
          name: '',
          status: res.data.status,
          progress: 10,
          chunk_count: 0,
          source_url: res.data.url
        });
        
        const pollInterval = setInterval(async () => {
          try {
            const statusRes = await documentApi.getImportStatus(res.data!.id);
            if (statusRes.success && statusRes.data) {
              setStatus(statusRes.data);
              if (statusRes.data.status === 'completed' || statusRes.data.status === 'failed') {
                clearInterval(pollInterval);
                setIsImporting(false);
                if (statusRes.data.status === 'completed' && onImportComplete) {
                  onImportComplete(statusRes.data);
                }
              }
            }
          } catch (err) {
            clearInterval(pollInterval);
            setIsImporting(false);
          }
        }, 2000);
      }
    } catch (err: any) {
      setError(err.response?.data?.error?.message || '导入失败，请重试');
      setIsImporting(false);
    }
  };

  return (
    <div className={`p-4 rounded-lg border ${isDm ? 'bg-dm-900/50 border-dm-700' : 'bg-gray-50 border-gray-200'}`}>
      <h3 className={`text-sm font-semibold mb-3 ${isDm ? 'text-dm-200' : 'text-gray-700'}`}>
        网页导入
      </h3>
      
      <div className="space-y-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="输入网页URL (https://...)"
          className={`w-full px-3 py-2 text-sm rounded border focus:outline-none focus:ring-2 ${isDm ? 'focus:ring-dm-500' : 'focus:ring-primary-500'} ${inputBg}`}
          disabled={isImporting}
        />
        
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="可选：自定义标题"
          className={`w-full px-3 py-2 text-sm rounded border focus:outline-none focus:ring-2 ${isDm ? 'focus:ring-dm-500' : 'focus:ring-primary-500'} ${inputBg}`}
          disabled={isImporting}
        />

        <button
          onClick={handleImport}
          disabled={isImporting || !url.trim()}
          className={`w-full px-3 py-2 text-sm rounded font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${btnPrimary}`}
        >
          {isImporting ? '抓取中...' : '开始导入'}
        </button>
      </div>

      {error && (
        <div className="mt-2 text-xs text-red-500">{error}</div>
      )}

      {status && (
        <div className={`mt-3 p-2 rounded text-xs ${
          status.status === 'completed' 
            ? isDm ? 'bg-green-900/30 text-green-300' : 'bg-green-50 text-green-700'
            : status.status === 'failed'
            ? isDm ? 'bg-red-900/30 text-red-300' : 'bg-red-50 text-red-700'
            : isDm ? 'bg-dm-800 text-dm-300' : 'bg-blue-50 text-blue-700'
        }`}>
          <div className="flex items-center justify-between mb-1">
            <span>{status.status === 'completed' ? '导入完成' : status.status === 'failed' ? '导入失败' : '处理中...'}</span>
            <span>{status.progress}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all duration-300 ${
                status.status === 'completed' ? 'bg-green-500' : status.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'
              }`}
              style={{ width: `${status.progress}%` }}
            />
          </div>
          {status.chunk_count > 0 && (
            <div className="mt-1">分块数量: {status.chunk_count}</div>
          )}
          {status.error_message && (
            <div className="mt-1 text-red-400">{status.error_message}</div>
          )}
        </div>
      )}
    </div>
  );
}
