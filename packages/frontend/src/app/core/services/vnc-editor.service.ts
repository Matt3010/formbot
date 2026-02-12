import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiService } from './api.service';
import { EditorMode, UserCorrections, TestSelectorResult } from '../models/vnc-editor.model';

@Injectable({ providedIn: 'root' })
export class VncEditorService {
  private api = inject(ApiService);

  startEditing(analysisId: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/start`);
  }

  resumeEditing(analysisId: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/resume`);
  }

  saveDraft(analysisId: string, corrections: UserCorrections): Observable<any> {
    return this.api.put(`/analyses/${analysisId}/editing/draft`, {
      user_corrections: corrections,
    });
  }

  sendCommand(analysisId: string, command: string, payload: Record<string, any> = {}): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/command`, {
      command,
      payload,
    });
  }

  setMode(analysisId: string, mode: EditorMode): Observable<any> {
    return this.sendCommand(analysisId, 'mode', { mode });
  }

  updateFields(analysisId: string, fields: any[]): Observable<any> {
    return this.sendCommand(analysisId, 'update-fields', { fields });
  }

  focusField(analysisId: string, fieldIndex: number): Observable<any> {
    return this.sendCommand(analysisId, 'focus-field', { field_index: fieldIndex });
  }

  testSelector(analysisId: string, selector: string): Observable<TestSelectorResult> {
    return this.sendCommand(analysisId, 'test-selector', { selector });
  }

  confirmAll(analysisId: string, corrections: UserCorrections, taskName?: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/confirm`, {
      user_corrections: corrections,
      name: taskName,
    });
  }

  cancelEditing(analysisId: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/cancel`);
  }

  navigateStep(analysisId: string, step: number, url: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/step`, { step, url });
  }
}
