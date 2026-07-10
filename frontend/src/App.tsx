import { useState, lazy, Suspense, useEffect, useCallback } from 'react';
import GameSwitcher from './components/GameSwitcher';
import MaintenanceDashboard from './components/MaintenanceDashboard';
import { FiDatabase, FiMonitor, FiSmartphone } from 'react-icons/fi';
import { MessageSkeleton } from './modern/components/SkeletonLoader';
import { routePreloader, usePreloadOnHover } from './modern/utils/preloadUtils';

// 懒加载组件
const OCGApp = lazy(() => import('./ocg/OCGApp'));
const DMApp = lazy(() => import('./dm/DMApp'));
const ModernApp = lazy(() => import('./modern/ModernApp'));

// 预加载器工厂
const preloadOCGApp = () => import('./ocg/OCGApp');
const preloadDMApp = () => import('./dm/DMApp');
const preloadModernApp = () => import('./modern/ModernApp');

export default function App() {
  const [currentGame, setCurrentGame] = useState<'ocg' | 'dm'>('ocg');
  const [showMaintenance, setShowMaintenance] = useState(false);
  const [useModernUI, setUseModernUI] = useState(true); // 默认使用新UI
  const isDm = currentGame === 'dm';

  // 初始化时预加载当前游戏的组件
  useEffect(() => {
    if (useModernUI) {
      routePreloader.preload('modern-app', preloadModernApp);
    } else {
      if (currentGame === 'ocg') {
        routePreloader.preload('ocg-app', preloadOCGApp);
      } else {
        routePreloader.preload('dm-app', preloadDMApp);
      }
    }
  }, [currentGame, useModernUI]);

  // 智能预加载 - 当用户悬停在游戏切换按钮时
  const preloadOnGameHover = useCallback((game: 'ocg' | 'dm') => {
    if (game === 'ocg') {
      routePreloader.preload('ocg-app', preloadOCGApp);
    } else {
      routePreloader.preload('dm-app', preloadDMApp);
    }
  }, []);

  // 智能预加载 - 当用户悬停在UI切换按钮时
  const preloadModernUIHandler = usePreloadOnHover('modern-app', preloadModernApp);
  const preloadClassicUIHandler = usePreloadOnHover(
    currentGame === 'ocg' ? 'ocg-app' : 'dm-app',
    currentGame === 'ocg' ? preloadOCGApp : preloadDMApp
  );

  // 切换游戏时预加载
  const handleSwitchGame = useCallback((game: 'ocg' | 'dm') => {
    // 立即预加载新游戏的组件
    if (!useModernUI) {
      if (game === 'ocg') {
        routePreloader.preload('ocg-app', preloadOCGApp);
      } else {
        routePreloader.preload('dm-app', preloadDMApp);
      }
    }
    setCurrentGame(game);
  }, [useModernUI]);

  if (showMaintenance) {
    return (
      <div className="h-screen">
        <MaintenanceDashboard onBack={() => setShowMaintenance(false)} />
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      {/* 游戏切换 Header - 统一设计 */}
      <header className={`border-b px-4 py-3 ${isDm ? 'bg-dm-900/80 backdrop-blur-sm border-dm-600/30 shadow-lg' : 'bg-white border-gray-200 shadow-sm'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              {isDm ? (
                <img 
                  src="/src/assets/logo.png" 
                  alt="Logo" 
                  className="w-10 h-10 object-contain rounded-lg"
                  style={{ filter: 'drop-shadow(0 0 8px rgba(168, 85, 247, 0.5))' }} 
                />
              ) : (
                <img src="/src/assets/logo.png" alt="Logo" className="w-10 h-10 object-contain" />
              )}
              <span className={`text-lg font-bold ${isDm ? 'text-white' : 'text-gray-800'}`}>
                {currentGame === 'ocg' ? '游戏王OCG规则问答' : '数码宝贝DCG规则问答'}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* UI切换按钮 - 支持智能预加载 */}
            <div className={`
              flex items-center rounded-lg p-1
              ${isDm ? 'bg-dm-800' : 'bg-gray-100'}
            `}>
              <button
                onClick={() => setUseModernUI(true)}
                onMouseEnter={preloadModernUIHandler}
                onFocus={preloadModernUIHandler}
                className={`
                  p-2 rounded-md transition-all duration-300
                  ${useModernUI
                    ? isDm 
                      ? 'bg-purple-600 text-white shadow' 
                      : 'bg-blue-600 text-white shadow'
                    : isDm
                      ? 'text-dm-300 hover:text-white'
                      : 'text-gray-600 hover:text-gray-90'
                  }
                `}
                title="现代化UI"
              >
                <FiMonitor className="w-4 h-4" />
              </button>
              <button
                onClick={() => setUseModernUI(false)}
                onMouseEnter={preloadClassicUIHandler}
                onFocus={preloadClassicUIHandler}
                className={`
                  p-2 rounded-md transition-all duration-300
                  ${!useModernUI
                    ? isDm 
                      ? 'bg-purple-600 text-white shadow' 
                      : 'bg-blue-600 text-white shadow'
                    : isDm
                      ? 'text-dm-300 hover:text-white'
                      : 'text-gray-600 hover:text-gray-90'
                  }
                `}
                title="经典UI"
              >
                <FiSmartphone className="w-4 h-4" />
              </button>
            </div>
            
            <button
              onClick={() => setShowMaintenance(true)}
              className={`p-2 rounded-lg flex items-center gap-2 ${
                isDm ? 'text-dm-200 hover:bg-dm-700/50' : 'text-gray-600 hover:bg-gray-100'
              }`}
              title="维护系统"
            >
              <FiDatabase className="w-5 h-5" />
              <span className="text-sm hidden md:inline">维护</span>
            </button>
            {/* 游戏切换组件 - 传递预加载回调 */}
            <GameSwitcher 
              currentGame={currentGame} 
              onSwitch={handleSwitchGame}
              onPreload={preloadOnGameHover}
            />
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <div className="flex-1 overflow-hidden">
        <Suspense fallback={<MessageSkeleton />}>
          {useModernUI ? (
            <ModernApp />
          ) : (
            currentGame === 'ocg' ? <OCGApp /> : <DMApp />
          )}
        </Suspense>
      </div>
    </div>
  );
}
