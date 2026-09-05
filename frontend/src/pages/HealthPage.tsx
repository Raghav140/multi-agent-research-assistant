import { useEffect, useState } from 'react';
import { apiClient } from '../lib/api-client';
import type { ProvidersHealthResponse } from '../types/api';

export function HealthPage() {
  const [healthData, setHealthData] = useState<ProvidersHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadHealth = async () => {
      try {
        const data = await apiClient.getProvidersHealth();
        setHealthData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load health data');
      } finally {
        setLoading(false);
      }
    };

    loadHealth();
  }, []);

  if (loading) {
    return (
      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">System Health</h2>
          <div className="text-slate-400">Loading health status...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">System Health</h2>
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
            <p className="text-red-400">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-8">
      <div className="max-w-6xl mx-auto">
        <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">System Health</h2>

        {healthData && (
          <div className="space-y-4 md:space-y-6">
            {healthData.providers.map((provider) => (
              <div key={provider.provider} className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 gap-2">
                  <h3 className="text-base md:text-lg font-semibold text-white capitalize">{provider.provider}</h3>
                  <span className={`px-3 py-1 rounded-full text-xs md:text-sm ${
                    provider.health.is_healthy
                      ? 'bg-green-900/30 text-green-400'
                      : 'bg-red-900/30 text-red-400'
                  }`}>
                    {provider.health.is_healthy ? 'Healthy' : 'Unhealthy'}
                  </span>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4 mb-4">
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Requests</p>
                    <p className="text-white font-medium text-sm md:text-base">{provider.health.total_requests}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Success Rate</p>
                    <p className="text-white font-medium text-sm md:text-base">{(provider.health.success_rate * 100).toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Avg Latency</p>
                    <p className="text-white font-medium text-sm md:text-base">{provider.health.average_latency_ms.toFixed(0)}ms</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Failures</p>
                    <p className="text-white font-medium text-sm md:text-base">{provider.health.failed_requests}</p>
                  </div>
                </div>

                <div className="flex items-center justify-between p-3 bg-slate-900 rounded-lg">
                  <div>
                    <p className="text-xs md:text-sm text-slate-400">Circuit Breaker</p>
                    <p className="text-white font-medium capitalize text-sm md:text-base">{provider.circuit_breaker.state.replace('_', ' ')}</p>
                  </div>
                  <div className={`w-3 h-3 rounded-full ${
                    provider.circuit_breaker.state === 'closed'
                      ? 'bg-green-400'
                      : provider.circuit_breaker.state === 'open'
                      ? 'bg-red-400'
                      : 'bg-yellow-400'
                  }`} />
                </div>
              </div>
            ))}

            {healthData.ollama && (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
                <h3 className="text-base md:text-lg font-semibold text-white mb-2">Ollama</h3>
                <p className="text-xs md:text-sm text-slate-400">{healthData.ollama.note}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
