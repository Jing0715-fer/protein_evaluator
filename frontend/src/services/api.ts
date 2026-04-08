// API Service for Protein Evaluator
// Connects to Flask backend at http://localhost:5002

import type {
  JobDetail,
  CreateJobRequest,
  CreateJobResponse,
  JobListResponse,
  JobProgressResponse,
  InteractionsResponse,
  PromptTemplate,
  TemplatesResponse,
  TemplateDetailResponse,
  CreateTemplateRequest,
  UpdateTemplateRequest,
  AIConfig,
  AIConfigResponse,
  AIModelConfig,
} from '../types';

const API_BASE_URL = 'http://localhost:5002';

// Helper for API calls
async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<{ success: boolean; data?: T; error?: string }> {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    const data = await response.json();

    if (!response.ok) {
      return {
        success: false,
        error: data.error || `HTTP ${response.status}: ${response.statusText}`,
      };
    }

    return { success: true, data };
  } catch (error) {
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Network error',
    };
  }
}

// Jobs API
export const jobsApi = {
  // List all jobs
  listJobs: async (
    params?: {
      status?: string;
      limit?: number;
      offset?: number;
      sort_by?: string;
      sort_order?: 'asc' | 'desc';
    }
  ): Promise<JobListResponse> => {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append('status', params.status);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());
    if (params?.sort_by) queryParams.append('sort_by', params.sort_by);
    if (params?.sort_order) queryParams.append('sort_order', params.sort_order);

    const query = queryParams.toString();
    const result = await fetchApi<JobListResponse>(
      `/api/v2/evaluate/multi${query ? `?${query}` : ''}`
    );

    if (result.success && result.data) {
      return result.data;
    }

    return {
      success: false,
      jobs: [],
      total: 0,
      offset: 0,
      limit: 50,
      error: result.error,
    } as JobListResponse;
  },

  // Get job details
  getJob: async (jobId: string, lang: string = 'zh'): Promise<JobDetail | null> => {
    const result = await fetchApi<JobDetail>(`/api/v2/evaluate/multi/${jobId}?lang=${lang}`);
    return result.success ? result.data || null : null;
  },

  // Create new job
  createJob: async (data: CreateJobRequest): Promise<CreateJobResponse> => {
    const result = await fetchApi<CreateJobResponse>('/api/v2/evaluate/multi', {
      method: 'POST',
      body: JSON.stringify({
        name: data.name,
        description: data.description,
        uniprot_ids: data.uniprot_ids,
        evaluation_mode: data.evaluation_mode,
        tags: data.tags,
        config: data.config,
      }),
    });

    if (result.success && result.data) {
      return result.data;
    }

    return {
      success: false,
      job_id: '',
      name: '',
      status: 'pending',
      target_count: 0,
      evaluation_mode: 'parallel',
      priority: 5,
      message: result.error || 'Failed to create job',
    };
  },

  // Delete job
  deleteJob: async (jobId: string): Promise<boolean> => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}`, {
      method: 'DELETE',
    });
    return result.success;
  },

  // Update job
  updateJob: async (
    jobId: string,
    data: { name?: string; description?: string; priority?: number }
  ): Promise<boolean> => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    return result.success;
  },
};

// Job Control API
export const jobControlApi = {
  // Start job
  startJob: async (jobId: string): Promise<boolean> => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/start`, {
      method: 'POST',
    });
    return result.success;
  },

  // Pause job
  pauseJob: async (jobId: string): Promise<boolean> => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/pause`, {
      method: 'POST',
    });
    return result.success;
  },

  // Resume job
  resumeJob: async (jobId: string): Promise<boolean> => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/resume`, {
      method: 'POST',
    });
    return result.success;
  },

  // Cancel job
  cancelJob: async (jobId: string): Promise<boolean> => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/cancel`, {
      method: 'POST',
    });
    return result.success;
  },

  // Restart job
  restartJob: async (jobId: string, resetFailedOnly = false, params?: { name?: string; description?: string; priority?: number; evaluation_mode?: string; max_pdb?: number }): Promise<boolean> => {
    const body: Record<string, any> = { reset_failed_only: resetFailedOnly };
    if (params) {
      if (params.name !== undefined) body.name = params.name;
      if (params.description !== undefined) body.description = params.description;
      if (params.priority !== undefined) body.priority = params.priority;
      if (params.evaluation_mode !== undefined) body.evaluation_mode = params.evaluation_mode;
      if (params.max_pdb !== undefined) body.max_pdb = params.max_pdb;
    }
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/restart`, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    return result.success;
  },

  // Update job parameters (without restarting)
  updateJobParams: async (jobId: string, params: { name?: string; description?: string; priority?: number; evaluation_mode?: string; max_pdb?: number }): Promise<boolean> => {
    const body: Record<string, any> = {};
    if (params.name !== undefined) body.name = params.name;
    if (params.description !== undefined) body.description = params.description;
    if (params.priority !== undefined) body.priority = params.priority;
    if (params.evaluation_mode !== undefined) body.evaluation_mode = params.evaluation_mode;
    if (params.max_pdb !== undefined) body.max_pdb = params.max_pdb;

    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/params`, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    return result.success;
  },

  // Get job logs
  getJobLogs: async (jobId: string): Promise<{ success: boolean; logs?: Array<{ timestamp: string; level: string; message: string }>; error?: string }> => {
    const result = await fetchApi<{ logs?: Array<{ timestamp: string; level: string; message: string }>; success?: boolean }>(`/api/v2/evaluate/multi/${jobId}/logs`);
    if (result.success && result.data) {
      return result.data as { success: boolean; logs?: Array<{ timestamp: string; level: string; message: string }>; error?: string };
    }
    return { success: false, error: result.error || 'Failed to fetch logs' };
  },
};

// Job Progress API
export const jobProgressApi = {
  // Get job progress
  getProgress: async (jobId: string): Promise<JobProgressResponse | null> => {
    const result = await fetchApi<JobProgressResponse>(
      `/api/v2/evaluate/multi/${jobId}/progress`
    );
    return result.success ? result.data || null : null;
  },
};

// Targets API
export const targetsApi = {
  // Get job targets
  getTargets: async (
    jobId: string,
    params?: {
      status?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{
    success: boolean;
    targets: Array<{
      target_id: number;
      uniprot_id: string;
      status: string;
      target_index: number;
      evaluation?: {
        id: number;
        overall_score?: number;
        status: string;
      };
    }>;
    total: number;
  } | null> => {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append('status', params.status);
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.offset !== undefined) queryParams.append('offset', params.offset.toString());

    const query = queryParams.toString();
    const result = await fetchApi<{
      success: boolean;
      targets: Array<{
        target_id: number;
        uniprot_id: string;
        status: string;
        target_index: number;
        evaluation?: {
          id: number;
          overall_score?: number;
          status: string;
        };
      }>;
      total: number;
    }>(`/api/v2/evaluate/multi/${jobId}/targets${query ? `?${query}` : ''}`);

    return result.success ? result.data || null : null;
  },

  // Get target detail
  getTargetDetail: async (jobId: string, targetId: string) => {
    const result = await fetchApi(`/api/v2/evaluate/multi/${jobId}/targets/${targetId}`);
    return result.success ? result.data : null;
  },
};

// Interactions API
export const interactionsApi = {
  // Get job interactions
  getInteractions: async (
    jobId: string,
    params?: {
      relationship_type?: string;
      min_score?: number;
      limit?: number;
    }
  ): Promise<InteractionsResponse | null> => {
    const queryParams = new URLSearchParams();
    if (params?.relationship_type) queryParams.append('relationship_type', params.relationship_type);
    if (params?.min_score !== undefined) queryParams.append('min_score', params.min_score.toString());
    if (params?.limit) queryParams.append('limit', params.limit.toString());

    const query = queryParams.toString();
    const result = await fetchApi<InteractionsResponse>(
      `/api/v2/evaluate/multi/${jobId}/interactions${query ? `?${query}` : ''}`
    );

    return result.success ? result.data || null : null;
  },

  // Get enhanced chain-level interactions (direct vs indirect)
  getChainInteractions: async (jobId: string): Promise<{
    success: boolean;
    nodes: Array<{
      id: string;
      label: string;
      gene_name: string;
      protein_name: string;
      is_input: boolean;
      pdb_count: number;
      organism: string;
    }>;
    direct_interactions: Array<{
      source_uniprot: string;
      target_uniprot: string;
      interaction_type: string;
      mediator_uniprot?: string;
      pdb_ids: string[];
      score: number;
      total_evidence: number;
      is_confirmed: boolean;
    }>;
    indirect_interactions: Array<{
      source_uniprot: string;
      target_uniprot: string;
      interaction_type: string;
      mediator_uniprot: string;
      score: number;
      is_confirmed: boolean;
    }>;
    all_interactions: Array<{
      source_uniprot: string;
      target_uniprot: string;
      interaction_type: string;
      mediator_uniprot?: string;
      pdb_ids: string[];
      score: number;
      is_confirmed: boolean;
    }>;
    chain_interactions: Array<{
      pdb_id: string;
      chain_a: string;
      chain_b: string;
      uniprot_a: string;
      uniprot_b: string;
    }>;
    pdb_structures: string[];
  } | null> => {
    const result = await fetchApi<{
      success: boolean;
      nodes: any[];
      direct_interactions: any[];
      indirect_interactions: any[];
      all_interactions: any[];
      chain_interactions: any[];
      pdb_structures: string[];
    }>(`/api/v2/evaluate/multi/${jobId}/interactions/chain`);

    return result.success ? result.data || null : null;
  },
};

// Health check
export const healthApi = {
  check: async (): Promise<{ status: string; service: string } | null> => {
    const result = await fetchApi<{ status: string; service: string }>('/health');
    return result.success ? result.data || null : null;
  },
};

// Prompt Templates API
export const templatesApi = {
  // List all templates
  listTemplates: async (): Promise<TemplatesResponse> => {
    const result = await fetchApi<TemplatesResponse>('/api/evaluation/templates');
    if (result.success && result.data) {
      return result.data;
    }
    return {
      success: false,
      templates: [],
      default_id: null,
      default_content: '',
    };
  },

  // Get single template
  getTemplate: async (id: number): Promise<PromptTemplate | null> => {
    const result = await fetchApi<TemplateDetailResponse>(`/api/evaluation/templates/${id}`);
    return result.success ? result.data?.template || null : null;
  },

  // Create new template
  createTemplate: async (data: CreateTemplateRequest): Promise<{ success: boolean; template?: PromptTemplate; error?: string }> => {
    const result = await fetchApi<{ success: boolean; template: PromptTemplate }>('/api/evaluation/templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (result.success && result.data) {
      return { success: true, template: result.data.template };
    }
    return { success: false, error: result.error };
  },

  // Update template
  updateTemplate: async (id: number, data: UpdateTemplateRequest): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>(`/api/evaluation/templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },

  // Delete template
  deleteTemplate: async (id: number): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>(`/api/evaluation/templates/${id}`, {
      method: 'DELETE',
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },

  // Set as default template
  setDefaultTemplate: async (id: number): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>(`/api/evaluation/templates/${id}/set-default`, {
      method: 'POST',
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },
};

// Batch Templates API
export const batchTemplatesApi = {
  // List all batch templates
  listTemplates: async (): Promise<TemplatesResponse> => {
    const result = await fetchApi<TemplatesResponse>('/api/evaluation/batch-templates');
    if (result.success && result.data) {
      return result.data;
    }
    return {
      success: false,
      templates: [],
      default_id: null,
      default_content: '',
    };
  },

  // Get single batch template
  getTemplate: async (id: number): Promise<PromptTemplate | null> => {
    const result = await fetchApi<TemplateDetailResponse>(`/api/evaluation/batch-templates/${id}`);
    return result.success ? result.data?.template || null : null;
  },

  // Create new batch template
  createTemplate: async (data: CreateTemplateRequest): Promise<{ success: boolean; template?: PromptTemplate; error?: string }> => {
    const result = await fetchApi<{ success: boolean; template: PromptTemplate }>('/api/evaluation/batch-templates', {
      method: 'POST',
      body: JSON.stringify(data),
    });
    if (result.success && result.data) {
      return { success: true, template: result.data.template };
    }
    return { success: false, error: result.error };
  },

  // Update batch template
  updateTemplate: async (id: number, data: UpdateTemplateRequest): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>(`/api/evaluation/batch-templates/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },

  // Delete batch template
  deleteTemplate: async (id: number): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>(`/api/evaluation/batch-templates/${id}`, {
      method: 'DELETE',
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },

  // Set as default batch template
  setDefaultTemplate: async (id: number): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>(`/api/evaluation/batch-templates/${id}/set-default`, {
      method: 'POST',
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },
};

// AI Configuration API
export const configApi = {
  // Get current AI config (legacy)
  getConfig: async (): Promise<AIConfig | null> => {
    const result = await fetchApi<AIConfigResponse>('/api/config');
    return result.success ? result.data?.config || null : null;
  },

  // Update AI config (legacy)
  updateConfig: async (config: Partial<AIConfig>): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>('/api/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },

  // Get all AI model configs
  getModels: async (): Promise<AIModelConfig[]> => {
    const result = await fetchApi<{ success: boolean; models: AIModelConfig[] }>('/api/evaluation/models');
    return result.success ? result.data?.models || [] : [];
  },

  // Save all AI model configs
  saveModels: async (models: AIModelConfig[]): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string }>('/api/evaluation/models', {
      method: 'PUT',
      body: JSON.stringify({ models }),
    });
    if (result.success) {
      return { success: true };
    }
    return { success: false, error: result.error };
  },

  // Test model connection
  testModelConnection: async (model: AIModelConfig): Promise<{ success: boolean; error?: string }> => {
    const result = await fetchApi<{ success: boolean; message: string; error?: string }>('/api/evaluation/models/test', {
      method: 'POST',
      body: JSON.stringify(model),
    });
    // result.data contains the actual API response with success/error
    if (result.success && result.data) {
      return {
        success: result.data.success,
        error: result.data.error,
      };
    }
    return {
      success: false,
      error: result.error || '请求失败',
    };
  },
};

// Export all APIs
export const api = {
  jobs: jobsApi,
  jobControl: jobControlApi,
  jobProgress: jobProgressApi,
  targets: targetsApi,
  interactions: interactionsApi,
  health: healthApi,
  templates: templatesApi,
  batchTemplates: batchTemplatesApi,
  config: configApi,
};

export default api;
