import { Component, input, inject, signal, OnInit, OnDestroy, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { Subscription } from 'rxjs';
import { WebSocketService, AiThinkingEvent } from '../../core/services/websocket.service';

@Component({
  selector: 'app-ai-thinking',
  standalone: true,
  imports: [
    MatCardModule,
    MatIconModule,
    MatButtonModule,
    MatProgressSpinnerModule,
  ],
  template: `
    <mat-card class="ai-thinking-card" [class.collapsed]="collapsed()">
      <div class="ai-thinking-header" (click)="toggleCollapse()">
        <div class="flex items-center gap-2">
          @if (!done()) {
            <mat-spinner diameter="16"></mat-spinner>
          } @else {
            <mat-icon class="done-icon">check_circle</mat-icon>
          }
          <span class="header-text">
            @if (!done()) {
              AI is analyzing the page...
            } @else {
              AI analysis complete
            }
          </span>
        </div>
        <button mat-icon-button class="collapse-btn">
          <mat-icon>{{ collapsed() ? 'expand_more' : 'expand_less' }}</mat-icon>
        </button>
      </div>

      @if (!collapsed()) {
        <div class="ai-thinking-content" #thinkingContent>
          <pre class="thinking-text">{{ thinkingText() }}<span class="cursor" [class.hidden]="done()">|</span></pre>
        </div>
      }
    </mat-card>
  `,
  styles: [`
    .ai-thinking-card {
      margin-top: 16px;
      border-left: 4px solid #7c4dff;
      overflow: hidden;
    }
    .ai-thinking-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      cursor: pointer;
      user-select: none;
    }
    .header-text {
      font-size: 14px;
      font-weight: 500;
      color: #7c4dff;
    }
    .done-icon {
      color: #4caf50;
      font-size: 20px;
      width: 20px;
      height: 20px;
    }
    .collapse-btn {
      width: 32px;
      height: 32px;
      line-height: 32px;
    }
    .ai-thinking-content {
      max-height: 300px;
      overflow-y: auto;
      padding: 0 16px 16px;
    }
    .thinking-text {
      font-family: 'Fira Code', 'Consolas', monospace;
      font-size: 12px;
      line-height: 1.5;
      color: #ccc;
      background: #1e1e1e;
      padding: 12px;
      border-radius: 8px;
      white-space: pre-wrap;
      word-break: break-word;
      margin: 0;
    }
    .cursor {
      animation: blink 1s step-end infinite;
      color: #7c4dff;
    }
    .cursor.hidden { display: none; }
    @keyframes blink {
      50% { opacity: 0; }
    }
    .collapsed .ai-thinking-content { display: none; }
  `]
})
export class AiThinkingComponent implements OnInit, OnDestroy, AfterViewChecked {
  private ws = inject(WebSocketService);
  private sub: Subscription | null = null;
  private shouldScroll = false;

  analysisId = input.required<string>();

  thinkingText = signal('');
  done = signal(false);
  collapsed = signal(false);

  @ViewChild('thinkingContent') contentEl?: ElementRef<HTMLDivElement>;

  ngOnInit() {
    this.sub = this.ws.subscribeToAnalysis(this.analysisId()).subscribe({
      next: (event: AiThinkingEvent) => {
        if (event.token) {
          this.thinkingText.update(t => t + event.token);
          this.shouldScroll = true;
        }
        if (event.done) {
          this.done.set(true);
        }
      },
      complete: () => {
        this.done.set(true);
      }
    });
  }

  ngAfterViewChecked() {
    if (this.shouldScroll && this.contentEl) {
      const el = this.contentEl.nativeElement;
      el.scrollTop = el.scrollHeight;
      this.shouldScroll = false;
    }
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
  }

  toggleCollapse() {
    this.collapsed.update(v => !v);
  }
}
