import { Component, inject, input, output, computed, signal } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { TaskService } from '../../core/services/task.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-vnc-viewer-analysis',
  standalone: true,
  imports: [
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatCheckboxModule,
  ],
  template: `
    <mat-card class="vnc-card">
      <mat-card-header>
        <mat-icon matCardAvatar>desktop_windows</mat-icon>
        <mat-card-title>Manual Intervention Required</mat-card-title>
        <mat-card-subtitle>{{ reason() === '2fa' ? 'Complete 2FA verification' : 'Solve the CAPTCHA' }} in the browser below</mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <div class="vnc-container">
          <iframe
            [src]="safeVncUrl()"
            class="vnc-iframe"
            frameborder="0"
            allow="clipboard-read; clipboard-write"
          ></iframe>
        </div>
      </mat-card-content>

      <mat-card-actions class="vnc-actions">
        <mat-checkbox
          [checked]="confirmed()"
          (change)="confirmed.set($event.checked)"
          color="primary"
        >
          I have completed the required action
        </mat-checkbox>
        <button mat-raised-button color="primary"
          [disabled]="!confirmed() || resuming()"
          (click)="onResume()">
          <mat-icon>play_arrow</mat-icon> Resume Analysis
        </button>
      </mat-card-actions>
    </mat-card>
  `,
  styles: [`
    .vnc-card { margin: 16px 0; }
    .vnc-container {
      width: 100%;
      height: 500px;
      border: 1px solid #ddd;
      border-radius: 4px;
      overflow: hidden;
    }
    .vnc-iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    .vnc-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px !important;
    }
  `]
})
export class VncViewerAnalysisComponent {
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);
  private sanitizer = inject(DomSanitizer);

  vncUrl = input.required<string>();
  analysisId = input.required<string>();
  sessionId = input.required<string>();
  reason = input<string>('captcha');
  resumed = output<void>();

  confirmed = signal(false);
  resuming = signal(false);

  safeVncUrl = computed(() =>
    this.sanitizer.bypassSecurityTrustResourceUrl(this.vncUrl())
  );

  onResume() {
    this.resuming.set(true);
    this.taskService.resumeAnalysisVnc(this.sessionId(), this.analysisId()).subscribe({
      next: () => {
        this.notify.success('Analysis resumed');
        this.confirmed.set(false);
        this.resuming.set(false);
        this.resumed.emit();
      },
      error: () => {
        this.notify.error('Failed to resume analysis');
        this.resuming.set(false);
      }
    });
  }
}
