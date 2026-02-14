import { Component, input, output } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { EditorMode } from '../../../core/models/vnc-editor.model';

@Component({
  selector: 'app-vnc-mode-toolbar',
  standalone: true,
  imports: [MatIconModule, MatTooltipModule],
  template: `
    <div class="toolbar-strip">
      @for (btn of buttons; track btn.value) {
        <button
          [disabled]="disabled()"
          [class.active]="mode() === btn.value"
          (click)="modeChanged.emit(btn.value)"
          [matTooltip]="btn.tooltip"
          matTooltipPosition="right">
          <mat-icon>{{ btn.icon }}</mat-icon>
        </button>
      }
    </div>
  `,
  styles: [`
    :host {
      display: flex;
      flex-shrink: 0;
    }
    .toolbar-strip {
      display: flex;
      flex-direction: column;
      background: #37474f;
      padding: 4px;
      gap: 2px;
    }
    button {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border: none;
      border-radius: 6px;
      background: transparent;
      color: #b0bec5;
      cursor: pointer;
      transition: all 0.15s;
    }
    button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    button:hover {
      background: rgba(255,255,255,0.1);
      color: white;
    }
    button.active {
      background: #2196F3;
      color: white;
    }
    mat-icon { font-size: 20px; width: 20px; height: 20px; }
  `]
})
export class VncModeToolbarComponent {
  mode = input<EditorMode>('select');
  disabled = input<boolean>(false);
  modeChanged = output<EditorMode>();

  buttons: { value: EditorMode; icon: string; tooltip: string }[] = [
    { value: 'select', icon: 'touch_app', tooltip: 'Select mode' },
    { value: 'add', icon: 'add_circle', tooltip: 'Add field' },
    { value: 'remove', icon: 'remove_circle', tooltip: 'Remove field' },
  ];
}
