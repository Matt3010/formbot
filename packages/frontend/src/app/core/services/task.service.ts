import { Injectable, inject } from '@angular/core';
import { ApiService } from './api.service';
import { Task, TaskPayload } from '../models/task.model';
import { ExecutionLog } from '../models/execution-log.model';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class TaskService {
  private api = inject(ApiService);

  getTasks(params?: Record<string, string>): Observable<{ data: Task[] }> {
    return this.api.get('/tasks', params);
  }

  getTask(id: string): Observable<{ data: Task }> {
    return this.api.get(`/tasks/${id}`);
  }

  createTask(task: Partial<Task> | TaskPayload): Observable<{ data: Task }> {
    return this.api.post('/tasks', task);
  }

  updateTask(id: string, task: Partial<Task> | TaskPayload): Observable<{ data: Task }> {
    return this.api.put(`/tasks/${id}`, task);
  }

  deleteTask(id: string): Observable<void> {
    return this.api.delete(`/tasks/${id}`);
  }

  cloneTask(id: string): Observable<{ data: Task }> {
    return this.api.post(`/tasks/${id}/clone`);
  }

  activateTask(id: string): Observable<{ data: Task }> {
    return this.api.post(`/tasks/${id}/activate`);
  }

  pauseTask(id: string): Observable<{ data: Task }> {
    return this.api.post(`/tasks/${id}/pause`);
  }

  executeTask(id: string): Observable<any> {
    return this.api.post(`/tasks/${id}/execute`);
  }

  dryRunTask(id: string): Observable<any> {
    return this.api.post(`/tasks/${id}/dry-run`);
  }

  exportTask(id: string): Observable<any> {
    return this.api.post(`/tasks/${id}/export`);
  }

  importTask(data: any): Observable<{ data: Task }> {
    return this.api.post('/tasks/import', data);
  }

  analyzeUrl(url: string): Observable<any> {
    return this.api.post('/analyze', { url });
  }

  analyzeNextPage(url: string): Observable<any> {
    return this.api.post('/analyze/next-page', { url });
  }

  analyzeLoginAndTarget(payload: {
    login_url: string;
    target_url: string;
    login_form_selector: string;
    login_submit_selector: string;
    login_fields: { field_selector: string; value: string; field_type?: string; is_sensitive?: boolean }[];
    needs_vnc?: boolean;
  }): Observable<any> {
    return this.api.post('/analyze/login-and-target', payload);
  }

  resumeAnalysisVnc(sessionId: string, analysisId: string): Observable<any> {
    return this.api.post('/analyze/resume-vnc', { session_id: sessionId, analysis_id: analysisId });
  }

  analyzeInteractive(analysisId: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/start`);
  }

  validateSelectors(taskId: string): Observable<any> {
    return this.api.post('/validate-selectors', { task_id: taskId });
  }

  getExecutions(taskId: string, params?: Record<string, string>): Observable<{ data: ExecutionLog[] }> {
    return this.api.get(`/tasks/${taskId}/executions`, params);
  }

  getExecution(id: string): Observable<{ data: ExecutionLog }> {
    return this.api.get(`/executions/${id}`);
  }

  uploadFile(file: File): Observable<{ path: string }> {
    const formData = new FormData();
    formData.append('file', file);
    return this.api.upload('/files/upload', formData);
  }
}
