import { useEffect, useState } from 'react';
import { Activity, Clock, TrendingUp, CheckCircle, Database, Zap } from 'lucide-react';
import { apiClient } from '../lib/api-client';
import type { MetricsSummary } from '../types/api';

export function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadMetrics = async () => {
      try {
        const data = await apiClient.getMetricsSummary();
        setMetrics(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load metrics');
      } finally {
        setLoading(false);
      }
    };

    loadMetrics();
  }, []);

  const stats = metrics ? [
    {
      label: 'Total Requests',
      value: metrics.request_count.toString(),
      icon: Activity,
      color: 'text-blue-400',
    },
    {
      label: 'Avg Latency',
      value: `${(metrics.average_latency_ms / 1000).toFixed(2)}s`,
      icon: Clock,
      color: 'text-green-400',
    },
    {
      label: 'Success Rate',
      value: `${(metrics.success_rate * 100).toFixed(1)}%`,
      icon: TrendingUp,
      color: 'text-purple-400',
    },
    {
      label: 'Cache Hit Rate',
      value: `${(metrics.cache_hit_rate * 100).toFixed(1)}%`,
      icon: Database,
      color: 'text-emerald-400',
    },
  ] : [];

  const secondaryStats = metrics ? [
    {
      label: 'Memory Reuse',
      value: metrics.memory_reuse.toString(),
      icon: Zap,
      color: 'text-yellow-400',
    },
    {
      label: 'Avg Confidence',
      value: (metrics.average_confidence * 100).toFixed(1) + '%',
      icon: CheckCircle,
      color: 'text-cyan-400',
    },
    {
      label: 'Avg Source Quality',
      value: (metrics.average_source_quality * 100).toFixed(1) + '%',
      icon: TrendingUp,
      color: 'text-pink-400',
    },
    {
      label: 'Avg Evidence Diversity',
      value: (metrics.average_evidence_diversity * 100).toFixed(1) + '%',
      icon: Activity,
      color: 'text-orange-400',
    },
  ] : [];

  if (loading) {
    return (
      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Dashboard</h2>
          <div className="text-slate-400">Loading metrics...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Dashboard</h2>
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
        <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Dashboard</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 mb-6 md:mb-8">
          {stats.map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
                <div className="flex items-center justify-between mb-4">
                  <Icon className={`w-5 h-5 md:w-6 md:h-6 ${stat.color}`} />
                </div>
                <p className="text-2xl md:text-3xl font-bold text-white">{stat.value}</p>
                <p className="text-xs md:text-sm text-slate-400 mt-1">{stat.label}</p>
              </div>
            );
          })}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6 mb-6 md:mb-8">
          {secondaryStats.map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3 md:p-4">
                <div className="flex items-center gap-2 md:gap-3 mb-2">
                  <Icon className={`w-4 h-4 md:w-5 md:h-5 ${stat.color}`} />
                  <p className="text-xs md:text-sm text-slate-400">{stat.label}</p>
                </div>
                <p className="text-xl md:text-2xl font-bold text-white">{stat.value}</p>
              </div>
            );
          })}
        </div>

        {metrics && Object.keys(metrics.provider_performance).length > 0 && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
            <h3 className="text-base md:text-lg font-semibold text-white mb-4">Provider Performance</h3>
            <div className="space-y-3">
              {Object.entries(metrics.provider_performance).map(([provider, perf]) => (
                <div key={provider} className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 bg-slate-900 rounded-lg gap-2">
                  <div>
                    <p className="text-white font-medium capitalize text-sm md:text-base">{provider}</p>
                    <p className="text-xs md:text-sm text-slate-400">{perf.count} requests</p>
                  </div>
                  <div className="text-right">
                    <p className="text-white font-medium text-sm md:text-base">{perf.avg_execution_time_ms.toFixed(0)}ms avg</p>
                    <p className="text-xs md:text-sm text-slate-400">{perf.avg_sources.toFixed(1)} sources</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
