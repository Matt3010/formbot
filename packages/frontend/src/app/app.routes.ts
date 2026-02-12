import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./features/auth/login.component').then(m => m.LoginComponent) },
  { path: 'register', loadComponent: () => import('./features/auth/register.component').then(m => m.RegisterComponent) },
  { path: '', canActivate: [authGuard], children: [
    { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
    { path: 'dashboard', loadComponent: () => import('./features/dashboard/dashboard.component').then(m => m.DashboardComponent) },
    { path: 'analyses', loadComponent: () => import('./features/analyses/analyses.component').then(m => m.AnalysesComponent) },
    { path: 'tasks/new', loadComponent: () => import('./features/task-wizard/task-wizard.component').then(m => m.TaskWizardComponent) },
    { path: 'tasks/:id/edit', loadComponent: () => import('./features/task-wizard/task-wizard.component').then(m => m.TaskWizardComponent) },
    { path: 'tasks/:id', loadComponent: () => import('./features/task-detail/task-detail.component').then(m => m.TaskDetailComponent) },
    { path: 'logs', loadComponent: () => import('./features/logs/logs.component').then(m => m.LogsComponent) },
    { path: 'settings', loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent) },
  ]},
  { path: '**', redirectTo: '' }
];
