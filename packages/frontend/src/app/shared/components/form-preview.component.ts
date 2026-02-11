import { Component, input } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTableModule } from '@angular/material/table';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatExpansionModule } from '@angular/material/expansion';
import { FormDefinition } from '../../core/models/task.model';

@Component({
  selector: 'app-form-preview',
  standalone: true,
  imports: [
    TitleCasePipe,
    MatCardModule,
    MatIconModule,
    MatChipsModule,
    MatTableModule,
    MatProgressBarModule,
    MatExpansionModule,
  ],
  template: `
    <mat-card class="form-preview">
      <mat-card-header>
        <mat-icon matCardAvatar>description</mat-icon>
        <mat-card-title>
          {{ form().form_type | titlecase }} Form
          <span class="step-badge">Step {{ form().step_order + 1 }}</span>
        </mat-card-title>
        <mat-card-subtitle>{{ form().page_url }}</mat-card-subtitle>
      </mat-card-header>

      <mat-card-content>
        <div class="meta-row flex gap-2 items-center mb-2">
          @if (form().ai_confidence != null) {
            <div class="confidence-bar">
              <span class="confidence-label">
                AI Confidence: {{ (form().ai_confidence! * 100).toFixed(0) }}%
              </span>
              <mat-progress-bar
                mode="determinate"
                [value]="form().ai_confidence! * 100"
                [color]="form().ai_confidence! > 0.7 ? 'primary' : 'warn'"
              ></mat-progress-bar>
            </div>
          }

          @if (form().captcha_detected) {
            <mat-chip color="warn">
              <mat-icon class="chip-icon">warning</mat-icon>
              CAPTCHA
            </mat-chip>
          }
        </div>

        <mat-expansion-panel>
          <mat-expansion-panel-header>
            <mat-panel-title>Selectors</mat-panel-title>
          </mat-expansion-panel-header>
          <div class="selector-info">
            <div><strong>Form:</strong> <code>{{ form().form_selector }}</code></div>
            <div><strong>Submit:</strong> <code>{{ form().submit_selector }}</code></div>
          </div>
        </mat-expansion-panel>

        @if (form().fields?.length) {
          <h4 class="mt-2">Fields ({{ form().fields.length }})</h4>
          <table mat-table [dataSource]="form().fields" class="full-width field-table">
            <ng-container matColumnDef="name">
              <th mat-header-cell *matHeaderCellDef>Name</th>
              <td mat-cell *matCellDef="let field">{{ field.field_name }}</td>
            </ng-container>

            <ng-container matColumnDef="type">
              <th mat-header-cell *matHeaderCellDef>Type</th>
              <td mat-cell *matCellDef="let field">{{ field.field_type }}</td>
            </ng-container>

            <ng-container matColumnDef="purpose">
              <th mat-header-cell *matHeaderCellDef>Purpose</th>
              <td mat-cell *matCellDef="let field">{{ field.field_purpose || '-' }}</td>
            </ng-container>

            <ng-container matColumnDef="value">
              <th mat-header-cell *matHeaderCellDef>Value</th>
              <td mat-cell *matCellDef="let field">
                @if (field.is_sensitive) {
                  <span class="sensitive">********</span>
                } @else {
                  {{ field.preset_value || '-' }}
                }
              </td>
            </ng-container>

            <ng-container matColumnDef="flags">
              <th mat-header-cell *matHeaderCellDef>Flags</th>
              <td mat-cell *matCellDef="let field">
                @if (field.is_required) {
                  <mat-icon class="flag-icon" matTooltip="Required">star</mat-icon>
                }
                @if (field.is_sensitive) {
                  <mat-icon class="flag-icon" matTooltip="Sensitive">lock</mat-icon>
                }
                @if (field.is_file_upload) {
                  <mat-icon class="flag-icon" matTooltip="File Upload">attach_file</mat-icon>
                }
              </td>
            </ng-container>

            <tr mat-header-row *matHeaderRowDef="['name', 'type', 'purpose', 'value', 'flags']"></tr>
            <tr mat-row *matRowDef="let row; columns: ['name', 'type', 'purpose', 'value', 'flags']"></tr>
          </table>
        }
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .form-preview { margin-bottom: 16px; }
    .step-badge {
      background: #e8eaf6;
      color: #3f51b5;
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 12px;
      margin-left: 8px;
    }
    .confidence-bar { width: 200px; }
    .confidence-label { font-size: 12px; color: #666; }
    .chip-icon { font-size: 16px; width: 16px; height: 16px; margin-right: 4px; }
    .selector-info { font-size: 13px; line-height: 2; }
    code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
    .field-table { margin-top: 8px; }
    .sensitive { color: #999; font-style: italic; }
    .flag-icon { font-size: 18px; width: 18px; height: 18px; color: #666; }
  `]
})
export class FormPreviewComponent {
  form = input.required<FormDefinition>();
}
