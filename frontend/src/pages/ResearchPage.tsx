import { useState } from 'react';
import { Send, X, Loader2, ExternalLink, Clock, FileText } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiClient } from '../lib/api-client';
import { useConnection } from '../lib/connection-context';
import type { ResearchResponse } from '../types/api';

export function ResearchPage() {
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ResearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { setConnectionStatus } = useConnection();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.research({ query });
      setResult(response);
      // If research succeeds, backend is connected
      setConnectionStatus('connected');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Research failed');
      // Mark as disconnected if it's a network error
      if (err instanceof Error && (err.message.includes('Failed to fetch') || err.message.includes('ECONNREFUSED') || err.message.includes('timeout'))) {
        setConnectionStatus('disconnected');
      }
    } finally {
      setLoading(false);
    }
  };

  const exampleQueries = [
    'What is artificial intelligence?',
    'How does FastAPI dependency injection work?',
    'Latest advances in quantum computing',
  ];

  const getSourceTypeColor = (sourceType?: string) => {
    switch (sourceType) {
      case 'web':
        return 'text-blue-400';
      case 'paper':
        return 'text-purple-400';
      case 'documentation':
        return 'text-emerald-400';
      default:
        return 'text-slate-400';
    }
  };

  return (
    <div className="p-4 md:p-8">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">New Research</h2>

        <form onSubmit={handleSubmit} className="mb-6 md:mb-8">
          <div className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your research question..."
              className="w-full h-32 md:h-40 bg-slate-800 border border-slate-700 rounded-lg p-4 text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none text-sm md:text-base"
              disabled={loading}
            />
            <div className="absolute bottom-4 right-4 flex gap-2">
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="p-2 text-slate-400 hover:text-white transition-colors"
                  disabled={loading}
                  aria-label="Clear input"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                aria-label="Submit research query"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </div>
        </form>

        {!query && !result && (
          <div className="mb-6 md:mb-8">
            <p className="text-sm text-slate-400 mb-3">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {exampleQueries.map((example) => (
                <button
                  key={example}
                  onClick={() => setQuery(example)}
                  className="px-3 md:px-4 py-2 bg-slate-800 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors text-xs md:text-sm"
                  disabled={loading}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 mb-6">
            <div className="flex flex-col items-center justify-center gap-4">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
              <p className="text-slate-300">Researching your query...</p>
              <p className="text-sm text-slate-400">This may take up to 30 seconds</p>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-900/20 border border-red-800 rounded-lg p-4 mb-6">
            <p className="text-red-400">{error}</p>
          </div>
        )}

        {result && (
          <div className="space-y-6">
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-white">Research Report</h3>
                <div className="flex items-center gap-2 text-sm text-slate-400">
                  <Clock className="w-4 h-4" />
                  <span>{(result.execution_time_ms / 1000).toFixed(2)}s</span>
                </div>
              </div>
              <div className="prose prose-invert prose-sm max-w-none prose-headings:text-white prose-headings:font-semibold prose-a:text-blue-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-white prose-code:text-blue-300 prose-pre:bg-slate-900 prose-pre:border prose-pre:border-slate-700">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.report}
                </ReactMarkdown>
              </div>
            </div>

            {(result.search_results.length > 0 || result.papers.length > 0) && (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
                <h3 className="text-lg font-semibold text-white mb-4">
                  Sources ({result.search_results.length + result.papers.length})
                </h3>
                <div className="space-y-3">
                  {result.search_results.map((source, index) => (
                    <div key={`web-${index}`} className="p-4 bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1"
                          >
                            {source.title}
                            <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          </a>
                          {source.snippet && (
                            <p className="text-sm text-slate-400 mt-2 line-clamp-2">{source.snippet}</p>
                          )}
                          <div className="flex items-center gap-3 mt-2 text-xs">
                            {source.source_type && (
                              <span className={`px-2 py-1 rounded bg-slate-800 ${getSourceTypeColor(source.source_type)}`}>
                                {source.source_type}
                              </span>
                            )}
                            {source.overall_score && (
                              <span className="text-slate-400">
                                Relevance: {(source.overall_score * 100).toFixed(0)}%
                              </span>
                            )}
                            {source.semantic_similarity && (
                              <span className="text-slate-400">
                                Similarity: {(source.semantic_similarity * 100).toFixed(0)}%
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}

                  {result.papers.map((paper, index) => (
                    <div key={`paper-${index}`} className="p-4 bg-slate-900 rounded-lg hover:bg-slate-800 transition-colors border-l-2 border-purple-500">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <FileText className="w-4 h-4 text-purple-400 flex-shrink-0" />
                            <span className="text-xs px-2 py-1 rounded bg-purple-900/30 text-purple-400">
                              Academic Paper
                            </span>
                          </div>
                          {(paper.url || paper.pdf_url) && (
                            <a
                              href={paper.url || paper.pdf_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-400 hover:text-blue-300 font-medium flex items-center gap-1"
                            >
                              {paper.title}
                              <ExternalLink className="w-3 h-3 flex-shrink-0" />
                            </a>
                          )}
                          {!paper.url && !paper.pdf_url && (
                            <p className="text-white font-medium">{paper.title}</p>
                          )}
                          {paper.authors && paper.authors.length > 0 && (
                            <p className="text-sm text-slate-400 mt-1">
                              {paper.authors.slice(0, 3).join(', ')}
                              {paper.authors.length > 3 && ' et al.'}
                            </p>
                          )}
                          {paper.abstract && (
                            <p className="text-sm text-slate-400 mt-2 line-clamp-2">{paper.abstract}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs text-slate-500">
              <p>Request ID: {result.request_id}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
