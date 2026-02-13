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

  analyzeUrl(url: string): Observable<any> {
    return this.api.post('/analyze', { url });
  }

  analyzeInteractive(analysisId: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/start`);
  }

  analyzeInteractiveWithUrl(analysisId: string, url: string): Observable<any> {
    return this.api.post(`/analyses/${analysisId}/editing/start`, { url });
  }

  getExecutions(taskId: string, params?: Record<string, string>): Observable<{ data: ExecutionLog[] }> {
    return this.api.get(`/tasks/${taskId}/executions`, params);
  }

  getExecution(id: string): Observable<{ data: ExecutionLog }> {
    return this.api.get(`/executions/${id}`);
  }
}
