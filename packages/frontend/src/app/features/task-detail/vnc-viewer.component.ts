import { Component, inject, input, output, computed, signal } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { ApiService } from '../../core/services/api.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-vnc-viewer',
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
        <mat-card-subtitle>Use the VNC viewer below to interact with the browser</mat-card-subtitle>
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
        <div class="action-buttons">
          <button mat-raised-button color="primary"
            [disabled]="!confirmed()"
            (click)="onResume()">
            <mat-icon>play_arrow</mat-icon> Resume Execution
          </button>
          <button mat-button color="warn" (click)="onAbort()">
            <mat-icon>stop</mat-icon> Abort
          </button>
        </div>
      </mat-card-actions>
    </mat-card>
  `,
  styles: [`
    .vnc-card { margin: 16px 0; }
    .vnc-container {
      width: 100%;
      height: 600px;
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
    .action-buttons {
      display: flex;
      gap: 8px;
    }
  `]
})
export class VncViewerComponent {
  private api = inject(ApiService);
  private notify = inject(NotificationService);
  private sanitizer = inject(DomSanitizer);

  vncUrl = input.required<string>();
  executionId = input.required<string>();
  resumed = output<void>();

  confirmed = signal(false);

  safeVncUrl = computed(() =>
    this.sanitizer.bypassSecurityTrustResourceUrl(this.vncUrl())
  );

  onResume() {
    this.api.post(`/executions/${this.executionId()}/resume`).subscribe({
      next: () => {
        this.notify.success('Execution resumed');
        this.confirmed.set(false);
        this.resumed.emit();
      },
      error: () => this.notify.error('Failed to resume execution')
    });
  }

  onAbort() {
    this.api.post(`/executions/${this.executionId()}/abort`).subscribe({
      next: () => {
        this.notify.info('Execution aborted');
        this.confirmed.set(false);
        this.resumed.emit();
      },
      error: () => this.notify.error('Failed to abort execution')
    });
  }
}
