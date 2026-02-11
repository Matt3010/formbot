import { Component, inject, output, signal, OnDestroy } from '@angular/core';
import { TitleCasePipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatCardModule } from '@angular/material/card';
import { MatListModule } from '@angular/material/list';
import { Subscription } from 'rxjs';
import { TaskService } from '../../../core/services/task.service';
import { NotificationService } from '../../../core/services/notification.service';
import { WebSocketService } from '../../../core/services/websocket.service';
import { FormDefinition } from '../../../core/models/task.model';

@Component({
  selector: 'app-step-url',
  standalone: true,
  imports: [
    TitleCasePipe,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatCardModule,
    MatListModule,
  ],
  template: `
    <div class="step-url">
      <h2>Step 1: Target URL</h2>
      <p>Enter the URL of the form you want to automate. FormBot will analyze the page and detect forms.</p>

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
        <button mat-stroked-button color="accent" class="mt-2" (click)="addPage()" [disabled]="analyzing()">
          <mat-icon>add</mat-icon> Add Another Page
        </button>
      }
    </div>
  `,
  styles: [`
    .step-url { max-width: 800px; }
  `]
})
export class StepUrlComponent implements OnDestroy {
  private fb = inject(FormBuilder);
  private taskService = inject(TaskService);
  private notify = inject(NotificationService);
  private ws = inject(WebSocketService);
  private analysisSub: Subscription | null = null;

  urlControl = this.fb.nonNullable.control('', [
    Validators.required,
    Validators.pattern(/^https?:\/\/.+/)
  ]);

  analyzing = signal(false);
  analysisResult = signal<any>(null);
  pages = signal<any[]>([]);

  formsDetected = output<FormDefinition[]>();

  analyze() {
    if (this.urlControl.invalid) return;
    this.analyzing.set(true);
    this.analysisSub?.unsubscribe();

    this.taskService.analyzeUrl(this.urlControl.value).subscribe({
      next: (response) => {
        const analysisId = response.analysis_id;
        this.notify.info('Analysis started, waiting for AI results...');

        // Subscribe to WebSocket for the result
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

    this.taskService.analyzeNextPage(this.urlControl.value).subscribe({
      next: (response) => {
        const analysisId = response.analysis_id;

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
              this.emitAllForms();
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

  private emitAllForms() {
    const allForms: FormDefinition[] = [];
    for (const page of this.pages()) {
      const twoFactorDetected = page.two_factor_detected === true;
      for (const form of (page.forms || [])) {
        allForms.push({
          ...form,
          ai_confidence: form.confidence ?? form.ai_confidence ?? null,
          two_factor_expected: form.two_factor_expected ??
            (twoFactorDetected && form.form_type === 'login'),
        });
      }
    }
    this.formsDetected.emit(allForms);
  }

  setUrl(url: string) {
    this.urlControl.setValue(url);
  }

  ngOnDestroy() {
    this.analysisSub?.unsubscribe();
  }
}
