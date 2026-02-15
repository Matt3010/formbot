import { Component, inject, input, output, signal, computed, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription, Subject, debounceTime } from 'rxjs';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VncEditorService } from '../../../core/services/vnc-editor.service';
import { FormDefinition } from '../../../core/models/task.model';
import {
  EditorMode, EditorPhase, EditorField, EditingStep, UserCorrections,
  HighlightingReadyEvent, FieldSelectedEvent, FieldAddedEvent, FieldRemovedEvent,
  FieldValueChangedEvent, LoginExecutionProgressEvent, LoginExecutionCompleteEvent,
  StepNavigationStateEvent,
} from '../../../core/models/vnc-editor.model';
import { VncModeToolbarComponent } from './vnc-mode-toolbar.component';
import { VncFieldListComponent } from './vnc-field-list.component';
import { VncFieldDetailComponent } from './vnc-field-detail.component';
import { VncStepTabsComponent } from './vnc-step-tabs.component';

@Component({
  selector: 'app-vnc-form-editor',
  standalone: true,
  imports: [
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatDividerModule,
    MatSlideToggleModule,
    MatTooltipModule,
    VncModeToolbarComponent,
    VncFieldListComponent,
    VncFieldDetailComponent,
    VncStepTabsComponent,
  ],
  template: `
    @if (loading()) {
      <div class="loading-state">
        <mat-spinner diameter="40"></mat-spinner>
        <p>Setting up VNC session and highlighting fields...</p>
      </div>
    } @else if (vncUrl()) {
      <div class="viewer-toolbar">
        <button mat-stroked-button (click)="toggleEditorHidden()" [disabled]="navigatingStep()">
          <mat-icon>{{ editorHidden() ? 'view_sidebar' : 'desktop_windows' }}</mat-icon>
          {{ editorHidden() ? 'Show Editor' : 'Focus VNC' }}
        </button>
        <button mat-stroked-button (click)="resetSplit()" [disabled]="navigatingStep()">
          <mat-icon>space_dashboard</mat-icon>
          Reset Layout
        </button>
      </div>

      <div class="split-view" [class.editor-hidden]="editorHidden()">
        <!-- Mode toolbar (vertical, left edge) -->
        @if (!editorHidden()) {
          <app-vnc-mode-toolbar
            [mode]="currentMode()"
            [disabled]="navigatingStep()"
            (modeChanged)="onModeChanged($event)"
          />
        }

        <!-- VNC Panel -->
        <div class="vnc-panel" [style.flex-grow]="splitPosition()">
          <iframe
            [src]="safeVncUrl()"
            class="vnc-iframe"
            frameborder="0"
            allow="clipboard-read; clipboard-write">
          </iframe>
          @if (navigatingStep()) {
            <div class="vnc-loading-overlay">
              <div class="vnc-loading-content">
                <mat-spinner diameter="30"></mat-spinner>
                <p>{{ navigationMessage() }}</p>
              </div>
            </div>
          }
        </div>

        <!-- Divider (draggable) -->
        @if (!editorHidden()) {
          <div class="divider" (mousedown)="startDrag($event)"></div>
        }

        <!-- Editor Panel -->
        @if (!editorHidden()) {
        <div class="editor-panel" [style.flex-grow]="100 - splitPosition()" [class.panel-busy]="navigatingStep()">
          <!-- Step tabs for multi-step -->
          <app-vnc-step-tabs
            [steps]="steps()"
            [activeStep]="activeStepIndex()"
            [disabled]="navigatingStep()"
            (stepChanged)="onStepChanged($event)"
          />

          <!-- Step flags -->
          <div class="step-flags">
            <mat-slide-toggle
              [checked]="currentStepBreakpoint()"
              [disabled]="navigatingStep()"
              (change)="onBreakpointToggle($event.checked)"
              color="warn">
              <mat-icon class="bp-icon">flag</mat-icon>
              Human breakpoint
            </mat-slide-toggle>
          </div>

          <!-- Field list -->
          <div class="field-list-section">
            <app-vnc-field-list
              [fields]="currentFields()"
              [selectedIndex]="selectedFieldIndex()"
              (fieldSelected)="onFieldSelected($event)"
              (fieldsReordered)="onFieldsReordered($event)"
            />
          </div>

          <mat-divider></mat-divider>

          <!-- Field detail -->
          <div class="field-detail-section">
            <app-vnc-field-detail
              [field]="selectedField()"
              [fieldIndex]="selectedFieldIndex()"
              (fieldChanged)="onFieldChanged($event)"
              (testSelectorRequested)="onTestSelector($event)"
            />
          </div>

          <mat-divider></mat-divider>

          <!-- Validation warning -->
          @if (hasValidationErrors()) {
            <div class="validation-warning">
              <mat-icon>warning</mat-icon>
              <span>Please fill in all required fields (name, selector) and add a submit button before confirming.</span>
            </div>
          }

          <!-- Actions (phase-dependent) -->
          <div class="actions">
            @if (currentPhase() === 'login') {
              <button mat-raised-button color="primary" (click)="onConfirmLoginAndProceed()"
                [disabled]="loginExecuting() || hasValidationErrors()"
                [matTooltip]="hasValidationErrors() ? 'Please fix validation errors before proceeding' : ''">
                <mat-icon>login</mat-icon> Confirm Login & Proceed
              </button>
              <button mat-stroked-button (click)="onCancel()">
                <mat-icon>close</mat-icon> Cancel
              </button>
            } @else if (currentPhase() === 'login-executing') {
              <div class="login-progress">
                <mat-spinner diameter="18"></mat-spinner>
                <span>{{ loginProgress() }}</span>
              </div>
              @if (breakpointWaiting()) {
                <button mat-raised-button color="accent" (click)="onResumeLogin()">
                  <mat-icon>play_arrow</mat-icon> Resume
                </button>
              }
            } @else {
              <button mat-stroked-button (click)="onAddTargetStep()" [disabled]="navigatingStep()">
                <mat-icon>add</mat-icon> Add Target Step
              </button>
              <button mat-raised-button color="primary" (click)="onConfirmAll()"
                [disabled]="confirming() || navigatingStep() || hasValidationErrors()"
                [matTooltip]="hasValidationErrors() ? 'Please fix validation errors before proceeding' : ''">
                @if (confirming()) {
                  <mat-spinner diameter="18"></mat-spinner>
                } @else {
                  <mat-icon>check</mat-icon> Confirm All
                }
              </button>
              <button mat-stroked-button (click)="onCancel()" [disabled]="navigatingStep()">
                <mat-icon>close</mat-icon> Cancel
              </button>
            }
          </div>
        </div>
        }
      </div>
    } @else {
      <div class="error-state">
        <mat-icon>error</mat-icon>
        <p>{{ initError() || 'Failed to initialize VNC session.' }}</p>
      </div>
    }
  `,
  styles: [`
    :host { display: block; width: 100%; }
    .loading-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 16px;
      padding: 48px;
      color: #666;
    }
    .split-view {
      display: flex;
      height: calc(100vh - 170px);
      min-height: 640px;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      overflow: hidden;
    }
    .viewer-toolbar {
      display: flex;
      gap: 8px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }
    .vnc-panel {
      position: relative;
      overflow: hidden;
      min-width: 0;
      background: #111;
    }
    .vnc-iframe {
      width: 100%;
      height: 100%;
      border: none;
    }
    .vnc-loading-overlay {
      position: absolute;
      inset: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(10, 10, 10, 0.72);
      pointer-events: all;
    }
    .vnc-loading-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 10px;
      color: #fff;
      text-align: center;
      font-size: 14px;
      padding: 0 20px;
    }
    .vnc-loading-content p {
      margin: 0;
    }
    .divider {
      width: 6px;
      background: #e0e0e0;
      cursor: col-resize;
      flex-shrink: 0;
      transition: background 0.15s;
    }
    .divider:hover { background: #2196F3; }
    .editor-panel {
      display: flex;
      flex-direction: column;
      overflow: hidden;
      background: #fafafa;
      min-width: 0;
    }
    .editor-panel.panel-busy {
      pointer-events: none;
      opacity: 0.78;
    }
    .field-list-section {
      flex: 1;
      overflow-y: auto;
      padding: 8px;
    }
    .field-detail-section {
      padding: 8px;
      max-height: 280px;
      overflow-y: auto;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      padding: 12px;
      background: white;
      border-top: 1px solid #e0e0e0;
    }
    .login-progress {
      display: flex;
      align-items: center;
      gap: 8px;
      color: #666;
    }
    .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 48px;
      color: #F44336;
    }
    .step-flags {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 6px 12px;
      border-bottom: 1px solid #e0e0e0;
      background: #fff8e1;
    }
    .bp-icon {
      font-size: 16px;
      height: 16px;
      width: 16px;
      vertical-align: middle;
      margin-right: 4px;
    }
    .split-view.editor-hidden .vnc-panel {
      flex-grow: 1 !important;
    }
    @media (max-width: 1279px) {
      .split-view {
        flex-direction: column;
        height: calc(100vh - 170px);
        min-height: 620px;
      }
      .vnc-panel {
        flex: 1 1 58%;
        min-height: 360px;
      }
      .divider {
        width: 100%;
        height: 6px;
        cursor: row-resize;
      }
      .editor-panel {
        flex: 1 1 42% !important;
      }
    }
    @media (max-width: 767px) {
      .split-view {
        min-height: 560px;
      }
      .vnc-panel {
        min-height: 320px;
      }
    }
  `]
})
export class VncFormEditorComponent implements OnInit, OnDestroy {
  @ViewChild(VncFieldDetailComponent) fieldDetail!: VncFieldDetailComponent;

