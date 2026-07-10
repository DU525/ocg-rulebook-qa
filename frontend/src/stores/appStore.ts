import { create } from 'zustand';
import type { Message, Conversation, Metrics, Citation, RetrievalSource } from '../types';

interface AppState {
  currentConversation: Conversation | null;
  conversations: Conversation[];
  messages: Message[];
  isLoading: boolean;
  metrics: Metrics | null;
  sidebarTab: 'conversations' | 'documents' | 'metrics' | 'settings';
  setCurrentConversation: (conversation: Conversation | null) => void;
  setConversations: (conversations: Conversation[]) => void;
  addConversation: (conversation: Conversation) => void;
  addMessage: (message: Message) => void;
  updateLastAssistantMessage: (chunk: string) => void;
  setAssistantMessageContent: (messageId: string, content: string) => void;
  updateLastAssistantCitations: (citations: Citation[], sources?: RetrievalSource[]) => void;
  setMessages: (messages: Message[]) => void;
  setIsLoading: (loading: boolean) => void;
  setMetrics: (metrics: Metrics) => void;
  setSidebarTab: (tab: 'conversations' | 'documents' | 'metrics' | 'settings') => void;
  clearCurrentConversation: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentConversation: null,
  conversations: [],
  messages: [],
  isLoading: false,
  metrics: null,
  sidebarTab: 'conversations',

  setCurrentConversation: (conversation) => set({ currentConversation: conversation }),
  setConversations: (conversations) => set({ conversations }),
  addConversation: (conversation) => set((state) => ({
    conversations: [conversation, ...state.conversations]
  })),
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message]
  })),
  updateLastAssistantMessage: (chunk) => set((state) => {
    const msgs = [...state.messages];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs[i] = { ...msgs[i], content: msgs[i].content + chunk };
        break;
      }
    }
    return { messages: msgs };
  }),
  setAssistantMessageContent: (messageId: string, content: string) => set((state) => {
    const msgs = state.messages.map((msg) =>
      msg.id === messageId ? { ...msg, content } : msg
    );
    return { messages: msgs };
  }),
  updateLastAssistantCitations: (citations, sources) => set((state) => {
    const msgs = [...state.messages];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs[i] = { ...msgs[i], citations, ...(sources ? { sources } : {}) };
        break;
      }
    }
    return { messages: msgs };
  }),
  setMessages: (messages) => set({ messages }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setMetrics: (metrics) => set({ metrics }),
  setSidebarTab: (sidebarTab) => set({ sidebarTab }),
  clearCurrentConversation: () => set({
    currentConversation: null,
    messages: []
  }),
}));