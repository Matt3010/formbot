import { Injectable, inject, signal } from '@angular/core';
import { ApiService } from './api.service';
import { User } from '../models/user.model';
import { tap } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = inject(ApiService);
  private _isLoggedIn = signal(!!localStorage.getItem('access_token'));
  private _user = signal<User | null>(null);

  isLoggedIn = this._isLoggedIn.asReadonly();
  user = this._user.asReadonly();

  login(email: string, password: string) {
    return this.api.post<{ token: string; user: User }>('/login', { email, password }).pipe(
      tap(res => {
        localStorage.setItem('access_token', res.token);
        this._isLoggedIn.set(true);
        this._user.set(res.user);
      })
    );
  }

  register(name: string, email: string, password: string, password_confirmation: string) {
    return this.api.post<{ token: string; user: User }>('/register', { name, email, password, password_confirmation }).pipe(
      tap(res => {
        localStorage.setItem('access_token', res.token);
        this._isLoggedIn.set(true);
        this._user.set(res.user);
      })
    );
  }

  logout() {
    this.api.post('/logout').subscribe({ error: () => {} });
    localStorage.removeItem('access_token');
    this._isLoggedIn.set(false);
    this._user.set(null);
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  loadUser() {
    return this.api.get<User>('/user').pipe(
      tap(user => this._user.set(user))
    );
  }
}