  analysisId = input.required<string>();
  analysisResult = input<any>(null);
  resumeCorrections = input<UserCorrections | null>(null);
  requiresLogin = input<boolean>(false);
  targetUrl = input<string | null>(null);
  confirmed = output<FormDefinition[]>();
  cancelled = output<void>();

  private sanitizer = inject(DomSanitizer);
  private ws = inject(WebSocketService);
  private editorService = inject(VncEditorService);
  private subs: Subscription[] = [];
  private draftSave$ = new Subject<void>();
  private fillField$ = new Subject<{ fieldIndex: number; value: string }>();
  private _suppressValueSync = false;

  loading = signal(true);
  initError = signal<string | null>(null);
  vncUrl = signal<string | null>(null);
  splitPosition = signal(65);
  editorHidden = signal(false);
  currentMode = signal<EditorMode>('select');
  userSelectedMode = signal(false);
  steps = signal<EditingStep[]>([]);
  activeStepIndex = signal(0);
  selectedFieldIndex = signal(-1);
  confirming = signal(false);

  // Multi-phase login state
  currentPhase = signal<EditorPhase>('target');
  loginExecuting = signal(false);
  loginProgress = signal('');
  breakpointWaiting = signal(false);
  navigatingStep = signal(false);
  navigationMessage = signal('Loading next target page...');

