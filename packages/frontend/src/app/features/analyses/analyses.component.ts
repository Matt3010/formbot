import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatDialog } from '@angular/material/dialog';
import { AnalysisService } from '../../core/services/analysis.service';
import { NotificationService } from '../../core/services/notification.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { Analysis } from '../../core/models/analysis.model';
import { AnalysisCardComponent } from './analysis-card.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-analyses',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatSelectModule,
    AnalysisCardComponent,
  ],
  template: `
    <div class="analyses-page">
      <div class="flex items-center justify-between mb-2">
        <h1>Analyses</h1>
      </div>

      @if (loading()) {
        <div class="flex items-center justify-center" style="padding: 48px;">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <div class="filters flex gap-2 mb-2">
          <mat-form-field appearance="outline" style="width: 200px;">
            <mat-label>Status</mat-label>
            <mat-select [ngModel]="statusFilter()" (ngModelChange)="onStatusFilterChange($event)">
              <mat-option value="">All</mat-option>
              <mat-option value="pending">Pending</mat-option>
              <mat-option value="analyzing">Analyzing</mat-option>
              <mat-option value="completed">Completed</mat-option>
              <mat-option value="failed">Failed</mat-option>
              <mat-option value="cancelled">Cancelled</mat-option>
              <mat-option value="timed_out">Timed Out</mat-option>
              <mat-option value="editing">Editing</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        @if (analyses().length === 0) {
          <div class="empty-state">
            <mat-icon class="empty-icon">analytics</mat-icon>
            <h2>No analyses yet</h2>
            <p>Analyses are created automatically when you analyze a URL in the task wizard. They'll appear here so you can track and resume them.</p>
            <button mat-raised-button color="primary" (click)="goToNewTask()">
              <mat-icon>add</mat-icon> New Task
            </button>
          </div>
        } @else {
          <div class="analysis-grid">
            @for (analysis of analyses(); track analysis.id) {
              <app-analysis-card
                [analysis]="analysis"
                (resume)="resumeAnalysis(analysis)"
                (resumeEditing)="resumeEditingSession(analysis)"
                (cancel)="cancelAnalysis(analysis)"
                (viewTask)="viewTask(analysis)"
              />
            }
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .analyses-page { padding-bottom: 32px; }
    .analysis-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
      gap: 16px;
    }
    .empty-state {
      text-align: center;
      padding: 64px 16px;
      color: #666;
    }
    .empty-icon {
      font-size: 72px;
      width: 72px;
      height: 72px;
      color: #ccc;
    }
  `]
})
export class AnalysesComponent implements OnInit, OnDestroy {
  private analysisService = inject(AnalysisService);
  private ws = inject(WebSocketService);
  private router = inject(Router);
  private notify = inject(NotificationService);
  private dialog = inject(MatDialog);

  /** WebSocket subscriptions keyed by analysis ID for cleanup. */
  private wsSubs = new Map<string, Subscription>();

  analyses = signal<Analysis[]>([]);
  loading = signal(true);
  statusFilter = signal('');

  ngOnInit() {
    this.loadAnalyses();
  }

  ngOnDestroy() {
    this.unsubscribeAll();
  }

  loadAnalyses() {
    const params: Record<string, string> = {};
    const status = this.statusFilter();
    if (status) params['status'] = status;

    this.analysisService.getAnalyses(params).subscribe({
      next: (res) => {
        this.analyses.set(res.data);
        this.loading.set(false);
        this.subscribeToActiveAnalyses();
      },
      error: () => {
        this.notify.error('Failed to load analyses');
        this.loading.set(false);
      }
    });
  }

  onStatusFilterChange(value: string) {
    this.statusFilter.set(value);
    this.loading.set(true);
    this.loadAnalyses();
  }

  resumeAnalysis(analysis: Analysis) {
    this.analysisService.setPendingResume(analysis);
    this.router.navigate(['/tasks/new'], { queryParams: { analysisId: analysis.id } });
  }

  cancelAnalysis(analysis: Analysis) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Cancel Analysis',
        message: `Are you sure you want to cancel the analysis of "${analysis.url}"?`
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.analysisService.cancelAnalysis(analysis.id).subscribe({
          next: () => {
            this.notify.success('Analysis cancelled');
            this.updateAnalysisInList(analysis.id, { status: 'cancelled' as const });
            this.cleanupSubscription(analysis.id);
          },
          error: () => this.notify.error('Failed to cancel analysis')
        });
      }
    });
  }

  resumeEditingSession(analysis: Analysis) {
    this.analysisService.setPendingResume(analysis);
    this.router.navigate(['/tasks/new'], { queryParams: { analysisId: analysis.id, editing: 'resume' } });
  }

  viewTask(analysis: Analysis) {
    if (analysis.task_id) {
      this.router.navigate(['/tasks', analysis.task_id]);
    }
  }

  goToNewTask() {
    this.router.navigate(['/tasks/new']);
  }

  /**
   * Subscribe to WebSocket channels for all active (pending/analyzing) analyses.
   * When an AnalysisCompleted event fires, the card updates instantly.
   */
  private subscribeToActiveAnalyses() {
    const active = this.analyses().filter(
      a => a.status === 'pending' || a.status === 'analyzing'
    );

    // Unsubscribe from analyses that are no longer active
    for (const [id, sub] of this.wsSubs) {
      if (!active.some(a => a.id === id)) {
        sub.unsubscribe();
        this.wsSubs.delete(id);
      }
    }

    // Subscribe to new active analyses
    for (const analysis of active) {
      if (this.wsSubs.has(analysis.id)) continue;

      const sub = this.ws.waitForAnalysis(analysis.id).subscribe({
        next: (data) => {
          if (data.error) {
            this.updateAnalysisInList(analysis.id, {
              status: 'failed',
              error: data.error,
              completed_at: new Date().toISOString(),
            });
          } else {
            this.updateAnalysisInList(analysis.id, {
              status: 'completed',
              result: data.result,
              error: null,
              completed_at: new Date().toISOString(),
            });
          }
          this.wsSubs.delete(analysis.id);
        }
      });

      this.wsSubs.set(analysis.id, sub);
    }
  }

  private updateAnalysisInList(id: string, patch: Partial<Analysis>) {
    this.analyses.update(list =>
      list.map(a => a.id === id ? { ...a, ...patch } : a)
    );
  }

  private cleanupSubscription(id: string) {
    const sub = this.wsSubs.get(id);
    if (sub) {
      sub.unsubscribe();
      this.wsSubs.delete(id);
    }
  }

  private unsubscribeAll() {
    for (const sub of this.wsSubs.values()) {
      sub.unsubscribe();
    }
    this.wsSubs.clear();
  }
}
