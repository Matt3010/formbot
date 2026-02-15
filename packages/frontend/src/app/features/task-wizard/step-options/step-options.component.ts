import { Component, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatSliderModule } from '@angular/material/slider';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

export interface TaskOptions {
  is_dry_run: boolean;
  custom_user_agent: string | null;
  max_retries: number;
  max_parallel: number;
}

@Component({
  selector: 'app-step-options',
  standalone: true,
  imports: [
    FormsModule,
    MatSlideToggleModule,
    MatSliderModule,
    MatFormFieldModule,
    MatInputModule,
    MatCardModule,
    MatIconModule,
  ],
  template: `
    <div class="step-options">
      <h2>Step 5: Options</h2>
      <p>Configure execution behavior and stealth settings.</p>

      <div class="options-grid">
        <mat-card class="option-card">
          <mat-card-header>
            <mat-icon matCardAvatar>science</mat-icon>
            <mat-card-title>Dry Run</mat-card-title>
            <mat-card-subtitle>Test without submitting forms</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <mat-slide-toggle [(ngModel)]="options.is_dry_run" (ngModelChange)="onOptionsChange()">
              {{ options.is_dry_run ? 'Enabled' : 'Disabled' }}
            </mat-slide-toggle>
          </mat-card-content>
        </mat-card>

        <mat-card class="option-card">
          <mat-card-header>
            <mat-icon matCardAvatar>replay</mat-icon>
            <mat-card-title>Max Retries</mat-card-title>
            <mat-card-subtitle>Retry on failure</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline" style="width: 120px;">
              <mat-label>Retries</mat-label>
              <input matInput type="number" [(ngModel)]="options.max_retries" (ngModelChange)="onOptionsChange()" min="0" max="10">
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card class="option-card">
          <mat-card-header>
            <mat-icon matCardAvatar>dynamic_feed</mat-icon>
            <mat-card-title>Max Parallel</mat-card-title>
            <mat-card-subtitle>Parallel browser sessions</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline" style="width: 120px;">
              <mat-label>Sessions</mat-label>
              <input matInput type="number" [(ngModel)]="options.max_parallel" (ngModelChange)="onOptionsChange()" min="1" max="10">
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card class="option-card full-span">
          <mat-card-header>
            <mat-icon matCardAvatar>person</mat-icon>
            <mat-card-title>Custom User Agent</mat-card-title>
            <mat-card-subtitle>Override the browser user agent string</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>User Agent</mat-label>
              <input matInput [(ngModel)]="options.custom_user_agent" (ngModelChange)="onOptionsChange()"
                placeholder="Leave empty for default">
            </mat-form-field>
          </mat-card-content>
        </mat-card>
      </div>
    </div>
  `,
  styles: [`
    .options-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 16px;
    }
    .option-card { padding: 8px; }
    .full-span { grid-column: 1 / -1; }
    .slider-value { margin-left: 12px; font-weight: 500; }
  `]
})
export class StepOptionsComponent {
  optionsChanged = output<TaskOptions>();

  options: TaskOptions = {
    is_dry_run: false,
    custom_user_agent: null,
    max_retries: 3,
    max_parallel: 1,
  };

  onOptionsChange() {
    this.optionsChanged.emit({ ...this.options });
  }

  setOptions(opts: Partial<TaskOptions>) {
    this.options = { ...this.options, ...opts };
  }
}
