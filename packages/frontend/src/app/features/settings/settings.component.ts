import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSliderModule } from '@angular/material/slider';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';

interface Settings {
  max_parallel_browsers: number;
  retention_days: number;
  default_max_retries: number;
}

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [
    FormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSliderModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatDividerModule,
  ],
  template: `
    <div class="settings-page">
      <h1>Settings</h1>

      @if (loading()) {
        <div class="flex items-center justify-center" style="padding: 48px;">
          <mat-spinner></mat-spinner>
        </div>
      } @else {
        <div class="settings-grid">
          <!-- Browser Settings -->
          <mat-card>
            <mat-card-header>
              <mat-icon matCardAvatar>web</mat-icon>
              <mat-card-title>Browser Settings</mat-card-title>
              <mat-card-subtitle>Parallel browser configuration</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              <div class="slider-field">
                <label>Max Parallel Browsers: {{ settings.max_parallel_browsers }}</label>
                <mat-slider min="1" max="10" step="1" showTickMarks>
                  <input matSliderThumb [(ngModel)]="settings.max_parallel_browsers">
                </mat-slider>
              </div>

              <mat-form-field appearance="outline" class="full-width mt-2">
                <mat-label>Default Max Retries</mat-label>
                <input matInput type="number" [(ngModel)]="settings.default_max_retries" min="0" max="10">
              </mat-form-field>
            </mat-card-content>
          </mat-card>

          <!-- Data Retention -->
          <mat-card>
            <mat-card-header>
              <mat-icon matCardAvatar>storage</mat-icon>
              <mat-card-title>Data Retention</mat-card-title>
              <mat-card-subtitle>Log and screenshot cleanup</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              <mat-form-field appearance="outline" class="full-width">
                <mat-label>Retention Days</mat-label>
                <input matInput type="number" [(ngModel)]="settings.retention_days" min="1" max="365">
                <mat-hint>Logs older than this will be automatically deleted</mat-hint>
              </mat-form-field>
            </mat-card-content>
          </mat-card>
        </div>

        <mat-divider class="mt-3 mb-2"></mat-divider>

        <div class="flex justify-between items-center">
          <span class="save-hint">Changes are not saved until you click Save.</span>
          <button mat-raised-button color="primary" (click)="save()" [disabled]="saving()">
            @if (saving()) {
              <mat-spinner diameter="20"></mat-spinner>
            } @else {
              <mat-icon>save</mat-icon> Save Settings
            }
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .settings-page { max-width: 800px; padding-bottom: 48px; }
    .settings-grid { display: flex; flex-direction: column; gap: 16px; }
    .slider-field { padding: 8px 0; }
    .slider-field label { display: block; margin-bottom: 8px; font-weight: 500; }
    .save-hint { color: #999; font-size: 13px; }
  `]
})
export class SettingsComponent implements OnInit {
  private api = inject(ApiService);
  private notify = inject(NotificationService);

  loading = signal(true);
  saving = signal(false);

  settings: Settings = {
    max_parallel_browsers: 2,
    retention_days: 30,
    default_max_retries: 3,
  };

  ngOnInit() {
    this.loadSettings();
  }

  loadSettings() {
    this.loading.set(true);
    this.api.get<Settings>('/settings').subscribe({
      next: (data) => {
        this.settings = { ...this.settings, ...data };
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
        this.notify.warn('Using default settings');
      }
    });
  }

  save() {
    this.saving.set(true);
    this.api.put('/settings', this.settings).subscribe({
      next: () => {
        this.saving.set(false);
        this.notify.success('Settings saved');
      },
      error: () => {
        this.saving.set(false);
        this.notify.error('Failed to save settings');
      }
    });
  }
}
