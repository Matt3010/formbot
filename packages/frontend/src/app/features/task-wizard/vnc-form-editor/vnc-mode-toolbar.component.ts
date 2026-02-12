import { Component, input, output } from '@angular/core';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { EditorMode } from '../../../core/models/vnc-editor.model';

@Component({
  selector: 'app-vnc-mode-toolbar',
  standalone: true,
  imports: [MatButtonToggleModule, MatIconModule, MatTooltipModule],
  template: `
    <mat-button-toggle-group [value]="mode()" (change)="modeChanged.emit($event.value)" appearance="standard">
      <mat-button-toggle value="view" matTooltip="View mode — inspect fields">
        <mat-icon>visibility</mat-icon>
      </mat-button-toggle>
      <mat-button-toggle value="select" matTooltip="Select mode — click fields in VNC to select">
        <mat-icon>touch_app</mat-icon>
      </mat-button-toggle>
      <mat-button-toggle value="add" matTooltip="Add mode — click to add new fields">
        <mat-icon>add_circle</mat-icon>
      </mat-button-toggle>
      <mat-button-toggle value="remove" matTooltip="Remove mode — click to remove fields">
        <mat-icon>remove_circle</mat-icon>
      </mat-button-toggle>
    </mat-button-toggle-group>
  `,
  styles: [`
    :host { display: block; }
    mat-button-toggle-group { width: 100%; }
    mat-button-toggle { flex: 1; }
  `]
})
export class VncModeToolbarComponent {
  mode = input<EditorMode>('view');
  modeChanged = output<EditorMode>();
}
