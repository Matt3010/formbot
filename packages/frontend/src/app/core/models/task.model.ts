export interface Task {
  id: string;
  user_id: number;
  name: string;
  target_url: string;
  schedule_type: 'once' | 'cron';
  schedule_cron: string | null;
  schedule_at: string | null;
  status: 'draft' | 'active' | 'paused' | 'completed' | 'failed' | 'running' | 'deleted';
  is_dry_run: boolean;
  max_retries: number;
  max_parallel: number;
  stealth_enabled: boolean;
  custom_user_agent: string | null;
  action_delay_ms: number;
  cloned_from: string | null;
  form_definitions: FormDefinition[];
  created_at: string;
  updated_at: string;
}

export interface FormDefinition {
  id: string;
  task_id: string;
  step_order: number;
  page_url: string;
  form_type: 'login' | 'intermediate' | 'target';
  form_selector: string;
  submit_selector: string;
  ai_confidence: number | null;
  captcha_detected: boolean;
  two_factor_expected: boolean;
  fields: FormField[];
  created_at: string;
  updated_at: string;
}

export interface FormField {
  id: string;
  form_definition_id: string;
  field_name: string;
  field_type: string;
  field_selector: string;
  field_purpose: string | null;
  preset_value: string | null;
  is_sensitive: boolean;
  is_file_upload: boolean;
  is_required: boolean;
  options: string[] | null;
  sort_order: number;
}
