// Types for Protein Evaluator

export type JobStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'paused' | 'running';
export type TargetStatus = 'pending' | 'processing' | 'completed' | 'failed';
export type EvaluationMode = 'parallel' | 'sequential';

// UI-facing Job type (camelCase)
export interface Job {
  id: string;
  title: string;
  description?: string;
  status: JobStatus;
  progress: number;
  targetCount: number;
  createdAt: string;
  updatedAt?: string;
  priority: number;
  evaluation_mode: EvaluationMode;
  tags?: Record<string, string>;
}

// API-facing Job type (snake_case) - matches backend response
export interface ApiJob {
  job_id: string;
  name: string;
  description?: string;
  status: JobStatus;
  progress?: {
    completed: number;
    total: number;
    percentage: number;
  };
  target_count: number;
  created_at: string;
  updated_at?: string;
  priority: number;
  evaluation_mode: EvaluationMode;
  tags?: Record<string, string>;
  config?: Record<string, any>;  // Job configuration including max_pdb
  report_content?: string | null;
  report_content_en?: string | null;
  report_format?: string;
  report_generated_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  interaction_ai_analysis?: string | null;
  interaction_ai_analysis_en?: string | null;
  interaction_prompt?: string | null;
  interaction_prompt_en?: string | null;
  chain_interaction_analysis?: {
    nodes: Array<{
      id: string;
      label: string;
      gene_name: string;
      protein_name: string;
      is_input: boolean;
      pdb_count: number;
      organism: string;
      connections: number;
    }>;
    direct_interactions: any[];
    indirect_interactions: any[];
    all_interactions: any[];
    chain_interactions: any[];
    pdb_structures: string[];
    interface_count: number;
    api_used: boolean;
    failed_pdbs?: string[];
  };
}

export interface Target {
  target_id: number;
  job_id: number;
  uniprot_id: string;
  target_index: number;
  status: TargetStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  evaluation?: {
    id: number;
    status: string;
    structure_quality_score?: number;
    function_score?: number;
    overall_score?: number;
    ai_analysis?: any;
    ai_analysis_en?: any;
    ai_analysis_zh?: any;
    pdb_data?: {
      pdb_ids: string[];
      structures: any[];
      coverage?: {
        coverage_percent: number;
        covered_residues: number;
        total_residues: number;
      };
    };
    blast_results?: {
      query_id: string;
      results: Array<{
        pdb_id: string;
        title: string;
        identity: number;
        score: number;
        evalue: number;
      }>;
    };
  };
}

export interface JobStatistics {
  total: number;
  completed: number;
  failed: number;
  processing: number;
  pending: number;
  success_rate: number;
}

export interface JobDetail {
  job: ApiJob;
  targets: Target[];
  progress: {
    completed: number;
    total: number;
    percentage: number;
  };
  statistics: JobStatistics;
}

export interface CreateJobRequest {
  name: string;
  description?: string;
  uniprot_ids: string[];
  evaluation_mode: EvaluationMode;
  tags?: Record<string, string>;
  config?: Record<string, unknown>;
}

export interface CreateJobResponse {
  success: boolean;
  job_id: string;
  name: string;
  status: JobStatus;
  target_count: number;
  evaluation_mode: EvaluationMode;
  priority: number;
  message: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export interface JobListResponse {
  success: boolean;
  jobs: ApiJob[];
  total: number;
  offset: number;
  limit: number;
}

export interface JobProgressResponse {
  success: boolean;
  job_id: number;
  status: JobStatus;
  progress: {
    percentage: number;
    completed: number;
    total: number;
    failed: number;
  };
  targets_status: Array<{
    target_id: number;
    uniprot_id: string;
    status: TargetStatus;
    target_index: number;
    started_at?: string;
    completed_at?: string;
  }>;
  estimated_remaining_seconds?: number;
}

export interface Interaction {
  relationship_id: number;
  source_target_id: number;
  target_target_id: number;
  source_uniprot: string | null;
  target_uniprot: string | null;
  relationship_type: string;
  score: number;
  metadata?: Record<string, unknown>;
}

export interface InteractionsResponse {
  success: boolean;
  job_id: number;
  interactions: Interaction[];
  total: number;
}

// Prompt Template Types
export interface PromptTemplate {
  id: number;
  name: string;
  name_en?: string;
  content: string;
  content_en?: string;
  description?: string;
  description_en?: string;
  is_default: boolean;
  template_type: 'single' | 'batch';
  created_at: string;
  updated_at?: string;
}

export interface TemplatesResponse {
  success: boolean;
  templates: PromptTemplate[];
  default_id: number | null;
  default_content: string;
}

export interface TemplateDetailResponse {
  success: boolean;
  template: PromptTemplate;
}

export interface CreateTemplateRequest {
  name: string;
  name_en?: string;
  content: string;
  content_en?: string;
  description?: string;
  description_en?: string;
  is_default?: boolean;
}

export interface UpdateTemplateRequest {
  name?: string;
  name_en?: string;
  content?: string;
  content_en?: string;
  description?: string;
  description_en?: string;
  is_default?: boolean;
}

// AI Configuration Types
export interface AIConfig {
  model: string;
  temperature: number;
  max_tokens: number;
  base_url?: string;
  api_key?: string;
}

export interface AIModelConfig {
  id: string;
  name: string;
  model: string;
  baseUrl: string;
  apiKey: string;
  temperature: number;
  maxTokens: number;
  isDefault: boolean;
  apiType?: 'openai' | 'anthropic' | 'custom';
}

export interface AIConfigResponse {
  success: boolean;
  config: AIConfig;
}

export interface UpdateAIConfigRequest {
  model?: string;
  temperature?: number;
  max_tokens?: number;
}

// PDB Structure Types
export interface Entity {
  chain: string;
  polymer_type: string;
  sequence: string;
}

export interface PdbStructure {
  pdb_id: string;
  source: 'pdb' | 'alphafold';
  entity_list?: Entity[];
  resolution?: number;
  title?: string;
  deposition_date?: string;
  authors?: string[];
  experimental_method?: string;
  citations?: Array<{
    title?: string;
    journal?: string;
    year?: number;
    pubmed_id?: string;
  }>;
  // Legacy format support
  basic_info?: {
    title?: string;
    experimental_method?: string;
    resolution?: number;
    deposition_date?: string;
    authors?: string[];
    entity_list?: Entity[];
  };
}

export interface PdbData {
  pdb_ids: string[];
  structures: PdbStructure[];
  coverage?: {
    coverage_percent: number;
    covered_residues: number;
    total_residues: number;
  };
}
