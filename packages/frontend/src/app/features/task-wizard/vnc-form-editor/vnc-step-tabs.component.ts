import { Component, input, output } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { MatTabsModule } from '@angular/material/tabs';
import { EditingStep } from '../../../core/models/vnc-editor.model';

@Component({
  selector: 'app-vnc-step-tabs',
  standalone: true,
  imports: [TitleCasePipe, MatTabsModule],
  template: `
    @if (steps().length > 1) {
      <mat-tab-group [selectedIndex]="activeStep()" (selectedIndexChange)="stepChanged.emit($event)">
        @for (step of steps(); track step.step_order; let i = $index) {
          <mat-tab [disabled]="disabled()">
            <ng-template matTabLabel>
              <div class="step-tab-label">
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
  `]
})
export class VncStepTabsComponent {
  steps = input<EditingStep[]>([]);
  activeStep = input<number>(0);
  disabled = input<boolean>(false);
  stepChanged = output<number>();
}
