import { useState, useEffect } from 'react';
import { documentApi } from '../services/api';
import type { DocumentPreview as DocumentPreviewType, DocumentChunk } from '../types';

interface DocumentPreviewProps {
  documentId: string;
  documentName: string;
  onClose: () => void;
}

export default function DocumentPreview({ documentId, documentName, onClose }: DocumentPreviewProps) {
  const [preview, setPreview] = useState<DocumentPreviewType | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'content' | 'chunks'>('content');
  const [selectedChunk, setSelectedChunk] = useState<DocumentChunk | null>(null);

  useEffect(() => {
    loadDocumentData();
  }, [documentId]);

  const loadDocumentData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [previewRes, chunksRes] = await Promise.all([
        documentApi.getPreview(documentId),
        documentApi.getChunks(documentId),
      ]);

      if (previewRes.success && previewRes.data) {
        setPreview(previewRes.data);
      } else {
        setError(previewRes.error?.message || '加载预览失败');
      }

      if (chunksRes.success && chunksRes.data) {
        setChunks(chunksRes.data);
      }
    } catch (err) {
      setError('加载文档数据失败');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '未知';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusLabel = (status: string): string => {
    const labels: Record<string, string> = {
      pending: '等待中',
      processing: '处理中',
      completed: '已完成',
      failed: '失败',
    };
    return labels[status] || status;
  };

  const getStatusColor = (status: string): string => {
    const colors: Record<string, string> = {
      pending: 'text-yellow-500',
      processing: 'text-blue-500',
      completed: 'text-green-500',
      failed: 'text-red-500',
    };
    return colors[status] || 'text-gray-500';
  };

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* 背景遮罩 */}
      <div 
        className="absolute inset-0 bg-black/30" 
        onClick={onClose}
      />

      {/* 侧边抽屉 */}
      <div className="absolute right-0 top-0 bottom-0 w-[600px] max-w-full bg-white shadow-xl flex flex-col animate-slide-in">
        {/* 头部 */}
        <div className="flex items-center justify-between px-6 py-4 border-b bg-gray-50">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h2 className="text-lg font-semibold text-gray-800 truncate max-w-[400px]">
              {documentName}
            </h2>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 内容区域 */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary-500 mx-auto" />
                <p className="mt-3 text-gray-500">加载中...</p>
              </div>
            </div>
          ) : error ? (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-red-500">
                <svg className="w-12 h-12 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p>{error}</p>
                <button 
                  onClick={loadDocumentData}
                  className="mt-3 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600"
                >
                  重试
                </button>
              </div>
            </div>
          ) : preview ? (
            <>
              {/* 文档信息 */}
              <div className="px-6 py-3 bg-gray-50 border-b">
                <div className="flex flex-wrap gap-4 text-sm text-gray-600">
                  <div className="flex items-center gap-1">
                    <span className="font-medium">状态:</span>
                    <span className={getStatusColor(preview.status)}>{getStatusLabel(preview.status)}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium">大小:</span>
                    <span>{formatFileSize(preview.file_size)}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium">分块:</span>
                    <span>{preview.chunk_count} 块</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="font-medium">来源:</span>
                    <span>{preview.source === 'builtin' ? '内置规则书' : '自定义上传'}</span>
                  </div>
                </div>
              </div>

              {/* Tab 切换 */}
              <div className="flex border-b">
                <button
                  onClick={() => { setActiveTab('content'); setSelectedChunk(null); }}
                  className={`flex-1 py-3 text-sm font-medium transition-colors ${
                    activeTab === 'content' 
                      ? 'text-primary-600 border-b-2 border-primary-500' 
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  文档内容
                </button>
                <button
                  onClick={() => setActiveTab('chunks')}
                  className={`flex-1 py-3 text-sm font-medium transition-colors ${
                    activeTab === 'chunks' 
                      ? 'text-primary-600 border-b-2 border-primary-500' 
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  分块列表 ({chunks.length})
                </button>
              </div>

              {/* 内容 */}
              <div className="flex-1 overflow-y-auto p-4">
                {activeTab === 'content' ? (
                  <div className="prose prose-sm max-w-none">
                    <pre className="whitespace-pre-wrap text-sm text-gray-700 font-sans leading-relaxed">
                      {preview.preview_text || '暂无预览内容'}
                    </pre>
                    {preview.preview_text && preview.preview_text.length >= 5000 && (
                      <div className="mt-4 p-3 bg-amber-50 text-amber-700 text-sm rounded-lg">
                        <svg className="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        预览内容已截断，仅显示前5000字符
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {chunks.length === 0 ? (
                      <div className="text-center text-gray-500 py-8">
                        暂无分块数据
                      </div>
                    ) : (
                      chunks.map((chunk) => (
                        <div
                          key={chunk.id}
                          onClick={() => setSelectedChunk(chunk)}
                          className={`p-4 rounded-lg border cursor-pointer transition-all ${
                            selectedChunk?.id === chunk.id
                              ? 'border-primary-500 bg-primary-50'
                              : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-2">
                            <span className="text-sm font-medium text-gray-700">
                              块 #{chunk.chunk_index + 1}
                            </span>
                            <span className="text-xs text-gray-400">
                              {chunk.text.length} 字符
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 line-clamp-3">
                            {chunk.text}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* 选中分块详情 */}
              {selectedChunk && (
                <div className="border-t bg-gray-50 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-sm font-medium text-gray-700">
                      块 #{selectedChunk.chunk_index + 1} 详情
                    </h4>
                    <button
                      onClick={() => setSelectedChunk(null)}
                      className="text-gray-400 hover:text-gray-600"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap max-h-40 overflow-y-auto bg-white p-3 rounded border">
                    {selectedChunk.text}
                  </pre>
                </div>
              )}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