  // Computed-like signals
  currentFields = signal<EditorField[]>([]);
  selectedField = signal<EditorField | null>(null);
  currentStepBreakpoint = signal(false);
  hasValidationErrors = signal(false);

  private isDragging = false;
  private boundMouseMove = this.onDrag.bind(this);
  private boundMouseUp = this.stopDrag.bind(this);
  private sessionExpired = false;
  private pendingNavigationRequestId: string | null = null;
  private pendingNavigationPreviousIndex: number | null = null;

  ngOnInit() {
    // Set initial phase based on login requirement
    if (this.requiresLogin()) {
      this.currentPhase.set('login');
    }

    // Listen for HighlightingReady via WebSocket
    const channelName = `private-analysis.${this.analysisId()}`;
    if (!this.ws['pusher']) this.ws.connect();
    const channel = this.ws['pusher'].subscribe(channelName);

    channel.bind('HighlightingReady', (data: HighlightingReadyEvent) => {
      this.loading.set(false);
      this.initError.set(null);
      this.vncUrl.set(data.vnc_url);

      // If resuming from a saved draft, use those corrections instead of fresh AI result
      const draft = this.resumeCorrections();
      if (draft?.steps?.length) {
        this.initializeFromDraft(draft);
        // Update highlights in VNC with draft fields
        const activeFields = draft.steps[0]?.fields || [];
        this.editorService.updateFields(this.analysisId(), activeFields).subscribe({
          error: (err) => this.handleSessionError(err)
        });
      } else {
        this.initializeFromResult(data.analysis_result, data.fields);
      }

      // Auto-set to 'add' mode on target phase so user can immediately start picking fields
      if (this.currentPhase() === 'target' && !this.userSelectedMode()) {
        this.onModeChanged('add', false);
      }
    });

    channel.bind('FieldSelected', (data: FieldSelectedEvent) => {
      this.selectedFieldIndex.set(data.index);
      this.updateSelectedField();
      // Read the current live value and sync into the panel
      this.editorService.readFieldValue(this.analysisId(), data.index).subscribe({
        next: (result) => {
          if (result?.value != null) {
            this.syncLiveValueToPanel(data.index, result.value);
          }
        },
      });
    });

    channel.bind('FieldAdded', (data: FieldAddedEvent) => {
      this.addFieldFromVnc(data);
    });

    channel.bind('FieldRemoved', (data: FieldRemovedEvent) => {
      this.removeFieldByIndex(data.index);
    });

    channel.bind('FieldValueChanged', (data: FieldValueChangedEvent) => {
      if (this._suppressValueSync) return;
      this.syncLiveValueToPanel(data.index, data.value);
    });

    // Login execution events
    channel.bind('LoginExecutionProgress', (data: LoginExecutionProgressEvent) => {
      this.loginProgress.set(data.message);
      this.breakpointWaiting.set(data.phase === 'human_breakpoint');
    });

    channel.bind('LoginExecutionComplete', (data: LoginExecutionCompleteEvent) => {
      this.loginExecuting.set(false);
      this.breakpointWaiting.set(false);
      if (data.success) {
        this.transitionToTargetPhase(data.target_result, data.target_fields || []);
      } else {
        this.loginProgress.set(`Login failed: ${data.error || 'Unknown error'}`);
        this.currentPhase.set('login');
      }
    });

    channel.bind('StepNavigationState', (data: StepNavigationStateEvent) => {
      this.handleStepNavigationEvent(data);
    });

    channel.bind('AnalysisCompleted', (data: any) => {
      // Interactive analyze bootstrap failed before VNC was ready.
      if (!this.vncUrl() && data?.error) {
        this.loading.set(false);
        this.initError.set(`Failed to initialize VNC session: ${data.error}`);
      }
    });

    this.subs.push(
      channel // keep reference for cleanup
    );

    // Debounced draft auto-save
    this.subs.push(
      this.draftSave$.pipe(debounceTime(2000)).subscribe(() => {
        this.saveDraft();
      })
    );

    // Debounced panel→VNC field fill
    this.subs.push(
      this.fillField$.pipe(debounceTime(300)).subscribe(({ fieldIndex, value }) => {
        this._suppressValueSync = true;
        this.editorService.fillField(this.analysisId(), fieldIndex, value).subscribe({
          complete: () => { setTimeout(() => this._suppressValueSync = false, 200); },
          error: () => { this._suppressValueSync = false; },
        });
      })
    );
  }

