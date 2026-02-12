import { Component, input, output } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { MatTabsModule } from '@angular/material/tabs';
import { MatIconModule } from '@angular/material/icon';
import { EditingStep } from '../../../core/models/vnc-editor.model';

@Component({
  selector: 'app-vnc-step-tabs',
  standalone: true,
  imports: [TitleCasePipe, MatTabsModule, MatIconModule],
  template: `
    @if (steps().length > 1) {
      <mat-tab-group [selectedIndex]="activeStep()" (selectedIndexChange)="stepChanged.emit($event)">
        @for (step of steps(); track step.step_order; let i = $index) {
          <mat-tab>
            <ng-template matTabLabel>
              <div class="step-tab-label">
                @if (step.status === 'confirmed') {
                  <mat-icon class="confirmed-icon">check_circle</mat-icon>
                }
                {{ i + 1 }}. {{ step.form_type | titlecase }}
              </div>
            </ng-template>
          </mat-tab>
        }
      </mat-tab-group>
    }
  `,
  styles: [`
    .step-tab-label {
      display: flex;
      align-items: center;
      gap: 4px;
    }
    .confirmed-icon { color: #4CAF50; font-size: 18px; width: 18px; height: 18px; }
  `]
})
export class VncStepTabsComponent {
  steps = input<EditingStep[]>([]);
  activeStep = input<number>(0);
  stepChanged = output<number>();
}
