import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatChipsModule } from '@angular/material/chips';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { ScreenshotService } from '../../core/services/screenshot.service';
import { ScreenshotListItem, ScreenshotStats } from '../../core/models/execution-log.model';
import { ScreenshotViewerComponent } from '../../shared/components/screenshot-viewer.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-screenshots',
  standalone: true,
  imports: [
    DatePipe,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
    MatChipsModule,
  ],
  template: `
    <div class="screenshots-page">
      <h1>Screenshots</h1>

      <!-- Stats Card -->
      <mat-card class="stats-card mb-3">
        <mat-card-content>
          @if (loadingStats()) {
            <div class="stats-loading">
              <mat-spinner diameter="24"></mat-spinner>
            </div>
          } @else if (stats()) {
            <div class="stats-grid">
              <div class="stat-item">
                <span class="stat-value">{{ stats()!.total.count }}</span>
                <span class="stat-label">Total Screenshots</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ formatSize(stats()!.total.total_size) }}</span>
                <span class="stat-label">Total Size</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ stats()!.minio.count }}</span>
                <span class="stat-label">MinIO Storage</span>
              </div>
              <div class="stat-item">
                <span class="stat-value">{{ stats()!.filesystem.count }}</span>
                <span class="stat-label">Filesystem (Legacy)</span>
              </div>
            </div>
          }
        </mat-card-content>
      </mat-card>

      <!-- Screenshots Table -->
      @if (loading()) {
        <div class="flex items-center justify-center" style="padding: 48px;">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <div class="table-container">
          <table mat-table [dataSource]="screenshots()" class="full-width">
            <!-- Task Column -->
            <ng-container matColumnDef="task_name">
              <th mat-header-cell *matHeaderCellDef>Task</th>
              <td mat-cell *matCellDef="let item">
                <a class="task-link" (click)="goToTask(item.task_id)">{{ item.task_name }}</a>
              </td>
            </ng-container>

            <!-- Date Column -->
            <ng-container matColumnDef="created_at">
              <th mat-header-cell *matHeaderCellDef>Date</th>
              <td mat-cell *matCellDef="let item">
                {{ item.created_at | date:'medium' }}
              </td>
            </ng-container>

            <!-- Size Column -->
            <ng-container matColumnDef="size">
              <th mat-header-cell *matHeaderCellDef>Size</th>
              <td mat-cell *matCellDef="let item">
                {{ item.size ? formatSize(item.size) : '-' }}
              </td>
            </ng-container>

            <!-- Storage Column -->
            <ng-container matColumnDef="storage">
              <th mat-header-cell *matHeaderCellDef>Storage</th>
              <td mat-cell *matCellDef="let item">
                <mat-chip [class]="'storage-' + item.storage" class="storage-chip">
                  {{ item.storage === 'minio' ? 'MinIO' : 'Filesystem' }}
                </mat-chip>
              </td>
            </ng-container>

            <!-- Actions Column -->
            <ng-container matColumnDef="actions">
              <th mat-header-cell *matHeaderCellDef>Actions</th>
              <td mat-cell *matCellDef="let item">
                <button mat-icon-button matTooltip="View" (click)="viewScreenshot(item.execution_id)">
                  <mat-icon>visibility</mat-icon>
                </button>
                <button mat-icon-button matTooltip="Delete" color="warn" (click)="confirmDelete(item)">
                  <mat-icon>delete</mat-icon>
                </button>
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
          </table>

          @if (screenshots().length === 0) {
            <div class="empty-state">
              <mat-icon>photo_library</mat-icon>
              <p>No screenshots found</p>
            </div>
          }

          <mat-paginator
            [length]="totalItems()"
            [pageSize]="pageSize"
            [pageSizeOptions]="[10, 25, 50]"
            [pageIndex]="currentPage() - 1"
            (page)="onPageChange($event)"
            showFirstLastButtons>
          </mat-paginator>
        </div>
      }
    </div>
  `,
  styles: [`
    .stats-card { margin-bottom: 24px; }
    .stats-loading { display: flex; justify-content: center; padding: 16px; }
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 24px;
    }
    .stat-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    .stat-value {
      font-size: 24px;
      font-weight: 500;
      color: #3f51b5;
    }
    .stat-label {
      font-size: 13px;
      color: #666;
      margin-top: 4px;
    }
    .table-container { overflow-x: auto; }
    .task-link { color: #3f51b5; cursor: pointer; text-decoration: underline; }
    .storage-chip { font-size: 11px; }
    .storage-minio { background-color: #4caf50 !important; color: white !important; }
    .storage-filesystem { background-color: #9e9e9e !important; color: white !important; }
    .empty-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 48px;
      color: #999;
    }
    .empty-state mat-icon {
      font-size: 48px;
      width: 48px;
      height: 48px;
      margin-bottom: 16px;
    }
  `]
})
export class ScreenshotsComponent implements OnInit {
  private screenshotService = inject(ScreenshotService);
  private router = inject(Router);
  private dialog = inject(MatDialog);
  private notification = inject(NotificationService);

  loading = signal(true);
  loadingStats = signal(true);
  screenshots = signal<ScreenshotListItem[]>([]);
  stats = signal<ScreenshotStats | null>(null);

  currentPage = signal(1);
  totalItems = signal(0);
  pageSize = 25;

  displayedColumns = ['task_name', 'created_at', 'size', 'storage', 'actions'];

  ngOnInit() {
    this.loadScreenshots();
    this.loadStats();
  }

  loadScreenshots() {
    this.loading.set(true);
    this.screenshotService.getScreenshots(this.currentPage(), this.pageSize).subscribe({
      next: (res) => {
        this.screenshots.set(res.data);
        this.totalItems.set(res.meta.total);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.notification.error('Failed to load screenshots');
      }
    });
  }

  loadStats() {
    this.loadingStats.set(true);
    this.screenshotService.getStats().subscribe({
      next: (stats) => {
        this.stats.set(stats);
        this.loadingStats.set(false);
      },
      error: () => {
        this.loadingStats.set(false);
      }
    });
  }

  onPageChange(event: PageEvent) {
    this.currentPage.set(event.pageIndex + 1);
    this.pageSize = event.pageSize;
    this.loadScreenshots();
  }

  formatSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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

  confirmDelete(item: ScreenshotListItem) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Screenshot',
        message: `Are you sure you want to delete this screenshot from "${item.task_name}"?`,
        confirmText: 'Delete',
        confirmColor: 'warn'
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.deleteScreenshot(item.execution_id);
      }
    });
  }

  deleteScreenshot(executionId: string) {
    this.screenshotService.deleteScreenshot(executionId).subscribe({
      next: () => {
        this.notification.success('Screenshot deleted');
        this.loadScreenshots();
        this.loadStats();
      },
      error: () => {
        this.notification.error('Failed to delete screenshot');
      }
    });
  }
}
