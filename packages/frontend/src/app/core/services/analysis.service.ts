import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { Analysis, AnalysisListResponse } from '../models/analysis.model';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AnalysisService {
  private api = inject(ApiService);

  private _pendingResume = signal<Analysis | null>(null);
  pendingResume = this._pendingResume.asReadonly();

  getAnalyses(params?: Record<string, string>): Observable<AnalysisListResponse> {
    return this.api.get('/analyses', params);
  }

  getAnalysis(id: string): Observable<{ data: Analysis }> {
    return this.api.get(`/analyses/${id}`);
  }

  cancelAnalysis(id: string): Observable<any> {
    return this.api.post(`/analyses/${id}/cancel`);
  }

  linkTask(analysisId: string, taskId: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/link-task`, { task_id: taskId });
  }

  setPendingResume(analysis: Analysis): void {
    this._pendingResume.set(analysis);
  }

  consumePendingResume(): Analysis | null {
    const analysis = this._pendingResume();
    this._pendingResume.set(null);
    return analysis;
  }
}
