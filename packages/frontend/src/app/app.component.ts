import { Component, OnDestroy, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, Router, NavigationEnd } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatSnackBarModule } from '@angular/material/snack-bar';
import { BreakpointObserver } from '@angular/cdk/layout';
import { Subscription, filter } from 'rxjs';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
    MatSnackBarModule,
  ],
  template: `
    @if (auth.isLoggedIn()) {
      <mat-toolbar color="primary">
        <button mat-icon-button (click)="sidenav.toggle()">
          <mat-icon>menu</mat-icon>
        </button>
        <span>FormBot</span>
        <span class="spacer"></span>
        <button mat-button (click)="logout()">
          <mat-icon>logout</mat-icon> Logout
        </button>
      </mat-toolbar>

      <mat-sidenav-container class="app-shell">
        <mat-sidenav #sidenav [mode]="isMobile() ? 'over' : 'side'" [opened]="!isMobile()">
          <mat-nav-list>
            <a mat-list-item routerLink="/dashboard" (click)="closeOnMobile(sidenav)">
              <mat-icon matListItemIcon>dashboard</mat-icon>
              <span matListItemTitle>Dashboard</span>
            </a>
            <a mat-list-item routerLink="/tasks/new" (click)="closeOnMobile(sidenav)">
              <mat-icon matListItemIcon>add_circle</mat-icon>
              <span matListItemTitle>New Task</span>
            </a>
            <a mat-list-item routerLink="/analyses" (click)="closeOnMobile(sidenav)">
              <mat-icon matListItemIcon>analytics</mat-icon>
              <span matListItemTitle>Analyses</span>
            </a>
            <a mat-list-item routerLink="/logs" (click)="closeOnMobile(sidenav)">
              <mat-icon matListItemIcon>list_alt</mat-icon>
              <span matListItemTitle>Logs</span>
            </a>
            <a mat-list-item routerLink="/settings" (click)="closeOnMobile(sidenav)">
              <mat-icon matListItemIcon>settings</mat-icon>
              <span matListItemTitle>Settings</span>
            </a>
          </mat-nav-list>
        </mat-sidenav>

        <mat-sidenav-content>
          <div class="content-shell" [class.workspace-shell]="isWorkspaceRoute()">
            <router-outlet />
          </div>
        </mat-sidenav-content>
      </mat-sidenav-container>
    } @else {
      <router-outlet />
    }
  `,
  styles: [`
    .app-shell { height: calc(100vh - 64px); }
    mat-sidenav { width: 240px; }
    .spacer { flex: 1 1 auto; }
    .content-shell {
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px 20px 32px;
      box-sizing: border-box;
    }
    .content-shell.workspace-shell {
      max-width: 100%;
      padding: 12px 16px 20px;
    }
    @media (max-width: 959px) {
      .content-shell {
        padding: 12px 12px 20px;
      }
    }
  `]
})
export class AppComponent implements OnDestroy {
  auth = inject(AuthService);
  private router = inject(Router);
  private breakpoint = inject(BreakpointObserver);
  private subs: Subscription[] = [];

  isMobile = signal(false);
  isWorkspaceRoute = signal(false);

  constructor() {
    this.subs.push(
      this.breakpoint.observe('(max-width: 959px)').subscribe((state) => {
        this.isMobile.set(state.matches);
      })
    );

    this.syncRouteMode(this.router.url);
    this.subs.push(
      this.router.events
        .pipe(filter((e) => e instanceof NavigationEnd))
        .subscribe((e) => this.syncRouteMode((e as NavigationEnd).urlAfterRedirects))
    );
  }

  logout() {
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  closeOnMobile(sidenav: { close: () => void }) {
    if (this.isMobile()) {
      sidenav.close();
    }
  }

  ngOnDestroy() {
    this.subs.forEach((s) => s.unsubscribe());
  }

  private syncRouteMode(url: string) {
    const isTaskWorkspace =
      url.startsWith('/tasks/new') ||
      url.startsWith('/tasks/') ||
      url.startsWith('/logs');

    this.isWorkspaceRoute.set(isTaskWorkspace);
  }
}
