import { useEffect, useState } from 'react';
import ChatWindow from '../components/ChatWindow';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import MemorySidebar from '../components/MemorySidebar';
import { useAppStore } from '../stores/appStore';
import { conversationApi, metricsApi } from '../services/api';

export default function OCGApp() {
  const { setConversations, setMetrics } = useAppStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [memoryOpen, setMemoryOpen] = useState(false);

  useEffect(() => {
    conversationApi.getList().then((response) => {
      if (response.success && response.data) {
        setConversations(response.data);
      }
    });

    metricsApi.get().then((response) => {
      if (response.success && response.data) {
        setMetrics(response.data);
      }
    });
  }, [setConversations, setMetrics]);

  return (
    <div className="flex h-full">
      {sidebarOpen && <Sidebar onClose={() => setSidebarOpen(false)} />}

      <div className="flex-1 flex flex-col">
        {/* 使用统一Header组件 */}
        <Header
          title="游戏王OCG规则问答"
          subtitle="基于官方规则书的智能问答助手"
          isDm={false}
          showMenuButton={true}
          onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
          logoSrc="/src/assets/logo.png"
          logoAlt="OCG Logo"
          showMemoryButton={true}
          memoryOpen={memoryOpen}
          onMemoryToggle={() => setMemoryOpen(!memoryOpen)}
        />

        <div className="flex-1 overflow-hidden flex">
          <div className="flex-1 overflow-hidden">
            <ChatWindow isDm={false} />
          </div>
          {memoryOpen && (
            <MemorySidebar isDark={false} onClose={() => setMemoryOpen(false)} />
          )}
        </div>
      </div>
    </div>
  );
}