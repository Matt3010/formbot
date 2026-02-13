import { Component, inject, input, output, OnInit, OnChanges, SimpleChanges, signal } from '@angular/core';
import { DatePipe, UpperCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { TaskService } from '../../core/services/task.service';
import { ExecutionLog } from '../../core/models/execution-log.model';
import { ExecutionProgress } from '../../core/services/websocket.service';
import { ScreenshotViewerComponent } from '../../shared/components/screenshot-viewer.component';

@Component({
  selector: 'app-execution-log',
  standalone: true,
  imports: [
    DatePipe,
    UpperCasePipe,
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatChipsModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
  ],
  template: `
    <div class="execution-log">
      <h3>Execution History</h3>

      @if (loading()) {
        <div class="flex items-center justify-center" style="padding: 24px;">
          <mat-spinner diameter="32"></mat-spinner>
        </div>
      } @else if (executions().length === 0) {
        <p class="no-data">No executions yet.</p>
      } @else {
        <div class="timeline">
          @for (exec of executions(); track exec.id) {
            <mat-card class="timeline-item mb-2" [class]="'border-' + exec.status">
              <mat-card-content>
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2">
                    @if (exec.status === 'running' || exec.status === 'queued') {
                      <mat-spinner diameter="20"></mat-spinner>
                    } @else {
                      <mat-icon [class]="'status-icon ' + exec.status">{{ getStatusIcon(exec.status) }}</mat-icon>
                    }
                    <div>
                      <mat-chip [class]="'status-' + exec.status" class="status-chip">
                        {{ exec.status | uppercase }}
                      </mat-chip>
                      @if (exec.is_dry_run) {
                        <mat-chip class="dry-run-chip">DRY RUN</mat-chip>
                      }
                    </div>
                  </div>

                  <div class="exec-meta">
                    @if (exec.started_at) {
                      <span>{{ exec.started_at | date:'short' }}</span>
                    }
                    @if (exec.started_at && exec.completed_at) {
                      <span class="duration">{{ getDuration(exec.started_at, exec.completed_at) }}</span>
                    }
                  </div>
                </div>

                @if (exec.error_message) {
                  <div class="error-message mt-1">
                    <mat-icon class="small-icon">error</mat-icon>
                    {{ exec.error_message }}
                  </div>
                }

                @if (exec.retry_count > 0) {
                  <div class="retry-info mt-1">
                    <mat-icon class="small-icon">replay</mat-icon>
                    Retry {{ exec.retry_count }}
                  </div>
                }

                <div class="flex items-center gap-1 mt-1">
                  @if (exec.screenshot_path) {
                    <button mat-icon-button matTooltip="View Screenshot" (click)="viewScreenshot(exec.id)">
                      <mat-icon>photo_camera</mat-icon>
                    </button>
                  }
                  @if (exec.vnc_session_id && exec.status === 'waiting_manual') {
                    <button mat-raised-button color="warn" matTooltip="Open VNC viewer"
                      (click)="onOpenVnc(exec)">
                      <mat-icon>desktop_windows</mat-icon> Connect VNC
                    </button>
                  } @else if (exec.vnc_session_id) {
                    <button mat-icon-button matTooltip="VNC session (closed)" disabled>
                      <mat-icon>desktop_windows</mat-icon>
                    </button>
                  }
                </div>
              </mat-card-content>
            </mat-card>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .no-data { text-align: center; color: #999; padding: 24px; }
    .timeline-item { border-left: 4px solid #ccc; }
    .border-success { border-left-color: #4caf50 !important; }
    .border-failed { border-left-color: #f44336 !important; }
    .border-running { border-left-color: #2196f3 !important; }
    .border-queued { border-left-color: #9e9e9e !important; }
    .border-waiting_manual { border-left-color: #ff9800 !important; }
    .border-captcha_blocked { border-left-color: #ff5722 !important; }
    .border-2fa_required { border-left-color: #9c27b0 !important; }
    .border-dry_run_ok { border-left-color: #8bc34a !important; }
    .status-icon.success { color: #4caf50; }
    .status-icon.failed { color: #f44336; }
    .status-icon.running { color: #2196f3; }
    .status-icon.queued { color: #9e9e9e; }
    .status-icon.waiting_manual { color: #ff9800; }
    .status-chip { font-size: 11px; }
    .dry-run-chip { font-size: 11px; margin-left: 4px; }
    .status-success { background-color: #4caf50 !important; color: white !important; }
    .status-failed { background-color: #f44336 !important; color: white !important; }
    .status-running { background-color: #2196f3 !important; color: white !important; }
    .status-queued { background-color: #9e9e9e !important; color: white !important; }
    .status-waiting_manual { background-color: #ff9800 !important; color: white !important; }
    .status-captcha_blocked { background-color: #ff5722 !important; color: white !important; }
    .status-2fa_required { background-color: #9c27b0 !important; color: white !important; }
    .status-dry_run_ok { background-color: #8bc34a !important; color: white !important; }
    .error-message { color: #f44336; font-size: 13px; display: flex; align-items: center; gap: 4px; }
    .retry-info { color: #666; font-size: 13px; display: flex; align-items: center; gap: 4px; }
    .small-icon { font-size: 18px; width: 18px; height: 18px; }
    .exec-meta { color: #666; font-size: 13px; text-align: right; }
    .duration { display: block; font-weight: 500; }
  `]
})
export class ExecutionLogComponent implements OnInit, OnChanges {
  private taskService = inject(TaskService);
  private dialog = inject(MatDialog);

