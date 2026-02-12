import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatStepperModule } from '@angular/material/stepper';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { TaskService } from '../../core/services/task.service';
import { NotificationService } from '../../core/services/notification.service';
import { Task, FormDefinition, TaskPayload } from '../../core/models/task.model';
import { StepUrlComponent, LoginConfig } from './step-url/step-url.component';
import { StepFormsComponent } from './step-forms/step-forms.component';
import { StepFillComponent } from './step-fill/step-fill.component';
import { StepScheduleComponent, ScheduleData } from './step-schedule/step-schedule.component';
import { StepOptionsComponent, TaskOptions } from './step-options/step-options.component';

@Component({
  selector: 'app-task-wizard',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatStepperModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
    MatProgressSpinnerModule,
    StepUrlComponent,
    StepFormsComponent,
    StepFillComponent,
    StepScheduleComponent,
    StepOptionsComponent,
  ],
  template: `
    <div class="wizard-container">
      <div class="flex items-center justify-between mb-2">
        <h1>{{ isEditing() ? 'Edit Task' : 'Create New Task' }}</h1>
      </div>

      <mat-form-field appearance="outline" class="full-width mb-2">
        <mat-label>Task Name</mat-label>
        <input matInput [formControl]="taskNameControl" placeholder="My Automation Task">
      </mat-form-field>

      <mat-stepper linear #stepper>
        <!-- Step 1: URL & Analyze -->
        <mat-step [completed]="detectedForms().length > 0">
          <ng-template matStepLabel>URL & Analyze</ng-template>
          <app-step-url
            (formsDetected)="onFormsDetected($event)"
            (loginConfigChanged)="onLoginConfigChanged($event)"
          />
          <div class="step-actions mt-2">
            <button mat-raised-button color="primary" matStepperNext [disabled]="detectedForms().length === 0">
              Next <mat-icon>arrow_forward</mat-icon>
            </button>
          </div>
        </mat-step>

        <!-- Step 2: Review Forms -->
        <mat-step [completed]="confirmedForms().length > 0">
          <ng-template matStepLabel>Review Forms</ng-template>
          <app-step-forms
            [forms]="detectedForms()"
            (formsConfirmed)="onFormsConfirmed($event)"
          />
          <div class="step-actions mt-2">
            <button mat-button matStepperPrevious>
              <mat-icon>arrow_back</mat-icon> Back
            </button>
            <button mat-raised-button color="primary" matStepperNext>
              Next <mat-icon>arrow_forward</mat-icon>
            </button>
          </div>
        </mat-step>

        <!-- Step 3: Fill Fields -->
        <mat-step>
          <ng-template matStepLabel>Fill Fields</ng-template>
          <app-step-fill
            [forms]="confirmedForms().length > 0 ? confirmedForms() : detectedForms()"
            (filledForms)="onFormsFilled($event)"
          />
          <div class="step-actions mt-2">
            <button mat-button matStepperPrevious>
              <mat-icon>arrow_back</mat-icon> Back
            </button>
            <button mat-raised-button color="primary" matStepperNext>
              Next <mat-icon>arrow_forward</mat-icon>
            </button>
          </div>
        </mat-step>

        <!-- Step 4: Schedule -->
        <mat-step>
          <ng-template matStepLabel>Schedule</ng-template>
          <app-step-schedule
            (scheduleChanged)="onScheduleChanged($event)"
          />
          <div class="step-actions mt-2">
            <button mat-button matStepperPrevious>
              <mat-icon>arrow_back</mat-icon> Back
            </button>
            <button mat-raised-button color="primary" matStepperNext>
              Next <mat-icon>arrow_forward</mat-icon>
            </button>
          </div>
        </mat-step>

        <!-- Step 5: Options -->
        <mat-step>
          <ng-template matStepLabel>Options</ng-template>
          <app-step-options
            (optionsChanged)="onOptionsChanged($event)"
          />
          <div class="step-actions mt-3">
            <button mat-button matStepperPrevious>
              <mat-icon>arrow_back</mat-icon> Back
            </button>
            <button mat-stroked-button (click)="saveDraft()" [disabled]="saving()">
              <mat-icon>save</mat-icon> Save Draft
            </button>
            <button mat-raised-button color="primary" (click)="activate()" [disabled]="saving()">
              @if (saving()) {
                <mat-spinner diameter="20"></mat-spinner>
              } @else {
                <mat-icon>rocket_launch</mat-icon> Activate
              }
            </button>
          </div>
        </mat-step>
      </mat-stepper>
    </div>
  `,
  styles: [`
    .wizard-container { max-width: 900px; padding-bottom: 48px; }
    .step-actions { display: flex; gap: 12px; align-items: center; }
  `]
})
export class TaskWizardComponent implements OnInit {
  @ViewChild(StepUrlComponent) stepUrl!: StepUrlComponent;
  @ViewChild(StepFormsComponent) stepForms!: StepFormsComponent;
  @ViewChild(StepFillComponent) stepFill!: StepFillComponent;
  @ViewChild(StepScheduleComponent) stepSchedule!: StepScheduleComponent;
  @ViewChild(StepOptionsComponent) stepOptions!: StepOptionsComponent;

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private fb = inject(FormBuilder);
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);

  isEditing = signal(false);
  editingTaskId = signal<string | null>(null);
  saving = signal(false);

  // Login config
  requiresLogin = signal(false);
  loginUrl = signal<string | null>(null);
  loginEveryTime = signal(true);

  taskNameControl = this.fb.nonNullable.control('', Validators.required);
  detectedForms = signal<FormDefinition[]>([]);
  confirmedForms = signal<FormDefinition[]>([]);
  filledForms = signal<FormDefinition[]>([]);
  scheduleData = signal<ScheduleData>({ schedule_type: 'once', schedule_cron: null, schedule_at: null });
  taskOptions = signal<TaskOptions>({
    is_dry_run: false,
    stealth_enabled: true,
    action_delay_ms: 500,
    custom_user_agent: null,
    max_retries: 3,
    max_parallel: 1,
  });

  ngOnInit() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) {
      this.isEditing.set(true);
      this.editingTaskId.set(id);
      this.loadTask(id);
    }
  }

  private loadTask(id: string) {
    this.taskService.getTask(id).subscribe({
      next: (res) => {
        const task = res.data;
        this.taskNameControl.setValue(task.name);
        if (task.form_definitions?.length) {
          this.detectedForms.set(task.form_definitions);
          this.confirmedForms.set(task.form_definitions);
          this.filledForms.set(task.form_definitions);
        }
        this.scheduleData.set({
          schedule_type: task.schedule_type,
          schedule_cron: task.schedule_cron,
          schedule_at: task.schedule_at,
        });
        this.taskOptions.set({
          is_dry_run: task.is_dry_run,
          stealth_enabled: task.stealth_enabled,
          action_delay_ms: task.action_delay_ms,
          custom_user_agent: task.custom_user_agent,
          max_retries: task.max_retries,
          max_parallel: task.max_parallel,
        });

        // Populate login config
        if (task.requires_login) {
          this.requiresLogin.set(true);
          this.loginUrl.set(task.login_url);
          this.loginEveryTime.set(task.login_every_time);
        }

        // Populate child components after view init
        setTimeout(() => {
          if (this.stepUrl) {
            this.stepUrl.setUrl(task.target_url);
            if (task.requires_login) {
              this.stepUrl.setLoginConfig({
                requires_login: task.requires_login,
                login_url: task.login_url,
                login_every_time: task.login_every_time,
              });
            }
          }
          if (this.stepForms) this.stepForms.setForms(task.form_definitions);
          if (this.stepFill) this.stepFill.setForms(task.form_definitions);
          if (this.stepSchedule) this.stepSchedule.setSchedule(this.scheduleData());
          if (this.stepOptions) this.stepOptions.setOptions(this.taskOptions());
        });
      },
      error: () => this.notify.error('Failed to load task')
    });
  }

  onLoginConfigChanged(config: LoginConfig) {
    this.requiresLogin.set(config.requires_login);
    this.loginUrl.set(config.login_url);
    this.loginEveryTime.set(config.login_every_time);
  }

  onFormsDetected(forms: FormDefinition[]) {
    this.detectedForms.set(forms);
    this.confirmedForms.set(forms);
  }

  onFormsConfirmed(forms: FormDefinition[]) {
    this.confirmedForms.set(forms);
  }

  onFormsFilled(forms: FormDefinition[]) {
    this.filledForms.set(forms);
  }

  onScheduleChanged(data: ScheduleData) {
    this.scheduleData.set(data);
  }

  onOptionsChanged(opts: TaskOptions) {
    this.taskOptions.set(opts);
  }

  private buildTaskPayload(status: string): TaskPayload {
    const forms = this.filledForms().length > 0 ? this.filledForms() :
                  this.confirmedForms().length > 0 ? this.confirmedForms() :
                  this.detectedForms();
    const schedule = this.scheduleData();
    const options = this.taskOptions();

    // For login-aware tasks, target_url should be the target page (not login page)
    const targetUrl = this.requiresLogin()
      ? forms.find(f => f.form_type !== 'login')?.page_url || forms[0]?.page_url || ''
      : forms[0]?.page_url || '';

    // Transform forms: rename 'fields' to 'form_fields' for backend
    const formDefs = forms.map(f => ({
      step_order: f.step_order,
      page_url: f.page_url,
      form_type: f.form_type,
      form_selector: f.form_selector,
      submit_selector: f.submit_selector,
      ai_confidence: f.ai_confidence,
      captcha_detected: f.captcha_detected ?? false,
      two_factor_expected: f.two_factor_expected ?? false,
      form_fields: (f.fields || []).map((field, idx) => ({
        field_name: field.field_name,
        field_type: field.field_type,
        field_selector: field.field_selector,
        field_purpose: field.field_purpose || null,
        preset_value: field.preset_value || null,
        is_sensitive: field.is_sensitive ?? false,
        is_file_upload: field.is_file_upload ?? false,
        is_required: field.is_required ?? false,
        options: field.options || null,
        sort_order: field.sort_order ?? idx,
      })),
    }));

    return {
      name: this.taskNameControl.value || 'Untitled Task',
      target_url: targetUrl,
      status: status as Task['status'],
      schedule_type: schedule.schedule_type,
      schedule_cron: schedule.schedule_cron,
      schedule_at: schedule.schedule_at,
      is_dry_run: options.is_dry_run,
      stealth_enabled: options.stealth_enabled,
      action_delay_ms: options.action_delay_ms,
      custom_user_agent: options.custom_user_agent,
      max_retries: options.max_retries,
      max_parallel: options.max_parallel,
      requires_login: this.requiresLogin(),
      login_url: this.loginUrl(),
      login_every_time: this.loginEveryTime(),
      form_definitions: formDefs,
    };
  }

  saveDraft() {
    this.saving.set(true);
    const payload = this.buildTaskPayload('draft');

    const request = this.editingTaskId()
      ? this.taskService.updateTask(this.editingTaskId()!, payload)
      : this.taskService.createTask(payload);

    request.subscribe({
      next: (res) => {
        this.saving.set(false);
        this.notify.success('Task saved as draft');
        this.router.navigate(['/tasks', res.data.id]);
      },
      error: (err) => {
        this.saving.set(false);
        this.notify.error(err.error?.message || 'Failed to save task');
      }
    });
  }

  activate() {
    this.saving.set(true);
    const payload = this.buildTaskPayload('active');

    const request = this.editingTaskId()
      ? this.taskService.updateTask(this.editingTaskId()!, payload)
      : this.taskService.createTask(payload);

    request.subscribe({
      next: (res) => {
        this.taskService.activateTask(res.data.id).subscribe({
          next: () => {
            this.saving.set(false);
            this.notify.success('Task activated!');
            this.router.navigate(['/tasks', res.data.id]);
          },
          error: () => {
            this.saving.set(false);
            this.notify.warn('Task saved but activation failed');
            this.router.navigate(['/tasks', res.data.id]);
          }
        });
      },
      error: (err) => {
        this.saving.set(false);
        this.notify.error(err.error?.message || 'Failed to save task');
      }
    });
  }
}
