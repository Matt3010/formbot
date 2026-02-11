import { Component, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatRadioModule } from '@angular/material/radio';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDatepickerModule } from '@angular/material/datepicker';
import { MatNativeDateModule } from '@angular/material/core';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatCardModule } from '@angular/material/card';
import { CronEditorComponent } from '../../../shared/components/cron-editor.component';

export interface ScheduleData {
  schedule_type: 'once' | 'cron';
  schedule_cron: string | null;
  schedule_at: string | null;
}

@Component({
  selector: 'app-step-schedule',
  standalone: true,
  imports: [
    FormsModule,
    MatRadioModule,
    MatFormFieldModule,
    MatInputModule,
    MatDatepickerModule,
    MatNativeDateModule,
    MatButtonModule,
    MatIconModule,
    MatCardModule,
    CronEditorComponent,
  ],
  template: `
    <div class="step-schedule">
      <h2>Step 4: Schedule</h2>
      <p>Choose when this task should run.</p>

      <mat-radio-group [(ngModel)]="scheduleType" (ngModelChange)="onScheduleChange()" class="flex flex-col gap-2 mb-2">
        <mat-radio-button value="once">Run Once</mat-radio-button>
        <mat-radio-button value="cron">Recurring (Cron)</mat-radio-button>
      </mat-radio-group>

      @if (scheduleType() === 'once') {
        <mat-card class="mt-2">
          <mat-card-content>
            <div class="flex gap-2">
              <mat-form-field appearance="outline">
                <mat-label>Date</mat-label>
                <input matInput [matDatepicker]="picker" [(ngModel)]="scheduleDate" (ngModelChange)="onScheduleChange()">
                <mat-datepicker-toggle matIconSuffix [for]="picker"></mat-datepicker-toggle>
                <mat-datepicker #picker></mat-datepicker>
              </mat-form-field>

              <mat-form-field appearance="outline">
                <mat-label>Time</mat-label>
                <input matInput type="time" [(ngModel)]="scheduleTime" (ngModelChange)="onScheduleChange()">
              </mat-form-field>
            </div>
            <p class="hint">Leave empty to run immediately when activated.</p>
          </mat-card-content>
        </mat-card>
      } @else {
        <mat-card class="mt-2">
          <mat-card-content>
            <app-cron-editor
              [cron]="cronExpression()"
              (cronChange)="onCronChange($event)"
            />
          </mat-card-content>
        </mat-card>
      }
    </div>
  `,
  styles: [`
    .step-schedule { max-width: 600px; }
    .hint { color: #999; font-size: 13px; margin-top: 8px; }
  `]
})
export class StepScheduleComponent {
  scheduleChanged = output<ScheduleData>();

  scheduleType = signal<'once' | 'cron'>('once');
  scheduleDate: Date | null = null;
  scheduleTime = '';
  cronExpression = signal('0 9 * * 1-5');

  onScheduleChange() {
    let scheduleAt: string | null = null;
    if (this.scheduleType() === 'once' && this.scheduleDate) {
      const date = new Date(this.scheduleDate);
      if (this.scheduleTime) {
        const [hours, minutes] = this.scheduleTime.split(':');
        date.setHours(parseInt(hours, 10), parseInt(minutes, 10));
      }
      scheduleAt = date.toISOString();
    }

    this.scheduleChanged.emit({
      schedule_type: this.scheduleType(),
      schedule_cron: this.scheduleType() === 'cron' ? this.cronExpression() : null,
      schedule_at: scheduleAt,
    });
  }

  onCronChange(cron: string) {
    this.cronExpression.set(cron);
    this.onScheduleChange();
  }

  setSchedule(data: ScheduleData) {
    this.scheduleType.set(data.schedule_type);
    if (data.schedule_at) {
      const date = new Date(data.schedule_at);
      this.scheduleDate = date;
      this.scheduleTime = `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
    }
    if (data.schedule_cron) {
      this.cronExpression.set(data.schedule_cron);
    }
  }
}
