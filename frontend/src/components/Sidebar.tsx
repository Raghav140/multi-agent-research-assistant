import { Home, History, Activity, BarChart3, Settings, X, Menu } from 'lucide-react';
import { useConnection } from '../lib/connection-context';

interface SidebarProps {
  currentPage: string;
  onPageChange: (page: string) => void;
  isMobile: boolean;
  isOpen: boolean;
  onToggle: () => void;
}

export function Sidebar({ currentPage, onPageChange, isMobile, isOpen, onToggle }: SidebarProps) {
  const { connectionStatus } = useConnection();

  const menuItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home },
    { id: 'research', label: 'New Research', icon: Activity },
    { id: 'history', label: 'History', icon: History },
    { id: 'health', label: 'System Health', icon: BarChart3 },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  const getConnectionDisplay = () => {
    switch (connectionStatus) {
      case 'connected':
        return <span className="text-green-400">Connected</span>;
      case 'disconnected':
        return <span className="text-red-400">Disconnected</span>;
      default:
        return <span className="text-slate-400">Checking...</span>;
    }
  };

  if (isMobile) {
    return (
      <>
        {isOpen && (
          <div className="fixed inset-0 bg-black/50 z-40" onClick={onToggle} />
        )}
        <aside
          className={`fixed top-0 left-0 h-full w-64 bg-slate-900 border-r border-slate-800 flex flex-col z-50 transition-transform duration-300 ${
            isOpen ? 'translate-x-0' : '-translate-x-full'
          }`}
        >
          <div className="p-6 border-b border-slate-800 flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-white">Research Assistant</h1>
              <p className="text-sm text-slate-400 mt-1">Multi-Agent AI</p>
            </div>
            <button
              onClick={onToggle}
              className="text-slate-400 hover:text-white transition-colors"
              aria-label="Close menu"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          <nav className="flex-1 p-4">
            <ul className="space-y-2">
              {menuItems.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => {
                        onPageChange(item.id);
                        onToggle();
                      }}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                        currentPage === item.id
                          ? 'bg-blue-600 text-white'
                          : 'text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <Icon className="w-5 h-5" />
                      <span>{item.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </nav>

          <div className="p-4 border-t border-slate-800">
            <div className="text-xs text-slate-500">
              <p>Backend: {getConnectionDisplay()}</p>
            </div>
          </div>
        </aside>
      </>
    );
  }

  return (
    <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col hidden md:flex">
      <div className="p-6 border-b border-slate-800">
        <h1 className="text-xl font-bold text-white">Research Assistant</h1>
        <p className="text-sm text-slate-400 mt-1">Multi-Agent AI</p>
      </div>

      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <li key={item.id}>
                <button
                  onClick={() => onPageChange(item.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                    currentPage === item.id
                      ? 'bg-blue-600 text-white'
                      : 'text-slate-300 hover:bg-slate-800'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span>{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-4 border-t border-slate-800">
        <div className="text-xs text-slate-500">
          <p>Backend: {getConnectionDisplay()}</p>
        </div>
      </div>
    </aside>
  );
}

export function MobileHeader({ onToggle }: { onToggle: () => void }) {
  return (
    <header className="md:hidden bg-slate-900 border-b border-slate-800 p-4 flex items-center justify-between">
      <div>
        <h1 className="text-lg font-bold text-white">Research Assistant</h1>
        <p className="text-xs text-slate-400">Multi-Agent AI</p>
      </div>
      <button
        onClick={onToggle}
        className="text-slate-400 hover:text-white transition-colors"
        aria-label="Open menu"
      >
        <Menu className="w-6 h-6" />
      </button>
    </header>
  );
}
