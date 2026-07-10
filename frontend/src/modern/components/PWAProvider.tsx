import React, { useEffect, useState, createContext, useContext, ReactNode } from 'react';

interface PWAContextType {
  isInstallable: boolean;
  isInstalled: boolean;
  installPrompt: Event | null;
  installApp: () => Promise<void>;
  updateAvailable: boolean;
  applyUpdate: () => void;
  isOffline: boolean;
}

const PWAContext = createContext<PWAContextType | undefined>(undefined);

export const usePWA = () => {
  const context = useContext(PWAContext);
  if (!context) {
    throw new Error('usePWA must be used within a PWAProvider');
  }
  return context;
};

interface PWAProviderProps {
  children: ReactNode;
}

export const PWAProvider: React.FC<PWAProviderProps> = ({ children }) => {
  const [isInstallable, setIsInstallable] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [installPrompt, setInstallPrompt] = useState<Event | null>(null);
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  // 网络状态监听
  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Service Worker 注册
  useEffect(() => {
    if ('serviceWorker' in navigator && import.meta.env.PROD) {
      const registerServiceWorker = async () => {
        try {
          const swUrl = '/service-worker.js';
          const reg = await navigator.serviceWorker.register(swUrl);
          setRegistration(reg);
          
          console.log('[PWA] Service Worker 注册成功');
          
          // 检查更新
          reg.addEventListener('updatefound', () => {
            const newWorker = reg.installing;
            if (newWorker) {
              newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                  setUpdateAvailable(true);
                }
              });
            }
          });
        } catch (error) {
          console.error('[PWA] Service Worker 注册失败:', error);
        }
      };

      registerServiceWorker();
    }
  }, []);

  // PWA 安装提示监听
  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setInstallPrompt(e);
      setIsInstallable(true);
    };

    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt as EventListener);

    const handleAppInstalled = () => {
      setIsInstallable(false);
      setInstallPrompt(null);
      setIsInstalled(true);
      console.log('[PWA] 应用已安装');
    };

    window.addEventListener('appinstalled', handleAppInstalled);

    // 检查是否已安装
    if (window.matchMedia('(display-mode: standalone)').matches || 
        (window.navigator as any).standalone) {
      setIsInstalled(true);
    }

    return () => {
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt as EventListener);
      window.removeEventListener('appinstalled', handleAppInstalled);
    };
  }, []);

  const installApp = async () => {
    if (!installPrompt) {
      console.warn('[PWA] 没有可用的安装提示');
      return;
    }

    try {
      const promptEvent = installPrompt as any;
      promptEvent.prompt();
      
      const result = await promptEvent.userChoice;
      if (result.outcome === 'accepted') {
        setIsInstalled(true);
        setIsInstallable(false);
        setInstallPrompt(null);
        console.log('[PWA] 用户接受了安装');
      } else {
        console.log('[PWA] 用户拒绝了安装');
      }
    } catch (error) {
      console.error('[PWA] 安装失败:', error);
    }
  };

  const applyUpdate = () => {
    if (registration && registration.waiting) {
      registration.waiting.postMessage({ type: 'SKIP_WAITING' });
      window.location.reload();
    }
  };

  const value: PWAContextType = {
    isInstallable,
    isInstalled,
    installPrompt,
    installApp,
    updateAvailable,
    applyUpdate,
    isOffline
  };

  return (
    <PWAContext.Provider value={value}>
      {children}
    </PWAContext.Provider>
  );
};

export default PWAProvider;
