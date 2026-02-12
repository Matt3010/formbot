import { Component, input, output, computed } from '@angular/core';
import { DatePipe, UpperCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Analysis } from '../../core/models/analysis.model';

@Component({
  selector: 'app-analysis-card',
  standalone: true,
  imports: [
    DatePipe,
    UpperCasePipe,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <mat-card class="analysis-card" [class.analyzing-card]="analysis().status === 'analyzing'">
      <mat-card-header>
        <mat-card-title class="analysis-url" [matTooltip]="analysis().url">
          {{ truncatedUrl() }}
        </mat-card-title>
        <mat-card-subtitle>
          <mat-chip class="type-chip">{{ typeLabel() }}</mat-chip>
        </mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <div class="status-row">
          <div class="status-wrapper" [class.status-analyzing-pulse]="analysis().status === 'analyzing'">
            @if (analysis().status === 'analyzing') {
              <mat-spinner diameter="16" class="analyzing-spinner"></mat-spinner>
            }
            <mat-chip [class]="'status-' + analysis().status">
              {{ analysis().status | uppercase }}
            </mat-chip>
          </div>
        </div>

        @if (analysis().status === 'completed' && analysis().result) {
          <div class="result-info mt-1">
            <mat-icon class="small-icon">description</mat-icon>
            {{ formsCount() }} form(s) found
          </div>
        }

        @if (analysis().error) {
          <div class="error-info mt-1">
            <mat-icon class="small-icon">error</mat-icon>
            {{ analysis().error }}
          </div>
        }

        <div class="time-info mt-1">
          <mat-icon class="small-icon">schedule</mat-icon>
          {{ analysis().created_at | date:'short' }}
          @if (duration()) {
            <span class="duration">({{ duration() }})</span>
          }
        </div>

        @if (analysis().model) {
          <div class="model-info mt-1">
            <mat-icon class="small-icon">smart_toy</mat-icon>
            {{ analysis().model }}
          </div>
        }
      </mat-card-content>

      <mat-card-actions align="end">
        @if (analysis().status === 'completed' && !analysis().task_id) {
          <button mat-button color="primary" (click)="resume.emit()" matTooltip="Resume task setup from this analysis">
            <mat-icon>play_arrow</mat-icon> Resume Setup
          </button>
        }
        @if (analysis().status === 'pending' || analysis().status === 'analyzing') {
          <button mat-button color="warn" (click)="cancel.emit()" matTooltip="Cancel this analysis">
            <mat-icon>cancel</mat-icon> Cancel
          </button>
        }
        @if (analysis().task_id) {
          <button mat-button (click)="viewTask.emit()" matTooltip="View linked task">
            <mat-icon>open_in_new</mat-icon> View Task
          </button>
        }
      </mat-card-actions>
    </mat-card>
  `,
  styles: [`
    .analysis-card { margin-bottom: 16px; transition: border-color 0.3s ease; }
    .analyzing-card { border: 1px solid #2196f3; }
    .analysis-url { font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 320px; }
    .type-chip { font-size: 11px; min-height: 24px; padding: 0 8px; }
    .status-row { display: flex; align-items: center; gap: 8px; }
    .status-wrapper { display: flex; align-items: center; gap: 6px; }
    .analyzing-spinner { display: inline-block; }
    .status-analyzing-pulse { animation: pulse 2s infinite; }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.6; }
    }
    .result-info, .time-info, .model-info { display: flex; align-items: center; gap: 4px; color: #666; font-size: 13px; }
    .error-info { display: flex; align-items: center; gap: 4px; color: #f44336; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .duration { color: #999; margin-left: 4px; }
    .small-icon { font-size: 18px; width: 18px; height: 18px; }
    .mt-1 { margin-top: 8px; }
    .status-pending { background-color: #9e9e9e !important; color: white !important; }
    .status-analyzing { background-color: #2196f3 !important; color: white !important; }
    .status-completed { background-color: #4caf50 !important; color: white !important; }
    .status-failed { background-color: #f44336 !important; color: white !important; }
    .status-cancelled { background-color: #ff9800 !important; color: white !important; }
    .status-timed_out { background-color: #795548 !important; color: white !important; }
  `]
})
export class AnalysisCardComponent {
  analysis = input.required<Analysis>();

  resume = output<void>();
  cancel = output<void>();
  viewTask = output<void>();

  truncatedUrl = computed(() => {
    const url = this.analysis().url;
    return url.length > 60 ? url.substring(0, 57) + '...' : url;
  });

  typeLabel = computed(() => {
    const type = this.analysis().type;
    if (type === 'login_and_target') return 'Login + Target';
    if (type === 'next_page') return 'Next Page';
    return 'Simple';
  });

  formsCount = computed(() => {
    const result = this.analysis().result;
    return result?.forms?.length ?? 0;
  });

  duration = computed(() => {
    const a = this.analysis();
    if (!a.started_at || !a.completed_at) return null;
    const ms = new Date(a.completed_at).getTime() - new Date(a.started_at).getTime();
    const secs = Math.round(ms / 1000);
    if (secs < 60) return `${secs}s`;
    return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  });
}