  ngOnDestroy() {
    const channelName = `private-analysis.${this.analysisId()}`;
    try {
      this.ws['pusher']?.unsubscribe(channelName);
    } catch {}
    this.subs.forEach(s => { if (s?.unsubscribe) s.unsubscribe(); });
    document.removeEventListener('mousemove', this.boundMouseMove);
    document.removeEventListener('mouseup', this.boundMouseUp);
  }

  safeVncUrl = computed(() => {
    const url = this.withVncDefaults(this.vncUrl() || '');
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  });

  // --- Initialization ---

  private initializeFromResult(result: any, fields: any[]) {
    const forms = result?.forms || [];
    const editingSteps: EditingStep[] = forms.map((form: any, i: number) => ({
      // Prefer per-form fields from analysis result; fallback to global fields for step 0.
      step_order: form.step_order ?? i,
      depends_on_step_order: form.depends_on_step_order ?? (
        i === 0
          ? null
          : (
              forms[0]?.form_type === 'login'
                ? (forms[0]?.step_order ?? 0)
                : (forms[i - 1]?.step_order ?? (i - 1))
            )
      ),
      page_url: form.page_url || '',
      form_type: form.form_type || 'target',
      form_selector: form.form_selector || '',
      submit_selector: form.submit_selector || '',
      human_breakpoint: form.human_breakpoint ?? false,
      fields: this.mapEditorFields(
        Array.isArray(form.fields) && form.fields.length > 0
          ? form.fields
          : (i === 0 ? fields : [])
      ),
    }));

    // If no forms at all, create a single step with all fields
    if (editingSteps.length === 0) {
      editingSteps.push({
        step_order: 0,
        depends_on_step_order: null,
        page_url: '',
        form_type: 'target',
        form_selector: '',
        submit_selector: '',
        human_breakpoint: false,
        fields: this.mapEditorFields(fields),
      });
    }

    this.steps.set(editingSteps);
    this.activeStepIndex.set(0);
    this.updateCurrentFields();
  }

  private initializeFromDraft(corrections: UserCorrections) {
    const editingSteps: EditingStep[] = corrections.steps.map(s => ({
      step_order: s.step_order,
      depends_on_step_order: s.depends_on_step_order ?? null,
      page_url: s.page_url,
      form_type: s.form_type,
      form_selector: s.form_selector,
      submit_selector: s.submit_selector,
      human_breakpoint: s.human_breakpoint ?? false,
      fields: (s.fields || []).map((f: any, i: number) => ({
        temp_id: f.temp_id || crypto.randomUUID(),
        field_name: f.field_name || '',
        field_type: f.field_type || 'text',
        field_selector: f.field_selector || '',
        field_purpose: f.field_purpose || 'other',
        preset_value: f.preset_value || '',
        is_sensitive: f.is_sensitive ?? false,
        is_required: f.is_required ?? false,
        is_file_upload: f.is_file_upload ?? false,
        options: f.options || null,
        sort_order: f.sort_order ?? i,
        original_selector: f.original_selector || f.field_selector || '',
      })),
    }));

    this.steps.set(editingSteps);
    this.activeStepIndex.set(0);
    this.updateCurrentFields();
  }

  // --- Mode ---

  onModeChanged(mode: EditorMode, markUserSelection: boolean = true) {
    if (markUserSelection) {
      this.userSelectedMode.set(true);
    }
    this.currentMode.set(mode);
    this.editorService.setMode(this.analysisId(), mode).subscribe({
      error: (err) => this.handleSessionError(err)
    });
  }

  // --- Field operations ---

  onFieldSelected(index: number) {
    if (this.navigatingStep()) {
      return;
    }
    this.selectedFieldIndex.set(index);
    this.updateSelectedField();
    this.editorService.focusField(this.analysisId(), index).subscribe();
  }

