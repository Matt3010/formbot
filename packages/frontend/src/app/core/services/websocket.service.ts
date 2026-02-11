import { Injectable, inject, signal } from '@angular/core';
import { AuthService } from './auth.service';
import { Subject, Observable } from 'rxjs';
import Pusher from 'pusher-js';

@Injectable({ providedIn: 'root' })
export class WebSocketService {
  private auth = inject(AuthService);
  private pusher: any = null;

  taskUpdated$ = new Subject<any>();
  executionUpdate$ = new Subject<any>();
  captchaDetected$ = new Subject<any>();
  analysisCompleted$ = new Subject<any>();
  connected = signal(false);

  connect() {
    if (this.pusher) return;

    try {
      this.pusher = new Pusher('formbot-key', {
        cluster: '',
        wsHost: window.location.hostname,
        wsPort: 6001,
        forceTLS: false,
        disableStats: true,
        enabledTransports: ['ws'],
      });

      const user = this.auth.user();
      if (user) {
        const channel = this.pusher.subscribe(`private-tasks.${user.id}`);
        channel.bind('TaskStatusChanged', (data: any) => this.taskUpdated$.next(data));
        channel.bind('ExecutionStarted', (data: any) => this.executionUpdate$.next(data));
        channel.bind('ExecutionCompleted', (data: any) => this.executionUpdate$.next(data));
        channel.bind('CaptchaDetected', (data: any) => this.captchaDetected$.next(data));
      }

      this.connected.set(true);
    } catch (e) {
      console.warn('WebSocket connection failed:', e);
    }
  }

  /**
   * Subscribe to analysis results for a specific analysis ID.
   * Uses a public channel (no auth needed).
   * Auto-unsubscribes after receiving the result.
   */
  waitForAnalysis(analysisId: string): Observable<any> {
    return new Observable(subscriber => {
      if (!this.pusher) {
        this.connect();
      }

      const channelName = `analysis.${analysisId}`;
      const channel = this.pusher.subscribe(channelName);

      channel.bind('AnalysisCompleted', (data: any) => {
        subscriber.next(data);
        subscriber.complete();
        this.pusher.unsubscribe(channelName);
      });

      // Cleanup on unsubscribe
      return () => {
        try {
          this.pusher?.unsubscribe(channelName);
        } catch {}
      };
    });
  }

  disconnect() {
    if (this.pusher) {
      this.pusher.disconnect();
      this.pusher = null;
      this.connected.set(false);
    }
  }
}
