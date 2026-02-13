import { Component, inject, input, output, computed, signal } from '@angular/core';
import { DomSanitizer } from '@angular/platform-browser';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatTooltipModule } from '@angular/material/tooltip';
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
    MatTooltipModule,
  ],
  template: `
    <mat-card class="vnc-card" [class.vnc-card-expanded]="expanded()">
      <mat-card-header>
        <mat-icon matCardAvatar>desktop_windows</mat-icon>
        <mat-card-title>Manual Intervention Required</mat-card-title>
        <mat-card-subtitle>Use the VNC viewer below to interact with the browser</mat-card-subtitle>
        <div class="header-actions">
          <button mat-icon-button (click)="openInNewTab()" matTooltip="Open in a new tab">
            <mat-icon>open_in_new</mat-icon>
          </button>
          <button mat-icon-button (click)="toggleExpanded()" matTooltip="Toggle full screen">
            <mat-icon>{{ expanded() ? 'fullscreen_exit' : 'fullscreen' }}</mat-icon>
          </button>
        </div>
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
    .header-actions {
      margin-left: auto;
      display: flex;
      gap: 4px;
    }
    .vnc-container {
      width: 100%;
      height: clamp(560px, 78vh, 980px);
      border: 1px solid #ddd;
      border-radius: 4px;
      overflow: hidden;
      background: #111;
    }
    .vnc-iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    .vnc-card-expanded {
      position: fixed;
      inset: 12px;
      margin: 0;
      z-index: 1000;
      display: flex;
      flex-direction: column;
    }
    .vnc-card-expanded mat-card-content {
      flex: 1;
      min-height: 0;
    }
    .vnc-card-expanded .vnc-container {
      height: 100%;
      min-height: 0;
    }
    .vnc-actions {
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      row-gap: 10px;
      padding: 8px 16px !important;
    }
    .action-buttons {
      display: flex;
      gap: 8px;
    }
    @media (max-width: 959px) {
      .vnc-container {
        height: 68vh;
        min-height: 420px;
      }
      .vnc-card-expanded {
        inset: 8px;
      }
      .action-buttons {
        width: 100%;
      }
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
  expanded = signal(false);

  safeVncUrl = computed(() => {
    let url = this.vncUrl();
    url = this.withVncDefaults(url);
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  });

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

  toggleExpanded() {
    this.expanded.update((v) => !v);
  }

  openInNewTab() {
    window.open(this.withVncDefaults(this.vncUrl()), '_blank', 'noopener,noreferrer');
  }

  private withVncDefaults(url: string): string {
    if (!url) return '';

    const ensure = (key: string, value: string) => {
      if (!new RegExp(`[?&]${key}=`).test(url)) {
        url += (url.includes('?') ? '&' : '?') + `${key}=${value}`;
      }
    };

    ensure('resize', 'scale');
    ensure('autoconnect', '1');
    ensure('reconnect', '1');
    return url;
  }
}
