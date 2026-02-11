import { Component, computed, input } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { Task } from '../../core/models/task.model';

@Component({
  selector: 'app-stats-panel',
  standalone: true,
  imports: [MatCardModule, MatIconModule],
  template: `
    <div class="stats-grid">
      <mat-card class="stat-card">
        <mat-card-content>
          <div class="stat-row">
            <mat-icon class="stat-icon total">assignment</mat-icon>
            <div>
              <div class="stat-value">{{ totalCount() }}</div>
              <div class="stat-label">Total Tasks</div>
            </div>
          </div>
        </mat-card-content>
      </mat-card>

      <mat-card class="stat-card">
        <mat-card-content>
          <div class="stat-row">
            <mat-icon class="stat-icon active">play_circle</mat-icon>
            <div>
              <div class="stat-value">{{ activeCount() }}</div>
              <div class="stat-label">Active</div>
            </div>
          </div>
        </mat-card-content>
      </mat-card>

      <mat-card class="stat-card">
        <mat-card-content>
          <div class="stat-row">
            <mat-icon class="stat-icon paused">pause_circle</mat-icon>
            <div>
              <div class="stat-value">{{ pausedCount() }}</div>
              <div class="stat-label">Paused</div>
            </div>
          </div>
        </mat-card-content>
      </mat-card>

      <mat-card class="stat-card">
        <mat-card-content>
          <div class="stat-row">
            <mat-icon class="stat-icon failed">error</mat-icon>
            <div>
              <div class="stat-value">{{ failedCount() }}</div>
              <div class="stat-label">Failed</div>
            </div>
          </div>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [`
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .stat-card { text-align: center; }
    .stat-row { display: flex; align-items: center; gap: 16px; padding: 8px; }
    .stat-icon { font-size: 40px; width: 40px; height: 40px; }
    .stat-icon.total { color: #3f51b5; }
    .stat-icon.active { color: #4caf50; }
    .stat-icon.paused { color: #ff9800; }
    .stat-icon.failed { color: #f44336; }
    .stat-value { font-size: 28px; font-weight: 500; }
    .stat-label { color: #666; font-size: 14px; }
  `]
})
export class StatsPanelComponent {
  tasks = input<Task[]>([]);

  totalCount = computed(() => this.tasks().length);
  activeCount = computed(() => this.tasks().filter(t => t.status === 'active').length);
  pausedCount = computed(() => this.tasks().filter(t => t.status === 'paused').length);
  failedCount = computed(() => this.tasks().filter(t => t.status === 'failed').length);
}
