import { Component, inject, input, output, signal, computed, OnInit, OnDestroy, ViewChild } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatDividerModule } from '@angular/material/divider';
import { Subscription, Subject, debounceTime } from 'rxjs';
import { WebSocketService } from '../../../core/services/websocket.service';
import { VncEditorService } from '../../../core/services/vnc-editor.service';
import { FormDefinition } from '../../../core/models/task.model';
import {
  EditorMode, EditorField, EditingStep, UserCorrections,
  HighlightingReadyEvent, FieldSelectedEvent, FieldAddedEvent, FieldRemovedEvent,
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
      <div class="split-view">
        <!-- Mode toolbar (vertical, left edge) -->
        <app-vnc-mode-toolbar
          [mode]="currentMode()"
          (modeChanged)="onModeChanged($event)"
        />

        <!-- VNC Panel -->
        <div class="vnc-panel" [style.flex-grow]="splitPosition()">
          <iframe
            [src]="safeVncUrl()"
            class="vnc-iframe"
            frameborder="0"
            allow="clipboard-read; clipboard-write">
          </iframe>
        </div>

        <!-- Divider (draggable) -->
        <div class="divider" (mousedown)="startDrag($event)"></div>

        <!-- Editor Panel -->
        <div class="editor-panel" [style.flex-grow]="100 - splitPosition()">
          <!-- Step tabs for multi-step -->
          <app-vnc-step-tabs
            [steps]="steps()"
            [activeStep]="activeStepIndex()"
            (stepChanged)="onStepChanged($event)"
          />

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

          <!-- Actions -->
          <div class="actions">
            <button mat-raised-button color="primary" (click)="onConfirmAll()" [disabled]="confirming()">
              @if (confirming()) {
                <mat-spinner diameter="18"></mat-spinner>
              } @else {
                <mat-icon>check</mat-icon> Confirm All
              }
            </button>
            <button mat-stroked-button (click)="onCancel()">
              <mat-icon>close</mat-icon> Cancel
            </button>
          </div>
        </div>
      </div>
    } @else {
      <div class="error-state">
        <mat-icon>error</mat-icon>
        <p>Failed to initialize VNC session.</p>
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
      height: calc(100vh - 200px);
      min-height: 500px;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      overflow: hidden;
    }
    .vnc-panel {
      position: relative;
      overflow: hidden;
      min-width: 0;
    }
    .vnc-iframe {
      width: 100%;
      height: 100%;
      border: none;
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
      padding: 12px;
      background: white;
      border-top: 1px solid #e0e0e0;
    }
    .error-state {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 48px;
      color: #F44336;
    }
  `]
})
export class VncFormEditorComponent implements OnInit, OnDestroy {
  @ViewChild(VncFieldDetailComponent) fieldDetail!: VncFieldDetailComponent;

  analysisId = input.required<string>();
  analysisResult = input<any>(null);
  resumeCorrections = input<UserCorrections | null>(null);

  confirmed = output<FormDefinition[]>();
  cancelled = output<void>();

  private sanitizer = inject(DomSanitizer);
  private ws = inject(WebSocketService);
  private editorService = inject(VncEditorService);
  private subs: Subscription[] = [];
  private draftSave$ = new Subject<void>();

  loading = signal(true);
  vncUrl = signal<string | null>(null);
  splitPosition = signal(65);
  currentMode = signal<EditorMode>('view');
  steps = signal<EditingStep[]>([]);
  activeStepIndex = signal(0);
  selectedFieldIndex = signal(-1);
  confirming = signal(false);

  // Computed-like signals
  currentFields = signal<EditorField[]>([]);
  selectedField = signal<EditorField | null>(null);

  private isDragging = false;
  private boundMouseMove = this.onDrag.bind(this);
  private boundMouseUp = this.stopDrag.bind(this);

  ngOnInit() {
    // Listen for HighlightingReady via WebSocket
    const channelName = `private-analysis.${this.analysisId()}`;
    if (!this.ws['pusher']) this.ws.connect();
    const channel = this.ws['pusher'].subscribe(channelName);

    channel.bind('HighlightingReady', (data: HighlightingReadyEvent) => {
      this.loading.set(false);
      this.vncUrl.set(data.vnc_url);

      // If resuming from a saved draft, use those corrections instead of fresh AI result
      const draft = this.resumeCorrections();
      if (draft?.steps?.length) {
        this.initializeFromDraft(draft);
        // Update highlights in VNC with draft fields
        const activeFields = draft.steps[0]?.fields || [];
        this.editorService.updateFields(this.analysisId(), activeFields).subscribe();
      } else {
        this.initializeFromResult(data.analysis_result, data.fields);
      }
    });

    channel.bind('FieldSelected', (data: FieldSelectedEvent) => {
      this.selectedFieldIndex.set(data.index);
      this.updateSelectedField();
    });

    channel.bind('FieldAdded', (data: FieldAddedEvent) => {
      this.addFieldFromVnc(data);
    });

    channel.bind('FieldRemoved', (data: FieldRemovedEvent) => {
      this.removeFieldByIndex(data.index);
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
    const url = this.vncUrl() || '';
    return this.sanitizer.bypassSecurityTrustResourceUrl(url);
  });

  // --- Initialization ---

  private initializeFromResult(result: any, fields: any[]) {
    const editorFields: EditorField[] = fields.map((f: any, i: number) => ({
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
      status: 'ai' as const,
      source: 'ai' as const,
      original_selector: f.field_selector || f.selector || '',
    }));

    const forms = result?.forms || [];
    const editingSteps: EditingStep[] = forms.map((form: any, i: number) => ({
      step_order: i,
      page_url: form.page_url || '',
      form_type: form.form_type || 'target',
      form_selector: form.form_selector || '',
      submit_selector: form.submit_selector || '',
      ai_confidence: form.confidence ?? form.ai_confidence ?? null,
      captcha_detected: form.captcha_detected ?? false,
      two_factor_expected: form.two_factor_expected ?? false,
      status: 'pending' as const,
      fields: editorFields.filter((_: any, fi: number) => {
        // Assign fields to the first form for now (simple case)
        return forms.length === 1 || i === 0;
      }),
    }));

    // If no forms at all, create a single step with all fields
    if (editingSteps.length === 0) {
      editingSteps.push({
        step_order: 0,
        page_url: '',
        form_type: 'target',
        form_selector: '',
        submit_selector: '',
        ai_confidence: null,
        captcha_detected: false,
        two_factor_expected: false,
        status: 'pending',
        fields: editorFields,
      });
    }

    this.steps.set(editingSteps);
    this.activeStepIndex.set(0);
    this.updateCurrentFields();
  }

  private initializeFromDraft(corrections: UserCorrections) {
    const editingSteps: EditingStep[] = corrections.steps.map(s => ({
      step_order: s.step_order,
      page_url: s.page_url,
      form_type: s.form_type,
      form_selector: s.form_selector,
      submit_selector: s.submit_selector,
      ai_confidence: s.ai_confidence ?? null,
      captcha_detected: s.captcha_detected ?? false,
      two_factor_expected: s.two_factor_expected ?? false,
      status: s.status || 'pending',
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
        status: f.status || 'ai',
        source: f.source || 'ai',
        original_selector: f.original_selector || f.field_selector || '',
      })),
    }));

    this.steps.set(editingSteps);
    this.activeStepIndex.set(0);
    this.updateCurrentFields();
  }

  // --- Mode ---

  onModeChanged(mode: EditorMode) {
    this.currentMode.set(mode);
    this.editorService.setMode(this.analysisId(), mode).subscribe();
  }

  // --- Field operations ---

  onFieldSelected(index: number) {
    this.selectedFieldIndex.set(index);
    this.updateSelectedField();
    this.editorService.focusField(this.analysisId(), index).subscribe();
  }

  onFieldChanged(updatedField: EditorField) {
    const stepIdx = this.activeStepIndex();
    const fieldIdx = this.selectedFieldIndex();
    const stepsClone = structuredClone(this.steps());
    if (stepsClone[stepIdx]?.fields[fieldIdx]) {
      stepsClone[stepIdx].fields[fieldIdx] = updatedField;
      this.steps.set(stepsClone);
      this.updateCurrentFields();
      this.draftSave$.next();

      // Update highlights in VNC
      this.editorService.updateFields(this.analysisId(), stepsClone[stepIdx].fields).subscribe();
    }
  }

  onFieldsReordered(fields: EditorField[]) {
    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    stepsClone[stepIdx].fields = fields;
    this.steps.set(stepsClone);
    this.updateCurrentFields();
    this.draftSave$.next();
    this.editorService.updateFields(this.analysisId(), fields).subscribe();
  }

  onTestSelector(selector: string) {
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
      options: null,
      sort_order: this.currentFields().length,
      status: 'added',
      source: 'user',
      original_selector: data.selector,
    };

    const stepIdx = this.activeStepIndex();
    const stepsClone = structuredClone(this.steps());
    stepsClone[stepIdx].fields.push(newField);
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
      this.editorService.updateFields(this.analysisId(), stepsClone[stepIdx].fields).subscribe();
    }
  }

  // --- Multi-step ---

  onStepChanged(index: number) {
    this.activeStepIndex.set(index);
    this.selectedFieldIndex.set(-1);
    this.selectedField.set(null);
    this.updateCurrentFields();

    const step = this.steps()[index];
    if (step?.page_url) {
      this.editorService.navigateStep(this.analysisId(), index, step.page_url).subscribe();
    }
  }

  // --- Confirm / Cancel ---

  onConfirmAll() {
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

  // --- Helpers ---

  private updateCurrentFields() {
    const step = this.steps()[this.activeStepIndex()];
    this.currentFields.set(step?.fields || []);
  }

  private updateSelectedField() {
    const fields = this.currentFields();
    const idx = this.selectedFieldIndex();
    this.selectedField.set(idx >= 0 && idx < fields.length ? fields[idx] : null);
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

  private buildFormDefinitions(): FormDefinition[] {
    return this.steps().map((step, i) => ({
      id: `vnc-step-${i}`,
      task_id: '',
      step_order: step.step_order,
      page_url: step.page_url,
      form_type: step.form_type,
      form_selector: step.form_selector,
      submit_selector: step.submit_selector,
      ai_confidence: step.ai_confidence,
      captcha_detected: step.captcha_detected,
      two_factor_expected: step.two_factor_expected,
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

}
