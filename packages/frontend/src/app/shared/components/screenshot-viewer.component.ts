import { Component, inject, signal } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatToolbarModule } from '@angular/material/toolbar';

export interface ScreenshotViewerData {
  screenshotPath: string;
}

@Component({
  selector: 'app-screenshot-viewer',
  standalone: true,
  imports: [
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatToolbarModule,
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
        <img
          [src]="'/api/screenshots/' + data.screenshotPath"
          [style.transform]="'scale(' + zoom() + ')'"
          alt="Execution Screenshot"
          class="screenshot-image"
        />
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
  `]
})
export class ScreenshotViewerComponent {
  data = inject<ScreenshotViewerData>(MAT_DIALOG_DATA);
  private dialogRef = inject(MatDialogRef<ScreenshotViewerComponent>);

  zoom = signal(1);

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
