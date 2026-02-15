import { Component, inject, input, output, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { TaskService } from '../../../core/services/task.service';
import { NotificationService } from '../../../core/services/notification.service';
import { FormDefinition } from '../../../core/models/task.model';

export interface LoginConfig {
  requires_login: boolean;
  login_url: string | null;
}

@Component({
  selector: 'app-step-url',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
  ],
  template: `
    <div class="step-url">
      <h2>Step 1: Target URL</h2>
      <p>Enter the URL of the form you want to automate. Click "Open Editor" to visually select fields.</p>

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
        <!-- Login flow: login URL + target URL -->
        <div class="login-urls mt-2">
          <div class="flex gap-2 items-center">
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
              (click)="analyze(loginUrlControl.value, true)"
              [disabled]="analyzingLogin() || loginUrlControl.invalid">
              @if (analyzingLogin()) {
                <mat-spinner diameter="20"></mat-spinner>
                Starting...
              } @else {
                <mat-icon>open_in_browser</mat-icon> Open Editor
              }
            </button>
          </div>

          <mat-form-field appearance="outline" class="full-width">
            <mat-label>Target URL (page to automate after login)</mat-label>
            <input matInput [formControl]="urlControl" placeholder="https://example.com/form">
            @if (urlControl.hasError('required')) {
              <mat-error>Target URL is required</mat-error>
            }
            @if (urlControl.hasError('pattern')) {
              <mat-error>Must be a valid URL</mat-error>
            }
          </mat-form-field>
        </div>
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

          <button mat-raised-button color="primary"
            (click)="analyze(urlControl.value, false)"
            [disabled]="analyzing() || urlControl.invalid">
            @if (analyzing()) {
              <mat-spinner diameter="20"></mat-spinner>
              Starting...
            } @else {
              <mat-icon>open_in_browser</mat-icon> Open Editor
            }
          </button>
        </div>
      }
    </div>
  `,
  styles: [`
    .step-url { max-width: 800px; }
    .login-toggle { padding: 8px 0; }
  `]
})
export class StepUrlComponent {
  private fb = inject(FormBuilder);
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);

  urlControl = this.fb.nonNullable.control('', [
    Validators.required,
    Validators.pattern(/^https?:\/\/.+/)
  ]);

  loginUrlControl = this.fb.nonNullable.control('', [
    Validators.required,
    Validators.pattern(/^https?:\/\/.+/)
  ]);

  requiresLogin = signal(false);
  analyzingLogin = signal(false);
  analyzing = signal(false);
  currentTaskId = signal<string | null>(null);

  initialLoginConfig = input<LoginConfig | undefined>(undefined);

  formsDetected = output<FormDefinition[]>();
  loginConfigChanged = output<LoginConfig>();

  onLoginToggle(checked: boolean) {
    this.requiresLogin.set(checked);
    this.emitLoginConfig();
  }

  private emitLoginConfig() {
    this.loginConfigChanged.emit({
      requires_login: this.requiresLogin(),
      login_url: this.requiresLogin() ? this.loginUrlControl.value || null : null,
    });
  }

  analyze(url: string, isLogin: boolean) {
    if (!url) return;

    // If there's already an analysis in progress, we should ideally cancel it first
    // to avoid having multiple VNC sessions for the same task
    const previousAnalysisId = this.currentTaskId();

    const setter = isLogin ? this.analyzingLogin : this.analyzing;
    setter.set(true);

    this.taskService.analyzeUrl(url).subscribe({
      next: (response) => {
        setter.set(false);
        const analysisId = response.task_id;
        this.currentTaskId.set(analysisId);

        if (isLogin) {
          this.emitLoginConfig();
          const allForms: FormDefinition[] = [{
            id: 'login-0',
            task_id: '',
            step_order: 0,
            depends_on_step_order: null,
            page_url: url,
            form_type: 'login',
            form_selector: '',
            submit_selector: '',
            human_breakpoint: false,
            fields: [],
            created_at: '',
            updated_at: '',
          }];
          this.formsDetected.emit(allForms);
          this.notify.info('Opening editor for login page...');
        } else {
          const forms: FormDefinition[] = [{
            id: 'manual-0',
            task_id: '',
            step_order: 0,
            depends_on_step_order: null,
            page_url: url,
            form_type: 'target',
            form_selector: '',
            submit_selector: '',
            human_breakpoint: false,
            fields: [],
            created_at: '',
            updated_at: '',
          }];
          this.formsDetected.emit(forms);
          this.notify.info('Opening editor...');
        }
      },
      error: (err) => {
        setter.set(false);
        this.notify.error(err.error?.message || 'Failed to create analysis');
      },
    });
  }

  setUrl(url: string) {
    this.urlControl.setValue(url);
  }

  setLoginConfig(config: LoginConfig) {
    this.requiresLogin.set(config.requires_login);
    if (config.login_url) {
      this.loginUrlControl.setValue(config.login_url);
    }
  }
}
