import React from 'react';
import { FiDatabase, FiMenu, FiX } from 'react-icons/fi';
import { FiSettings, FiHelpCircle } from 'react-icons/fi';

interface ModernHeaderProps {
  currentGame: 'ocg' | 'dm';
  onGameSwitch: (game: 'ocg' | 'dm') => void;
  onMaintenance: () => void;
  isDark?: boolean;
}

const ModernHeader: React.FC<ModernHeaderProps> = ({
  currentGame,
  onGameSwitch,
  onMaintenance,
  isDark = false
}) => {
  const isOcg = currentGame === 'ocg';
  
  return (
    <header className={`
      border-b backdrop-blur-md
      ${isDark 
        ? 'bg-slate-900/95 border-slate-700' 
        : 'bg-white/95 border-gray-200'
      }
    `}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo区域 */}
          <div className="flex items-center space-x-4">
            <div className={`
              w-10 h-10 rounded-xl flex items-center justify-center
              ${isOcg 
                ? 'bg-gradient-to-br from-blue-500 to-blue-600' 
                : 'bg-gradient-to-br from-purple-500 to-purple-600'
              }
              shadow-lg
            `}>
              <span className="text-white font-bold text-lg">
                {isOcg ? 'OCG' : 'DM'}
              </span>
            </div>
            
            <div>
              <h1 className={`
                text-lg font-bold
                ${isDark ? 'text-white' : 'text-gray-900'}
              `}>
                {isOcg ? '游戏王OCG规则问答' : '数码宝贝DCG规则问答'}
              </h1>
              <p className={`
                text-xs
                ${isDark ? 'text-slate-400' : 'text-gray-500'}
              `}>
                基于官方规则书的智能问答助手
              </p>
            </div>
          </div>

          {/* 游戏切换 */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => onGameSwitch('ocg')}
              className={`
                px-4 py-2 rounded-lg font-medium text-sm transition-all duration-300
                ${isOcg 
                  ? 'bg-blue-600 text-white shadow-lg' 
                  : isDark 
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800' 
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }
              `}
            >
              游戏王OCG
            </button>
            <button
              onClick={() => onGameSwitch('dm')}
              className={`
                px-4 py-2 rounded-lg font-medium text-sm transition-all duration-300
                ${!isOcg 
                  ? 'bg-purple-600 text-white shadow-lg' 
                  : isDark 
                    ? 'text-slate-400 hover:text-white hover:bg-slate-800' 
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }
              `}
            >
              数码宝贝DCG
            </button>
          </div>

          {/* 右侧工具 */}
          <div className="flex items-center space-x-2">
            <button
              onClick={onMaintenance}
              className={`
                p-2 rounded-lg transition-all duration-300
                ${isDark 
                  ? 'text-slate-400 hover:text-white hover:bg-slate-800' 
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }
              `}
              title="维护系统"
            >
              <FiDatabase className="w-5 h-5" />
            </button>
            <button
              className={`
                p-2 rounded-lg transition-all duration-300
                ${isDark 
                  ? 'text-slate-400 hover:text-white hover:bg-slate-800' 
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                }
              `}
              title="帮助"
            >
              <FiHelpCircle className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default ModernHeader;
