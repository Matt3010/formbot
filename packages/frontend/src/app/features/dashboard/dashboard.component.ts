import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialog } from '@angular/material/dialog';
import { TaskService } from '../../core/services/task.service';
import { NotificationService } from '../../core/services/notification.service';
import { Task } from '../../core/models/task.model';
import { TaskCardComponent } from './task-card.component';
import { StatsPanelComponent } from './stats-panel.component';
import { ConfirmDialogComponent } from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    TaskCardComponent,
    StatsPanelComponent,
  ],
  template: `
    <div class="dashboard">
      <div class="flex items-center justify-between mb-2">
        <h1>Dashboard</h1>
        <button mat-fab color="primary" (click)="createTask()" matTooltip="New Task">
          <mat-icon>add</mat-icon>
        </button>
      </div>

      @if (loading()) {
        <div class="flex items-center justify-center" style="padding: 48px;">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <app-stats-panel [tasks]="tasks()" />

        <div class="filters flex gap-2 mb-2">
          <mat-form-field appearance="outline" class="filter-search">
            <mat-label>Search tasks</mat-label>
            <input matInput [ngModel]="searchQuery()" (ngModelChange)="searchQuery.set($event)" placeholder="Name or URL...">
            <mat-icon matSuffix>search</mat-icon>
          </mat-form-field>
          <mat-form-field appearance="outline" style="width: 180px;">
            <mat-label>Status</mat-label>
            <mat-select [ngModel]="statusFilter()" (ngModelChange)="statusFilter.set($event)">
              <mat-option value="">All</mat-option>
              <mat-option value="draft">Draft</mat-option>
              <mat-option value="active">Active</mat-option>
              <mat-option value="paused">Paused</mat-option>
              <mat-option value="completed">Completed</mat-option>
              <mat-option value="failed">Failed</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        @if (filteredTasks().length === 0 && tasks().length > 0) {
          <div class="empty-state">
            <mat-icon class="empty-icon">filter_list_off</mat-icon>
            <h2>No matching tasks</h2>
            <p>Try adjusting your search or filters.</p>
          </div>
        } @else if (tasks().length === 0) {
          <div class="empty-state">
            <mat-icon class="empty-icon">inbox</mat-icon>
            <h2>No tasks yet</h2>
            <p>Create your first automation task to get started.</p>
            <button mat-raised-button color="primary" (click)="createTask()">
              <mat-icon>add</mat-icon> Create Task
            </button>
          </div>
        } @else {
          <div class="task-grid">
            @for (task of filteredTasks(); track task.id) {
              <app-task-card
                [task]="task"
                (view)="viewTask(task)"
                (execute)="executeTask(task)"
                (pause)="pauseTask(task)"
                (clone)="cloneTask(task)"
                (edit)="editTask(task)"
                (deleteTask)="deleteTask(task)"
              />
            }
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .dashboard { padding-bottom: 32px; }
    .task-grid {
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
    .filter-search { flex: 1; }
  `]
})
export class DashboardComponent implements OnInit {
  private taskService = inject(TaskService);
  private router = inject(Router);
  private notify = inject(NotificationService);
  private dialog = inject(MatDialog);

  tasks = signal<Task[]>([]);
  loading = signal(true);
  searchQuery = signal('');
  statusFilter = signal('');

  filteredTasks = computed(() => {
    let result = this.tasks();
    const query = this.searchQuery().toLowerCase();
    const status = this.statusFilter();
    if (query) {
      result = result.filter(t =>
        t.name.toLowerCase().includes(query) ||
        t.target_url.toLowerCase().includes(query)
      );
    }
    if (status) {
      result = result.filter(t => t.status === status);
    }
    return result;
  });

  ngOnInit() {
    this.loadTasks();
  }

  loadTasks() {
    this.loading.set(true);
    this.taskService.getTasks().subscribe({
      next: (res) => {
        this.tasks.set(res.data);
        this.loading.set(false);
      },
      error: () => {
        this.notify.error('Failed to load tasks');
        this.loading.set(false);
      }
    });
  }

  createTask() {
    this.router.navigate(['/tasks/new']);
  }

  viewTask(task: Task) {
    this.router.navigate(['/tasks', task.id]);
  }

  editTask(task: Task) {
    this.router.navigate(['/tasks', task.id, 'edit']);
  }

  executeTask(task: Task) {
    this.taskService.executeTask(task.id).subscribe({
      next: () => {
        this.notify.success(`Task "${task.name}" execution started`);
        this.loadTasks();
      },
      error: () => this.notify.error('Failed to execute task')
    });
  }

  pauseTask(task: Task) {
    this.taskService.pauseTask(task.id).subscribe({
      next: () => {
        this.notify.success(`Task "${task.name}" paused`);
        this.loadTasks();
      },
      error: () => this.notify.error('Failed to pause task')
    });
  }

  cloneTask(task: Task) {
    this.taskService.cloneTask(task.id).subscribe({
      next: (res) => {
        this.notify.success(`Task cloned as "${res.data.name}"`);
        this.loadTasks();
      },
      error: () => this.notify.error('Failed to clone task')
    });
  }

  deleteTask(task: Task) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      data: {
        title: 'Delete Task',
        message: `Are you sure you want to delete "${task.name}"? This action cannot be undone.`
      }
    });

    dialogRef.afterClosed().subscribe(confirmed => {
      if (confirmed) {
        this.taskService.deleteTask(task.id).subscribe({
          next: () => {
            this.notify.success('Task deleted');
            this.loadTasks();
          },
          error: () => this.notify.error('Failed to delete task')
        });
      }
    });
  }
}
