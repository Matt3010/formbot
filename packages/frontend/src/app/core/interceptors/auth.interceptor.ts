import { HttpInterceptorFn } from '@angular/common/http';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  const token = localStorage.getItem('access_token');
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  req = req.clone({ setHeaders: headers });
  return next(req);
};