  onFieldChanged(updatedField: EditorField) {
    if (this.navigatingStep()) {
      return;
    }
    const stepIdx = this.activeStepIndex();
    const fieldIdx = this.selectedFieldIndex();
    const stepsClone = structuredClone(this.steps());
    if (stepsClone[stepIdx]?.fields[fieldIdx]) {
      const previousValue = stepsClone[stepIdx].fields[fieldIdx].preset_value;
      stepsClone[stepIdx].fields[fieldIdx] = updatedField;
      this.steps.set(stepsClone);
      this.updateCurrentFields();
      this.draftSave$.next();

      // Update highlights in VNC
      this.editorService.updateFields(this.analysisId(), stepsClone[stepIdx].fields).subscribe({
        error: (err) => this.handleSessionError(err)
      });

      // If preset_value changed, push to live page (debounced)
      if (updatedField.preset_value !== previousValue) {
        this.fillField$.next({ fieldIndex: fieldIdx, value: updatedField.preset_value });
      }
    }
  }

  onFieldsReordered(fields: EditorField[]) {
    if (this.navigatingStep()) {
      return;
    }
    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    stepsClone[stepIdx].fields = fields;
    this.steps.set(stepsClone);
    this.updateCurrentFields();
    this.draftSave$.next();
    this.editorService.updateFields(this.analysisId(), fields).subscribe({
      error: (err) => this.handleSessionError(err)
    });
  }

  onTestSelector(selector: string) {
    if (this.navigatingStep()) {
      return;
    }
    this.editorService.testSelector(this.analysisId(), selector).subscribe({
      next: (result) => {
        if (this.fieldDetail) {
          this.fieldDetail.setTestResult(result);
        }
      },
    });
  }

  // --- VNC callbacks ---

  private addFieldFromVnc(data: FieldAddedEvent) {
    const newField: EditorField = {
      temp_id: crypto.randomUUID(),
      field_name: data.name || '',
      field_type: data.type || 'text',
      field_selector: data.selector,
      field_purpose: data.purpose || 'other',
      preset_value: '',
      is_sensitive: false,
      is_required: false,
      is_file_upload: false,
      options: data.options || null,
      sort_order: this.currentFields().length,
      original_selector: data.selector,
    };

    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    stepsClone[stepIdx].fields.push(newField);

    // Auto-detect form_selector and submit_selector from the added field's parent form
    if (data.form_selector && !stepsClone[stepIdx].form_selector) {
      stepsClone[stepIdx].form_selector = data.form_selector;
    }
    if (data.submit_selector && !stepsClone[stepIdx].submit_selector) {
      stepsClone[stepIdx].submit_selector = data.submit_selector;
    }

    this.steps.set(stepsClone);
    this.updateCurrentFields();
    this.draftSave$.next();

    // Select the newly added field
    this.selectedFieldIndex.set(stepsClone[stepIdx].fields.length - 1);
    this.updateSelectedField();

    this.editorService.updateFields(this.analysisId(), stepsClone[stepIdx].fields).subscribe();
  }

  private removeFieldByIndex(index: number) {
    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    if (stepsClone[stepIdx]?.fields[index]) {
      stepsClone[stepIdx].fields.splice(index, 1);
      stepsClone[stepIdx].fields.forEach((f, i) => f.sort_order = i);
      this.steps.set(stepsClone);
      this.updateCurrentFields();

      if (this.selectedFieldIndex() === index) {
        this.selectedFieldIndex.set(-1);
        this.selectedField.set(null);
      } else if (this.selectedFieldIndex() > index) {
        this.selectedFieldIndex.update(i => i - 1);
        this.updateSelectedField();
      }

      this.draftSave$.next();
      this.editorService.updateFields(this.analysisId(), stepsClone[stepIdx].fields).subscribe({
        error: (err) => this.handleSessionError(err)
      });
    }
  }

  // --- Multi-step ---

  onStepChanged(index: number, onReady?: () => void) {
    const allSteps = this.steps();
    if (this.navigatingStep()) {
      return;
    }
    if (index < 0 || index >= allSteps.length) {
      return;
    }

    const previousIndex = this.activeStepIndex();
    if (index === previousIndex) {
      return;
    }

    this.setActiveStepState(index);
    const targetStep = allSteps[index];
    this.startNavigationWait(targetStep?.page_url);

    if (targetStep?.page_url) {
      const requestId = crypto.randomUUID();
      this.pendingNavigationRequestId = requestId;
      this.pendingNavigationPreviousIndex = previousIndex;

      this.editorService.navigateStep(this.analysisId(), index, targetStep.page_url, requestId).subscribe({
        next: () => {
          this.applyStepFieldsAfterNavigation(requestId, onReady);
        },
        error: (err) => {
          if (this.pendingNavigationRequestId !== requestId) {
            return;
          }
          const fallbackPrevious = this.pendingNavigationPreviousIndex;
          this.clearPendingNavigation();
          this.finishNavigationWait();
          this.handleSessionError(err);
          if (fallbackPrevious != null) {
            this.restoreStepAfterNavigationError(fallbackPrevious);
          }
        },
      });
      return;
    }

    this.applyStepFieldsAfterNavigation(undefined, onReady);
  }

