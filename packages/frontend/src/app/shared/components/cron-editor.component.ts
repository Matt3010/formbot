import { Component, input, output, signal, computed, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatSelectModule } from '@angular/material/select';
import { MatInputModule } from '@angular/material/input';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-cron-editor',
  standalone: true,
  imports: [
    FormsModule,
    MatFormFieldModule,
    MatSelectModule,
    MatInputModule,
    MatCardModule,
    MatIconModule,
  ],
  template: `
    <div class="cron-editor">
      <div class="cron-fields flex gap-2">
        <mat-form-field appearance="outline" style="width: 120px;">
          <mat-label>Minute</mat-label>
          <mat-select [(ngModel)]="minute" (ngModelChange)="buildCron()">
            <mat-option value="*">Every</mat-option>
            <mat-option value="0">:00</mat-option>
            <mat-option value="15">:15</mat-option>
            <mat-option value="30">:30</mat-option>
            <mat-option value="45">:45</mat-option>
            @for (m of minuteOptions; track m) {
              <mat-option [value]="m">:{{ m.padStart(2, '0') }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" style="width: 120px;">
          <mat-label>Hour</mat-label>
          <mat-select [(ngModel)]="hour" (ngModelChange)="buildCron()">
            <mat-option value="*">Every</mat-option>
            @for (h of hourOptions; track h) {
              <mat-option [value]="h">{{ h }}:00</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" style="width: 140px;">
          <mat-label>Day of Month</mat-label>
          <mat-select [(ngModel)]="dayOfMonth" (ngModelChange)="buildCron()">
            <mat-option value="*">Every</mat-option>
            @for (d of dayOptions; track d) {
              <mat-option [value]="d">{{ d }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" style="width: 140px;">
          <mat-label>Month</mat-label>
          <mat-select [(ngModel)]="month" (ngModelChange)="buildCron()">
            <mat-option value="*">Every</mat-option>
            @for (m of monthNames; track m.value) {
              <mat-option [value]="m.value">{{ m.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>

        <mat-form-field appearance="outline" style="width: 140px;">
          <mat-label>Weekday</mat-label>
          <mat-select [(ngModel)]="weekday" (ngModelChange)="buildCron()">
            <mat-option value="*">Every</mat-option>
            <mat-option value="1-5">Mon-Fri</mat-option>
            <mat-option value="0,6">Weekends</mat-option>
            @for (w of weekdayNames; track w.value) {
              <mat-option [value]="w.value">{{ w.label }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </div>

      <mat-form-field appearance="outline" class="full-width mt-1">
        <mat-label>Cron Expression</mat-label>
        <input matInput [(ngModel)]="cronRaw" (ngModelChange)="onRawCronChange($event)">
        <mat-hint>{{ humanReadable() }}</mat-hint>
      </mat-form-field>
    </div>
  `,
  styles: [`
    .cron-editor { padding: 8px 0; }
    .cron-fields { flex-wrap: wrap; }
  `]
})
export class CronEditorComponent {
  cron = input<string>('0 9 * * 1-5');
  cronChange = output<string>();

  minute = '0';
  hour = '9';
  dayOfMonth = '*';
  month = '*';
  weekday = '1-5';
  cronRaw = '0 9 * * 1-5';

  minuteOptions = Array.from({ length: 60 }, (_, i) => i.toString()).filter(m => !['0', '15', '30', '45'].includes(m));
  hourOptions = Array.from({ length: 24 }, (_, i) => i.toString());
  dayOptions = Array.from({ length: 31 }, (_, i) => (i + 1).toString());

  monthNames = [
    { value: '1', label: 'January' },
    { value: '2', label: 'February' },
    { value: '3', label: 'March' },
    { value: '4', label: 'April' },
    { value: '5', label: 'May' },
    { value: '6', label: 'June' },
    { value: '7', label: 'July' },
    { value: '8', label: 'August' },
    { value: '9', label: 'September' },
    { value: '10', label: 'October' },
    { value: '11', label: 'November' },
    { value: '12', label: 'December' },
  ];

  weekdayNames = [
    { value: '0', label: 'Sunday' },
    { value: '1', label: 'Monday' },
    { value: '2', label: 'Tuesday' },
    { value: '3', label: 'Wednesday' },
    { value: '4', label: 'Thursday' },
    { value: '5', label: 'Friday' },
    { value: '6', label: 'Saturday' },
  ];

  humanReadable = signal('At 9:00 AM, Monday through Friday');

  constructor() {
    effect(() => {
      const incoming = this.cron();
      if (incoming) {
        this.parseCron(incoming);
      }
    });
  }

  private parseCron(expr: string) {
    const parts = expr.split(' ');
    if (parts.length === 5) {
      this.minute = parts[0];
      this.hour = parts[1];
      this.dayOfMonth = parts[2];
      this.month = parts[3];
      this.weekday = parts[4];
      this.cronRaw = expr;
      this.updateHumanReadable();
    }
  }

  buildCron() {
    this.cronRaw = `${this.minute} ${this.hour} ${this.dayOfMonth} ${this.month} ${this.weekday}`;
    this.updateHumanReadable();
    this.cronChange.emit(this.cronRaw);
  }

  onRawCronChange(value: string) {
    const parts = value.split(' ');
    if (parts.length === 5) {
      this.minute = parts[0];
      this.hour = parts[1];
      this.dayOfMonth = parts[2];
      this.month = parts[3];
      this.weekday = parts[4];
      this.updateHumanReadable();
      this.cronChange.emit(value);
    }
  }

  private updateHumanReadable() {
    const parts: string[] = [];

    if (this.minute === '*' && this.hour === '*') {
      parts.push('Every minute');
    } else if (this.hour === '*') {
      parts.push(`At minute ${this.minute} of every hour`);
    } else if (this.minute === '*') {
      parts.push(`Every minute of hour ${this.hour}`);
    } else {
      const h = parseInt(this.hour, 10);
      const ampm = h >= 12 ? 'PM' : 'AM';
      const hour12 = h === 0 ? 12 : h > 12 ? h - 12 : h;
      parts.push(`At ${hour12}:${this.minute.padStart(2, '0')} ${ampm}`);
    }

    if (this.dayOfMonth !== '*') {
      parts.push(`on day ${this.dayOfMonth}`);
    }

    if (this.month !== '*') {
      const monthName = this.monthNames.find(m => m.value === this.month);
      parts.push(`of ${monthName?.label || this.month}`);
    }

    if (this.weekday === '1-5') {
      parts.push('Monday through Friday');
    } else if (this.weekday === '0,6') {
      parts.push('on weekends');
    } else if (this.weekday !== '*') {
      const dayName = this.weekdayNames.find(w => w.value === this.weekday);
      parts.push(`on ${dayName?.label || this.weekday}`);
    }

    this.humanReadable.set(parts.join(', '));
  }
}
