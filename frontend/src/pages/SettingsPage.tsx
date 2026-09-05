import { useState } from 'react';
import { Save, RotateCcw } from 'lucide-react';

export function SettingsPage() {
  const [apiUrl, setApiUrl] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('apiUrl') || 'http://127.0.0.1:8000';
    }
    return 'http://127.0.0.1:8000';
  });
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    localStorage.setItem('apiUrl', apiUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    const defaultUrl = 'http://127.0.0.1:8000';
    setApiUrl(defaultUrl);
    localStorage.setItem('apiUrl', defaultUrl);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="p-4 md:p-8">
      <div className="max-w-2xl mx-auto">
        <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Settings</h2>

        <div className="space-y-4 md:space-y-6">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
            <h3 className="text-base md:text-lg font-semibold text-white mb-4">Backend Connection</h3>
            <div className="space-y-4">
              <div>
                <label htmlFor="apiUrl" className="block text-sm text-slate-400 mb-2">
                  API URL
                </label>
                <input
                  id="apiUrl"
                  type="text"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  placeholder="http://127.0.0.1:8000"
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm md:text-base"
                />
                <p className="text-xs text-slate-500 mt-2">
                  Requires page reload to take effect
                </p>
              </div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
            <h3 className="text-base md:text-lg font-semibold text-white mb-4">About</h3>
            <div className="space-y-2 text-xs md:text-sm text-slate-400">
              <p><span className="text-white">Multi-Agent Research Assistant</span></p>
              <p>Version: 1.0.0</p>
              <p>A research assistant powered by multiple AI agents and retrieval providers.</p>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              onClick={handleSave}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm md:text-base"
            >
              <Save className="w-4 h-4" />
              Save Settings
            </button>
            <button
              onClick={handleReset}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-slate-700 text-white rounded-lg hover:bg-slate-600 transition-colors text-sm md:text-base"
            >
              <RotateCcw className="w-4 h-4" />
              Reset to Default
            </button>
          </div>

          {saved && (
            <div className="bg-emerald-900/20 border border-emerald-800 rounded-lg p-4">
              <p className="text-emerald-400 text-sm md:text-base">Settings saved successfully!</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
