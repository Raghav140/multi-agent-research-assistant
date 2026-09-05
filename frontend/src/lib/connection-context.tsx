/** Connection status context for backend availability tracking */
/* eslint-disable react-refresh/only-export-components */
import { useState, useEffect, createContext, useContext, useCallback } from 'react';
import { apiClient } from './api-client';

export type ConnectionStatus = 'connected' | 'disconnected' | 'unknown';

interface ConnectionContextType {
  connectionStatus: ConnectionStatus;
  setConnectionStatus: (status: ConnectionStatus) => void;
  checkConnection: () => Promise<void>;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export function useConnection() {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnection must be used within ConnectionProvider');
  }
  return context;
}

export function ConnectionProvider({ children }: { children: React.ReactNode }) {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('unknown');

  const checkConnection = useCallback(async () => {
    try {
      await apiClient.getSystemHealth();
      setConnectionStatus('connected');
    } catch (error) {
      // Only mark as disconnected if it's a network/connection error
      if (error instanceof Error && (error.message.includes('Failed to fetch') || error.message.includes('ECONNREFUSED') || error.message.includes('timeout'))) {
        setConnectionStatus('disconnected');
      }
    }
  }, []);

  useEffect(() => {
    // Initial check
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkConnection();

    // Poll every 30 seconds
    const interval = setInterval(checkConnection, 30000);

    return () => clearInterval(interval);
  }, [checkConnection]);

  return (
    <ConnectionContext.Provider value={{ connectionStatus, setConnectionStatus, checkConnection }}>
      {children}
    </ConnectionContext.Provider>
  );
}
