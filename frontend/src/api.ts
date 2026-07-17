/* api.ts - Typed API Client for AHAL AI Backend */

export interface RepoRead {
  id: string;
  url: string;
  status: 'pending' | 'indexing' | 'ready' | 'failed';
  node_count?: number;
  edge_count?: number;
  commit_count?: number;
  created_at: string;
  updated_at: string;
}

export interface IndexJobRead {
  id: string;
  repo_id: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface PredictionItem {
  target: string;
  score: number;
  calibrated_score: number | null;
  basis: string;
}

export interface RepoCreateResponse {
  repo: RepoRead;
  job: IndexJobRead;
}

export interface CalibrationPoint {
  band: string;
  raw_confidence: number;
  calibrated_confidence: number;
  actual_hit_rate: number;
}

export interface RepoValidationReport {
  name: string;
  status: 'failed' | 'partial' | 'success';
  gating_cleared: boolean;
  commits_evaluated: number;
  precision: number;
  recall: number;
  tp: number;
  fp: number;
  fn: number;
  calibrator_status: string;
  reason: string;
  calibration_curve: CalibrationPoint[];
}

export interface ValidationReport {
  repos: RepoValidationReport[];
}

const BASE_URL = '/api/v1';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP Error: ${response.statusText} (${response.status})`);
  }
  return response.json();
}

export const api = {
  // List all repositories
  listRepos: async (): Promise<RepoRead[]> => {
    const res = await fetch(`${BASE_URL}/repos`);
    return handleResponse<RepoRead[]>(res);
  },

  // Get detailed repository status
  getRepo: async (id: string): Promise<RepoRead> => {
    const res = await fetch(`${BASE_URL}/repos/${id}`);
    return handleResponse<RepoRead>(res);
  },

  // Connect & index a new repository
  connectRepo: async (url: string): Promise<RepoCreateResponse> => {
    const res = await fetch(`${BASE_URL}/repos`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    });
    return handleResponse<RepoCreateResponse>(res);
  },

  // Get status of indexing job
  getJobStatus: async (repoId: string, jobId: string): Promise<IndexJobRead> => {
    const res = await fetch(`${BASE_URL}/repos/${repoId}/jobs/${jobId}`);
    return handleResponse<IndexJobRead>(res);
  },

  // Generate impact predictions
  predict: async (repoId: string, changedFiles: string[]): Promise<PredictionItem[]> => {
    const res = await fetch(`${BASE_URL}/repos/${repoId}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(changedFiles),
    });
    return handleResponse<PredictionItem[]>(res);
  },

  // Get chronological backtest validation report
  getValidationReport: async (): Promise<ValidationReport> => {
    const res = await fetch(`${BASE_URL}/repos/validation/report`);
    return handleResponse<ValidationReport>(res);
  },
};
