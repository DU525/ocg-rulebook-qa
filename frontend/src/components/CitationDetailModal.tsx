import { useState, useEffect } from 'react';
import { citationApi } from '../services/api';
import type { CitationDetail } from '../types';

interface CitationDetailModalProps {
  chunkId: string | null;
  isDm: boolean;
  onClose: () => void;
}

export default function CitationDetailModal({ chunkId, isDm, onClose }: CitationDetailModalProps) {
  const [detail, setDetail] = useState<CitationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const overlayBg = isDm ? 'bg-black/70' : 'bg-black/50';
  const modalBg = isDm ? 'bg-dm-900 border-dm-700' : 'bg-white';
  const textPrimary = isDm ? 'text-dm-100' : 'text-gray-900';
  const textSecondary = isDm ? 'text-dm-400' : 'text-gray-500';

  useEffect(() => {
    if (!chunkId) return;

    const fetchDetail = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await citationApi.getDetail(chunkId);
        if (res.success && res.data) {
          setDetail(res.data);
        } else {
          setError('获取引用详情失败');
        }
      } catch (err) {
        setError('网络请求失败');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [chunkId]);

  if (!chunkId) return null;

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center ${overlayBg}`} onClick={onClose}>
      <div
        className={`relative w-full max-w-2xl mx-4 max-h-[80vh] rounded-xl shadow-2xl border ${modalBg} overflow-hidden`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b ${isDm ? 'border-dm-700' : 'border-gray-200'}`}>
          <h2 className={`text-lg font-semibold ${textPrimary}`}>引用原文</h2>
          <button
            onClick={onClose}
            className={`p-1 rounded-lg transition-colors ${isDm ? 'hover:bg-dm-700 text-dm-400' : 'hover:bg-gray-100 text-gray-500'}`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-4 overflow-y-auto max-h-[calc(80vh-80px)]">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className={`w-8 h-8 border-2 rounded-full animate-spin ${isDm ? 'border-dm-400 border-t-transparent' : 'border-gray-400 border-t-transparent'}`} />
            </div>
          ) : error ? (
            <div className="text-red-500 text-sm py-4">{error}</div>
          ) : detail ? (
            <div className="space-y-4">
              {/* Metadata */}
              {(detail.source || detail.chapter || detail.section) && (
                <div className={`flex flex-wrap gap-2 text-xs ${textSecondary}`}>
                  {detail.source && (
                    <span className={`px-2 py-1 rounded ${isDm ? 'bg-dm-800' : 'bg-gray-100'}`}>
                      来源: {detail.source}
                    </span>
                  )}
                  {detail.chapter && (
                    <span className={`px-2 py-1 rounded ${isDm ? 'bg-dm-800' : 'bg-gray-100'}`}>
                      章节: {detail.chapter}
                    </span>
                  )}
                  {detail.section && (
                    <span className={`px-2 py-1 rounded ${isDm ? 'bg-dm-800' : 'bg-gray-100'}`}>
                      小节: {detail.section}
                    </span>
                  )}
                </div>
              )}

              {/* Text Content */}
              <div className={`text-sm leading-relaxed whitespace-pre-wrap ${textPrimary}`}>
                {detail.text}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
