import { useEffect, useState } from 'react';
import ChatWindow from '../components/ChatWindow';
import Sidebar from '../components/Sidebar';
import Header from '../components/Header';
import MemorySidebar from '../components/MemorySidebar';
import { useDmStore } from '../dm/dmStore';
import { dmConversationApi, dmMetricsApi } from '../dm/dmApi';

interface DMAppProps {
  onClose?: () => void;
}

export default function DMApp({ onClose }: DMAppProps) {
  const { setDmConversations, setDmMetrics } = useDmStore();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [memoryOpen, setMemoryOpen] = useState(false);

  useEffect(() => {
    dmConversationApi.getList().then((response: any) => {
      if (response.success && response.data) {
        setDmConversations(response.data);
      }
    });

    dmMetricsApi.get().then((response: any) => {
      if (response.success && response.data) {
        setDmMetrics(response.data);
      }
    });
  }, [setDmConversations, setDmMetrics]);

  return (
    <div className="flex h-full">
      {sidebarOpen && (
        <Sidebar onClose={() => {
          setSidebarOpen(false);
          onClose?.();
        }} isDm={true} />
      )}

      <div className="flex-1 flex flex-col">
        {/* 使用统一Header组件 - DM主题 */}
        <Header
          title="数码宝贝卡牌规则问答"
          subtitle="数码宝贝卡牌游戏官方规则智能问答助手"
          isDm={true}
          showMenuButton={true}
          onMenuToggle={() => setSidebarOpen(!sidebarOpen)}
          logoSrc="/src/assets/logo.png"
          logoAlt="DM Logo"
          showMemoryButton={true}
          memoryOpen={memoryOpen}
          onMemoryToggle={() => setMemoryOpen(!memoryOpen)}
        />

        <div className="flex-1 overflow-hidden flex">
          <div className="flex-1 overflow-hidden">
            <ChatWindow isDm={true} />
          </div>
          {memoryOpen && (
            <MemorySidebar isDark={true} onClose={() => setMemoryOpen(false)} />
          )}
        </div>
      </div>
    </div>
  );
}