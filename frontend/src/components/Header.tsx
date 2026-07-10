interface HeaderProps {
  title: string;
  subtitle?: string;
  isDm?: boolean;
  showMenuButton?: boolean;
  onMenuToggle?: () => void;
  logoSrc?: string;
  logoAlt?: string;
  /** 是否显示对话记忆切换按钮 */
  showMemoryButton?: boolean;
  /** 对话记忆侧栏是否已展开 */
  memoryOpen?: boolean;
  /** 切换对话记忆侧栏 */
  onMemoryToggle?: () => void;
}

export default function Header({
  title,
  subtitle,
  isDm = false,
  showMenuButton = true,
  onMenuToggle,
  logoSrc = '/src/assets/logo.png',
  logoAlt = 'Logo',
  showMemoryButton = false,
  memoryOpen = false,
  onMemoryToggle,
}: HeaderProps) {
  const bgClass = isDm
    ? 'bg-dm-900/80 backdrop-blur-sm border-dm-600/30 shadow-lg'
    : 'bg-white border-gray-200 shadow-sm';

  const textPrimary = isDm ? 'text-white' : 'text-gray-800';
  const textSecondary = isDm ? 'text-dm-300' : 'text-gray-500';

  const menuButtonClass = isDm
    ? 'text-dm-200 hover:bg-dm-700/50'
    : 'text-gray-600 hover:bg-gray-100';

  return (
    <header className={`${bgClass} border-b px-4 py-3 flex items-center justify-between`}>
      <div className="flex items-center gap-4">
        {showMenuButton && (
          <button
            onClick={onMenuToggle}
            className={`p-2 rounded-lg transition-colors ${menuButtonClass}`}
            aria-label="Toggle menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
        <div className="flex items-center gap-3">
          {isDm ? (
            <img
              src={logoSrc}
              alt={logoAlt}
              className="w-10 h-10 object-contain rounded-lg"
              style={{ filter: 'drop-shadow(0 0 8px rgba(168, 85, 247, 0.5))' }}
            />
          ) : (
            <img src={logoSrc} alt={logoAlt} className="w-10 h-10 object-contain" />
          )}
          <h1 className={`text-xl font-bold ${textPrimary}`}>{title}</h1>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {subtitle && (
          <div className={`text-sm ${textSecondary} hidden sm:block`}>
            {subtitle}
          </div>
        )}
        {showMemoryButton && onMemoryToggle && (
          <button
            onClick={onMemoryToggle}
            className={`p-2 rounded-lg transition-colors ${
              memoryOpen
                ? isDm
                  ? 'bg-dm-600 text-white'
                  : 'bg-primary-500 text-white'
                : menuButtonClass
            }`}
            aria-label="Toggle memory panel"
            title="对话记忆"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </button>
        )}
      </div>
    </header>
  );
}
