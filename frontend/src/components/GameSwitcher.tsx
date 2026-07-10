interface GameSwitcherProps {
  currentGame: 'ocg' | 'dm';
  onSwitch: (game: 'ocg' | 'dm') => void;
  onPreload?: (game: 'ocg' | 'dm') => void;
}

export default function GameSwitcher({ currentGame, onSwitch, onPreload }: GameSwitcherProps) {
  return (
    <div className="flex items-center gap-3 px-4 py-2">
      <button
        onClick={() => onSwitch('ocg')}
        onMouseEnter={() => onPreload?.('ocg')}
        onFocus={() => onPreload?.('ocg')}
        className={`game-tab ${currentGame === 'ocg' ? 'game-tab-ocg active' : 'game-tab-ocg'}`}
      >
        <span className="flex items-center gap-2">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          游戏王OCG
        </span>
      </button>
      <button
        onClick={() => onSwitch('dm')}
        onMouseEnter={() => onPreload?.('dm')}
        onFocus={() => onPreload?.('dm')}
        className={`game-tab ${currentGame === 'dm' ? 'game-tab-dm active' : 'game-tab-dm'}`}
      >
        <span className="flex items-center gap-2">
          <img src="/src/assets/logo.png" alt="" className="w-5 h-5 object-contain" />
          数码宝贝DCG
        </span>
      </button>
    </div>
  );
}