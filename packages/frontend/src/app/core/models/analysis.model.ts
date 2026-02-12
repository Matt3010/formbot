export interface Analysis {
  id: string;
  url: string;
  target_url: string | null;
  login_url: string | null;
  type: 'simple' | 'login_and_target' | 'next_page';
  status: 'pending' | 'analyzing' | 'completed' | 'failed' | 'cancelled' | 'timed_out' | 'editing';
  result: any | null;
  error: string | null;
  model: string | null;
  task_id: string | null;
  vnc_session_id: string | null;
  editing_status: 'idle' | 'active' | 'confirmed' | 'cancelled';
  editing_step: number;
  user_corrections: any | null;
  editing_started_at: string | null;
  editing_expires_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnalysisListResponse {
  data: Analysis[];
  meta: {
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
  };
}
