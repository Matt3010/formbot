import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { DatePipe, UpperCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDividerModule } from '@angular/material/divider';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';
import { Subscription } from 'rxjs';
import { TaskService } from '../../core/services/task.service';
import { NotificationService } from '../../core/services/notification.service';
import { WebSocketService, ExecutionProgress } from '../../core/services/websocket.service';
import { Task } from '../../core/models/task.model';
import { ExecutionLogComponent } from './execution-log.component';
import { VncViewerComponent } from './vnc-viewer.component';
import { FormPreviewComponent } from '../../shared/components/form-preview.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-task-detail',
  standalone: true,
  imports: [
    DatePipe,
    UpperCasePipe,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatTabsModule,
    MatDividerModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    ExecutionLogComponent,
    VncViewerComponent,
    FormPreviewComponent,
  ],
  template: `
    @if (loading()) {
      <div class="flex items-center justify-center" style="padding: 64px;">
        <mat-spinner></mat-spinner>
      </div>
    } @else if (task()) {
      <div class="task-detail">
        <div class="task-header mb-2">
          <div class="task-title-block">
            <h1>{{ task()!.name }}</h1>
            <mat-chip [class]="'status-' + task()!.status">
              {{ task()!.status | uppercase }}
            </mat-chip>
          </div>

          <div class="task-actions">
            <button mat-raised-button color="primary" (click)="execute()" matTooltip="Execute now"
              [disabled]="task()!.status === 'draft'">
              <mat-icon>play_arrow</mat-icon> Execute
            </button>
            <button mat-stroked-button (click)="dryRun()" matTooltip="Dry run (no submit)">
              <mat-icon>science</mat-icon> Dry Run
            </button>

            @if (task()!.status === 'active') {
              <button mat-stroked-button color="warn" (click)="pause()">
                <mat-icon>pause</mat-icon> Pause
              </button>
            }

            <button mat-stroked-button (click)="clone()">
              <mat-icon>content_copy</mat-icon> Clone
            </button>

            <button mat-stroked-button (click)="exportTask()">
              <mat-icon>download</mat-icon> Export
            </button>

            <button mat-stroked-button (click)="edit()">
              <mat-icon>edit</mat-icon> Edit
            </button>

            <button mat-icon-button color="warn" (click)="deleteTask()" matTooltip="Delete task">
              <mat-icon>delete</mat-icon>
            </button>
          </div>
        </div>

        <mat-divider class="mb-2"></mat-divider>

        <!-- Execution Progress Bar -->
        @if (executionStatus()) {
          <mat-card class="mb-2 execution-progress-card">
            <mat-card-content>
              <div class="flex items-center gap-2">
                <mat-spinner diameter="20"></mat-spinner>
                <span class="progress-text">{{ executionStatus() }}</span>
              </div>
            </mat-card-content>
          </mat-card>
        }

        <!-- Task Info -->
        <mat-card class="mb-2">
          <mat-card-content>
            <div class="info-grid">
              <div class="info-item">
                <span class="info-label">Target URL</span>
                <span class="info-value">{{ task()!.target_url }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Schedule</span>
                <span class="info-value">
                  @if (task()!.schedule_type === 'cron') {
                    Recurring: {{ task()!.schedule_cron }}
                  } @else if (task()!.schedule_at) {
                    Once: {{ task()!.schedule_at | date:'medium' }}
                  } @else {
                    Manual
                  }
                </span>
              </div>
              <div class="info-item">
                <span class="info-label">Stealth Mode</span>
                <span class="info-value">{{ task()!.stealth_enabled ? 'Enabled' : 'Disabled' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Action Delay</span>
                <span class="info-value">{{ task()!.action_delay_ms }}ms</span>
              </div>
              <div class="info-item">
                <span class="info-label">Max Retries</span>
                <span class="info-value">{{ task()!.max_retries }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Dry Run</span>
                <span class="info-value">{{ task()!.is_dry_run ? 'Yes' : 'No' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Created</span>
                <span class="info-value">{{ task()!.created_at | date:'medium' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">Updated</span>
                <span class="info-value">{{ task()!.updated_at | date:'medium' }}</span>
              </div>
            </div>
          </mat-card-content>
        </mat-card>

        @if (vncUrl()) {
          <app-vnc-viewer
            [vncUrl]="vncUrl()!"
            [executionId]="vncExecutionId()!"
            (resumed)="onVncResumed()"
          />
        }

        <!-- Tabs: Forms & Executions -->
        <mat-tab-group>
          <mat-tab label="Forms ({{ task()!.form_definitions?.length || 0 }})">
            <div class="tab-content">
              @if (task()!.form_definitions?.length) {
                @for (form of task()!.form_definitions; track form.id) {
                  <app-form-preview [form]="form" class="mb-2" />
                }
              } @else {
                <p class="no-data">No form definitions configured.</p>
              }
            </div>
          </mat-tab>

          <mat-tab label="Executions">
            <div class="tab-content">
              <app-execution-log
                [taskId]="task()!.id"
                [liveUpdate]="lastExecutionUpdate()"
                (openVnc)="onOpenVnc($event)"
              />
            </div>
          </mat-tab>
        </mat-tab-group>
      </div>
    }
  `,
  styles: [`
    .task-detail { padding-bottom: 48px; }
    .task-header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
    }
    .task-title-block h1 {
      margin: 0 0 8px 0;
      line-height: 1.2;
    }
    .task-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }
    .info-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 16px;
    }
    .info-item { display: flex; flex-direction: column; }
    .info-label { font-size: 12px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; }
    .info-value { font-size: 15px; margin-top: 4px; }
    .tab-content { padding: 16px 0; }
    .no-data { text-align: center; color: #999; padding: 32px; }
    .execution-progress-card { border-left: 4px solid #2196f3; }
    .progress-text { font-size: 14px; color: #2196f3; }
    .status-draft { background-color: #9e9e9e !important; color: white !important; }
    .status-active { background-color: #4caf50 !important; color: white !important; }
    .status-paused { background-color: #ff9800 !important; color: white !important; }
    .status-completed { background-color: #2196f3 !important; color: white !important; }
    .status-failed { background-color: #f44336 !important; color: white !important; }
    .status-running { background-color: #2196f3 !important; color: white !important; }
    .status-waiting_manual { background-color: #ff9800 !important; color: white !important; }
    @media (max-width: 959px) {
      .task-actions {
        width: 100%;
        justify-content: flex-start;
      }
    }
  `]
})
export class TaskDetailComponent implements OnInit, OnDestroy {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);
  private ws = inject(WebSocketService);
  private dialog = inject(MatDialog);
  private subs: Subscription[] = [];

  task = signal<Task | null>(null);
  loading = signal(true);
  vncUrl = signal<string | null>(null);
  vncExecutionId = signal<string | null>(null);
  executionStatus = signal<string | null>(null);
  lastExecutionUpdate = signal<ExecutionProgress | null>(null);

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.loadTask(id);
    }

    // Connect WebSocket
    this.ws.connect();

    // Subscribe to task updates
    this.subs.push(
      this.ws.taskUpdated$.subscribe(data => {
        const current = this.task();
        if (current && current.id === data.id) {
          this.task.set({ ...current, status: data.status, updated_at: data.updated_at || current.updated_at });
        }
      })
    );

    // Subscribe to execution progress
    this.subs.push(
      this.ws.executionProgress$.subscribe(data => {
        const current = this.task();
        if (!current || data.task_id !== current.id) return;

        this.lastExecutionUpdate.set(data);
        this.updateExecutionStatus(data);
      })
    );

    // Subscribe to VNC waiting events
    this.subs.push(
      this.ws.executionWaitingManual$.subscribe(data => {
        const current = this.task();
        if (!current || data.task_id !== current.id) return;

        if (data.vnc_url) {
          this.vncUrl.set(data.vnc_url);
          this.vncExecutionId.set(data.execution_id);
          this.executionStatus.set(`Waiting for manual intervention (${data.reason})...`);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }
      })
    );

    // Subscribe to task deletion
    this.subs.push(
      this.ws.taskDeleted$.subscribe(data => {
        const current = this.task();
        if (current && current.id === data.id) {
          this.notify.info('This task has been deleted');
          this.router.navigate(['/dashboard']);
        }
      })
    );
  }

  ngOnDestroy() {
    this.subs.forEach(s => s.unsubscribe());
  }

  private updateExecutionStatus(data: ExecutionProgress) {
    switch (data.status) {
      case 'running':
        if (data.step != null && data.total_steps) {
          this.executionStatus.set(`Step ${data.step}/${data.total_steps}: Navigating to ${data.page_url || 'page'}...`);
        } else {
          this.executionStatus.set('Execution started...');
        }
        break;
      case 'submitted':
        this.executionStatus.set(`Step ${data.step}/${data.total_steps}: Form submitted`);
        break;
      case 'waiting_manual':
        // Handled by executionWaitingManual$ subscription
        break;
      case 'success':
      case 'dry_run_ok':
        this.executionStatus.set(null);
        this.loadTask(this.task()!.id);
        break;
      case 'failed':
        this.executionStatus.set(null);
        this.notify.error(data.error || 'Execution failed');
        this.loadTask(this.task()!.id);
        break;
      default:
        if (data.field_name) {
          this.executionStatus.set(`Filling field: ${data.field_name}...`);
        }
    }
  }

  loadTask(id: string) {
    this.loading.set(true);
    this.taskService.getTask(id).subscribe({
      next: (res) => {
        this.task.set(res.data);
        this.loading.set(false);
      },
      error: () => {
        this.notify.error('Failed to load task');
        this.loading.set(false);
      }
    });
  }

  execute() {
    this.taskService.executeTask(this.task()!.id).subscribe({
      next: () => {
        this.notify.success('Execution started');
        this.executionStatus.set('Execution queued...');
      },
      error: () => this.notify.error('Failed to start execution')
    });
  }

  dryRun() {
    this.taskService.dryRunTask(this.task()!.id).subscribe({
      next: () => {
        this.notify.success('Dry run started');
        this.executionStatus.set('Dry run queued...');
      },
      error: () => this.notify.error('Failed to start dry run')
    });
  }

  pause() {
    this.taskService.pauseTask(this.task()!.id).subscribe({
      next: () => {
        this.notify.success('Task paused');
      },
      error: () => this.notify.error('Failed to pause task')
    });
  }

  clone() {
    this.taskService.cloneTask(this.task()!.id).subscribe({
      next: (res) => {
        this.notify.success('Task cloned');
        this.router.navigate(['/tasks', res.data.id]);
      },
      error: () => this.notify.error('Failed to clone task')
    });
  }

  exportTask() {
    this.taskService.exportTask(this.task()!.id).subscribe({
      next: (data) => {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `task-${this.task()!.name}.json`;
        a.click();
        URL.revokeObjectURL(url);
        this.notify.success('Task exported');
      },
      error: () => this.notify.error('Failed to export task')
    });
  }

  edit() {
    this.router.navigate(['/tasks', this.task()!.id, 'edit']);
  }

  deleteTask() {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Task',
        message: `Are you sure you want to delete "${this.task()!.name}"? This action cannot be undone.`
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.taskService.deleteTask(this.task()!.id).subscribe({
          next: () => {
            this.notify.success('Task deleted');
            this.router.navigate(['/dashboard']);
          },
          error: () => this.notify.error('Failed to delete task')
        });
      }
    });
  }

  onVncResumed() {
    this.vncUrl.set(null);
    this.vncExecutionId.set(null);
    this.executionStatus.set('Resumed, continuing execution...');
    this.loadTask(this.task()!.id);
  }

  onOpenVnc(event: { vncUrl: string; executionId: string }) {
    this.vncUrl.set(event.vncUrl);
    this.vncExecutionId.set(event.executionId);
    // Scroll to top where VNC viewer is rendered
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
