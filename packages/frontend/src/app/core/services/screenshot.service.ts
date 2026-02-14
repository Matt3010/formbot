import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ScreenshotListItem, ScreenshotStats, ScreenshotResponse } from '../models/execution-log.model';

export interface PaginatedResponse<T> {
  data: T[];
  meta: {
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
  };
}

@Injectable({ providedIn: 'root' })
export class ScreenshotService {
  private http = inject(HttpClient);
  private baseUrl = '/api';

  getScreenshots(page: number = 1, perPage: number = 25): Observable<PaginatedResponse<ScreenshotListItem>> {
    return this.http.get<PaginatedResponse<ScreenshotListItem>>(
      `${this.baseUrl}/screenshots`,
      { params: { page: page.toString(), per_page: perPage.toString() } }
    );
  }

  getStats(): Observable<ScreenshotStats> {
    return this.http.get<ScreenshotStats>(`${this.baseUrl}/screenshots/stats`);
  }

  getScreenshot(executionId: string): Observable<ScreenshotResponse | Blob> {
    return this.http.get(`${this.baseUrl}/executions/${executionId}/screenshot`, {
      responseType: 'blob',
      observe: 'response'
    }).pipe() as any;
  }

  deleteScreenshot(executionId: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/executions/${executionId}/screenshot`);
  }
}
