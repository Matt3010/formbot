import { Component, input, output } from '@angular/core';
import { UpperCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';
import { Task } from '../../core/models/task.model';

@Component({
  selector: 'app-task-card',
  standalone: true,
  imports: [
    UpperCasePipe,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatTooltipModule,
    MatMenuModule,
  ],
  template: `
    <mat-card class="task-card">
      <mat-card-header>
        <mat-card-title class="task-title">{{ task().name }}</mat-card-title>
        <mat-card-subtitle>{{ task().target_url }}</mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <div class="task-meta">
          <mat-chip [class]="'status-' + task().status">
            {{ task().status | uppercase }}
          </mat-chip>

          <span class="schedule-info">
            <mat-icon class="small-icon">schedule</mat-icon>
            @if (task().schedule_type === 'cron') {
              Recurring: {{ task().schedule_cron }}
            } @else {
              @if (task().schedule_at) {
                Once: {{ task().schedule_at }}
              } @else {
                Manual
              }
            }
          </span>
        </div>

        <div class="form-count mt-1">
          <mat-icon class="small-icon">description</mat-icon>
          {{ task().form_definitions?.length || 0 }} form(s) configured
        </div>

        @if (task().is_dry_run) {
          <div class="dry-run-badge mt-1">
            <mat-icon class="small-icon">science</mat-icon>
            Dry Run Mode
          </div>
        }
      </mat-card-content>

      <mat-card-actions align="end">
        <button mat-icon-button matTooltip="View Details" (click)="view.emit()">
          <mat-icon>visibility</mat-icon>
        </button>

        @if (task().status === 'active') {
          <button mat-icon-button matTooltip="Pause" (click)="pause.emit()">
            <mat-icon>pause</mat-icon>
          </button>
        } @else {
          <button mat-icon-button matTooltip="Execute" (click)="execute.emit()" [disabled]="task().status === 'draft'">
            <mat-icon>play_arrow</mat-icon>
          </button>
        }

        <button mat-icon-button [matMenuTriggerFor]="menu">
          <mat-icon>more_vert</mat-icon>
        </button>

        <mat-menu #menu="matMenu">
          <button mat-menu-item (click)="execute.emit()">
            <mat-icon>play_arrow</mat-icon> Execute
          </button>
          <button mat-menu-item (click)="clone.emit()">
            <mat-icon>content_copy</mat-icon> Clone
          </button>
          <button mat-menu-item (click)="edit.emit()">
            <mat-icon>edit</mat-icon> Edit
          </button>
          <button mat-menu-item (click)="deleteTask.emit()" class="delete-action">
            <mat-icon>delete</mat-icon> Delete
          </button>
        </mat-menu>
      </mat-card-actions>
    </mat-card>
  `,
  styles: [`
    .task-card { margin-bottom: 16px; }
    .task-title { font-size: 18px; }
    .task-meta { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .schedule-info { display: flex; align-items: center; gap: 4px; color: #666; font-size: 13px; }
    .form-count { display: flex; align-items: center; gap: 4px; color: #666; font-size: 13px; }
    .dry-run-badge { display: flex; align-items: center; gap: 4px; color: #ff9800; font-size: 13px; }
    .small-icon { font-size: 18px; width: 18px; height: 18px; }
    .status-draft { background-color: #9e9e9e !important; color: white !important; }
    .status-active { background-color: #4caf50 !important; color: white !important; }
    .status-paused { background-color: #ff9800 !important; color: white !important; }
    .status-completed { background-color: #2196f3 !important; color: white !important; }
    .status-failed { background-color: #f44336 !important; color: white !important; }
    .delete-action { color: #f44336; }
  `]
})
export class TaskCardComponent {
  task = input.required<Task>();

  view = output<void>();
  execute = output<void>();
  pause = output<void>();
  clone = output<void>();
  edit = output<void>();
  deleteTask = output<void>();
}