  private setActiveStepState(index: number) {
    this.activeStepIndex.set(index);
    this.selectedFieldIndex.set(-1);
    this.selectedField.set(null);
    this.updateCurrentFields();
    this.currentStepBreakpoint.set(this.steps()[index]?.human_breakpoint ?? false);
  }

  private startNavigationWait(pageUrl?: string) {
    const message = pageUrl
      ? `Navigating to ${pageUrl}...`
      : 'Preparing step...';
    this.navigationMessage.set(message);
    this.navigatingStep.set(true);
  }

  private finishNavigationWait() {
    this.navigatingStep.set(false);
    this.navigationMessage.set('Loading next target page...');
  }

  private clearPendingNavigation() {
    this.pendingNavigationRequestId = null;
    this.pendingNavigationPreviousIndex = null;
  }

  private applyStepFieldsAfterNavigation(requestId?: string, onReady?: () => void) {
    if (requestId && this.pendingNavigationRequestId && this.pendingNavigationRequestId !== requestId) {
      return;
    }
    const step = this.steps()[this.activeStepIndex()];
    this.editorService.updateFields(this.analysisId(), step?.fields || []).subscribe({
      next: () => {
        this.clearPendingNavigation();
        this.finishNavigationWait();
        onReady?.();
      },
      error: (err) => {
        this.clearPendingNavigation();
        this.finishNavigationWait();
        this.handleSessionError(err);
      },
    });
  }

  private handleStepNavigationEvent(data: StepNavigationStateEvent) {
    if (!this.pendingNavigationRequestId) {
      return;
    }
    if (data.request_id && data.request_id !== this.pendingNavigationRequestId) {
      return;
    }

    if (data.status === 'started') {
      this.navigationMessage.set(data.message || `Navigating to ${data.url}...`);
      this.navigatingStep.set(true);
      return;
    }

    if (data.status === 'completed') {
      this.applyStepFieldsAfterNavigation(data.request_id);
      return;
    }

    if (data.status === 'failed') {
      const previousIndex = this.pendingNavigationPreviousIndex;
      this.clearPendingNavigation();
      this.finishNavigationWait();
      if (previousIndex != null) {
        this.restoreStepAfterNavigationError(previousIndex);
      }
      return;
    }
  }

  private restoreStepAfterNavigationError(index: number) {
    if (index < 0 || index >= this.steps().length) {
      return;
    }
    this.setActiveStepState(index);
    const previousStep = this.steps()[index];
    this.editorService.updateFields(this.analysisId(), previousStep?.fields || []).subscribe({
      error: (err) => this.handleSessionError(err),
    });
  }

  onBreakpointToggle(value: boolean) {
    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    if (stepsClone[stepIdx]) {
      stepsClone[stepIdx].human_breakpoint = value;
      this.steps.set(stepsClone);
      this.currentStepBreakpoint.set(value);
      this.draftSave$.next();
    }
  }

  onAddTargetStep() {
    if (this.currentPhase() !== 'target' || this.navigatingStep()) {
      return;
    }

    this.blurVncIfFocused();
    const currentStep = this.steps()[this.activeStepIndex()];
    const suggestedUrl = (currentStep?.page_url || this.targetUrl() || '').trim();
    const enteredUrl = window.prompt('Target page URL for the new step', suggestedUrl);
    if (enteredUrl === null) {
      return;
    }

    const pageUrl = enteredUrl.trim() || suggestedUrl;
    if (!pageUrl) {
      return;
    }

    const stepsClone = structuredClone(this.steps());
    const nextStepOrder = stepsClone.reduce((max, step) => Math.max(max, step.step_order), -1) + 1;
    const loginStep = stepsClone.find(step => step.form_type === 'login');
    const fallbackDependency = stepsClone.length > 0 ? stepsClone[stepsClone.length - 1].step_order : null;

    const newTargetStep: EditingStep = {
      step_order: nextStepOrder,
      depends_on_step_order: loginStep?.step_order ?? fallbackDependency,
      page_url: pageUrl,
      form_type: 'target',
      form_selector: '',
      submit_selector: '',
      human_breakpoint: false,
      fields: [],
    };

    stepsClone.push(newTargetStep);
    this.steps.set(stepsClone);
    this.draftSave$.next();

    const autoSetAddMode = !this.userSelectedMode();
    this.onStepChanged(stepsClone.length - 1, () => {
      if (autoSetAddMode) {
        this.onModeChanged('add', false);
      }
    });
  }

  // --- Login phase ---

  onConfirmLoginAndProceed() {
    const step = this.steps()[this.activeStepIndex()];
    if (!step) return;

    this.blurVncIfFocused();

    // Collect login fields with their preset values
    const loginFields = step.fields.map(f => ({
      field_selector: f.field_selector,
      value: f.preset_value || '',
      field_type: f.field_type,
      is_sensitive: f.is_sensitive,
    }));

    const targetUrl = this.targetUrl() || '';
    const submitSelector = step.submit_selector || '';

    // Transition to executing phase
    this.currentPhase.set('login-executing');
    this.loginExecuting.set(true);
    this.loginProgress.set('Filling login form...');

    // Call backend to execute login in the existing VNC session
    this.editorService.executeLogin(this.analysisId(), loginFields, targetUrl, submitSelector, {
      human_breakpoint: step.human_breakpoint,
    }).subscribe({
      error: (err) => {
        this.loginExecuting.set(false);
        this.loginProgress.set(`Failed: ${err.error?.message || 'Unknown error'}`);
        this.currentPhase.set('login');
      },
    });
  }

