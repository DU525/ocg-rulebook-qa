import { useState } from 'react';
import Toast from './Toast';
import type { Document } from '../types';

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.rst'];

const formatFileSize = (bytes: number): string => {
  if (!bytes || bytes === 0) return '';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const formatDate = (dateStr: string): string => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}小时前`;
  if (diffMins < 10080) return `${Math.floor(diffMins / 1440)}天前`;
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
};

interface DocumentListProps {
  documents: Document[];
  onUpload: (file: File) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onPreview: (id: string, name: string) => void;
  isDm: boolean;
}

export default function DocumentList({ documents, onUpload, onDelete, onPreview, isDm }: DocumentListProps) {
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const showToast = (message: string, type: 'success' | 'error' | 'info') => {
    setToast({ message, type });
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    if (uploadFile.size > MAX_FILE_SIZE) {
      showToast('文件大小超过限制（最大50MB）', 'error');
      return;
    }
    const ext = '.' + (uploadFile.name.split('.').pop() || '').toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      showToast(`不支持的文件格式，支持：${ALLOWED_EXTENSIONS.join(', ')}`, 'error');
      return;
    }
    setUploading(true);
    try {
      await onUpload(uploadFile);
      showToast('文件上传成功，正在后台处理中...', 'info');
      setUploadFile(null);
    } catch (error: any) {
      setUploading(false);
      showToast(error.response?.data?.error?.message || '上传失败，请重试', 'error');
    }
  };

  const uploadZoneClass = isDm ? 'border-dm-500 bg-dm-900/30' : 'border-gray-300';

  return (
    <div className="space-y-4">
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      <div className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors ${uploadZoneClass}`}>
        <input
          type="file"
          accept=".pdf,.docx,.txt,.rst"
          onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
          className="hidden"
          id="file-upload"
          disabled={uploading}
        />
        <label htmlFor="file-upload" className={`cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}>
          <svg className={`w-8 h-8 mx-auto ${isDm ? 'text-dm-400' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <p className={`mt-2 text-sm ${isDm ? 'text-dm-300' : 'text-gray-600'}`}>
            {uploadFile ? uploadFile.name : '点击选择文件'}
          </p>
          {uploadFile && <p className={`text-xs mt-1 ${isDm ? 'text-dm-400' : 'text-gray-400'}`}>{(uploadFile.size / 1024 / 1024).toFixed(2)} MB</p>}
          <p className={`text-xs mt-1 ${isDm ? 'text-dm-500' : 'text-gray-400'}`}>支持 PDF, DOCX, TXT, RST（最大50MB）</p>
        </label>
        {uploadFile && !uploading && (
          <button onClick={handleUpload} className={`mt-3 px-4 py-2 text-white rounded-lg ${isDm ? 'bg-dm-500 hover:bg-dm-600' : 'bg-primary-500 hover:bg-primary-600'}`}>
            上传
          </button>
        )}
      </div>

      <div className="relative">
        <input
          type="text"
          placeholder="搜索文档..."
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          className={`w-full pl-8 pr-3 py-2 text-sm border rounded-lg ${
            isDm ? 'bg-dm-900 border-dm-600 text-dm-200 placeholder-dm-500 focus:ring-dm-500' : 'border-gray-300 text-gray-900 placeholder-gray-400 focus:ring-primary-500'
          }`}
        />
        <svg className={`absolute left-2.5 top-2.5 w-4 h-4 ${isDm ? 'text-dm-400' : 'text-gray-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      </div>

      <div className="flex gap-1">
        {['all', 'completed', 'processing', 'failed'].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`flex-1 py-1.5 text-xs rounded transition-colors ${
              statusFilter === status
                ? (isDm ? 'bg-dm-500 text-white' : 'bg-primary-500 text-white')
                : (isDm ? 'bg-dm-700 text-dm-300 hover:bg-dm-600' : 'bg-gray-100 text-gray-600 hover:bg-gray-200')
            }`}
          >
            {status === 'all' ? '全部' : status === 'completed' ? '完成' : status === 'processing' ? '处理中' : '失败'}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        <h3 className={`text-sm font-medium ${isDm ? 'text-dm-300' : 'text-gray-600'}`}>已加载文档 ({documents.length})</h3>
        {documents.map(doc => (
          <div key={doc.id} className={`flex items-center justify-between px-3 py-2 rounded-lg ${isDm ? 'bg-dm-900/30' : 'bg-gray-50'}`}>
            <div className="flex-1 min-w-0" onClick={() => onPreview(doc.id, doc.name)}>
              <p className={`text-sm font-medium cursor-pointer truncate ${isDm ? 'text-dm-200 hover:text-dm-100' : 'hover:text-primary-600'}`}>
                {doc.name}
              </p>
              <div className={`flex items-center gap-2 text-xs mt-0.5 ${isDm ? 'text-dm-400' : 'text-gray-500'}`}>
                <span className={`px-1.5 py-0.5 rounded text-xs ${
                  doc.status === 'completed' ? (isDm ? 'bg-green-900/50 text-green-300' : 'bg-green-100 text-green-700') :
                  doc.status === 'processing' || doc.status === 'uploading' ? (isDm ? 'bg-yellow-900/50 text-yellow-300' : 'bg-yellow-100 text-yellow-700') :
                  doc.status === 'failed' ? (isDm ? 'bg-red-900/50 text-red-300' : 'bg-red-100 text-red-700') :
                  (isDm ? 'bg-gray-700 text-gray-300' : 'bg-gray-100 text-gray-600')
                }`}>
                  {doc.status === 'completed' ? '完成' : doc.status === 'processing' || doc.status === 'uploading' ? '处理中' : doc.status === 'failed' ? '失败' : '等待'}
                </span>
                <span>{doc.source === 'builtin' ? '内置' : '上传'}</span>
                <span>{doc.chunkCount}块</span>
              </div>
              <div className={`flex items-center gap-2 text-xs ${isDm ? 'text-dm-500' : 'text-gray-400'} mt-0.5`}>
                {doc.fileSize && doc.fileSize > 0 && <span>{formatFileSize(doc.fileSize)}</span>}
                {doc.uploadTime && <span>{formatDate(doc.uploadTime)}</span>}
              </div>
            </div>
            {doc.source === 'uploaded' && (
              <button
                onClick={() => onDelete(doc.id)}
                className={`p-1 rounded ml-2 ${isDm ? 'hover:bg-red-900/50' : 'hover:bg-red-100'}`}
              >
                <svg className={`w-4 h-4 ${isDm ? 'text-red-400' : 'text-red-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            )}
          </div>
        ))}
        {documents.length === 0 && <p className={`text-sm text-center py-4 ${isDm ? 'text-dm-500' : 'text-gray-400'}`}>暂无文档</p>}
      </div>
    </div>
  );
}
