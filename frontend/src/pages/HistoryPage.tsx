import { useEffect, useState } from 'react';
import { Clock } from 'lucide-react';
import { apiClient } from '../lib/api-client';
import type { MemoryHistoryResponse } from '../types/api';

export function HistoryPage() {
  const [history, setHistory] = useState<MemoryHistoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadHistory = async () => {
      try {
        const data = await apiClient.getMemoryHistory(20);
        setHistory(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load history');
      } finally {
        setLoading(false);
      }
    };

    loadHistory();
  }, []);

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString();
  };

  if (loading) {
    return (
      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Research History</h2>
          <div className="text-slate-400">Loading history...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 md:p-8">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Research History</h2>
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
        <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">Research History</h2>

        {history && history.stats && (
          <div className="mb-4 md:mb-6 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs md:text-sm text-slate-400">
            <span>Total Records: {history.stats.total_records}</span>
            {history.stats.newest_record && (
              <span>Latest: {formatDate(history.stats.newest_record)}</span>
            )}
          </div>
        )}

        {history && history.records.length > 0 ? (
          <div className="space-y-3 md:space-y-4">
            {history.records.map((record) => (
              <div key={record.id} className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6 hover:bg-slate-750 transition-colors">
                <div className="flex flex-col gap-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-white font-medium mb-2 line-clamp-2 text-sm md:text-base">{record.query}</h3>
                    <div className="flex flex-wrap items-center gap-2 md:gap-4 text-xs md:text-sm text-slate-400 mb-2 md:mb-3">
                      <div className="flex items-center gap-1">
                        <Clock className="w-3 h-3 md:w-4 md:h-4" />
                        <span>{formatDate(record.timestamp)}</span>
                      </div>
                      <span>{(record.execution_time_ms / 1000).toFixed(2)}s</span>
                      <span>{record.sources_count} sources</span>
                      {record.papers_count > 0 && (
                        <span>{record.papers_count} papers</span>
                      )}
                      {record.confidence && (
                        <span>Confidence: {(record.confidence * 100).toFixed(0)}%</span>
                      )}
                    </div>
                    {record.answer && (
                      <p className="text-xs md:text-sm text-slate-300 line-clamp-3">{record.answer}</p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-4 md:p-6">
            <p className="text-slate-400 text-sm md:text-base">No research history yet. Start a new research query to see results here.</p>
          </div>
        )}
      </div>
    </div>
  );
}