  onResumeLogin() {
    this.blurVncIfFocused();
    this.breakpointWaiting.set(false);
    this.loginProgress.set('Resuming after manual intervention...');
    this.editorService.resumeLogin(this.analysisId()).subscribe({
      error: () => {
        this.loginProgress.set('Failed to resume. Try again.');
        this.breakpointWaiting.set(true);
      },
    });
  }

  private transitionToTargetPhase(targetResult: any, targetFields: any[]) {
    const stepsClone = structuredClone(this.steps());
    const rootDependency = stepsClone[0]?.step_order ?? null;

    // Build target step(s) from result
    const targetForms = targetResult?.forms || [];
    const targetSteps: EditingStep[] = targetForms.length > 0
      ? targetForms.map((form: any, i: number) => ({
          step_order: stepsClone.length + i,
          depends_on_step_order: rootDependency,
          page_url: form.page_url || this.targetUrl() || '',
          form_type: form.form_type || 'target',
          form_selector: form.form_selector || '',
          submit_selector: form.submit_selector || '',
          human_breakpoint: form.human_breakpoint ?? false,
          fields: this.mapEditorFields(
            Array.isArray(form.fields) && form.fields.length > 0
              ? form.fields
              : (i === 0 ? targetFields : [])
          ),
        }))
      : [{
          step_order: stepsClone.length,
          depends_on_step_order: rootDependency,
          page_url: this.targetUrl() || '',
          form_type: 'target' as const,
          form_selector: '',
          submit_selector: '',
          human_breakpoint: false,
          fields: this.mapEditorFields(targetFields),
        }];

    // Append target steps after login
    const firstNewTargetIndex = stepsClone.length; // Index of the first newly added target
    stepsClone.push(...targetSteps);
    this.steps.set(stepsClone);

    // Switch phase
    this.currentPhase.set('target');
    this.loginProgress.set('');

    // Navigate to the first newly added target step
    const targetStepIndex = firstNewTargetIndex;
    if (targetStepIndex < stepsClone.length) {
      this.setActiveStepState(targetStepIndex);

      // Auto-set to 'add' mode so user can immediately start picking fields
      if (!this.userSelectedMode()) {
        this.onModeChanged('add', false);
      }

      const activeStep = stepsClone[targetStepIndex];
      this.editorService.updateFields(this.analysisId(), activeStep?.fields || []).subscribe({
        error: (err) => this.handleSessionError(err),
      });
    }
  }

  // --- Confirm / Cancel ---

  onConfirmAll() {
    if (this.navigatingStep() || this.confirming()) {
      return;
    }

    this.blurVncIfFocused();
    this.confirming.set(true);
    const corrections = this.buildCorrections();

    this.editorService.confirmAll(this.analysisId(), corrections).subscribe({
      next: (result) => {
        this.confirming.set(false);
        // Build FormDefinition[] for wizard
        const formDefs = this.buildFormDefinitions();
        this.confirmed.emit(formDefs);
      },
      error: (err) => {
        this.confirming.set(false);
        console.error('Confirm failed:', err);
      },
    });
  }

  onCancel() {
    if (this.navigatingStep()) {
      return;
    }

    this.blurVncIfFocused();
    this.editorService.cancelEditing(this.analysisId()).subscribe({
      next: () => this.cancelled.emit(),
      error: () => this.cancelled.emit(),
    });
  }

  // --- Draft save ---

  private saveDraft() {
    const corrections = this.buildCorrections();
    this.editorService.saveDraft(this.analysisId(), corrections).subscribe();
  }

  // --- Validation ---

  private validateAllFields() {
    const allSteps = this.steps();
    let hasErrors = false;

    for (const step of allSteps) {
      // Check if step has fields but no submit selector
      if (step.fields.length > 0 && !step.submit_selector?.trim()) {
        hasErrors = true;
        break;
      }

      for (const field of step.fields) {
        // Name is always required
        if (!field.field_name?.trim()) {
          hasErrors = true;
          break;
        }

        // Selector is always required
        if (!field.field_selector?.trim()) {
          hasErrors = true;
          break;
        }

        // For required fields (not submit/button), value should be present
        if (field.field_type !== 'submit' && field.field_type !== 'button' &&
            field.is_required && !field.preset_value?.trim()) {
          hasErrors = true;
          break;
        }
      }
      if (hasErrors) break;
    }

    this.hasValidationErrors.set(hasErrors);
  }

  // --- Helpers ---

