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
  custom_user_agent: string | null;
  cloned_from: string | null;
  requires_login: boolean;
  login_url: string | null;
  form_definitions: FormDefinition[];
  created_at: string;
  updated_at: string;
}

export interface FormDefinition {
  id: string;
  task_id: string;
  step_order: number;
  depends_on_step_order: number | null;
  page_url: string;
  form_type: 'login' | 'intermediate' | 'target';
  form_selector: string;
  submit_selector: string;
  human_breakpoint: boolean;
  fields: FormField[];
  created_at: string;
  updated_at: string;
}

export interface FormFieldPayload {
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

export interface FormDefinitionPayload {
  step_order: number;
  depends_on_step_order: number | null;
  page_url: string;
  form_type: 'login' | 'intermediate' | 'target';
  form_selector: string | null;
  submit_selector: string | null;
  human_breakpoint: boolean;
  form_fields: FormFieldPayload[];
}

export interface TaskPayload {
  name: string;
  target_url: string;
  status: Task['status'];
  schedule_type: 'once' | 'cron';
  schedule_cron: string | null;
  schedule_at: string | null;
  is_dry_run: boolean;
  custom_user_agent: string | null;
  max_retries: number;
  max_parallel: number;
  requires_login: boolean;
  login_url: string | null;
  form_definitions: FormDefinitionPayload[];
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
