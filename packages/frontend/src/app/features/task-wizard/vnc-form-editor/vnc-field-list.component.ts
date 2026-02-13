import { Component, input, output, signal } from '@angular/core';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { EditorField } from '../../../core/models/vnc-editor.model';

@Component({
  selector: 'app-vnc-field-list',
  standalone: true,
  imports: [DragDropModule, MatListModule, MatIconModule, MatButtonModule, MatChipsModule],
  template: `
    <div class="field-list-header">
      <span class="field-count">{{ fields().length }} field(s)</span>
    </div>

    <div cdkDropList (cdkDropListDropped)="onDrop($event)" class="field-list">
      @for (field of fields(); track field.temp_id; let i = $index) {
        <div cdkDrag
          class="field-item"
          [class.selected]="selectedIndex() === i"
          (click)="onFieldClick(i)">
          <div class="field-drag-handle" cdkDragHandle>
            <mat-icon>drag_indicator</mat-icon>
          </div>
          <div class="field-badge">{{ i + 1 }}</div>
          <div class="field-info">
            <span class="field-name">{{ field.field_name || field.field_selector }}</span>
            <span class="field-type-chip">{{ field.field_type }}</span>
          </div>
          <div class="field-actions">
            @if (field.is_sensitive) {
              <mat-icon class="sensitive-icon">lock</mat-icon>
            }
          </div>
        </div>
      }
    </div>

    @if (fields().length === 0) {
      <div class="empty-state">
        <mat-icon>info</mat-icon>
        <span>No fields detected. Use "Add" mode to click on form elements.</span>
      </div>
    }
  `,
  styles: [`
    .field-list-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 8px 0;
      font-size: 12px;
      color: #666;
    }
    .field-list {
      max-height: 300px;
      overflow-y: auto;
    }
    .field-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      margin-bottom: 4px;
      cursor: pointer;
      background: white;
      transition: background 0.15s;
    }
    .field-item:hover { background: #f5f5f5; }
    .field-item.selected { background: #e3f2fd; border-color: #2196F3; }
    .field-drag-handle { cursor: move; color: #999; display: flex; }
    .field-badge {
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: #2196F3;
      color: white;
      font-size: 11px;
      font-weight: bold;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
    .field-info {
      flex: 1;
      min-width: 0;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .field-name {
      font-size: 13px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .field-type-chip {
      font-size: 10px;
      padding: 1px 6px;
      border-radius: 8px;
      background: #e0e0e0;
      color: #616161;
      flex-shrink: 0;
    }
    .field-actions { display: flex; gap: 4px; align-items: center; }
    .sensitive-icon { font-size: 16px; color: #FF9800; }
    .empty-state {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 16px;
      color: #999;
      font-size: 13px;
    }
    .cdk-drag-preview {
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      border-radius: 4px;
    }
    .cdk-drag-placeholder {
      opacity: 0.3;
    }
  `]
})
export class VncFieldListComponent {
  fields = input<EditorField[]>([]);
  selectedIndex = input<number>(-1);

  fieldSelected = output<number>();
  fieldsReordered = output<EditorField[]>();

  onFieldClick(index: number) {
    this.fieldSelected.emit(index);
  }

  onDrop(event: CdkDragDrop<EditorField[]>) {
    const fieldsCopy = [...this.fields()];
    moveItemInArray(fieldsCopy, event.previousIndex, event.currentIndex);
    // Update sort_order
    fieldsCopy.forEach((f, i) => f.sort_order = i);
    this.fieldsReordered.emit(fieldsCopy);
  }
}
