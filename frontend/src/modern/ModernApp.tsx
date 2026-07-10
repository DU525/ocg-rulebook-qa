import React, { useState } from 'react';
import ModernChatApp from './components/ModernChatApp';
import MaintenanceDashboard from '../components/MaintenanceDashboard';
import { PerformanceDashboard } from './components/PerformanceDashboard';

const ModernApp: React.FC = () => {
  const [currentGame, setCurrentGame] = useState<'ocg' | 'dm'>('ocg');
  const [showMaintenance, setShowMaintenance] = useState(false);

  if (showMaintenance) {
    return (
      <div className="min-h-screen">
        <MaintenanceDashboard onBack={() => setShowMaintenance(false)} />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <ModernChatApp 
        gameType={currentGame}
        onMaintenance={() => setShowMaintenance(true)}
      />
      <PerformanceDashboard />
    </div>
  );
};

export default ModernApp;
