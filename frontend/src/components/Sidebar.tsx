import { useEffect, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import { useDmStore } from '../dm/dmStore';
import { conversationApi, documentApi, metricsApi } from '../services/api';
import { dmConversationApi, dmDocumentApi, dmMetricsApi } from '../dm/dmApi';
import MetricsDashboard from './MetricsDashboard';
import SettingsPanel from './SettingsPanel';
import DocumentPreview from './DocumentPreview';
import ConversationList from './ConversationList';
import ConversationSearch from './ConversationSearch';
import DocumentList from './DocumentList';
import type { Document } from '../types';

interface SidebarProps {
  onClose: () => void;
  isDm?: boolean;
}

export default function Sidebar({ onClose, isDm = false }: SidebarProps) {
  const { sidebarTab, setSidebarTab, conversations, setConversations, setMetrics, currentConversation, setCurrentConversation, clearCurrentConversation, setMessages } = useAppStore();
  const { dmSidebarTab, setDmSidebarTab, dmConversations, setDmConversations, setDmMetrics, dmCurrentConversation, setDmCurrentConversation, clearDmCurrentConversation, setDmMessages } = useDmStore();

  const [documents, setDocuments] = useState<Document[]>([]);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const [previewDocName, setPreviewDocName] = useState<string>('');
  const [searchKeyword, setSearchKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');

  const sidebarTabValue = isDm ? dmSidebarTab : sidebarTab;
  const setSidebarTabFn = isDm ? setDmSidebarTab : setSidebarTab;
  const conversationsData = isDm ? dmConversations : conversations;
  const setConversationsFn = isDm ? setDmConversations : setConversations;
  const setMetricsFn = isDm ? setDmMetrics : setMetrics;
  const currentConversationData = isDm ? dmCurrentConversation : currentConversation;
  const setCurrentConversationFn = isDm ? setDmCurrentConversation : setCurrentConversation;
  const clearCurrentConversationFn = isDm ? clearDmCurrentConversation : clearCurrentConversation;
  const setMessagesFn = isDm ? setDmMessages : setMessages;

  const convApi = isDm ? dmConversationApi : conversationApi;
  const docApi = isDm ? dmDocumentApi : documentApi;
  const metApi = isDm ? dmMetricsApi : metricsApi;

  useEffect(() => {
    loadConversations();
    loadDocuments();
    loadMetrics();
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => { loadDocuments(); }, searchKeyword ? 300 : 0);
    return () => clearTimeout(timer);
  }, [searchKeyword, statusFilter]);

  const loadConversations = async () => {
    const response = await convApi.getList();
    if (response.success && response.data) setConversationsFn(response.data);
  };

  const loadDocuments = async () => {
    const params = statusFilter === 'all' ? undefined : statusFilter;
    const response = await docApi.getList(params);
    if (response.success && response.data) {
      let docs = response.data;
      if (searchKeyword) {
        const keyword = searchKeyword.toLowerCase();
        docs = docs.filter((d: any) => d.name.toLowerCase().includes(keyword));
      }
      setDocuments(docs);
    }
  };

  const loadMetrics = async () => {
    const response = await metApi.get();
    if (response.success && response.data) setMetricsFn(response.data);
  };

  const handleSelectConversation = async (id: string) => {
    const response = await convApi.getDetail(id);
    if (response.success && response.data) {
      const conversation = conversationsData.find(c => c.id === id);
      setCurrentConversationFn({
        id, title: conversation?.title || '对话',
        messages: response.data.map((msg: any) => ({ id: msg.id, role: msg.role as 'user' | 'assistant', content: msg.content, citations: msg.citations, createdAt: msg.created_at })),
        createdAt: (conversation as any)?.created_at || new Date().toISOString(),
        updatedAt: (conversation as any)?.updated_at || new Date().toISOString()
      });
      setMessagesFn(response.data.map((msg: any) => ({ id: msg.id, role: msg.role as 'user' | 'assistant', content: msg.content, citations: msg.citations, createdAt: msg.created_at })));
    }
  };

  const handleNewChat = () => { clearCurrentConversationFn(); };

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await convApi.delete(id);
    loadConversations();
    if (currentConversationData?.id === id) clearCurrentConversationFn();
  };

  const handleUpload = async (file: File) => {
    const response = await docApi.upload(file);
    if (response.success) setTimeout(() => loadDocuments(), 2000);
  };

  const handleDeleteDocument = async (id: string) => {
    await docApi.delete(id);
    loadDocuments();
  };

  const handlePreview = (id: string, name: string) => { setPreviewDocId(id); setPreviewDocName(name); };
  const handleClosePreview = () => { setPreviewDocId(null); setPreviewDocName(''); };

  const bgClass = isDm ? 'bg-dm-800 border-dm-600/30' : 'bg-white border-gray-200';
  const textPrimary = isDm ? 'text-white' : 'text-gray-700';
  const textSecondary = isDm ? 'text-dm-300' : 'text-gray-500';
  const activeTabClass = isDm ? 'border-dm-500 text-dm-400' : 'border-primary-500 text-primary-600';

  return (
    <div className={`w-72 ${bgClass} border-r flex flex-col h-full`}>
      <div className={`p-4 border-b flex justify-between items-center ${isDm ? 'border-dm-600/30' : 'border-gray-200'}`}>
        <h2 className={`font-semibold ${textPrimary}`}>菜单</h2>
        <button onClick={onClose} className={`p-2 rounded-lg ${isDm ? 'hover:bg-dm-700 text-dm-300' : 'hover:bg-gray-100'}`}>
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className={`flex border-b ${isDm ? 'border-dm-600/30' : 'border-gray-200'}`}>
        {(['conversations', 'documents', 'metrics', 'settings'] as const).map(tab => (
          <button key={tab} onClick={() => setSidebarTabFn(tab)}
            className={`flex-1 py-2 text-sm ${sidebarTabValue === tab ? `border-b-2 ${activeTabClass}` : textSecondary}`}>
            {tab === 'conversations' ? '对话' : tab === 'documents' ? '文档' : tab === 'metrics' ? '统计' : '设置'}
          </button>
        ))}
      </div>

      <div className={`flex-1 overflow-y-auto p-2 ${isDm ? 'scrollbar-dm' : ''}`}>
        {sidebarTabValue === 'conversations' && (
          <>
            <div className="mb-2">
              <ConversationSearch isDm={isDm} onSelectConversation={handleSelectConversation} />
            </div>
            <ConversationList
              conversations={conversationsData}
              currentId={currentConversationData?.id || null}
              onSelect={handleSelectConversation}
              onDelete={handleDeleteConversation}
              onNewChat={handleNewChat}
              isDm={isDm}
            />
          </>
        )}
        {sidebarTabValue === 'documents' && (
          <DocumentList
            documents={documents}
            onUpload={handleUpload}
            onDelete={handleDeleteDocument}
            onPreview={handlePreview}
            isDm={isDm}
          />
        )}
        {sidebarTabValue === 'metrics' && <MetricsDashboard />}
        {sidebarTabValue === 'settings' && <SettingsPanel isDm={isDm} onImportComplete={loadDocuments} />}
      </div>

      {previewDocId && <DocumentPreview documentId={previewDocId} documentName={previewDocName} onClose={handleClosePreview} />}
    </div>
  );
}
