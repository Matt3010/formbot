export type EditorMode = 'view' | 'select' | 'add' | 'remove';
export type EditorPhase = 'login' | 'login-executing' | 'target';

export interface EditorField {
  temp_id: string;
  field_name: string;
  field_type: string;
  field_selector: string;
  field_purpose: string;
  preset_value: string;
  is_sensitive: boolean;
  is_required: boolean;
  is_file_upload: boolean;
  options: string[] | null;
  sort_order: number;
  status: 'ai' | 'confirmed' | 'added' | 'modified';
  source: 'ai' | 'user';
  original_selector: string;
}

export interface EditingStep {
  step_order: number;
  page_url: string;
  form_type: 'login' | 'intermediate' | 'target';
  form_selector: string;
  submit_selector: string;
  ai_confidence: number | null;
  captcha_detected: boolean;
  two_factor_expected: boolean;
  human_breakpoint: boolean;
  status: 'pending' | 'confirmed';
  fields: EditorField[];
}

export interface UserCorrections {
  version: number;
  steps: EditingStep[];
}

export interface HighlightingReadyEvent {
  analysis_id: string;
  vnc_url: string;
  vnc_session_id: string;
  fields: any[];
  analysis_result: any;
}

export interface FieldSelectedEvent {
  analysis_id: string;
  index: number;
  selector: string;
  name: string;
  type: string;
  purpose: string;
  value: string;
}

export interface FieldAddedEvent {
  analysis_id: string;
  selector: string;
  tagName: string;
  type: string;
  name: string;
  value: string;
  purpose: string;
  form_selector?: string;
  submit_selector?: string;
}

export interface FieldRemovedEvent {
  analysis_id: string;
  index: number;
  selector: string;
}

export interface FieldValueChangedEvent {
  analysis_id: string;
  index: number;
  selector: string;
  value: string;
}

export interface TestSelectorResult {
  status: string;
  found: boolean;
  matchCount: number;
}

export interface LoginExecutionProgressEvent {
  analysis_id: string;
  phase: string;       // 'filling' | 'captcha' | '2fa' | 'submitting' | 'navigating' | 'analyzing'
  message: string;
  needs_vnc?: boolean;
}

export interface LoginExecutionCompleteEvent {
  analysis_id: string;
  success: boolean;
  error?: string;
  target_result?: any;
  target_fields?: any[];
}
