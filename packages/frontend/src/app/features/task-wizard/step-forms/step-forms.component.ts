import { Component, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatExpansionModule } from '@angular/material/expansion';
import { MatChipsModule } from '@angular/material/chips';
import { MatTableModule } from '@angular/material/table';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { FormDefinition } from '../../../core/models/task.model';

@Component({
  selector: 'app-step-forms',
  standalone: true,
  imports: [
    FormsModule,
    DragDropModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
    MatButtonModule,
    MatExpansionModule,
    MatChipsModule,
    MatTableModule,
    MatProgressBarModule,
    MatCheckboxModule,
  ],
  template: `
    <div class="step-forms">
      <h2>Step 2: Review Detected Forms</h2>
      <p>Review and adjust the detected forms. Drag to reorder steps.</p>

      @if (editableForms().length === 0) {
        <p class="no-forms">No forms detected yet. Go back to Step 1 and analyze a URL.</p>
      } @else {
        <div cdkDropList (cdkDropListDropped)="onDrop($event)">
          @for (form of editableForms(); track form.id || $index) {
            <mat-card cdkDrag class="form-card mb-2">
              <div class="drag-handle" cdkDragHandle>
                <mat-icon>drag_indicator</mat-icon>
                Step {{ $index + 1 }}
              </div>

              <mat-card-content>
                <div class="form-header flex gap-2 items-center">
                  <mat-form-field appearance="outline" style="width: 200px;">
                    <mat-label>Form Type</mat-label>
                    <mat-select [(ngModel)]="form.form_type" (ngModelChange)="onFormsChange()">
                      <mat-option value="login">Login</mat-option>
                      <mat-option value="intermediate">Intermediate</mat-option>
                      <mat-option value="target">Target</mat-option>
                    </mat-select>
                  </mat-form-field>

                  @if (form.ai_confidence != null) {
                    <div class="confidence">
                      <span>AI Confidence: {{ (form.ai_confidence! * 100).toFixed(0) }}%</span>
                      <mat-progress-bar
                        mode="determinate"
                        [value]="form.ai_confidence! * 100"
                        [color]="form.ai_confidence! > 0.7 ? 'primary' : 'warn'"
                      ></mat-progress-bar>
                    </div>
                  }

                  @if (form.captcha_detected) {
                    <mat-chip color="warn">CAPTCHA Detected</mat-chip>
                  }

                  @if (form.two_factor_expected) {
                    <mat-chip color="accent">2FA Expected</mat-chip>
                  }
                </div>

                <mat-expansion-panel>
                  <mat-expansion-panel-header>
                    <mat-panel-title>Selectors</mat-panel-title>
                  </mat-expansion-panel-header>

                  <div class="flex flex-col gap-2">
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Form Selector</mat-label>
                      <input matInput [(ngModel)]="form.form_selector" (ngModelChange)="onFormsChange()">
                    </mat-form-field>
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Submit Selector</mat-label>
                      <input matInput [(ngModel)]="form.submit_selector" (ngModelChange)="onFormsChange()">
                    </mat-form-field>
                    <mat-form-field appearance="outline" class="full-width">
                      <mat-label>Page URL</mat-label>
                      <input matInput [(ngModel)]="form.page_url" (ngModelChange)="onFormsChange()">
                    </mat-form-field>

                    <div class="flex gap-4 mt-1">
                      <mat-checkbox
                        [(ngModel)]="form.captcha_detected"
                        (ngModelChange)="onFormsChange()"
                      >CAPTCHA on this page (pause before submit)</mat-checkbox>

                      <mat-checkbox
                        [(ngModel)]="form.two_factor_expected"
                        (ngModelChange)="onFormsChange()"
                      >2FA after submit (pause for OTP/code)</mat-checkbox>
                    </div>
                  </div>
                </mat-expansion-panel>

                <mat-expansion-panel class="mt-1">
                  <mat-expansion-panel-header>
                    <mat-panel-title>Fields ({{ form.fields?.length || 0 }})</mat-panel-title>
                  </mat-expansion-panel-header>

                  @if (form.fields?.length) {
                    <table mat-table [dataSource]="form.fields" class="full-width">
                      <ng-container matColumnDef="name">
                        <th mat-header-cell *matHeaderCellDef>Name</th>
                        <td mat-cell *matCellDef="let field">{{ field.field_name }}</td>
                      </ng-container>
                      <ng-container matColumnDef="type">
                        <th mat-header-cell *matHeaderCellDef>Type</th>
                        <td mat-cell *matCellDef="let field">{{ field.field_type }}</td>
                      </ng-container>
                      <ng-container matColumnDef="selector">
                        <th mat-header-cell *matHeaderCellDef>Selector</th>
                        <td mat-cell *matCellDef="let field">
                          <code>{{ field.field_selector }}</code>
                        </td>
                      </ng-container>
                      <ng-container matColumnDef="required">
                        <th mat-header-cell *matHeaderCellDef>Required</th>
                        <td mat-cell *matCellDef="let field">
                          @if (field.is_required) {
                            <mat-icon color="primary">check_circle</mat-icon>
                          }
                        </td>
                      </ng-container>
                      <tr mat-header-row *matHeaderRowDef="['name', 'type', 'selector', 'required']"></tr>
                      <tr mat-row *matRowDef="let row; columns: ['name', 'type', 'selector', 'required']"></tr>
                    </table>
                  } @else {
                    <p>No fields detected for this form.</p>
                  }
                </mat-expansion-panel>
              </mat-card-content>
            </mat-card>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .form-card { cursor: default; }
    .drag-handle {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      background: #f5f5f5;
      cursor: grab;
      border-radius: 4px 4px 0 0;
      font-weight: 500;
    }
    .drag-handle:active { cursor: grabbing; }
    .confidence { width: 200px; }
    .no-forms { text-align: center; padding: 32px; color: #999; }
    code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
    .cdk-drag-preview { box-shadow: 0 5px 15px rgba(0,0,0,0.2); }
    .cdk-drag-placeholder { opacity: 0.3; }
  `]
})
export class StepFormsComponent {
  forms = input<FormDefinition[]>([]);
  formsConfirmed = output<FormDefinition[]>();

  editableForms = signal<FormDefinition[]>([]);

  ngOnChanges() {
    const incoming = this.forms();
    if (incoming.length > 0 && this.editableForms().length === 0) {
      this.editableForms.set(incoming.map((f, i) => ({ ...f, step_order: i })));
    }
  }

  onDrop(event: CdkDragDrop<FormDefinition[]>) {
    const forms = [...this.editableForms()];
    moveItemInArray(forms, event.previousIndex, event.currentIndex);
    forms.forEach((f, i) => f.step_order = i);
    this.editableForms.set(forms);
    this.onFormsChange();
  }

  onFormsChange() {
    this.formsConfirmed.emit(this.editableForms());
  }

  setForms(forms: FormDefinition[]) {
    this.editableForms.set(forms.map((f, i) => ({ ...f, step_order: i })));
  }
}
