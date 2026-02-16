import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { EditorMode, UserCorrections, TestSelectorResult } from '../models/vnc-editor.model';

@Injectable({ providedIn: 'root' })
export class VncEditorService {
  private api = inject(ApiService);

  startEditing(taskId: string, url?: string, isLoginStep?: boolean): Observable<any> {
    const payload: any = {};
    if (url) payload.url = url;
    if (isLoginStep !== undefined) payload.is_login_step = isLoginStep;
    return this.api.post(`/tasks/${taskId}/editing/start`, payload);
  }

  resumeEditing(taskId: string): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/resume`);
  }

  saveDraft(taskId: string, corrections: UserCorrections): Observable<any> {
    return this.api.patch(`/tasks/${taskId}/editing/draft`, {
      user_corrections: corrections,
    });
  }

  sendCommand(taskId: string, command: string, payload: Record<string, any> = {}): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/command`, {
      command,
      payload,
    });
  }

  setMode(taskId: string, mode: EditorMode): Observable<any> {
    return this.sendCommand(taskId, 'mode', { mode });
  }

  updateFields(taskId: string, fields: any[]): Observable<any> {
    return this.sendCommand(taskId, 'update-fields', { fields });
  }

  focusField(taskId: string, fieldIndex: number): Observable<any> {
    return this.sendCommand(taskId, 'focus-field', { field_index: fieldIndex });
  }

  testSelector(taskId: string, selector: string): Observable<TestSelectorResult> {
    return this.sendCommand(taskId, 'test-selector', { selector });
  }

  fillField(taskId: string, fieldIndex: number, value: string): Observable<any> {
    return this.sendCommand(taskId, 'fill-field', { field_index: fieldIndex, value });
  }

  readFieldValue(taskId: string, fieldIndex: number): Observable<any> {
    return this.sendCommand(taskId, 'read-field-value', { field_index: fieldIndex });
  }

  confirmAll(taskId: string, corrections: UserCorrections, taskName?: string): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/confirm`, {
      user_corrections: corrections,
      name: taskName,
    });
  }

  cancelEditing(taskId: string): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/cancel`);
  }

  navigateStep(taskId: string, step: number, url: string, requestId?: string): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/step`, {
      step,
      url,
      request_id: requestId,
    });
  }

  executeLogin(taskId: string, loginFields: any[], targetUrl: string, submitSelector: string, flags?: { human_breakpoint?: boolean }): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/execute-login`, {
      login_fields: loginFields,
      target_url: targetUrl,
      submit_selector: submitSelector,
      human_breakpoint: flags?.human_breakpoint ?? false,
    });
  }

  resumeLogin(taskId: string): Observable<any> {
    return this.api.post(`/tasks/${taskId}/editing/resume-login`);
  }
}
