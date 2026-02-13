import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { HttpClient } from '@angular/common/http';
import { Subscription } from 'rxjs';

export interface ScreenshotViewerData {
  executionId: string;
}

@Component({
  selector: 'app-screenshot-viewer',
  standalone: true,
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatToolbarModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <div class="screenshot-viewer">
      <mat-toolbar class="viewer-toolbar">
        <span>Screenshot</span>
        <span class="spacer"></span>
        <button mat-icon-button (click)="zoomIn()">
          <mat-icon>zoom_in</mat-icon>
        </button>
        <button mat-icon-button (click)="zoomOut()">
          <mat-icon>zoom_out</mat-icon>
        </button>
        <button mat-icon-button (click)="resetZoom()">
          <mat-icon>fit_screen</mat-icon>
        </button>
        <button mat-icon-button (click)="close()">
          <mat-icon>close</mat-icon>
        </button>
      </mat-toolbar>

      <div class="image-container">
        @if (loading()) {
          <div class="loader-wrap">
            <mat-spinner diameter="36"></mat-spinner>
          </div>
        } @else if (imageUrl()) {
          <img
            [src]="imageUrl()!"
            [style.transform]="'scale(' + zoom() + ')'"
            alt="Execution Screenshot"
            class="screenshot-image"
          />
        } @else {
          <div class="error-wrap">
            <mat-icon>broken_image</mat-icon>
            <span>Screenshot not available.</span>
          </div>
        }
      </div>
    </div>
  `,
  styles: [`
    .screenshot-viewer { min-width: 600px; }
    .viewer-toolbar { background: #333; color: white; }
    .spacer { flex: 1 1 auto; }
    .image-container {
      overflow: auto;
      max-height: 70vh;
      display: flex;
      justify-content: center;
      align-items: flex-start;
      background: #1e1e1e;
      padding: 16px;
    }
    .screenshot-image {
      max-width: 100%;
      transition: transform 0.2s ease;
      transform-origin: top center;
    }
    .loader-wrap, .error-wrap {
      min-height: 220px;
      width: 100%;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      color: #bbb;
      gap: 10px;
    }
  `]
})
export class ScreenshotViewerComponent implements OnInit, OnDestroy {
  data = inject<ScreenshotViewerData>(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<ScreenshotViewerComponent>);
  private http = inject(HttpClient);
  private sub?: Subscription;

  zoom = signal(1);
  imageUrl = signal<string | null>(null);
  loading = signal(true);

  ngOnInit() {
    this.sub = this.http.get(`/api/executions/${this.data.executionId}/screenshot`, { responseType: 'blob' })
      .subscribe({
        next: (blob) => {
          this.imageUrl.set(URL.createObjectURL(blob));
          this.loading.set(false);
        },
        error: () => {
          this.imageUrl.set(null);
          this.loading.set(false);
        },
      });
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    const url = this.imageUrl();
    if (url) URL.revokeObjectURL(url);
  }

  zoomIn() {
    this.zoom.update(z => Math.min(z + 0.25, 3));
  }

  zoomOut() {
    this.zoom.update(z => Math.max(z - 0.25, 0.25));
  }

  resetZoom() {
    this.zoom.set(1);
  }

  close() {
    this.dialogRef.close();
  }
}
