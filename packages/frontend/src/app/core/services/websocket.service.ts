import { Injectable, inject, signal, NgZone } from '@angular/core';
import { AuthService } from './auth.service';
import { Subject, Observable } from 'rxjs';
import Pusher from 'pusher-js';
import {
  HighlightingReadyEvent,
  FieldSelectedEvent,
  FieldAddedEvent,
  FieldRemovedEvent,
  LoginExecutionProgressEvent,
  LoginExecutionCompleteEvent,
} from '../models/vnc-editor.model';

export interface ExecutionProgress {
  execution_id: string;
  task_id: string;
  status: string;
  step?: number;
  total_steps?: number;
  page_url?: string;
  form_type?: string;
  field_name?: string;
  field_type?: string;
  is_dry_run?: boolean;
  error?: string;
  screenshot?: string;
  started_at?: string;
  vnc_session_id?: string;
  vnc_url?: string;
  reason?: string;
  ws_port?: number;
}

export interface WaitingManualEvent {
  execution_id: string;
  task_id: string;
  status: string;
  reason: string;
  vnc_session_id: string;
  vnc_url: string;
  ws_port?: number;
}

@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private auth = inject(AuthService);
  private zone = inject(NgZone);
  private pusher: any = null;
  private subscribedChannels = new Map<string, any>();

  taskUpdated$ = new Subject<any>();
  taskDeleted$ = new Subject<any>();
  executionUpdate$ = new Subject<any>();
  executionProgress$ = new Subject<ExecutionProgress>();
  executionWaitingManual$ = new Subject<WaitingManualEvent>();
  captchaDetected$ = new Subject<any>();
  analysisCompleted$ = new Subject<any>();
  highlightingReady$ = new Subject<HighlightingReadyEvent>();
  vncFieldSelected$ = new Subject<FieldSelectedEvent>();
  vncFieldAdded$ = new Subject<FieldAddedEvent>();
  vncFieldRemoved$ = new Subject<FieldRemovedEvent>();
  loginExecutionProgress$ = new Subject<LoginExecutionProgressEvent>();
  loginExecutionComplete$ = new Subject<LoginExecutionCompleteEvent>();
  connected = signal(false);
  connectionState = signal<string>('disconnected');

  connect() {
    if (this.pusher) return;

    const token = this.auth.getToken();

    try {
      this.pusher = new Pusher('formbot-key', {
        cluster: '',
        wsHost: window.location.hostname,
        wsPort: 6001,
        forceTLS: false,
        disableStats: true,
        enabledTransports: ['ws'],
        authEndpoint: '/api/broadcasting/auth',
        auth: {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: 'application/json',
          }
        },
      });

      // Connection state monitoring
      this.pusher.connection.bind('state_change', (states: { current: string; previous: string }) => this.zone.run(() => {
        this.connectionState.set(states.current);
        this.connected.set(states.current === 'connected');
      }));

      this.pusher.connection.bind('connected', () => this.zone.run(() => {
        this.connected.set(true);
        this.connectionState.set('connected');
      }));

      this.pusher.connection.bind('disconnected', () => this.zone.run(() => {
        this.connected.set(false);
        this.connectionState.set('disconnected');
      }));

      const user = this.auth.user();
      if (user) {
        this.subscribeToUserChannel(user.id);
      } else {
        // User not loaded yet (page refresh) - load user then subscribe
        this.auth.loadUser().subscribe({
          next: (u) => {
            if (u) this.subscribeToUserChannel(u.id);
          }
        });
      }
    } catch (e) {
      console.warn('WebSocket connection failed:', e);
    }
  }

  private subscribeToUserChannel(userId: number) {
    const channelName = `private-tasks.${userId}`;
    if (this.subscribedChannels.has(channelName)) return;

    const channel = this.pusher.subscribe(channelName);
    this.subscribedChannels.set(channelName, channel);

    channel.bind('TaskStatusChanged', (data: any) => this.zone.run(() => {
      if (data.status === 'deleted') {
        this.taskDeleted$.next(data);
      } else {
        this.taskUpdated$.next(data);
      }
    }));
    channel.bind('ExecutionStarted', (data: any) => this.zone.run(() => {
      this.executionUpdate$.next(data);
      this.executionProgress$.next({ ...data, status: data.status || 'running' });
    }));
    channel.bind('ExecutionCompleted', (data: any) => this.zone.run(() => this.executionUpdate$.next(data)));
    channel.bind('CaptchaDetected', (data: any) => this.zone.run(() => this.captchaDetected$.next(data)));

    // Python-originated execution events
    channel.bind('execution.started', (data: any) => this.zone.run(() => this.executionProgress$.next(data)));
    channel.bind('execution.step_started', (data: any) => this.zone.run(() => this.executionProgress$.next(data)));
    channel.bind('execution.step_completed', (data: any) => this.zone.run(() => this.executionProgress$.next(data)));
    channel.bind('execution.field_filled', (data: any) => this.zone.run(() => this.executionProgress$.next(data)));
    channel.bind('execution.completed', (data: any) => this.zone.run(() => {
      this.executionProgress$.next(data);
      this.executionUpdate$.next(data);
    }));
    channel.bind('execution.failed', (data: any) => this.zone.run(() => {
      this.executionProgress$.next(data);
      this.executionUpdate$.next(data);
    }));
    channel.bind('execution.waiting_manual', (data: any) => this.zone.run(() => {
      this.executionProgress$.next(data);
      this.executionWaitingManual$.next(data as WaitingManualEvent);
    }));
    channel.bind('execution.resumed', (data: any) => this.zone.run(() => this.executionProgress$.next(data)));
  }

  /**
   * Subscribe to execution-specific channel for detailed progress.
   */
  subscribeToExecution(executionId: string): void {
    const channelName = `private-execution.${executionId}`;
    if (this.subscribedChannels.has(channelName)) return;
    if (!this.pusher) this.connect();

    const channel = this.pusher.subscribe(channelName);
    this.subscribedChannels.set(channelName, channel);

    const events = [
      'execution.started', 'execution.step_started', 'execution.step_completed',
      'execution.field_filled', 'execution.completed', 'execution.failed',
      'execution.waiting_manual', 'execution.resumed',
    ];

    for (const event of events) {
      channel.bind(event, (data: any) => this.zone.run(() => {
        this.executionProgress$.next(data);
        if (event === 'execution.waiting_manual') {
          this.executionWaitingManual$.next(data as WaitingManualEvent);
        }
        if (event === 'execution.completed' || event === 'execution.failed') {
          this.executionUpdate$.next(data);
        }
      }));
    }
  }

  /**
   * Unsubscribe from an execution channel.
   */
  unsubscribeFromExecution(executionId: string): void {
    const channelName = `private-execution.${executionId}`;
    this.unsubscribeChannel(channelName);
  }

  /**
   * Subscribe to analysis results for a specific analysis ID.
   * Uses a private channel (auth required).
   * Auto-unsubscribes after receiving the result.
   */
  waitForAnalysis(analysisId: string): Observable<any> {
    return new Observable(subscriber => {
      if (!this.pusher) {
        this.connect();
      }

      const channelName = `private-analysis.${analysisId}`;
      const channel = this.pusher.subscribe(channelName);
      this.subscribedChannels.set(channelName, channel);

      channel.bind('AnalysisCompleted', (data: any) => this.zone.run(() => {
        subscriber.next(data);
        subscriber.complete();
        this.unsubscribeChannel(channelName);
      }));

      // Cleanup on unsubscribe
      return () => {
        this.unsubscribeChannel(channelName);
      };
    });
  }

  /**
   * Subscribe to analysis events (highlighting, field selection, login progress).
   */
  subscribeToAnalysis(analysisId: string): Observable<any> {
    return new Observable(subscriber => {
      if (!this.pusher) {
        this.connect();
      }

      const channelName = `private-analysis.${analysisId}`;
      let channel = this.subscribedChannels.get(channelName);
      if (!channel) {
        channel = this.pusher.subscribe(channelName);
        this.subscribedChannels.set(channelName, channel);
      }

      channel.bind('HighlightingReady', (data: HighlightingReadyEvent) => this.zone.run(() => {
        this.highlightingReady$.next(data);
      }));

      channel.bind('FieldSelected', (data: FieldSelectedEvent) => this.zone.run(() => {
        this.vncFieldSelected$.next(data);
      }));

      channel.bind('FieldAdded', (data: FieldAddedEvent) => this.zone.run(() => {
        this.vncFieldAdded$.next(data);
      }));

      channel.bind('FieldRemoved', (data: FieldRemovedEvent) => this.zone.run(() => {
        this.vncFieldRemoved$.next(data);
      }));

      channel.bind('LoginExecutionProgress', (data: LoginExecutionProgressEvent) => this.zone.run(() => {
        this.loginExecutionProgress$.next(data);
      }));

      channel.bind('LoginExecutionComplete', (data: LoginExecutionCompleteEvent) => this.zone.run(() => {
        this.loginExecutionComplete$.next(data);
      }));

      return () => {
        try {
          channel?.unbind('HighlightingReady');
          channel?.unbind('FieldSelected');
          channel?.unbind('FieldAdded');
          channel?.unbind('FieldRemoved');
          channel?.unbind('LoginExecutionProgress');
          channel?.unbind('LoginExecutionComplete');
        } catch {}
      };
    });
  }

  private unsubscribeChannel(channelName: string) {
    try {
      this.pusher?.unsubscribe(channelName);
      this.subscribedChannels.delete(channelName);
    } catch {}
  }

  disconnect() {
    if (this.pusher) {
      this.subscribedChannels.clear();
      this.pusher.disconnect();
      this.pusher = null;
      this.connected.set(false);
      this.connectionState.set('disconnected');
    }
  }
}