  /**
   * Blur the VNC iframe if it has focus to prevent focus-related click issues.
   * This ensures buttons outside the iframe respond to the first click.
   */
  private blurVncIfFocused() {
    const iframe = document.querySelector('.vnc-iframe') as HTMLIFrameElement;
    if (iframe && document.activeElement === iframe) {
      iframe.blur();
    }
  }

  private handleSessionError(err: any) {
    if (err?.status === 409) {
      return;
    }
    if (err.status === 404 && !this.sessionExpired) {
      this.sessionExpired = true;
      alert('VNC session expired or lost. The editor will close.');
      this.cancelled.emit();
    }
  }

  private updateCurrentFields() {
    const step = this.steps()[this.activeStepIndex()];
    this.currentFields.set(step?.fields || []);
    this.currentStepBreakpoint.set(step?.human_breakpoint ?? false);
    this.validateAllFields();
  }

  private updateSelectedField() {
    const fields = this.currentFields();
    const idx = this.selectedFieldIndex();
    this.selectedField.set(idx >= 0 && idx < fields.length ? fields[idx] : null);
  }

  private syncLiveValueToPanel(fieldIndex: number, value: string) {
    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    const field = stepsClone[stepIdx]?.fields[fieldIndex];
    if (!field || field.preset_value === value) return;

    field.preset_value = value;
    this.steps.set(stepsClone);
    this.updateCurrentFields();

    // Update selected field if it's the one that changed
    if (this.selectedFieldIndex() === fieldIndex) {
      this.updateSelectedField();
    }

    this.draftSave$.next();
  }

  private buildCorrections(): UserCorrections {
    return {
      version: 1,
      steps: this.steps().map(s => ({
        ...s,
        fields: s.fields.map(f => ({ ...f })),
      })),
    };
  }

  // --- Divider drag ---

  startDrag(event: MouseEvent) {
    if (window.innerWidth < 1280 || this.editorHidden()) return;
    event.preventDefault();
    this.isDragging = true;
    document.addEventListener('mousemove', this.boundMouseMove);
    document.addEventListener('mouseup', this.boundMouseUp);
  }

  private onDrag(event: MouseEvent) {
    if (!this.isDragging) return;
    const container = (event.target as HTMLElement).closest('.split-view') ||
                      document.querySelector('.split-view');
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const pct = ((event.clientX - rect.left) / rect.width) * 100;
    this.splitPosition.set(Math.max(30, Math.min(85, pct)));
  }

  private stopDrag() {
    this.isDragging = false;
    document.removeEventListener('mousemove', this.boundMouseMove);
    document.removeEventListener('mouseup', this.boundMouseUp);
  }

  toggleEditorHidden() {
    this.editorHidden.update((v) => !v);
  }

  resetSplit() {
    this.splitPosition.set(65);
    this.editorHidden.set(false);
  }

  private withVncDefaults(url: string): string {
    if (!url) return '';

    const ensure = (key: string, value: string) => {
      if (!new RegExp(`[?&]${key}=`).test(url)) {
        url += (url.includes('?') ? '&' : '?') + `${key}=${value}`;
      }
    };

    ensure('resize', 'scale');
    ensure('autoconnect', '1');
    ensure('reconnect', '1');
    return url;
  }

  private buildFormDefinitions(): FormDefinition[] {
    return this.steps().map((step, i) => ({
      id: `vnc-step-${i}`,
      task_id: '',
      step_order: step.step_order,
      depends_on_step_order: step.depends_on_step_order ?? null,
      page_url: step.page_url,
      form_type: step.form_type,
      form_selector: step.form_selector,
      submit_selector: step.submit_selector,
      human_breakpoint: step.human_breakpoint,
      fields: step.fields.map((f, fi) => ({
        id: f.temp_id,
        form_definition_id: `vnc-step-${i}`,
        field_name: f.field_name,
        field_type: f.field_type,
        field_selector: f.field_selector,
        field_purpose: f.field_purpose,
        preset_value: f.preset_value || null,
        is_sensitive: f.is_sensitive,
        is_file_upload: f.is_file_upload,
        is_required: f.is_required,
        options: f.options,
        sort_order: fi,
      })),
      created_at: '',
      updated_at: '',
    }));
  }

  private mapEditorFields(sourceFields: any[]): EditorField[] {
    return (sourceFields || []).map((f: any, i: number) => ({
      temp_id: crypto.randomUUID(),
      field_name: f.field_name || f.name || '',
      field_type: f.field_type || f.type || 'text',
      field_selector: f.field_selector || f.selector || '',
      field_purpose: f.field_purpose || f.purpose || 'other',
      preset_value: f.preset_value || '',
      is_sensitive: f.is_sensitive ?? false,
      is_required: f.required ?? f.is_required ?? false,
      is_file_upload: f.is_file_upload ?? false,
      options: f.options || null,
      sort_order: i,
      original_selector: f.original_selector || f.field_selector || f.selector || '',
    }));
  }

}
