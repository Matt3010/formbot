import { Component, input, output, signal, effect, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { EditorField, TestSelectorResult } from '../../../core/models/vnc-editor.model';
import { ApiService } from '../../../core/services/api.service';

@Component({
  selector: 'app-vnc-field-detail',
  standalone: true,
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatIconModule,
    MatTooltipModule,
    MatProgressSpinnerModule,
  ],
  template: `
    @if (field()) {
      <div class="field-detail">
        <h4>Field #{{ fieldIndex() + 1 }}</h4>

        @if (validationErrors().length > 0) {
          <div class="validation-errors">
            <mat-icon>error</mat-icon>
            <div class="error-list">
              @for (error of validationErrors(); track error) {
                <div class="error-item">{{ error }}</div>
              }
            </div>
          </div>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Name</mat-label>
          <input matInput [(ngModel)]="editName" (ngModelChange)="emitChange()">
        </mat-form-field>

        <div class="selector-row">
          <mat-form-field appearance="outline" class="flex-1">
            <mat-label>CSS Selector</mat-label>
            <input matInput [(ngModel)]="editSelector" (ngModelChange)="emitChange()">
          </mat-form-field>
          <button mat-icon-button matTooltip="Test selector" (click)="onTestSelector()">
            <mat-icon [class.test-pass]="testResult()?.found" [class.test-fail]="testResult() && !testResult()?.found">
              {{ testResult()?.found ? 'check_circle' : testResult() ? 'cancel' : 'play_circle' }}
            </mat-icon>
          </button>
        </div>

        @if (testResult() && testResult()!.matchCount > 1) {
          <div class="selector-warning">
            <mat-icon>warning</mat-icon>
            Selector matches {{ testResult()!.matchCount }} elements — should match exactly 1
          </div>
        }

        <mat-form-field appearance="outline" class="full-width">
          <mat-label>Type</mat-label>
          <mat-select [(ngModel)]="editType" (ngModelChange)="emitChange()">
            <mat-option value="text">Text</mat-option>
            <mat-option value="password">Password</mat-option>
            <mat-option value="email">Email</mat-option>
            <mat-option value="tel">Phone</mat-option>
            <mat-option value="number">Number</mat-option>
            <mat-option value="select">Select</mat-option>
            <mat-option value="checkbox">Checkbox</mat-option>
            <mat-option value="radio">Radio</mat-option>
            <mat-option value="file">File</mat-option>
            <mat-option value="hidden">Hidden</mat-option>
            <mat-option value="textarea">Textarea</mat-option>
            <mat-option value="submit">Submit</mat-option>
          </mat-select>
        </mat-form-field>

        @if (editType === 'file') {
          <div class="file-upload-section">
            <div class="file-upload-header">
              <mat-label>Upload File</mat-label>
            </div>
            <input type="file" #fileInput (change)="onFileSelected($event)" [disabled]="uploadingFile()" class="file-input">
            @if (uploadingFile()) {
              <div class="upload-progress">
                <mat-spinner diameter="20"></mat-spinner>
                <span>Uploading...</span>
              </div>
            }
            @if (uploadedFileName()) {
              <div class="uploaded-file">
                <mat-icon>attach_file</mat-icon>
                <span>{{ uploadedFileName() }}</span>
                <button mat-icon-button (click)="clearFile()" matTooltip="Clear file" class="clear-btn">
                  <mat-icon>close</mat-icon>
                </button>
              </div>
            }
          </div>
        } @else if (editType !== 'submit' && editType !== 'button') {
          @if (field()?.options && field()!.options!.length > 0) {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Value (Available Options)</mat-label>
              <mat-select [(ngModel)]="editValue" (ngModelChange)="emitChange()">
                @for (option of field()!.options; track option) {
                  <mat-option [value]="option">{{ option }}</mat-option>
                }
              </mat-select>
            </mat-form-field>
          } @else {
            <mat-form-field appearance="outline" class="full-width">
              <mat-label>Value</mat-label>
              <input matInput [(ngModel)]="editValue"
                [type]="editSensitive ? 'password' : 'text'"
                (ngModelChange)="emitChange()">
            </mat-form-field>
          }

          <mat-checkbox [(ngModel)]="editSensitive" (ngModelChange)="emitChange()">
            Sensitive (encrypted at rest)
          </mat-checkbox>

          <mat-checkbox [(ngModel)]="editRequired" (ngModelChange)="emitChange()" class="ml-2">
            Required
          </mat-checkbox>
        }
      </div>
    } @else {
      <div class="no-selection">
        <mat-icon>touch_app</mat-icon>
        <span>Select a field to edit its properties</span>
      </div>
    }
  `,
  styles: [`
    .field-detail { display: flex; flex-direction: column; gap: 8px; }
    .field-detail h4 { margin: 0 0 4px; }
    .selector-row { display: flex; align-items: center; gap: 4px; }
    .flex-1 { flex: 1; }
    .full-width { width: 100%; }
    .test-pass { color: #4CAF50; }
    .test-fail { color: #F44336; }
    .selector-warning {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 8px;
      background: #FFF3E0;
      border-radius: 4px;
      font-size: 12px;
      color: #E65100;
    }
    .selector-warning mat-icon { font-size: 16px; width: 16px; height: 16px; }
    .validation-errors {
      display: flex;
      align-items: flex-start;
      gap: 6px;
      padding: 8px 12px;
      background: #FFEBEE;
      border-radius: 4px;
      border-left: 3px solid #F44336;
      margin-bottom: 4px;
    }
    .validation-errors mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: #F44336;
      flex-shrink: 0;
      margin-top: 1px;
    }
    .error-list {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .error-item {
      font-size: 12px;
      color: #C62828;
      line-height: 1.4;
    }
    .no-selection {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 24px;
      color: #999;
      text-align: center;
    }
    .ml-2 { margin-left: 16px; }
    mat-checkbox { font-size: 13px; }
    .file-upload-section {
      padding: 12px;
      border: 1px dashed #ccc;
      border-radius: 4px;
      background: #fafafa;
      margin-bottom: 8px;
    }
    .file-upload-header {
      margin-bottom: 8px;
      font-weight: 500;
      color: rgba(0, 0, 0, 0.6);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .file-input {
      width: 100%;
      padding: 8px;
      margin-bottom: 8px;
      cursor: pointer;
    }
    .file-input:disabled {
      cursor: not-allowed;
      opacity: 0.5;
    }
    .upload-progress {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      background: #e3f2fd;
      border-radius: 4px;
      font-size: 13px;
      color: #1976d2;
    }
    .uploaded-file {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: #e8f5e9;
      border-radius: 4px;
      font-size: 13px;
      color: #2e7d32;
    }
    .uploaded-file mat-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
    }
    .uploaded-file span {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .clear-btn {
      width: 24px;
      height: 24px;
      line-height: 24px;
    }
    .clear-btn mat-icon {
      font-size: 16px;
      width: 16px;
      height: 16px;
    }
  `]
})
export class VncFieldDetailComponent {
  private apiService = inject(ApiService);

