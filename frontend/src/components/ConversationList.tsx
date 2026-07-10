interface ConversationListProps {
  conversations: Array<{ id: string; title: string }>;
  currentId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string, e: React.MouseEvent) => void;
  onNewChat: () => void;
  isDm: boolean;
}

export default function ConversationList({ conversations, currentId, onSelect, onDelete, onNewChat, isDm }: ConversationListProps) {
  const activeClass = isDm ? 'bg-dm-700' : 'bg-primary-100';
  const hoverClass = isDm ? 'hover:bg-dm-700' : 'hover:bg-gray-100';
  const newChatClass = isDm ? 'bg-dm-700 text-dm-200 hover:bg-dm-600' : 'bg-primary-50 text-primary-600 hover:bg-primary-100';

  return (
    <div className="space-y-2">
      <button onClick={onNewChat} className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg ${newChatClass}`}>
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        新建对话
      </button>
      <div className="mt-4 space-y-1">
        {conversations.map(conv => (
          <div
            key={conv.id}
            onClick={() => onSelect(conv.id)}
            className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer ${currentId === conv.id ? activeClass : hoverClass}`}
          >
            <span className={`text-sm truncate flex-1 ${isDm ? 'text-dm-200' : ''}`}>{conv.title}</span>
            <button
              onClick={(e) => onDelete(conv.id, e)}
              className={`opacity-0 group-hover:opacity-100 p-1 rounded ${isDm ? 'hover:bg-red-900/50' : 'hover:bg-red-100'}`}
            >
              <svg className={`w-4 h-4 ${isDm ? 'text-red-400' : 'text-red-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
