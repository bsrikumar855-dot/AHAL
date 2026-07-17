import { useState, useEffect, useRef } from 'react';
import { 
  Plus, 
  RefreshCw, 

  GitBranch, 
  Activity, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  HelpCircle,
  Play,
  FileSearch
} from 'lucide-react';
import { 
  ResponsiveContainer, 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend 
} from 'recharts';
import { api } from './api';
import type { RepoRead, PredictionItem, ValidationReport, IndexJobRead } from './api';


type Tab = 'repos' | 'validation' | 'timeline';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('repos');
  const [repos, setRepos] = useState<RepoRead[]>([]);
  const [validationReport, setValidationReport] = useState<ValidationReport | null>(null);
  
  // Selected repo for detailed view & prediction
  const [selectedRepo, setSelectedRepo] = useState<RepoRead | null>(null);
  const [activeJob, setActiveJob] = useState<IndexJobRead | null>(null);
  
  // Connect repo modal
  const [showConnectModal, setShowConnectModal] = useState(false);
  const [repoUrlInput, setRepoUrlInput] = useState('');
  const [connectLoading, setConnectLoading] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  // Predictions
  const [changedFilesInput, setChangedFilesInput] = useState('');
  const [predictions, setPredictions] = useState<PredictionItem[]>([]);
  const [predictLoading, setPredictLoading] = useState(false);
  const [predictError, setPredictError] = useState<string | null>(null);
  const [hasRunPredict, setHasRunPredict] = useState(false);

  // Global UI status
  const [reposLoading, setReposLoading] = useState(false);
  const [reposError, setReposError] = useState<string | null>(null);
  const [validationLoading, setValidationLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const pollIntervalRef = useRef<number | null>(null);

  // Load repositories on startup
  useEffect(() => {
    fetchRepos();
    fetchValidation();
  }, []);

  // Poll for active indexing job if any
  useEffect(() => {
    if (activeJob && (activeJob.status === 'pending' || activeJob.status === 'running')) {
      startJobPolling(activeJob.repo_id, activeJob.id);
    } else {
      stopJobPolling();
    }
    return () => stopJobPolling();
  }, [activeJob]);

  const fetchRepos = async () => {
    setReposLoading(true);
    setReposError(null);
    try {
      const data = await api.listRepos();
      setRepos(data);
      
      // Update selected repo if it is currently open
      if (selectedRepo) {
        const updated = data.find(r => r.id === selectedRepo.id);
        if (updated) {
          setSelectedRepo(updated);
        }
      }
    } catch (err: any) {
      setReposError(err.message || 'Failed to fetch repositories');
    } finally {
      setReposLoading(false);
    }
  };

  const fetchValidation = async () => {
    setValidationLoading(true);
    setValidationError(null);
    try {
      const data = await api.getValidationReport();
      setValidationReport(data);
    } catch (err: any) {
      setValidationError(err.message || 'Failed to load validation report');
    } finally {
      setValidationLoading(false);
    }
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoUrlInput.trim()) return;

    setConnectLoading(true);
    setConnectError(null);
    try {
      const res = await api.connectRepo(repoUrlInput.trim());
      setRepos(prev => [res.repo, ...prev]);
      setShowConnectModal(false);
      setRepoUrlInput('');
      
      // Set as active job to watch progress
      setActiveJob(res.job);
      setSelectedRepo(res.repo);
    } catch (err: any) {
      setConnectError(err.message || 'Failed to connect repository');
    } finally {
      setConnectLoading(false);
    }
  };

  const startJobPolling = (repoId: string, jobId: string) => {
    stopJobPolling();
    pollIntervalRef.current = window.setInterval(async () => {
      try {
        const job = await api.getJobStatus(repoId, jobId);
        setActiveJob(job);
        
        if (job.status === 'succeeded' || job.status === 'failed') {
          stopJobPolling();
          // Reload repos to update ready state
          fetchRepos();
        }
      } catch (err) {
        console.error('Job polling failed', err);
        stopJobPolling();
      }
    }, 2000);
  };

  const stopJobPolling = () => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  };

  const handlePredict = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRepo || !changedFilesInput.trim()) return;

    const files = changedFilesInput
      .split(/[\n,]+/)
      .map(f => f.trim())
      .filter(Boolean);

    if (files.length === 0) return;

    setPredictLoading(true);
    setPredictError(null);
    setHasRunPredict(true);
    try {
      const results = await api.predict(selectedRepo.id, files);
      setPredictions(results);
    } catch (err: any) {
      setPredictError(err.message || 'Prediction call failed');
      setPredictions([]);
    } finally {
      setPredictLoading(false);
    }
  };

  const selectRepoForDetail = (repo: RepoRead) => {
    setSelectedRepo(repo);
    setPredictions([]);
    setChangedFilesInput('');
    setHasRunPredict(false);
    setPredictError(null);
    setActiveJob(null);
    // If the repo is indexing or pending, check if we have a job to watch
    if (repo.status === 'indexing' || repo.status === 'pending') {
      // Set dummy job to trigger fetching of real status
      setActiveJob({
        id: 'active-index-job',
        repo_id: repo.id,
        status: repo.status === 'indexing' ? 'running' : 'pending',
        created_at: '',
        updated_at: ''
      });
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      
      {/* NAVBAR */}
      <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-indigo-600/20 text-indigo-400 p-2 rounded-lg border border-indigo-500/30">
              <Activity className="h-6 w-6 animate-pulse" />
            </div>
            <span className="font-bold text-xl tracking-tight">
              AHAL <span className="text-cyan-400">AI</span>
            </span>
          </div>

          <nav className="flex space-x-1">
            <button
              onClick={() => { setActiveTab('repos'); setSelectedRepo(null); }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeTab === 'repos'
                  ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              Repositories
            </button>
            <button
              onClick={() => { setActiveTab('validation'); setSelectedRepo(null); }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeTab === 'validation'
                  ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              Validation Suite
            </button>
            <button
              onClick={() => { setActiveTab('timeline'); setSelectedRepo(null); }}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeTab === 'timeline'
                  ? 'bg-indigo-600/15 text-indigo-300 border border-indigo-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
              }`}
            >
              Incident Timeline
            </button>
          </nav>
        </div>
      </header>

      {/* CONTAINER */}
      <main className="flex-grow max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        
        {/* REPOS VIEW */}
        {activeTab === 'repos' && !selectedRepo && (
          <div>
            <div className="flex justify-between items-center mb-8">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Connected Repositories</h1>
                <p className="text-slate-400 text-sm mt-1">Manage, index, and analyze repositories for blast-radius predictions.</p>
              </div>
              <button
                onClick={() => setShowConnectModal(true)}
                className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-2 px-4 rounded-lg transition-colors shadow-lg shadow-indigo-600/20"
              >
                <Plus className="h-4 w-4" />
                Connect Repository
              </button>
            </div>

            {reposError && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg flex items-center gap-3 mb-6">
                <AlertCircle className="h-5 w-5 shrink-0" />
                <span>{reposError}</span>
                <button onClick={fetchRepos} className="ml-auto text-sm underline hover:no-underline">Retry</button>
              </div>
            )}

            {reposLoading && repos.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
                <RefreshCw className="h-8 w-8 animate-spin text-indigo-500" />
                <span className="text-sm">Fetching repositories...</span>
              </div>
            ) : repos.length === 0 ? (
              <div className="text-center py-20 border border-dashed border-slate-800 rounded-xl bg-slate-900/20">
                <FileSearch className="h-12 w-12 text-slate-600 mx-auto mb-4" />
                <h3 className="font-semibold text-lg text-slate-300">No repositories connected</h3>
                <p className="text-slate-500 text-sm mt-1 mb-6">Connect your first git repository to start indexing code change relationships.</p>
                <button
                  onClick={() => setShowConnectModal(true)}
                  className="bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-800 py-2 px-4 rounded-lg transition-colors inline-flex items-center gap-2"
                >
                  <Plus className="h-4 w-4" />
                  Connect Repository
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {repos.map(repo => (
                  <div
                    key={repo.id}
                    onClick={() => selectRepoForDetail(repo)}
                    className="group bg-slate-900/40 hover:bg-slate-900/70 border border-slate-800 hover:border-slate-700/80 rounded-xl p-5 cursor-pointer transition-all duration-200 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex justify-between items-start gap-4 mb-2">
                        <h3 className="font-semibold text-lg tracking-tight truncate group-hover:text-indigo-400 transition-colors">
                          {repo.url.split('/').pop()?.replace('.git', '') || 'Repository'}
                        </h3>
                        <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${
                          repo.status === 'ready'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : repo.status === 'indexing'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse'
                            : repo.status === 'pending'
                            ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                            : 'bg-red-500/10 text-red-400 border-red-500/20'
                        }`}>
                          {repo.status}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 break-all mb-6">{repo.url}</p>
                    </div>

                    <div className="flex justify-between items-center text-xs text-slate-400 border-t border-slate-800/80 pt-4 mt-auto">
                      <div className="flex gap-4">
                        <span>Nodes: <strong className="text-slate-300">{repo.node_count ?? 0}</strong></span>
                        <span>Edges: <strong className="text-slate-300">{repo.edge_count ?? 0}</strong></span>
                      </div>
                      <span className="text-slate-500">Commits: {repo.commit_count ?? 0}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* REPO DETAIL VIEW */}
        {activeTab === 'repos' && selectedRepo && (
          <div>
            <div className="mb-6 flex items-center gap-2 text-sm text-slate-400">
              <button onClick={() => setSelectedRepo(null)} className="hover:text-indigo-400 transition-colors">Repositories</button>
              <span>/</span>
              <span className="text-slate-200">{selectedRepo.url.split('/').pop()?.replace('.git', '')}</span>
            </div>

            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 mb-8 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <div className="flex items-center gap-3 mb-2 flex-wrap">
                  <h1 className="text-2xl font-bold tracking-tight">{selectedRepo.url.split('/').pop()?.replace('.git', '')}</h1>
                  <span className={`px-2 py-0.5 text-xs font-semibold rounded-full border ${
                    selectedRepo.status === 'ready'
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : selectedRepo.status === 'indexing'
                      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse'
                      : selectedRepo.status === 'pending'
                      ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                      : 'bg-red-500/10 text-red-400 border-red-500/20'
                  }`}>
                    {selectedRepo.status}
                  </span>
                </div>
                <p className="text-sm text-slate-500 break-all">{selectedRepo.url}</p>
              </div>

              <div className="flex gap-6 shrink-0">
                <div className="text-center px-4 py-2 border border-slate-800 rounded-lg bg-slate-950/40">
                  <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Nodes</div>
                  <div className="text-xl font-bold text-indigo-400 mt-1">{selectedRepo.node_count ?? 0}</div>
                </div>
                <div className="text-center px-4 py-2 border border-slate-800 rounded-lg bg-slate-950/40">
                  <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Edges</div>
                  <div className="text-xl font-bold text-cyan-400 mt-1">{selectedRepo.edge_count ?? 0}</div>
                </div>
                <div className="text-center px-4 py-2 border border-slate-800 rounded-lg bg-slate-950/40">
                  <div className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Commits</div>
                  <div className="text-xl font-bold text-slate-200 mt-1">{selectedRepo.commit_count ?? 0}</div>
                </div>
              </div>
            </div>

            {/* INDEXING JOB STATUS */}
            {activeJob && (activeJob.status === 'pending' || activeJob.status === 'running') && (
              <div className="bg-amber-600/10 border border-amber-500/20 text-amber-300 p-5 rounded-xl flex items-center gap-4 mb-8">
                <RefreshCw className="h-6 w-6 animate-spin text-amber-400 shrink-0" />
                <div>
                  <h4 className="font-semibold text-sm">Indexing process is actively running</h4>
                  <p className="text-xs text-amber-400/80 mt-0.5">
                    Analyzing imports and commit co-changes. This view will update automatically upon completion.
                  </p>
                </div>
              </div>
            )}

            {/* PREDICT PANEL */}
            {selectedRepo.status === 'ready' && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                
                {/* Form Input */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6 h-fit">
                  <h3 className="font-bold text-lg mb-4 flex items-center gap-2">
                    <span>🔮 Predict Blast-Radius</span>
                  </h3>
                  <form onSubmit={handlePredict} className="space-y-4">
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                        Changed File Paths
                      </label>
                      <textarea
                        rows={6}
                        value={changedFilesInput}
                        onChange={(e) => setChangedFilesInput(e.target.value)}
                        placeholder="e.g.&#10;ahal/extract.py&#10;backend/app/main.py"
                        className="w-full bg-slate-950 border border-slate-850 rounded-lg p-3 text-sm font-mono text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
                      />
                    </div>
                    <button
                      type="submit"
                      disabled={predictLoading || !changedFilesInput.trim()}
                      className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-semibold py-2.5 px-4 rounded-lg transition-colors shadow-lg shadow-indigo-600/20"
                    >
                      {predictLoading ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" />
                          Analyzing Code...
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4 fill-current" />
                          Generate Predictions
                        </>
                      )}
                    </button>
                  </form>
                </div>

                {/* Predictions Results list */}
                <div className="lg:col-span-2 space-y-4">
                  <h3 className="font-bold text-lg text-slate-300">Verified Predictions Surface</h3>
                  
                  {predictError && (
                    <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg flex items-center gap-3">
                      <AlertCircle className="h-5 w-5 shrink-0" />
                      <span>{predictError}</span>
                    </div>
                  )}

                  {!hasRunPredict && (
                    <div className="flex flex-col items-center justify-center py-24 border border-slate-850 bg-slate-900/10 rounded-xl text-slate-500">
                      <FileText className="h-10 w-10 text-slate-700 mb-3" />
                      <p className="text-sm">Enter changed files in the left console to generate verification blast-radius output.</p>
                    </div>
                  )}

                  {hasRunPredict && !predictLoading && predictions.length === 0 && (
                    <div className="flex flex-col items-center justify-center py-24 border border-slate-850 bg-slate-900/10 rounded-xl text-slate-500">
                      <XCircle className="h-10 w-10 text-slate-700 mb-3" />
                      <p className="text-sm">No predictions met the verification guidelines. All candidate results dropped.</p>
                    </div>
                  )}

                  {hasRunPredict && !predictLoading && predictions.length > 0 && (
                    <div className="space-y-4">
                      {predictions.map((p, idx) => (
                        <div key={idx} className="bg-slate-900/50 border border-slate-850 hover:border-slate-800 rounded-xl p-5 flex flex-col md:flex-row justify-between gap-4 transition-all duration-200">
                          
                          {/* Left: Component & Basis */}
                          <div className="space-y-2">
                            <h4 className="font-bold text-indigo-400 text-lg tracking-tight break-all">
                              {p.target}
                            </h4>
                            
                            {/* Visual emphasis on Basis */}
                            <div className="bg-slate-950/60 border border-slate-800 rounded-lg p-3 text-sm text-slate-300 flex items-start gap-2">
                              <GitBranch className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
                              <div>
                                <span className="text-xs uppercase font-semibold text-cyan-500 block mb-1">Prediction Basis</span>
                                <span>{p.basis}</span>
                              </div>
                            </div>
                          </div>

                          {/* Right: Scores */}
                          <div className="flex md:flex-col justify-between md:justify-center md:items-end gap-2 shrink-0 border-t md:border-t-0 border-slate-800/80 pt-3 md:pt-0">
                            <div>
                              <span className="text-xs text-slate-500 uppercase font-semibold block">Raw Score</span>
                              <span className="text-sm font-bold text-amber-500">{(p.score * 100).toFixed(1)}%</span>
                            </div>
                            <div className="md:text-right">
                              <span className="text-xs text-slate-500 uppercase font-semibold block">Calibrated Confidence</span>
                              <span className="text-lg font-extrabold text-emerald-400">
                                {p.calibrated_score !== null ? `${(p.calibrated_score * 100).toFixed(1)}%` : 'N/A'}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}

                      {/* Disclaimer banner */}
                      <div className="bg-amber-500/5 border border-amber-500/20 text-slate-400 text-xs p-3 rounded-lg flex items-center gap-2">
                        <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
                        <span>Proposed-protocol evaluation output — not a validated production accuracy claim.</span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* VALIDATION VIEW */}
        {activeTab === 'validation' && (
          <div>
            <div className="flex justify-between items-center mb-6">
              <div>
                <h1 className="text-2xl font-bold tracking-tight">Chronological Backtest Validation Suite</h1>
                <p className="text-slate-400 text-sm mt-1">Section 6 backtest results replaying merge history with fit/eval split.</p>
              </div>
              <span className="px-3 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs font-semibold rounded-full uppercase tracking-wider">
                Proposed-Protocol Outputs
              </span>
            </div>

            {validationError && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg flex items-center gap-3 mb-6">
                <AlertCircle className="h-5 w-5 shrink-0" />
                <span>{validationError}</span>
                <button onClick={fetchValidation} className="ml-auto text-sm underline hover:no-underline">Retry</button>
              </div>
            )}

            {validationLoading && !validationReport ? (
              <div className="flex flex-col items-center justify-center py-20 text-slate-400 gap-3">
                <RefreshCw className="h-8 w-8 animate-spin text-indigo-500" />
                <span className="text-sm">Loading validation metrics...</span>
              </div>
            ) : validationReport ? (
              <div className="space-y-12">
                
                {/* Repos comparison Table */}
                <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
                  <div className="px-6 py-4 border-b border-slate-800 bg-slate-900/20">
                    <h3 className="font-bold text-lg">Stage 1 Gating Gird</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 bg-slate-950/20 text-slate-400 font-semibold">
                          <th className="p-4">Repository</th>
                          <th className="p-4">Commits</th>
                          <th className="p-4">Precision</th>
                          <th className="p-4">Recall</th>
                          <th className="p-4">Calibrator Status</th>
                          <th className="p-4 text-center">Gating Threshold</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/80">
                        {validationReport.repos.map((repo, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/10 transition-colors">
                            <td className="p-4 font-semibold text-slate-200">{repo.name}</td>
                            <td className="p-4 text-slate-400">{repo.commits_evaluated}</td>
                            <td className="p-4 text-amber-500 font-medium">{(repo.precision * 100).toFixed(1)}%</td>
                            <td className="p-4 text-cyan-400 font-medium">{(repo.recall * 100).toFixed(1)}%</td>
                            <td className="p-4 text-xs text-slate-400 font-mono">{repo.calibrator_status}</td>
                            <td className="p-4 text-center">
                              <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-semibold rounded-full border ${
                                repo.gating_cleared
                                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                                  : 'bg-red-500/10 text-red-400 border-red-500/20'
                              }`}>
                                {repo.gating_cleared ? (
                                  <>
                                    <CheckCircle2 className="h-3 w-3" />
                                    Cleared
                                  </>
                                ) : (
                                  <>
                                    <XCircle className="h-3 w-3" />
                                    Failed
                                  </>
                                )}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Side-by-side Repo Cards displaying failures as first-class */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {validationReport.repos.map((repo, idx) => (
                    <div 
                      key={idx} 
                      className={`bg-slate-900/40 border rounded-xl p-5 flex flex-col justify-between ${
                        repo.gating_cleared ? 'border-slate-800' : 'border-red-900/30 bg-red-950/5'
                      }`}
                    >
                      <div>
                        <div className="flex justify-between items-start gap-3 mb-3">
                          <h4 className="font-bold text-slate-200">{repo.name}</h4>
                          <span className={`px-2 py-0.5 text-2xs font-semibold rounded-full uppercase tracking-wider ${
                            repo.gating_cleared
                              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                              : 'bg-red-500/10 text-red-400 border border-red-500/20'
                          }`}>
                            {repo.gating_cleared ? 'Pass' : 'Fail'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 leading-relaxed mb-6">{repo.reason}</p>
                      </div>

                      <div className="flex gap-4 text-xs border-t border-slate-850 pt-4 mt-auto">
                        <div>
                          <span className="text-slate-500">TP/FP:</span>{' '}
                          <strong className="text-slate-300">{repo.tp}</strong>
                          <span className="text-slate-500">/</span>
                          <strong className="text-slate-300">{repo.fp}</strong>
                        </div>
                        <div>
                          <span className="text-slate-500">FN:</span>{' '}
                          <strong className="text-slate-300">{repo.fn}</strong>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                {/* THE KEY CHART SECTION */}
                <div>
                  <h3 className="font-bold text-lg mb-2">Isotonic Calibration Curves</h3>
                  <p className="text-slate-400 text-sm mb-6">
                    Three-series visualization showing Raw predicted score, the Actual hit rate, and the Calibrated curve.
                  </p>

                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {validationReport.repos.map((repo, idx) => {
                      const hasCurve = repo.calibration_curve && repo.calibration_curve.length > 0;
                      
                      const chartData = hasCurve 
                        ? repo.calibration_curve.map(point => ({
                            name: point.band,
                            'Raw predicted confidence': point.raw_confidence * 100,
                            'Calibrated confidence': point.calibrated_confidence * 100,
                            'Actual held-out hit rate': point.actual_hit_rate * 100
                          }))
                        : [];

                      return (
                        <div key={idx} className="bg-slate-900/40 border border-slate-800 rounded-xl p-5 flex flex-col">
                          <div className="flex justify-between items-center mb-6">
                            <h4 className="font-bold text-slate-200 text-sm">{repo.name} Curve</h4>
                            <span className="text-2xs text-slate-500 uppercase tracking-wider font-mono">
                              {repo.calibrator_status}
                            </span>
                          </div>

                          <div className="h-64 w-full flex items-center justify-center">
                            {hasCurve ? (
                              <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                  <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
                                  <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                                  <YAxis stroke="#64748b" fontSize={10} tickLine={false} unit="%" domain={[0, 100]} />
                                  <Tooltip 
                                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', color: '#f8fafc' }}
                                    labelStyle={{ fontWeight: 'bold' }}
                                    formatter={(value: any) => [`${Number(value).toFixed(1)}%`]}
                                  />
                                  <Legend 
                                    verticalAlign="bottom" 
                                    height={36} 
                                    iconType="circle"
                                    iconSize={8}
                                    wrapperStyle={{ fontSize: 10, paddingTop: 10 }}
                                  />
                                  <Line 
                                    type="monotone" 
                                    dataKey="Raw predicted confidence" 
                                    stroke="#f59e0b" 
                                    strokeWidth={1.5}
                                    strokeDasharray="5 5"
                                    activeDot={{ r: 4 }} 
                                  />
                                  <Line 
                                    type="monotone" 
                                    dataKey="Calibrated confidence" 
                                    stroke="#10b981" 
                                    strokeWidth={3}
                                    activeDot={{ r: 6 }} 
                                  />
                                  <Line 
                                    type="monotone" 
                                    dataKey="Actual held-out hit rate" 
                                    stroke="#ef4444" 
                                    strokeWidth={2}
                                    activeDot={{ r: 4 }} 
                                  />
                                </LineChart>
                              </ResponsiveContainer>
                            ) : (
                              <div className="flex flex-col items-center justify-center h-full w-full border border-dashed border-slate-800 rounded-lg p-6 bg-slate-950/40 text-slate-500 text-center">
                                <HelpCircle className="h-8 w-8 text-slate-700 mb-2" />
                                <span className="text-xs font-medium">Identity Fallback Applied</span>
                                <span className="text-3xs text-slate-650 mt-1 max-w-[240px]">
                                  No calibration fit values available due to severe cold start.
                                </span>
                              </div>
                            )}
                          </div>
                          
                          {/* Locked Banner below chart */}
                          <div className="bg-slate-950/80 border border-slate-850 text-slate-500 text-3xs font-semibold py-1.5 px-3 rounded-md text-center mt-4 tracking-wider uppercase">
                            Proposed-protocol evaluation output — not a validated production accuracy claim.
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Footer validation banner */}
                <div className="bg-red-500/5 border border-dashed border-red-500/20 text-red-400 text-xs p-4 rounded-xl flex items-center justify-center gap-3">
                  <AlertCircle className="h-5 w-5 shrink-0" />
                  <span className="font-semibold uppercase tracking-wider">
                    Proposed-protocol evaluation output — not a validated production accuracy claim.
                  </span>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* INCIDENT TIMELINE VIEW */}
        {activeTab === 'timeline' && (
          <div className="flex flex-col items-center justify-center py-28 border border-dashed border-slate-800 rounded-xl bg-slate-900/20 max-w-2xl mx-auto text-center px-6">
            <GitBranch className="h-10 w-10 text-slate-600 mb-3" />
            <h3 className="font-bold text-lg text-slate-300">Engineering Flight Recorder & Incident Timeline</h3>
            <div className="w-16 h-0.5 bg-indigo-500/50 my-4"></div>
            <p className="text-slate-400 text-sm max-w-md">
              <strong>Notice</strong>: The Flight Recorder depends on Stage 2 diagnosis telemetry data which does not exist yet. This view is currently a placeholder to prevent loading mock/fake telemetry data.
            </p>
          </div>
        )}

      </main>

      {/* FIXED PERMANENT FOOTER DISCLAIMER */}
      <footer className="sticky bottom-0 z-50 w-full bg-slate-950 border-t border-slate-850 py-3 text-center text-slate-400 text-2xs font-semibold tracking-wider uppercase">
        <div className="max-w-7xl mx-auto px-4 flex items-center justify-center gap-2">
          <AlertCircle className="h-3.5 w-3.5 text-amber-500 shrink-0" />
          <span>Proposed-protocol evaluation output — not a validated production accuracy claim.</span>
        </div>
      </footer>

      {/* CONNECT REPO MODAL */}
      {showConnectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl max-w-md w-full p-6 relative animate-in fade-in zoom-in-95 duration-150">
            <button 
              onClick={() => setShowConnectModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-200 transition-colors"
            >
              <Plus className="h-5 w-5 rotate-45" />
            </button>
            <h3 className="font-bold text-lg text-slate-200 mb-2">Connect Repository</h3>
            <p className="text-slate-400 text-xs mb-4">Provide a local folder absolute path or remote Git repository URL to clone and index.</p>
            
            {connectError && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-xs flex items-center gap-2 mb-4">
                <AlertCircle className="h-4 w-4 shrink-0" />
                <span>{connectError}</span>
              </div>
            )}

            <form onSubmit={handleConnect} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  Repository URL / Local Path
                </label>
                <input
                  type="text"
                  required
                  value={repoUrlInput}
                  onChange={(e) => setRepoUrlInput(e.target.value)}
                  placeholder="e.g., https://github.com/pallets/click.git"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              <div className="flex gap-3 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setShowConnectModal(false)}
                  className="px-4 py-2 border border-slate-800 text-slate-300 rounded-lg hover:bg-slate-800 text-sm font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={connectLoading}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-850 text-white rounded-lg text-sm font-semibold transition-colors flex items-center gap-2"
                >
                  {connectLoading && <RefreshCw className="h-3 w-3 animate-spin" />}
                  Connect & Index
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  );
}
