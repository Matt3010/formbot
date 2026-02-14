export interface ExecutionLog {
  id: string;
  task_id: string;
  started_at: string | null;
  completed_at: string | null;
  status: 'queued' | 'running' | 'waiting_manual' | 'success' | 'failed' | 'dry_run_ok';
  is_dry_run: boolean;
  retry_count: number;
  error_message: string | null;
  screenshot_path: string | null;
  screenshot_url: string | null;
  screenshot_size: number | null;
  has_screenshot: boolean;
  steps_log: any[];
  vnc_session_id: string | null;
  created_at: string;
}

export interface ScreenshotListItem {
  execution_id: string;
  task_id: string;
  task_name: string;
  created_at: string;
  size: number | null;
  storage: 'minio' | 'filesystem';
}

export interface ScreenshotStats {
  minio: { total_size: number; count: number };
  filesystem: { total_size: number; count: number };
  total: { total_size: number; count: number };
}

export interface ScreenshotResponse {
  url: string;
  expires_in: number;
  storage: 'minio';
}
