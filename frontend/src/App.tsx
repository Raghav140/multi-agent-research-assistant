import { useState, useEffect } from 'react';
import { Sidebar, MobileHeader } from './components/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { ResearchPage } from './pages/ResearchPage';
import { HistoryPage } from './pages/HistoryPage';
import { HealthPage } from './pages/HealthPage';
import { SettingsPage } from './pages/SettingsPage';
import { ConnectionProvider } from './lib/connection-context';

function App() {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  const handlePageChange = (page: string) => {
    setCurrentPage(page);
  };

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  return (
    <ConnectionProvider>
      <div className="min-h-screen bg-slate-950 flex flex-col md:flex-row">
        <MobileHeader onToggle={toggleMobileMenu} />
        <Sidebar
          currentPage={currentPage}
          onPageChange={handlePageChange}
          isMobile={isMobile}
          isOpen={isMobileMenuOpen}
          onToggle={toggleMobileMenu}
        />
        <main className="flex-1 overflow-auto">
          {currentPage === 'dashboard' && <DashboardPage />}
          {currentPage === 'research' && <ResearchPage />}
          {currentPage === 'history' && <HistoryPage />}
          {currentPage === 'health' && <HealthPage />}
          {currentPage === 'settings' && <SettingsPage />}
        </main>
      </div>
    </ConnectionProvider>
  );
}

export default App;