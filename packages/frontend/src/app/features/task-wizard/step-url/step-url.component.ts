import { Component, inject, input, output, signal, OnDestroy, ViewChild } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators, FormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { MatListModule } from '@angular/material/list';
import { MatTabsModule, MatTabGroup } from '@angular/material/tabs';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { Subscription } from 'rxjs';
import { TaskService } from '../../../core/services/task.service';
import { NotificationService } from '../../../core/services/notification.service';
import { WebSocketService, AnalysisVncEvent } from '../../../core/services/websocket.service';
import { FormDefinition } from '../../../core/models/task.model';
import { AiThinkingComponent } from '../../../shared/components/ai-thinking.component';
import { VncViewerAnalysisComponent } from '../../../shared/components/vnc-viewer-analysis.component';

export interface LoginConfig {
  requires_login: boolean;
  login_url: string | null;
  login_every_time: boolean;
}

@Component({
  selector: 'app-step-url',
  standalone: true,
  imports: [
    TitleCasePipe,
    ReactiveFormsModule,
    FormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatCardModule,
    MatListModule,
    MatTabsModule,
    MatSlideToggleModule,
    MatCheckboxModule,
    AiThinkingComponent,
    VncViewerAnalysisComponent,
  ],
  template: `
    <div class="step-url">
      <h2>Step 1: Target URL</h2>
      <p>Enter the URL of the form you want to automate. FormBot will analyze the page and detect forms.</p>

      <!-- Login toggle -->
      <div class="login-toggle mb-2">
        <mat-slide-toggle
          [checked]="requiresLogin()"
          (change)="onLoginToggle($event.checked)"
          color="primary">
          This site requires login
        </mat-slide-toggle>
      </div>

      @if (requiresLogin()) {
        <mat-tab-group [selectedIndex]="selectedTab()" (selectedIndexChange)="selectedTab.set($event)" #tabGroup>
          <!-- Tab 1: Login Setup -->
          <mat-tab label="Login Setup">
            <div class="tab-content">
              <div class="flex gap-2 items-center mt-2">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Login Page URL</mat-label>
                  <input matInput [formControl]="loginUrlControl" placeholder="https://example.com/login">
                  @if (loginUrlControl.hasError('required')) {
                    <mat-error>Login URL is required</mat-error>
                  }
                  @if (loginUrlControl.hasError('pattern')) {
                    <mat-error>Must be a valid URL</mat-error>
                  }
                </mat-form-field>

                <button mat-raised-button color="primary"
                  (click)="analyzeLoginPage()"
                  [disabled]="analyzingLogin() || loginUrlControl.invalid">
                  @if (analyzingLogin()) {
                    <mat-spinner diameter="20"></mat-spinner>
                    Analyzing...
                  } @else {
                    <mat-icon>search</mat-icon> Analyze Login Page
                  }
                </button>
              </div>

              <!-- AI Thinking for login analysis -->
              @if (loginAnalysisId() && analyzingLogin()) {
                <app-ai-thinking [analysisId]="loginAnalysisId()!" />
              }

              <!-- Login form result -->
              @if (loginFormResult()) {
                <mat-card class="mt-2">
                  <mat-card-header>
                    <mat-icon matCardAvatar>lock</mat-icon>
                    <mat-card-title>Login Form Detected</mat-card-title>
                    <mat-card-subtitle>
                      {{ loginFormResult()!.fields?.length || 0 }} fields
                      @if (loginFormResult()!.captcha_detected) {
                        | CAPTCHA detected
                      }
                    </mat-card-subtitle>
                  </mat-card-header>
                  <mat-card-content>
                    <div class="login-fields mt-1">
                      @for (field of loginFormResult()!.fields || []; track $index) {
                        <mat-form-field appearance="outline" class="full-width mb-1">
                          <mat-label>{{ field.field_name }} ({{ field.field_purpose || field.field_type }})</mat-label>
                          <input matInput
                            [(ngModel)]="field.preset_value"
                            [type]="field.field_type === 'password' || field.field_purpose === 'password' ? 'password' : 'text'"
                            [placeholder]="field.field_purpose || ''">
                        </mat-form-field>
                      }
                    </div>

                    @if (loginFormResult()!.captcha_detected) {
                      <div class="captcha-notice mt-1">
                        <mat-icon color="warn">warning</mat-icon>
                        <span>CAPTCHA detected - VNC viewer will open during login for manual solving</span>
                      </div>
                    }

                    <div class="login-options mt-2">
                      <mat-slide-toggle
                        [checked]="!loginEveryTime()"
                        (change)="onLoginEveryTimeToggle(!$event.checked)"
                        color="primary">
                        Reuse session (skip login if cookies are valid)
                      </mat-slide-toggle>
                    </div>
                  </mat-card-content>
                </mat-card>
              }
            </div>
          </mat-tab>

          <!-- Tab 2: Target URL Analysis -->
          <mat-tab label="Target URL Analysis">
            <div class="tab-content">
              <div class="flex gap-2 items-center mt-2">
                <mat-form-field appearance="outline" class="full-width">
                  <mat-label>Target URL</mat-label>
                  <input matInput [formControl]="urlControl" placeholder="https://example.com/form">
                  @if (urlControl.hasError('required')) {
                    <mat-error>URL is required</mat-error>
                  }
                  @if (urlControl.hasError('pattern')) {
                    <mat-error>Must be a valid URL</mat-error>
                  }
                </mat-form-field>

                <button mat-raised-button color="primary"
                  (click)="analyzeLoginAndTarget()"
                  [disabled]="analyzing() || urlControl.invalid || !loginFormResult()">
                  @if (analyzing()) {
                    <mat-spinner diameter="20"></mat-spinner>
                    Analyzing...
                  } @else {
                    <mat-icon>login</mat-icon> Login & Analyze Target
                  }
                </button>
              </div>

              @if (!loginFormResult()) {
                <p class="hint mt-1">Configure the login form in the "Login Setup" tab first.</p>
              }

              <!-- AI Thinking Panel -->
              @if (currentAnalysisId() && analyzing()) {
                <app-ai-thinking [analysisId]="currentAnalysisId()!" />
              }

              <!-- VNC Viewer for CAPTCHA/2FA during analysis -->
              @if (analysisVncEvent()) {
                <app-vnc-viewer-analysis
                  [vncUrl]="analysisVncEvent()!.vnc_url"
                  [analysisId]="analysisVncEvent()!.analysis_id"
                  [sessionId]="analysisVncEvent()!.vnc_session_id"
                  [reason]="analysisVncEvent()!.reason"
                  (resumed)="onVncResumed()"
                />
              }

              @if (analysisResult()) {
                <mat-card class="mt-2">
                  <mat-card-header>
                    <mat-card-title>Analysis Results</mat-card-title>
                    <mat-card-subtitle>{{ analysisResult()!.forms?.length || 0 }} form(s) detected on target page</mat-card-subtitle>
                  </mat-card-header>
                  <mat-card-content>
                    @if (analysisResult()!.forms?.length) {
                      <mat-list>
                        @for (form of analysisResult()!.forms; track $index) {
                          <mat-list-item>
                            <mat-icon matListItemIcon>description</mat-icon>
                            <span matListItemTitle>{{ form.form_type | titlecase }} Form</span>
                            <span matListItemLine>
                              {{ form.fields?.length || 0 }} fields
                              @if (form.ai_confidence != null) {
                                | Confidence: {{ (form.ai_confidence * 100).toFixed(0) }}%
                              }
                              @if (form.captcha_detected) {
                                | CAPTCHA detected
                              }
                            </span>
                          </mat-list-item>
                        }
                      </mat-list>
                    } @else {
                      <p>No forms were detected on the target page.</p>
                    }
                  </mat-card-content>
                </mat-card>
              }

              @if (pages().length > 0) {
                <div class="mt-2">
                  <h3>Multi-Page Flow</h3>
                  @for (page of pages(); track $index) {
                    <mat-card class="mb-1">
                      <mat-card-content>
                        <div class="flex items-center justify-between">
                          <span>Page {{ $index + 1 }}: {{ page.url }}</span>
                          <span>{{ page.forms?.length || 0 }} form(s)</span>
                        </div>
                      </mat-card-content>
                    </mat-card>
                  }
                </div>
              }

              @if (analysisResult()) {
                <div class="mt-2 flex gap-2">
                  <button mat-stroked-button color="accent" (click)="addPage()" [disabled]="analyzing()">
                    <mat-icon>add</mat-icon> Add Another Page
                  </button>
                </div>
              }
            </div>
          </mat-tab>
        </mat-tab-group>
      } @else {
        <!-- Standard flow (no login required) -->
        <div class="flex gap-2 items-center">
          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Target URL</mat-label>
            <input matInput [formControl]="urlControl" placeholder="https://example.com/form">
            @if (urlControl.hasError('required')) {
              <mat-error>URL is required</mat-error>
            }
            @if (urlControl.hasError('pattern')) {
              <mat-error>Must be a valid URL</mat-error>
            }
          </mat-form-field>

          <button mat-raised-button color="primary" (click)="analyze()" [disabled]="analyzing() || urlControl.invalid">
            @if (analyzing()) {
              <mat-spinner diameter="20"></mat-spinner>
              Analyzing...
            } @else {
              <mat-icon>search</mat-icon> Analyze
            }
          </button>
        </div>

        <!-- AI Thinking Panel -->
        @if (currentAnalysisId() && analyzing()) {
          <app-ai-thinking [analysisId]="currentAnalysisId()!" />
        }

        @if (analysisResult()) {
          <mat-card class="mt-2">
            <mat-card-header>
              <mat-card-title>Analysis Results</mat-card-title>
              <mat-card-subtitle>{{ analysisResult()!.forms?.length || 0 }} form(s) detected</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              @if (analysisResult()!.forms?.length) {
                <mat-list>
                  @for (form of analysisResult()!.forms; track $index) {
                    <mat-list-item>
                      <mat-icon matListItemIcon>description</mat-icon>
                      <span matListItemTitle>{{ form.form_type | titlecase }} Form</span>
                      <span matListItemLine>
                        {{ form.fields?.length || 0 }} fields
                        @if (form.ai_confidence != null) {
                          | Confidence: {{ (form.ai_confidence * 100).toFixed(0) }}%
                        }
                        @if (form.captcha_detected) {
                          | CAPTCHA detected
                        }
                        @if (analysisResult()!.two_factor_detected) {
                          | 2FA detected
                        }
                      </span>
                    </mat-list-item>
                  }
                </mat-list>
              } @else {
                <p>No forms were detected on this page. Try a different URL or check that the page loads correctly.</p>
              }
            </mat-card-content>
          </mat-card>
        }

        @if (pages().length > 0) {
          <div class="mt-2">
            <h3>Multi-Page Flow</h3>
            @for (page of pages(); track $index) {
              <mat-card class="mb-1">
                <mat-card-content>
                  <div class="flex items-center justify-between">
                    <span>Page {{ $index + 1 }}: {{ page.url }}</span>
                    <span>{{ page.forms?.length || 0 }} form(s)</span>
                  </div>
                </mat-card-content>
              </mat-card>
            }
          </div>
        }

        @if (analysisResult()) {
          <div class="mt-2 flex gap-2">
            <button mat-stroked-button color="accent" (click)="addPage()" [disabled]="analyzing()">
              <mat-icon>add</mat-icon> Add Another Page
            </button>
          </div>
        }
      }
    </div>
  `,
  styles: [`
    .step-url { max-width: 800px; }
    .tab-content { padding: 8px 0; }
    .login-toggle { padding: 8px 0; }
    .captcha-notice {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      background: #fff3e0;
      border-radius: 4px;
    }
    .login-options { padding: 8px 0; }
    .hint { color: #999; font-style: italic; }
  `]
})
export class StepUrlComponent implements OnDestroy {
  @ViewChild('tabGroup') tabGroup!: MatTabGroup;

