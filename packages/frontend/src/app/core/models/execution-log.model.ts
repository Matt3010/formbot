export interface ExecutionLog {
  id: string;
  task_id: string;
  started_at: string | null;
  completed_at: string | null;
  status: 'queued' | 'running' | 'waiting_manual' | 'success' | 'failed' | 'captcha_blocked' | '2fa_required' | 'dry_run_ok';
  is_dry_run: boolean;
  retry_count: number;
  error_message: string | null;
  screenshot_path: string | null;
  steps_log: any[];
  vnc_session_id: string | null;
  created_at: string;
}
