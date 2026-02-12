import { Component, inject, input, output, signal } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatChipsModule } from '@angular/material/chips';
import { FormDefinition, FormField } from '../../../core/models/task.model';
import { TaskService } from '../../../core/services/task.service';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-step-fill',
  standalone: true,
  imports: [
    TitleCasePipe,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    MatExpansionModule,
    MatChipsModule,
  ],
  template: `
    <div class="step-fill">
      <h2>Step 3: Fill Field Values</h2>
      <p>Provide values for each form field. Sensitive fields will be encrypted at rest.</p>

      @if (editableForms().length === 0) {
        <p class="no-forms">No forms configured. Go back to previous steps.</p>
      } @else {
        @for (form of editableForms(); track form.id || $index) {
          <mat-expansion-panel [expanded]="$index === 0" class="mb-2">
            <mat-expansion-panel-header>
              <mat-panel-title>
                @if (form.form_type === 'login' && form.step_order === 0) {
                  <mat-icon class="panel-icon">login</mat-icon> Login Credentials
                } @else {
                  Step {{ $index + 1 }}: {{ form.form_type | titlecase }} Form
                }
              </mat-panel-title>
              <mat-panel-description>
                {{ form.fields?.length || 0 }} fields
              </mat-panel-description>
            </mat-expansion-panel-header>

            <div class="fields-container">
              @if (form.fields?.length) {
                @for (field of form.fields; track field.id || $index) {
                  <mat-card class="field-card mb-1">
                    <mat-card-content>
                      <div class="field-header flex items-center justify-between mb-1">
                        <div>
                          <strong>{{ field.field_name }}</strong>
                          <span class="field-type">({{ field.field_type }})</span>
                          @if (field.is_required) {
                            <mat-chip class="required-chip">Required</mat-chip>
                          }
                          @if (field.field_purpose) {
                            <span class="field-purpose">- {{ field.field_purpose }}</span>
                          }
                        </div>
                      </div>

                      @if (field.is_file_upload) {
                        <div class="flex items-center gap-2">
                          <button mat-stroked-button (click)="fileInput.click()">
                            <mat-icon>upload_file</mat-icon> Choose File
                          </button>
                          <input #fileInput type="file" hidden (change)="onFileSelected($event, field)">
                          @if (field.preset_value) {
                            <span>{{ field.preset_value }}</span>
                          }
                        </div>
                      } @else if (field.options?.length) {
                        <mat-form-field appearance="outline" class="full-width">
                          <mat-label>{{ field.field_name }}</mat-label>
                          <mat-select [(ngModel)]="field.preset_value" (ngModelChange)="onValuesChange()">
                            @for (opt of field.options; track opt) {
                              <mat-option [value]="opt">{{ opt }}</mat-option>
                            }
                          </mat-select>
                        </mat-form-field>
                      } @else if (field.field_type === 'checkbox') {
                        <mat-checkbox
                          [checked]="field.preset_value === 'true'"
                          (change)="field.preset_value = $event.checked ? 'true' : 'false'; onValuesChange()">
                          {{ field.field_name }}
                        </mat-checkbox>
                      } @else if (field.field_type === 'textarea') {
                        <mat-form-field appearance="outline" class="full-width">
                          <mat-label>{{ field.field_name }}</mat-label>
                          <textarea matInput [(ngModel)]="field.preset_value" (ngModelChange)="onValuesChange()" rows="3"></textarea>
                        </mat-form-field>
                      } @else {
                        <mat-form-field appearance="outline" class="full-width">
                          <mat-label>{{ field.field_name }}</mat-label>
                          <input matInput
                            [(ngModel)]="field.preset_value"
                            (ngModelChange)="onValuesChange()"
                            [type]="field.is_sensitive || field.field_type === 'password' ? 'password' : 'text'"
                            [placeholder]="field.field_purpose || ''">
                        </mat-form-field>
                      }

                      <mat-checkbox
                        [(ngModel)]="field.is_sensitive"
                        (ngModelChange)="onValuesChange()"
                        class="mt-1">
                        Mark as sensitive (encrypted at rest)
                      </mat-checkbox>
                    </mat-card-content>
                  </mat-card>
                }
              } @else {
                <p>No fields in this form.</p>
              }
            </div>
          </mat-expansion-panel>
        }
      }
    </div>
  `,
  styles: [`
    .step-fill { max-width: 800px; }
    .no-forms { text-align: center; padding: 32px; color: #999; }
    .field-card { border-left: 3px solid #3f51b5; }
    .field-type { color: #999; font-size: 13px; margin-left: 4px; }
    .field-purpose { color: #666; font-size: 13px; margin-left: 4px; }
    .required-chip { font-size: 11px; margin-left: 8px; }
    .fields-container { padding: 8px 0; }
    .panel-icon { vertical-align: middle; margin-right: 4px; font-size: 20px; }
  `]
})
export class StepFillComponent {
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);

  forms = input<FormDefinition[]>([]);
  filledForms = output<FormDefinition[]>();

  editableForms = signal<FormDefinition[]>([]);

  ngOnChanges() {
    const incoming = this.forms();
    if (incoming.length > 0) {
      this.editableForms.set(incoming.map(f => ({
        ...f,
        fields: f.fields?.map(field => ({
          ...field,
          // Auto-mark password fields in login forms as sensitive
          is_sensitive: field.is_sensitive ||
            (f.form_type === 'login' && (field.field_type === 'password' || field.field_purpose === 'password')),
        })) || []
      })));
    }
  }

  onFileSelected(event: Event, field: FormField) {
    const input = event.target as HTMLInputElement;
    if (input.files?.length) {
      const file = input.files[0];
      this.taskService.uploadFile(file).subscribe({
        next: (res) => {
          field.preset_value = res.path;
          this.onValuesChange();
          this.notify.success('File uploaded');
        },
        error: () => this.notify.error('File upload failed')
      });
    }
  }

  onValuesChange() {
    this.filledForms.emit(this.editableForms());
  }

  setForms(forms: FormDefinition[]) {
    this.editableForms.set(forms.map(f => ({
      ...f,
      fields: f.fields?.map(field => ({ ...field })) || []
    })));
  }
}
