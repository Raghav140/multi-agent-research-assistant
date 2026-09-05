/** API types matching FastAPI backend responses */

export interface ResearchRequest {
  query: string;
}

export interface ResearchResponse {
  success: boolean;
  degraded?: boolean;
  answer: string;
  report: string;
  search_results: SearchResult[];
  papers: ResearchPaper[];
  execution_time_ms: number;
  request_id: string;
  cache_hit?: boolean | null;
  cache_metrics?: CacheMetrics | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface CacheMetrics {
  hits: number;
  memory_hits: number;
  total_variations: number;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet?: string;
  domain_score?: number;
  source_type?: 'web' | 'paper' | 'documentation';
  fusion_score?: number;
  semantic_similarity?: number;
  quality_score?: number;
  reliability_score?: number;
  freshness_score?: number;
  diversity_score?: number;
  overall_score?: number;
}

export interface ResearchPaper {
  title: string;
  authors?: string[];
  abstract?: string;
  url?: string;
  pdf_url?: string;
  published_date?: string;
  provider?: string;
  source_type?: 'paper';
}

export interface SystemHealth {
  status: string;
  timestamp?: number;
}

export interface ProvidersHealthResponse {
  providers: ProviderInfo[];
  ollama?: OllamaInfo;
}

export interface ProviderInfo {
  provider: string;
  health: ProviderHealth;
  circuit_breaker: CircuitBreaker;
}

export interface ProviderHealth {
  provider: string;
  is_healthy: boolean;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  consecutive_failures: number;
  consecutive_successes: number;
  success_rate: number;
  average_latency_ms: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  last_successful_request: number;
  last_failure: number;
}

export interface CircuitBreaker {
  provider: string;
  state: 'closed' | 'open' | 'half_open';
  failure_count: number;
  success_count: number;
  last_failure_time: number;
  cooldown_until: number;
  is_open: boolean;
  is_closed: boolean;
  is_half_open: boolean;
}

export interface OllamaInfo {
  provider: string;
  note: string;
}

export interface MetricsSummary {
  request_count: number;
  success_rate: number;
  average_latency_ms: number;
  provider_performance: Record<string, ProviderPerformance>;
  cache_hit_rate: number;
  cache_hits: number;
  cache_misses: number;
  memory_reuse: number;
  average_confidence: number;
  average_source_quality: number;
  average_evidence_diversity: number;
}

export interface ProviderPerformance {
  count: number;
  total_sources: number;
  total_execution_time: number;
  avg_sources: number;
  avg_execution_time_ms: number;
}

export interface MemoryHistoryResponse {
  records: MemoryRecord[];
  stats: MemoryStats;
}

export interface MemoryRecord {
  id: number;
  query: string;
  timestamp: number;
  execution_time_ms: number;
  sources_count: number;
  papers_count: number;
  confidence?: number;
  answer?: string;
}

export interface MemoryStats {
  total_records: number;
  oldest_record?: number;
  newest_record?: number;
}