  field = input<EditorField | null>(null);
  fieldIndex = input<number>(-1);

  fieldChanged = output<EditorField>();
  testSelectorRequested = output<string>();

  testResult = signal<TestSelectorResult | null>(null);
  validationErrors = signal<string[]>([]);
  uploadingFile = signal(false);
  uploadedFileName = signal<string | null>(null);

  editName = '';
  editSelector = '';
  editType = '';
  editValue = '';
  editSensitive = false;
  editRequired = false;

  constructor() {
    effect(() => {
      const f = this.field();
      if (f) {
        this.editName = f.field_name;
        this.editSelector = f.field_selector;
        this.editType = f.field_type;
        this.editValue = f.preset_value || '';
        this.editSensitive = f.is_sensitive;
        this.editRequired = f.is_required;
        this.testResult.set(null);

        // If value is a file path, extract filename for display
        if (f.field_type === 'file' && f.preset_value) {
          const filename = f.preset_value.split('/').pop() || f.preset_value;
          this.uploadedFileName.set(filename);
        } else {
          this.uploadedFileName.set(null);
        }
      }
    });
  }

  emitChange() {
    const f = this.field();
    if (!f) return;
    this.validate();
    this.fieldChanged.emit({
      ...f,
      field_name: this.editName,
      field_selector: this.editSelector,
      field_type: this.editType,
      preset_value: this.editValue,
      is_sensitive: this.editSensitive,
      is_required: this.editRequired,
    });
  }

  validate(): boolean {
    const errors: string[] = [];

    // Name is always required
    if (!this.editName?.trim()) {
      errors.push('Name is required');
    }

    // Selector is always required
    if (!this.editSelector?.trim()) {
      errors.push('CSS Selector is required');
    }

    // For submit/button types, value is not needed but name and selector are critical
    // For other types, if field is marked required, value should be present
    if (this.editType !== 'submit' && this.editType !== 'button' && this.editRequired && !this.editValue?.trim()) {
      errors.push('Value is required for required fields');
    }

    this.validationErrors.set(errors);
    return errors.length === 0;
  }

  onTestSelector() {
    this.testSelectorRequested.emit(this.editSelector);
  }

  setTestResult(result: TestSelectorResult) {
    this.testResult.set(result);
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (!input.files?.length) return;

    this.uploadingFile.set(true);
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);

    this.apiService.post<{path: string, filename: string}>('/files/upload', formData)
      .subscribe({
        next: (response) => {
          this.uploadedFileName.set(response.filename);
          this.editValue = response.path;
          this.uploadingFile.set(false);
          this.emitChange();
        },
        error: (err) => {
          alert('File upload failed: ' + (err.error?.message || 'Unknown error'));
          this.uploadingFile.set(false);
          input.value = ''; // Reset input
        }
      });
  }

  clearFile() {
    this.editValue = '';
    this.uploadedFileName.set(null);
    this.emitChange();
  }
}