  taskId = input.required<string>();
  liveUpdate = input<ExecutionProgress | null>(null);
  openVnc = output<{ vncUrl: string; executionId: string }>();
  executions = signal<ExecutionLog[]>([]);
  loading = signal(true);

  ngOnInit() {
    this.loadExecutions();
  }

  ngOnChanges(changes: SimpleChanges) {
    if (changes['liveUpdate'] && this.liveUpdate()) {
      this.handleLiveUpdate(this.liveUpdate()!);
    }
  }

  private handleLiveUpdate(data: ExecutionProgress) {
    const execId = data.execution_id;
    if (!execId) return;

    this.executions.update(execs => {
      const idx = execs.findIndex(e => e.id === execId);
      if (idx !== -1) {
        // Update existing execution in-place
        const updated = { ...execs[idx] };
        if (data.status === 'success' || data.status === 'failed' || data.status === 'dry_run_ok') {
          updated.status = data.status as any;
          updated.completed_at = new Date().toISOString();
          if (data.error) updated.error_message = data.error;
          if (data.screenshot) updated.screenshot_path = data.screenshot;
        } else if (data.status === 'waiting_manual') {
          updated.status = 'waiting_manual';
        } else if (data.status === 'running') {
          updated.status = 'running';
        }
        return [...execs.slice(0, idx), updated, ...execs.slice(idx + 1)];
      } else {
        // New execution - add to front of list
        const newExec: ExecutionLog = {
          id: execId,
          task_id: data.task_id,
          started_at: data.started_at || new Date().toISOString(),
          completed_at: null,
          status: (data.status as any) || 'running',
          is_dry_run: data.is_dry_run || false,
          retry_count: 0,
          error_message: null,
          screenshot_path: null,
          steps_log: [],
          vnc_session_id: null,
          created_at: new Date().toISOString(),
        };
        return [newExec, ...execs];
      }
    });
  }

  loadExecutions() {
    this.loading.set(true);
    this.taskService.getExecutions(this.taskId()).subscribe({
      next: (res) => {
        this.executions.set(res.data);
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  getStatusIcon(status: string): string {
    const icons: Record<string, string> = {
      'queued': 'schedule',
      'running': 'play_circle',
      'waiting_manual': 'front_hand',
      'success': 'check_circle',
      'failed': 'cancel',
      'captcha_blocked': 'block',
      '2fa_required': 'security',
      'dry_run_ok': 'science',
    };
    return icons[status] || 'help';
  }

  getDuration(start: string, end: string): string {
    const ms = new Date(end).getTime() - new Date(start).getTime();
    if (ms < 1000) return `${ms}ms`;
    const seconds = Math.floor(ms / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}m ${secs}s`;
  }

  onOpenVnc(exec: ExecutionLog) {
    // Extract VNC URL from the last step that has one
    const vncStep = [...(exec.steps_log || [])].reverse().find(
      (s: any) => s.vnc_url
    );
    if (vncStep?.vnc_url) {
      this.openVnc.emit({ vncUrl: vncStep.vnc_url, executionId: exec.id });
    }
  }

  viewScreenshot(executionId: string) {
    this.dialog.open(ScreenshotViewerComponent, {
      data: { executionId },
      maxWidth: '90vw',
      maxHeight: '90vh',
    });
  }
}
