import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { DatePipe, SlicePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule, MatTableDataSource } from '@angular/material/table';
import { MatPaginator, MatPaginatorModule } from '@angular/material/paginator';
import { MatSort, MatSortModule } from '@angular/material/sort';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { ApiService } from '../../core/services/api.service';
import { ExecutionLog } from '../../core/models/execution-log.model';
import { ScreenshotViewerComponent } from '../../shared/components/screenshot-viewer.component';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [
    DatePipe,
    SlicePipe,
    FormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatSortModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
  ],
  template: `
    <div class="logs-page">
      <h1>Execution Logs</h1>

      <!-- Filters -->
      <mat-card class="mb-2">
        <mat-card-content>
          <div class="filters flex gap-2 items-center">
            <mat-form-field appearance="outline">
              <mat-label>Search</mat-label>
              <input matInput [(ngModel)]="searchText" (ngModelChange)="applyFilter()" placeholder="Search logs...">
              <mat-icon matSuffix>search</mat-icon>
            </mat-form-field>

            <mat-form-field appearance="outline">
              <mat-label>Status</mat-label>
              <mat-select [(ngModel)]="statusFilter" (ngModelChange)="applyFilter()">
                <mat-option value="">All</mat-option>
                <mat-option value="queued">Queued</mat-option>
                <mat-option value="running">Running</mat-option>
                <mat-option value="success">Success</mat-option>
                <mat-option value="failed">Failed</mat-option>
                <mat-option value="waiting_manual">Waiting Manual</mat-option>
                <mat-option value="dry_run_ok">Dry Run OK</mat-option>
              </mat-select>
            </mat-form-field>

            <button mat-icon-button (click)="loadLogs()" matTooltip="Refresh">
              <mat-icon>refresh</mat-icon>
            </button>
          </div>
        </mat-card-content>
      </mat-card>

      @if (loading()) {
        <div class="flex items-center justify-center" style="padding: 48px;">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <div class="table-container">
          <table mat-table [dataSource]="dataSource" matSort class="full-width">
            <!-- Status Column -->
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Status</th>
              <td mat-cell *matCellDef="let log">
                <mat-chip [class]="'status-' + log.status" class="status-chip">
                  {{ log.status }}
                </mat-chip>
                @if (log.is_dry_run) {
                  <mat-chip class="dry-chip">DRY</mat-chip>
                }
              </td>
            </ng-container>

            <!-- Task Column -->
            <ng-container matColumnDef="task_id">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Task</th>
              <td mat-cell *matCellDef="let log">
                <a class="task-link" (click)="goToTask(log.task_id)">{{ log.task_id | slice:0:8 }}...</a>
              </td>
            </ng-container>

            <!-- Started Column -->
            <ng-container matColumnDef="started_at">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Started</th>
              <td mat-cell *matCellDef="let log">
                {{ log.started_at ? (log.started_at | date:'short') : '-' }}
              </td>
            </ng-container>

            <!-- Completed Column -->
            <ng-container matColumnDef="completed_at">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Completed</th>
              <td mat-cell *matCellDef="let log">
                {{ log.completed_at ? (log.completed_at | date:'short') : '-' }}
              </td>
            </ng-container>

            <!-- Retries Column -->
            <ng-container matColumnDef="retry_count">
              <th mat-header-cell *matHeaderCellDef mat-sort-header>Retries</th>
              <td mat-cell *matCellDef="let log">{{ log.retry_count }}</td>
            </ng-container>

            <!-- Error Column -->
            <ng-container matColumnDef="error_message">
              <th mat-header-cell *matHeaderCellDef>Error</th>
              <td mat-cell *matCellDef="let log">
                @if (log.error_message) {
                  <span class="error-text" [matTooltip]="log.error_message">
                    {{ log.error_message | slice:0:50 }}
                  </span>
                } @else {
                  -
                }
              </td>
            </ng-container>

            <!-- Actions Column -->
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef>Actions</th>
              <td mat-cell *matCellDef="let log">
                @if (log.screenshot_path) {
                  <button mat-icon-button matTooltip="Screenshot" (click)="viewScreenshot(log.id)">
                    <mat-icon>photo_camera</mat-icon>
                  </button>
                }
                <button mat-icon-button matTooltip="View Task" (click)="goToTask(log.task_id)">
                  <mat-icon>open_in_new</mat-icon>
                </button>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
          </table>

          <mat-paginator [pageSizeOptions]="[10, 25, 50]" showFirstLastButtons></mat-paginator>
        </div>
      }
    </div>
  `,
  styles: [`
    .filters { flex-wrap: wrap; }
    .table-container { overflow-x: auto; }
    .task-link { color: #3f51b5; cursor: pointer; text-decoration: underline; }
    .error-text { color: #f44336; font-size: 13px; }
    .status-chip { font-size: 11px; }
    .dry-chip { font-size: 10px; margin-left: 4px; }
    .status-success { background-color: #4caf50 !important; color: white !important; }
    .status-failed { background-color: #f44336 !important; color: white !important; }
    .status-running { background-color: #2196f3 !important; color: white !important; }
    .status-queued { background-color: #9e9e9e !important; color: white !important; }
    .status-waiting_manual { background-color: #ff9800 !important; color: white !important; }
    .status-dry_run_ok { background-color: #8bc34a !important; color: white !important; }
  `]
})
export class LogsComponent implements OnInit {
  @ViewChild(MatPaginator) paginator!: MatPaginator;
  @ViewChild(MatSort) sort!: MatSort;

  private api = inject(ApiService);
  private router = inject(Router);
  private dialog = inject(MatDialog);

  loading = signal(true);
  searchText = '';
  statusFilter = '';

  displayedColumns = ['status', 'task_id', 'started_at', 'completed_at', 'retry_count', 'error_message', 'actions'];
  dataSource = new MatTableDataSource<ExecutionLog>([]);
  private hadStatusFilter = false;

  ngOnInit() {
    this.loadLogs();
  }

  ngAfterViewInit() {
    this.dataSource.paginator = this.paginator;
    this.dataSource.sort = this.sort;
  }

  loadLogs() {
    this.loading.set(true);
    const params: Record<string, string> = {};
    if (this.statusFilter) params['status'] = this.statusFilter;
    this.hadStatusFilter = !!this.statusFilter;

    this.api.get<{ data: ExecutionLog[] }>('/logs', params).subscribe({
      next: (res) => {
        this.dataSource.data = res.data;
        this.dataSource.filter = this.searchText.trim().toLowerCase();
        this.loading.set(false);
      },
      error: () => this.loading.set(false)
    });
  }

  applyFilter() {
    this.dataSource.filter = this.searchText.trim().toLowerCase();
    if (this.statusFilter || this.hadStatusFilter) {
      this.loadLogs();
    }
  }

  goToTask(taskId: string) {
    this.router.navigate(['/tasks', taskId]);
  }

  viewScreenshot(executionId: string) {
    this.dialog.open(ScreenshotViewerComponent, {
      data: { executionId },
      maxWidth: '90vw',
      maxHeight: '90vh',
    });
  }
}