  private fb = inject(FormBuilder);
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);
  private ws = inject(WebSocketService);
  private analysisSub: Subscription | null = null;
  private loginAnalysisSub: Subscription | null = null;
  private vncSub: Subscription | null = null;

  urlControl = this.fb.nonNullable.control('', [
    Validators.required,
    Validators.pattern(/^https?:\/\/.+/)
  ]);

  loginUrlControl = this.fb.nonNullable.control('', [
    Validators.required,
    Validators.pattern(/^https?:\/\/.+/)
  ]);

  // Login state
  requiresLogin = signal(false);
  loginEveryTime = signal(true);
  selectedTab = signal(0);
  analyzingLogin = signal(false);
  loginAnalysisId = signal<string | null>(null);
  loginFormResult = signal<any>(null);

  // Standard analysis state
  analyzing = signal(false);
  analysisResult = signal<any>(null);
  pages = signal<any[]>([]);
  currentAnalysisId = signal<string | null>(null);

  // VNC state for analysis
  analysisVncEvent = signal<AnalysisVncEvent | null>(null);

  // Initial login config (for editing mode)
  initialLoginConfig = input<LoginConfig | undefined>(undefined);

  formsDetected = output<FormDefinition[]>();
  loginConfigChanged = output<LoginConfig>();

  // --- Login Toggle ---
  onLoginToggle(checked: boolean) {
    this.requiresLogin.set(checked);
    this.emitLoginConfig();
    if (!checked) {
      this.loginFormResult.set(null);
    }
  }

  onLoginEveryTimeToggle(value: boolean) {
    this.loginEveryTime.set(value);
    this.emitLoginConfig();
  }

  private emitLoginConfig() {
    this.loginConfigChanged.emit({
      requires_login: this.requiresLogin(),
      login_url: this.requiresLogin() ? this.loginUrlControl.value || null : null,
      login_every_time: this.loginEveryTime(),
    });
  }

  // --- Analyze Login Page (reuses standard analyze endpoint) ---
  analyzeLoginPage() {
    if (this.loginUrlControl.invalid) return;
    this.analyzingLogin.set(true);
    this.loginAnalysisSub?.unsubscribe();
    this.loginAnalysisId.set(null);

    this.taskService.analyzeUrl(this.loginUrlControl.value).subscribe({
      next: (response) => {
        const analysisId = response.analysis_id;
        this.loginAnalysisId.set(analysisId);
        this.notify.info('Analyzing login page...');

        this.loginAnalysisSub = this.ws.waitForAnalysis(analysisId).subscribe({
          next: (data) => {
            this.analyzingLogin.set(false);
            if (data.error) {
              this.notify.error(data.error);
              return;
            }
            const result = data.result;
            // Find the login form (or first form)
            const loginForm = result.forms?.find((f: any) => f.form_type === 'login') || result.forms?.[0];
            if (loginForm) {
              // Initialize preset_value for each field
              loginForm.fields = (loginForm.fields || []).map((f: any) => ({
                ...f,
                preset_value: f.preset_value || '',
                is_sensitive: f.field_type === 'password' || f.field_purpose === 'password',
              }));
              this.loginFormResult.set(loginForm);
              this.emitLoginConfig();
              this.notify.success('Login form detected');
            } else {
              this.notify.warn('No login form detected on this page');
            }
          },
          error: () => {
            this.analyzingLogin.set(false);
            this.notify.error('WebSocket connection lost');
          }
        });
      },
      error: (err) => {
        this.analyzingLogin.set(false);
        this.notify.error(err.error?.message || 'Failed to analyze login page');
      }
    });
  }

  // --- Login & Analyze Target ---
  analyzeLoginAndTarget() {
    if (this.urlControl.invalid || !this.loginFormResult()) return;
    this.analyzing.set(true);
    this.analysisResult.set(null);
    this.analysisSub?.unsubscribe();
    this.currentAnalysisId.set(null);
    this.analysisVncEvent.set(null);

    const loginForm = this.loginFormResult()!;
    const needsVnc = loginForm.captcha_detected === true;

    const loginFields = (loginForm.fields || [])
      .filter((f: any) => f.preset_value)
      .map((f: any) => ({
        field_selector: f.field_selector,
        value: f.preset_value,
        field_type: f.field_type,
        is_sensitive: f.is_sensitive || f.field_type === 'password',
      }));

    this.taskService.analyzeLoginAndTarget({
      login_url: this.loginUrlControl.value,
      target_url: this.urlControl.value,
      login_form_selector: loginForm.form_selector,
      login_submit_selector: loginForm.submit_selector,
      login_fields: loginFields,
      needs_vnc: needsVnc,
    }).subscribe({
      next: (response) => {
        const analysisId = response.analysis_id;
        this.currentAnalysisId.set(analysisId);
        this.notify.info('Login-aware analysis started...');

        // Subscribe to VNC events
        this.vncSub?.unsubscribe();
        this.vncSub = this.ws.analysisVncRequired$.subscribe((event) => {
          if (event.analysis_id === analysisId) {
            this.analysisVncEvent.set(event);
          }
        });

        // Subscribe to AI thinking + analysis result
        this.ws.subscribeToAnalysis(analysisId).subscribe();

        this.analysisSub = this.ws.waitForAnalysis(analysisId).subscribe({
          next: (data) => {
            this.analyzing.set(false);
            this.analysisVncEvent.set(null);
            this.vncSub?.unsubscribe();

            if (data.error) {
              this.notify.error(data.error);
              return;
            }
            const result = data.result;
            this.analysisResult.set(result);

            if (result.forms?.length) {
              this.pages.update(p => [{
                url: this.urlControl.value,
                forms: result.forms,
                two_factor_detected: result.two_factor_detected,
              }, ...p.slice(1)]);
              this.emitAllFormsWithLogin();
              this.notify.success('Target page analyzed successfully');
            } else {
              this.notify.warn('No forms detected on target page');
            }
          },
          error: () => {
            this.analyzing.set(false);
            this.analysisVncEvent.set(null);
            this.notify.error('WebSocket connection lost');
          }
        });
      },
      error: (err) => {
        this.analyzing.set(false);
        this.notify.error(err.error?.message || 'Failed to start login analysis');
      }
    });
  }

  onVncResumed() {
    this.analysisVncEvent.set(null);
  }

  // --- Standard Analyze (no login) ---
  analyze() {
    if (this.urlControl.invalid) return;
    this.analyzing.set(true);
    this.analysisSub?.unsubscribe();
    this.currentAnalysisId.set(null);

    this.taskService.analyzeUrl(this.urlControl.value).subscribe({
      next: (response) => {
        const analysisId = response.analysis_id;
        this.currentAnalysisId.set(analysisId);
        this.notify.info('Analysis started, waiting for AI results...');

        this.analysisSub = this.ws.waitForAnalysis(analysisId).subscribe({
          next: (data) => {
            if (data.error) {
              this.analyzing.set(false);
              this.notify.error(data.error);
              return;
            }
            const result = data.result;
            this.analysisResult.set(result);
            this.analyzing.set(false);

            // Auto-detection: if page requires login
            if (result.page_requires_login) {
              this.notify.warn('Login required! The page redirected to a login form.');
              this.requiresLogin.set(true);
              this.emitLoginConfig();

              // If Ollama found a login form, populate login form result
              const loginForm = result.forms?.find((f: any) => f.form_type === 'login') || result.forms?.[0];
              if (loginForm) {
                loginForm.fields = (loginForm.fields || []).map((f: any) => ({
                  ...f,
                  preset_value: f.preset_value || '',
                  is_sensitive: f.field_type === 'password' || f.field_purpose === 'password',
                }));
                this.loginFormResult.set(loginForm);
                // Auto-set login URL from the page that was found
                this.loginUrlControl.setValue(loginForm.page_url || this.urlControl.value);
              }

              // Switch to Login Setup tab
              this.selectedTab.set(0);
              return;
            }

            if (result.forms?.length) {
              this.pages.update(p => [{
                url: this.urlControl.value,
                forms: result.forms,
                two_factor_detected: result.two_factor_detected,
              }, ...p.slice(1)]);
              this.emitAllForms();
              this.notify.success('Page analyzed successfully');
            } else {
              this.notify.warn('No forms detected on this page');
            }
          },
          error: () => {
            this.analyzing.set(false);
            this.notify.error('WebSocket connection lost');
          }
        });
      },
      error: (err) => {
        this.analyzing.set(false);
        this.notify.error(err.error?.message || 'Failed to start analysis');
      }
    });
  }

  addPage() {
    this.analyzing.set(true);
    this.analysisSub?.unsubscribe();
    this.currentAnalysisId.set(null);

    this.taskService.analyzeNextPage(this.urlControl.value).subscribe({
      next: (response) => {
        const analysisId = response.analysis_id;
        this.currentAnalysisId.set(analysisId);

        this.analysisSub = this.ws.waitForAnalysis(analysisId).subscribe({
          next: (data) => {
            this.analyzing.set(false);
            if (data.error) {
              this.notify.error(data.error);
              return;
            }
            const result = data.result;
            if (result.forms?.length) {
              this.pages.update(p => [...p, {
                url: result.url || 'Next page',
                forms: result.forms,
                two_factor_detected: result.two_factor_detected,
              }]);
              if (this.requiresLogin()) {
                this.emitAllFormsWithLogin();
              } else {
                this.emitAllForms();
              }
              this.notify.success('Additional page detected');
            } else {
              this.notify.info('No additional pages detected');
            }
          },
          error: () => {
            this.analyzing.set(false);
            this.notify.error('WebSocket connection lost');
          }
        });
      },
      error: () => {
        this.analyzing.set(false);
        this.notify.error('Failed to detect next page');
      }
    });
  }

  // --- Form emission helpers ---
  private normalizeFormType(type: string): string {
    if (type === 'login') return 'login';
    if (type === 'intermediate') return 'intermediate';
    return 'target';
  }

  private emitAllForms() {
    const allForms: FormDefinition[] = [];
    let stepOrder = 0;
    for (const page of this.pages()) {
      const twoFactorDetected = page.two_factor_detected === true;
      for (const form of (page.forms || [])) {
        allForms.push({
          ...form,
          page_url: form.page_url || page.url,
          step_order: stepOrder++,
          form_type: this.normalizeFormType(form.form_type),
          ai_confidence: form.confidence ?? form.ai_confidence ?? null,
          two_factor_expected: form.two_factor_expected ??
            (twoFactorDetected && form.form_type === 'login'),
        });
      }
    }
    this.formsDetected.emit(allForms);
  }

  private emitAllFormsWithLogin() {
    const allForms: FormDefinition[] = [];
    const loginForm = this.loginFormResult();

    // Add login form as step_order=0
    if (loginForm) {
      allForms.push({
        ...loginForm,
        step_order: 0,
        form_type: 'login',
        page_url: this.loginUrlControl.value,
        ai_confidence: loginForm.confidence ?? loginForm.ai_confidence ?? null,
        two_factor_expected: loginForm.two_factor_expected ?? false,
        fields: (loginForm.fields || []).map((f: any, idx: number) => ({
          ...f,
          is_sensitive: f.is_sensitive || f.field_type === 'password' || f.field_purpose === 'password',
          sort_order: idx,
        })),
      });
    }

    // Add target forms starting at step_order=1
    let stepOrder = 1;
    for (const page of this.pages()) {
      const twoFactorDetected = page.two_factor_detected === true;
      for (const form of (page.forms || [])) {
        allForms.push({
          ...form,
          page_url: form.page_url || page.url,
          step_order: stepOrder++,
          form_type: this.normalizeFormType(form.form_type),
          ai_confidence: form.confidence ?? form.ai_confidence ?? null,
          two_factor_expected: form.two_factor_expected ??
            (twoFactorDetected && form.form_type === 'login'),
        });
      }
    }

    this.formsDetected.emit(allForms);
  }

  // --- Public methods for parent component ---
  setUrl(url: string) {
    this.urlControl.setValue(url);
  }

  setLoginConfig(config: LoginConfig) {
    this.requiresLogin.set(config.requires_login);
    if (config.login_url) {
      this.loginUrlControl.setValue(config.login_url);
    }
    this.loginEveryTime.set(config.login_every_time);
  }

  ngOnDestroy() {
    this.analysisSub?.unsubscribe();
    this.loginAnalysisSub?.unsubscribe();
    this.vncSub?.unsubscribe();
  }
}
