import { Component, inject, OnInit, signal, ViewChild } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatStepperModule, MatStepper } from '@angular/material/stepper';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { TaskService } from '../../core/services/task.service';
import { NotificationService } from '../../core/services/notification.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { VncEditorService } from '../../core/services/vnc-editor.service';
import { Task, FormDefinition, TaskPayload } from '../../core/models/task.model';
import { Analysis } from '../../core/models/analysis.model';
import { StepUrlComponent, LoginConfig } from './step-url/step-url.component';
import { StepScheduleComponent, ScheduleData } from './step-schedule/step-schedule.component';
import { StepOptionsComponent, TaskOptions } from './step-options/step-options.component';
import { VncFormEditorComponent } from './vnc-form-editor/vnc-form-editor.component';
import { WorkflowGraphComponent } from './workflow-graph/workflow-graph.component';

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
    StepScheduleComponent,
    StepOptionsComponent,
    VncFormEditorComponent,
    WorkflowGraphComponent,
  ],
  template: `
    <div class="wizard-container vnc-active">
      <div class="flex items-center justify-between mb-2">
        <h1>{{ isEditing() ? 'Edit Task' : 'Create New Task' }}</h1>
      </div>

      <mat-form-field appearance="outline" class="full-width mb-2">
        <mat-label>Task Name</mat-label>
        <input matInput [formControl]="taskNameControl" placeholder="My Automation Task">
      </mat-form-field>

      <mat-stepper [linear]="!resumingFromAnalysis()" #stepper>
        <!-- Step 1: URL & Analyze -->
        <mat-step [completed]="detectedForms().length > 0">
          <ng-template matStepLabel>URL & Analyze</ng-template>
          <app-step-url
            (formsDetected)="onFormsDetected($event)"
            (loginConfigChanged)="onLoginConfigChanged($event)"

          />
          <div class="step-actions mt-2">
            <button mat-raised-button color="primary" (click)="proceedToVncEditor()" [disabled]="detectedForms().length === 0">
              Next <mat-icon>arrow_forward</mat-icon>
            </button>
          </div>
        </mat-step>

        <!-- Step 2: Configure Forms (VNC Editor) -->
        <mat-step [completed]="confirmedFromVnc().length > 0">
          <ng-template matStepLabel>Configure Forms</ng-template>
          @if (vncAnalysisId()) {
            <app-vnc-form-editor
              [analysisId]="vncAnalysisId()!"
              [analysisResult]="vncAnalysisResult()"
              [resumeCorrections]="vncResumeCorrections()"
              [requiresLogin]="requiresLogin()"
              [targetUrl]="vncTargetUrl()"
              (confirmed)="onVncConfirmed($event)"
              (cancelled)="onVncCancelled()"
            />
          } @else {
            <p>Click "Next" on Step 1 after analyzing a URL to start the visual editor.</p>
          }
          <div class="step-actions mt-2">
            <button mat-button matStepperPrevious>
              <mat-icon>arrow_back</mat-icon> Back
            </button>
          </div>
        </mat-step>

        <!-- Step 3: Workflow Graph -->
        <mat-step [completed]="workflowForms().length > 0">
          <ng-template matStepLabel>Workflow Graph</ng-template>
          @if (workflowForms().length > 0) {
            <app-workflow-graph
              [forms]="workflowForms()"
              [editable]="true"
              (formsChange)="onWorkflowFormsChanged($event)"
            />
          } @else {
            <p>Confirm forms in the visual editor to configure dependencies.</p>
          }
          <div class="step-actions mt-2">
            <button mat-button matStepperPrevious>
              <mat-icon>arrow_back</mat-icon> Back
            </button>
            <button mat-raised-button color="primary" matStepperNext [disabled]="workflowForms().length === 0">
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
    .wizard-container.vnc-active { max-width: 100%; }
    .step-actions { display: flex; gap: 12px; align-items: center; }
  `]
})
export class TaskWizardComponent implements OnInit {
  @ViewChild(StepUrlComponent) stepUrl!: StepUrlComponent;
  @ViewChild(StepScheduleComponent) stepSchedule!: StepScheduleComponent;
  @ViewChild(StepOptionsComponent) stepOptions!: StepOptionsComponent;
  @ViewChild(VncFormEditorComponent) vncEditor!: VncFormEditorComponent;
  @ViewChild('stepper') stepper!: MatStepper;

  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private fb = inject(FormBuilder);
  private taskService = inject(TaskService);
  private analysisService = inject(AnalysisService);
  private notify = inject(NotificationService);
  private vncEditorService = inject(VncEditorService);

