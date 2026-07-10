import { create } from 'zustand';
import type { Message, Conversation, Metrics, Citation, RetrievalSource } from '../types';

interface DMState {
  dmCurrentConversation: Conversation | null;
  dmConversations: Conversation[];
  dmMessages: Message[];
  dmIsLoading: boolean;
  dmMetrics: Metrics | null;
  dmSidebarTab: 'conversations' | 'documents' | 'metrics' | 'settings';
  currentGame: 'ocg' | 'dm';
  setCurrentGame: (game: 'ocg' | 'dm') => void;
  setDmCurrentConversation: (conversation: Conversation | null) => void;
  setDmConversations: (conversations: Conversation[]) => void;
  addDmConversation: (conversation: Conversation) => void;
  addDmMessage: (message: Message) => void;
  updateDmLastAssistantMessage: (chunk: string) => void;
  setDmAssistantMessageContent: (messageId: string, content: string) => void;
  updateDmLastAssistantCitations: (citations: Citation[], sources?: RetrievalSource[]) => void;
  setDmMessages: (messages: Message[]) => void;
  setDmIsLoading: (loading: boolean) => void;
  setDmMetrics: (metrics: Metrics) => void;
  setDmSidebarTab: (tab: 'conversations' | 'documents' | 'metrics' | 'settings') => void;
  clearDmCurrentConversation: () => void;
}

export const useDmStore = create<DMState>((set) => ({
  dmCurrentConversation: null,
  dmConversations: [],
  dmMessages: [],
  dmIsLoading: false,
  dmMetrics: null,
  dmSidebarTab: 'conversations',
  currentGame: 'ocg',

  setCurrentGame: (game) => set({ currentGame: game }),
  setDmCurrentConversation: (conversation) => set({ dmCurrentConversation: conversation }),
  setDmConversations: (conversations) => set({ dmConversations: conversations }),
  addDmConversation: (conversation) => set((state) => ({
    dmConversations: [conversation, ...state.dmConversations]
  })),
  addDmMessage: (message) => set((state) => ({
    dmMessages: [...state.dmMessages, message]
  })),
  updateDmLastAssistantMessage: (chunk) => set((state) => {
    const msgs = [...state.dmMessages];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs[i] = { ...msgs[i], content: msgs[i].content + chunk };
        break;
      }
    }
    return { dmMessages: msgs };
  }),
  setDmAssistantMessageContent: (messageId: string, content: string) => set((state) => {
    const msgs = state.dmMessages.map((msg) =>
      msg.id === messageId ? { ...msg, content } : msg
    );
    return { dmMessages: msgs };
  }),
  updateDmLastAssistantCitations: (citations, sources) => set((state) => {
    const msgs = [...state.dmMessages];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === 'assistant') {
        msgs[i] = { ...msgs[i], citations, ...(sources ? { sources } : {}) };
        break;
      }
    }
    return { dmMessages: msgs };
  }),
  setDmMessages: (messages) => set({ dmMessages: messages }),
  setDmIsLoading: (loading) => set({ dmIsLoading: loading }),
  setDmMetrics: (metrics) => set({ dmMetrics: metrics }),
  setDmSidebarTab: (tab) => set({ dmSidebarTab: tab }),
  clearDmCurrentConversation: () => set({
    dmCurrentConversation: null,
    dmMessages: []
  }),
}));