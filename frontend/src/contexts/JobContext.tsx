// React Context for Job Management
import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import type { Job, JobStatus, JobDetail, JobProgressResponse } from '../types';
import { api } from '../services/api';

interface JobContextType {
  // State
  jobs: Job[];
  selectedJob: JobDetail | null;
  jobProgress: JobProgressResponse | null;
  isLoading: boolean;
  error: string | null;
  totalJobs: number;

  // Actions
  fetchJobs: (params?: {
    status?: string;
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) => Promise<void>;
  fetchJobDetail: (jobId: string, lang?: string) => Promise<void>;
  fetchJobProgress: (jobId: string) => Promise<void>;
  createJob: (data: {
    name: string;
    description?: string;
    uniprot_ids: string[];
    evaluation_mode: 'parallel' | 'sequential';
    config?: { max_pdb?: number; template?: string };
  }) => Promise<{ success: boolean; jobId?: string; error?: string }>;
  deleteJob: (jobId: string) => Promise<boolean>;
  startJob: (jobId: string) => Promise<boolean>;
  pauseJob: (jobId: string) => Promise<boolean>;
  resumeJob: (jobId: string) => Promise<boolean>;
  cancelJob: (jobId: string) => Promise<boolean>;
  restartJob: (jobId: string, resetFailedOnly?: boolean, params?: { name?: string; description?: string; priority?: number; evaluation_mode?: string }) => Promise<boolean>;
  clearError: () => void;
  clearSelectedJob: () => void;

  // Polling
  startPolling: (jobId: string) => void;
  stopPolling: () => void;
  isPolling: boolean;
}

const JobContext = createContext<JobContextType | undefined>(undefined);

// Define the expected response type
interface JobFromAPI {
  job_id?: string;
  id?: string;
  name?: string;
  title?: string;
  description?: string;
  status?: JobStatus;
  progress?: { percentage?: number } | number;
  target_count?: number;
  targetCount?: number;
  created_at?: string;
  createdAt?: string;
  updated_at?: string;
  updatedAt?: string;
  priority?: number;
  evaluation_mode?: 'parallel' | 'sequential';
}

export const JobProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // State
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [jobProgress, setJobProgress] = useState<JobProgressResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalJobs, setTotalJobs] = useState(0);
  const [isPolling, setIsPolling] = useState(false);

  // Refs for polling and SSE
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const currentPollingJobId = useRef<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Fetch jobs list
  const fetchJobs = useCallback(async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  }) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.jobs.listJobs(params);
      if (response.success && response.jobs) {
        // Transform jobs to match the Job interface
        const transformedJobs: Job[] = response.jobs.map((job: unknown) => {
          const j = job as JobFromAPI;
          const progressValue = typeof j.progress === 'number' ? j.progress : (j.progress?.percentage ?? 0);
          return {
            id: String(j.job_id ?? j.id ?? ''),
            title: String(j.name ?? j.title ?? ''),
            description: j.description ?? '',
            status: (j.status as JobStatus) ?? 'pending',
            progress: progressValue,
            targetCount: j.target_count ?? j.targetCount ?? 0,
            createdAt: String(j.created_at ?? j.createdAt ?? ''),
            updatedAt: j.updated_at ?? j.updatedAt,
            priority: j.priority ?? 5,
            evaluation_mode: (j.evaluation_mode as 'parallel' | 'sequential') ?? 'parallel',
          };
        });
        setJobs(transformedJobs);
        setTotalJobs(response.total || 0);
      } else {
        setError('Failed to fetch jobs');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch jobs');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch job detail
  const fetchJobDetail = useCallback(async (jobId: string, lang: string = 'zh') => {
    setIsLoading(true);
    setError(null);
    try {
      const jobDetail = await api.jobs.getJob(jobId, lang);
      if (jobDetail) {
        setSelectedJob(jobDetail);
      } else {
        setError('Failed to fetch job details');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch job details');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch job progress
  const fetchJobProgress = useCallback(async (jobId: string) => {
    try {
      const progress = await api.jobProgress.getProgress(jobId);
      if (progress) {
        setJobProgress(progress);
      }
    } catch (err) {
      console.error('Failed to fetch job progress:', err);
    }
  }, []);

  // Create job
  const createJob = useCallback(async (data: {
    name: string;
    description?: string;
    uniprot_ids: string[];
    evaluation_mode: 'parallel' | 'sequential';
    config?: { max_pdb?: number; template?: string };
  }): Promise<{ success: boolean; jobId?: string; error?: string }> => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.jobs.createJob({
        name: data.name,
        description: data.description,
        uniprot_ids: data.uniprot_ids,
        evaluation_mode: data.evaluation_mode,
        config: data.config,
      });
      if (response.success) {
        // Refresh jobs list
        await fetchJobs();
        return { success: true, jobId: response.job_id };
      } else {
        const errorMsg = response.message || 'Failed to create job';
        setError(errorMsg);
        return { success: false, error: errorMsg };
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to create job';
      setError(errorMsg);
      return { success: false, error: errorMsg };
    } finally {
      setIsLoading(false);
    }
  }, [fetchJobs]);

  // Delete job
  const deleteJob = useCallback(async (jobId: string) => {
    setIsLoading(true);
    try {
      const success = await api.jobs.deleteJob(jobId);
      if (success) {
        setJobs((prev) => prev.filter((j) => j.id !== jobId));
        if (selectedJob?.job.job_id === jobId || selectedJob?.job.job_id === jobId) {
          setSelectedJob(null);
        }
        return true;
      }
      return false;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete job');
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [selectedJob]);

  // SSE streaming for job progress (primary method)
  const startProgressStream = useCallback((jobId: string) => {
    // Stop any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }

    // Close existing SSE connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const url = `/api/v2/evaluate/multi/${jobId}/progress/stream`;
    console.log('[SSE] Connecting to:', url);

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;
    currentPollingJobId.current = jobId;
    setIsPolling(true);

    eventSource.onopen = () => {
      console.log('[SSE] Connection established');
    };

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Skip heartbeats
        if (data.type === 'heartbeat') return;

        // Handle errors
        if (data.error) {
          console.error('[SSE] Error:', data.error);
          return;
        }

        setJobProgress(data);

        // Stop streaming when job is done
        if (data.done || data.status === 'completed' || data.status === 'failed') {
          console.log('[SSE] Job complete, closing connection');
          eventSource.close();
          eventSourceRef.current = null;
          setIsPolling(false);
          // Fetch final job detail
          fetchJobDetail(jobId);
        }
      } catch (err) {
        console.error('[SSE] Parse error:', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('[SSE] Connection error, falling back to polling:', err);
      eventSource.close();
      eventSourceRef.current = null;
      // Fallback to polling with longer interval
      startPollingWithInterval(jobId, 5000);
    };
  }, [fetchJobDetail]);

  // Polling with custom interval (fallback when SSE fails)
  const startPollingWithInterval = useCallback((jobId: string, interval: number = 5000) => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    currentPollingJobId.current = jobId;
    setIsPolling(true);

    fetchJobProgress(jobId);
    pollingIntervalRef.current = setInterval(() => {
      fetchJobProgress(jobId);
      fetchJobDetail(jobId);
    }, interval);
  }, [fetchJobProgress, fetchJobDetail]);

  // Start polling for job progress (legacy fallback)
  const startPolling = useCallback((jobId: string) => {
    // Clear any existing polling/SSE
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    currentPollingJobId.current = jobId;
    setIsPolling(true);

    // Initial fetch
    fetchJobProgress(jobId);

    // Set up interval
    pollingIntervalRef.current = setInterval(() => {
      fetchJobProgress(jobId);
      // Also refresh job detail for status updates
      fetchJobDetail(jobId);
    }, 2000); // Poll every 2 seconds
  }, [fetchJobProgress, fetchJobDetail]);

  // Start job
  const startJob = useCallback(async (jobId: string) => {
    try {
      const success = await api.jobControl.startJob(jobId);
      if (success) {
        await fetchJobDetail(jobId);
        // Start SSE streaming for job progress
        startProgressStream(jobId);
      }
      return success;
    } catch (err) {
      console.error('Failed to start job:', err);
      return false;
    }
  }, [fetchJobDetail, startProgressStream]);

  // Pause job
  const pauseJob = useCallback(async (jobId: string) => {
    try {
      const success = await api.jobControl.pauseJob(jobId);
      if (success) {
        await fetchJobDetail(jobId);
      }
      return success;
    } catch (err) {
      console.error('Failed to pause job:', err);
      return false;
    }
  }, [fetchJobDetail]);

  // Resume job
  const resumeJob = useCallback(async (jobId: string) => {
    try {
      const success = await api.jobControl.resumeJob(jobId);
      if (success) {
        await fetchJobDetail(jobId);
        // Start SSE streaming for job progress
        startProgressStream(jobId);
      }
      return success;
    } catch (err) {
      console.error('Failed to resume job:', err);
      return false;
    }
  }, [fetchJobDetail, startProgressStream]);

  // Cancel job
  const cancelJob = useCallback(async (jobId: string) => {
    try {
      const success = await api.jobControl.cancelJob(jobId);
      if (success) {
        await fetchJobDetail(jobId);
      }
      return success;
    } catch (err) {
      console.error('Failed to cancel job:', err);
      return false;
    }
  }, [fetchJobDetail]);

  // Restart job
  const restartJob = useCallback(async (jobId: string, resetFailedOnly = false, params?: { name?: string; description?: string; priority?: number; evaluation_mode?: string }) => {
    try {
      const success = await api.jobControl.restartJob(jobId, resetFailedOnly, params);
      if (success) {
        await fetchJobDetail(jobId);
        // Start SSE streaming for job progress
        startProgressStream(jobId);
      }
      return success;
    } catch (err) {
      console.error('Failed to restart job:', err);
      return false;
    }
  }, [fetchJobDetail, startProgressStream]);

  // Clear error
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // Clear selected job
  const clearSelectedJob = useCallback(() => {
    setSelectedJob(null);
    setJobProgress(null);
  }, []);

  // Stop polling
  const stopPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    currentPollingJobId.current = null;
    setIsPolling(false);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  const value: JobContextType = {
    jobs,
    selectedJob,
    jobProgress,
    isLoading,
    error,
    totalJobs,
    fetchJobs,
    fetchJobDetail,
    fetchJobProgress,
    createJob,
    deleteJob,
    startJob,
    pauseJob,
    resumeJob,
    cancelJob,
    restartJob,
    clearError,
    clearSelectedJob,
    startPolling,
    stopPolling,
    isPolling,
  };

  return <JobContext.Provider value={value}>{children}</JobContext.Provider>;
};

// Hook to use JobContext
export const useJobs = (): JobContextType => {
  const context = useContext(JobContext);
  if (context === undefined) {
    throw new Error('useJobs must be used within a JobProvider');
  }
  return context;
};