  isEditing = signal(false);
  editingTaskId = signal<string | null>(null);
  resumingFromAnalysis = signal(false);
  resumeAnalysisId = signal<string | null>(null);
  saving = signal(false);

  // Login config
  requiresLogin = signal(false);
  loginUrl = signal<string | null>(null);

  // VNC editor state
  vncAnalysisId = signal<string | null>(null);
  vncAnalysisResult = signal<any>(null);
  vncResumeCorrections = signal<any>(null);
  vncTargetUrl = signal<string | null>(null);

  taskNameControl = this.fb.nonNullable.control('', Validators.required);
  detectedForms = signal<FormDefinition[]>([]);
  confirmedFromVnc = signal<FormDefinition[]>([]);
  workflowForms = signal<FormDefinition[]>([]);
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
      return;
    }

    // Check for analysis resume flow
    const analysisId = this.route.snapshot.queryParamMap.get('analysisId');
    const editingMode = this.route.snapshot.queryParamMap.get('editing');
    if (analysisId) {
      this.resumeAnalysisId.set(analysisId);
      const pending = this.analysisService.consumePendingResume();

      if (editingMode === 'resume') {
        // Resume VNC editing from saved draft
        this.resumeVncEditing(analysisId, pending);
      } else if (pending && pending.id === analysisId) {
        this.applyAnalysis(pending);
      } else {
        // Fallback: fetch from API (e.g., user refreshed the page)
        this.analysisService.getAnalysis(analysisId).subscribe({
          next: (res) => this.applyAnalysis(res.data),
          error: () => this.notify.error('Failed to load analysis for resume'),
        });
      }
    }
  }

  private resumeVncEditing(analysisId: string, pending: Analysis | null) {
    this.resumingFromAnalysis.set(true);
    this.vncAnalysisId.set(analysisId);

    // Set URL in step-url and load corrections if we have the analysis data
    if (pending) {
      if (pending.user_corrections) {
        this.vncResumeCorrections.set(pending.user_corrections);
      }
      setTimeout(() => {
        if (this.stepUrl) {
          this.stepUrl.setUrl(pending.url);
        }
      });
    }

    // Call resume endpoint to re-open VNC with saved draft
    this.vncEditorService.resumeEditing(analysisId).subscribe({
      next: (res) => {
        // Backend may return user_corrections in response
        if (res?.user_corrections && !this.vncResumeCorrections()) {
          this.vncResumeCorrections.set(res.user_corrections);
        }
        this.notify.info('Resuming visual editing session...');
        setTimeout(() => {
          if (this.stepper) {
            this.stepper.selectedIndex = 1;
          }
          setTimeout(() => this.resumingFromAnalysis.set(false), 100);
        });
      },
      error: (err) => {
        this.notify.error(err.error?.message || 'Failed to resume editing session');
        this.resumingFromAnalysis.set(false);
      },
    });
  }

  private applyAnalysis(analysis: Analysis) {
    if (analysis.status !== 'completed' || !analysis.result) {
      this.notify.warn('This analysis is not completed yet');
      return;
    }

    this.resumingFromAnalysis.set(true);

    // Build FormDefinition[] from the analysis result
    const forms: FormDefinition[] = (analysis.result.forms || []).map((form: any, idx: number) => ({
      id: form.id || `temp-${idx}`,
      task_id: '',
      step_order: form.step_order ?? idx + 1,
      depends_on_step_order: form.depends_on_step_order ?? null,
      page_url: form.page_url || analysis.url,
      form_type: form.form_type || 'target',
      form_selector: form.form_selector || '',
      submit_selector: form.submit_selector || '',
      human_breakpoint: form.human_breakpoint ?? false,
      fields: (form.fields || []).map((field: any, fIdx: number) => ({
        id: field.id || `temp-field-${idx}-${fIdx}`,
        form_definition_id: form.id || `temp-${idx}`,
        field_name: field.field_name || field.name || '',
        field_type: field.field_type || field.type || 'text',
        field_selector: field.field_selector || field.selector || '',
        field_purpose: field.field_purpose || field.purpose || null,
        preset_value: field.preset_value || null,
        is_sensitive: field.is_sensitive ?? false,
        is_file_upload: field.is_file_upload ?? false,
        is_required: field.is_required ?? false,
        options: field.options || null,
        sort_order: field.sort_order ?? fIdx,
      })),
      created_at: '',
      updated_at: '',
    }));

    // Set login config if applicable
    if (analysis.type === 'login_and_target' && analysis.login_url) {
      this.requiresLogin.set(true);
      this.loginUrl.set(analysis.login_url);
    }

    this.detectedForms.set(this.normalizeWorkflowForms(forms));

    // Set URL and login config in step-url, then start VNC session
    setTimeout(() => {
      if (this.stepUrl) {
        this.stepUrl.setUrl(analysis.url);
        this.stepUrl.currentAnalysisId.set(analysis.id);
        if (analysis.type === 'login_and_target' && analysis.login_url) {
          this.stepUrl.setLoginConfig({
            requires_login: true,
            login_url: analysis.login_url,
          });
        }
      }

      // Start VNC session and advance to Step 2
      this.vncAnalysisId.set(analysis.id);
      this.vncAnalysisResult.set(analysis.result);
      this.taskService.analyzeInteractive(analysis.id).subscribe({
        next: () => {
          this.notify.info('Starting visual editor...');
          if (this.stepper) {
            this.stepper.selectedIndex = 1;
          }
          setTimeout(() => this.resumingFromAnalysis.set(false), 100);
        },
        error: (err) => {
          this.notify.error(err.error?.message || 'Failed to start visual editor');
          this.resumingFromAnalysis.set(false);
        },
      });
    });
  }

  private loadTask(id: string) {
    this.taskService.getTask(id).subscribe({
      next: (res) => {
        const task = res.data;
        this.taskNameControl.setValue(task.name);
        if (task.form_definitions?.length) {
          const normalizedForms = this.normalizeWorkflowForms(task.form_definitions);
          this.detectedForms.set(normalizedForms);
          this.confirmedFromVnc.set(normalizedForms);
          this.workflowForms.set(normalizedForms);
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
        }

        // Populate child components after view init
        setTimeout(() => {
          if (this.stepUrl) {
            this.stepUrl.setUrl(task.target_url);
            if (task.requires_login) {
              this.stepUrl.setLoginConfig({
                requires_login: task.requires_login,
                login_url: task.login_url,
              });
            }
          }
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
  }

  onFormsDetected(forms: FormDefinition[]) {
    const normalized = this.normalizeWorkflowForms(forms);
    this.detectedForms.set(normalized);
    if (this.confirmedFromVnc().length === 0) {
      this.workflowForms.set(normalized);
    }
    // Auto-advance to VNC editor as soon as initial forms are available
    if (forms.length > 0 && !this.isEditing()) {
      setTimeout(() => this.proceedToVncEditor());
    }
  }

  proceedToVncEditor() {
    const analysisId = this.stepUrl.currentAnalysisId();
    if (!analysisId) {
      this.notify.error('No analysis available. Please analyze the URL first.');
      return;
    }

    this.vncAnalysisId.set(analysisId);
    this.vncAnalysisResult.set(null);

    // When login is required, pass the login URL so VNC opens the login page.
    // The target URL is stored separately for the login→target transition.
    if (this.requiresLogin()) {
      const loginUrl = this.stepUrl.loginUrlControl.value;
      const targetUrl = this.stepUrl.urlControl.value;
      this.vncTargetUrl.set(targetUrl || null);

      // Start editing with the login URL override
      this.taskService.analyzeInteractiveWithUrl(analysisId, loginUrl).subscribe({
        next: () => {
          this.notify.info('Starting visual editor (login page)...');
          this.resumingFromAnalysis.set(true);
          setTimeout(() => {
            if (this.stepper) {
              this.stepper.selectedIndex = 1;
            }
            setTimeout(() => this.resumingFromAnalysis.set(false), 100);
          });
        },
        error: (err) => {
          this.notify.error(err.error?.message || 'Failed to start visual editor');
        },
      });
    } else {
      this.vncTargetUrl.set(null);

      // Start the interactive session via backend
      this.taskService.analyzeInteractive(analysisId).subscribe({
        next: () => {
          this.notify.info('Starting visual editor...');
          this.resumingFromAnalysis.set(true);
          setTimeout(() => {
            if (this.stepper) {
              this.stepper.selectedIndex = 1;
            }
            setTimeout(() => this.resumingFromAnalysis.set(false), 100);
          });
        },
        error: (err) => {
          this.notify.error(err.error?.message || 'Failed to start visual editor');
        },
      });
    }
  }

  onVncConfirmed(forms: FormDefinition[]) {
    const normalized = this.normalizeWorkflowForms(forms);
    this.confirmedFromVnc.set(normalized);
    this.workflowForms.set(normalized);
    this.notify.success('Forms confirmed via visual editor');

    // Advance to Workflow Graph step
    setTimeout(() => {
      if (this.stepper) {
        this.stepper.selectedIndex = 2;
      }
    });
  }

  onVncCancelled() {
    this.vncAnalysisId.set(null);
    this.vncResumeCorrections.set(null);
    this.workflowForms.set([]);
    this.notify.info('Visual verification cancelled');
  }

  onScheduleChanged(data: ScheduleData) {
    this.scheduleData.set(data);
  }

  onOptionsChanged(opts: TaskOptions) {
    this.taskOptions.set(opts);
  }

  onWorkflowFormsChanged(forms: FormDefinition[]) {
    const normalized = this.normalizeWorkflowForms(forms);
    this.workflowForms.set(normalized);
    this.confirmedFromVnc.set(normalized);
  }

  private normalizeWorkflowForms(forms: FormDefinition[]): FormDefinition[] {
    const sorted = [...forms]
      .map((form) => ({
        ...form,
        depends_on_step_order: form.depends_on_step_order ?? null,
      }))
      .sort((a, b) => a.step_order - b.step_order);

    const stepOrders = new Set(sorted.map((form) => form.step_order));

    return sorted.map((form) => {
      if (form.depends_on_step_order === form.step_order) {
        return { ...form, depends_on_step_order: null };
      }
      if (form.depends_on_step_order !== null && !stepOrders.has(form.depends_on_step_order)) {
        return { ...form, depends_on_step_order: null };
      }
      return form;
    });
  }

  private buildTaskPayload(status: string): TaskPayload {
    const forms = this.workflowForms().length > 0
      ? this.workflowForms()
      : (
          this.confirmedFromVnc().length > 0
            ? this.confirmedFromVnc()
            : this.detectedForms()
        );
    const schedule = this.scheduleData();
    const options = this.taskOptions();

    // For login-aware tasks, target_url should be the target page (not login page)
    const targetUrl = this.requiresLogin()
      ? forms.find(f => f.form_type !== 'login')?.page_url || forms[0]?.page_url || ''
      : forms[0]?.page_url || '';

    // Transform forms: rename 'fields' to 'form_fields' for backend
    const formDefs = forms.map(f => ({
      step_order: f.step_order,
      depends_on_step_order: f.depends_on_step_order ?? null,
      page_url: f.page_url,
      form_type: f.form_type,
      form_selector: f.form_selector || null,
      submit_selector: f.submit_selector || null,
      human_breakpoint: f.human_breakpoint ?? false,
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
        this.linkAnalysisIfNeeded(res.data.id);
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
        this.linkAnalysisIfNeeded(res.data.id);
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

  private linkAnalysisIfNeeded(taskId: string) {
    const analysisId = this.resumeAnalysisId();
    if (analysisId) {
      this.analysisService.linkTask(analysisId, taskId).subscribe({
        error: () => console.warn('Failed to link analysis to task'),
      });
    }
  }
}
