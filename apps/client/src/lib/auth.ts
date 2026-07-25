import { Platform } from 'react-native';

const STORAGE_KEY = 'posted_session_token';

export function getToken(): string | null {
  if (Platform.OS !== 'web') return null;
  return window.localStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string | null): void {
  if (Platform.OS !== 'web') return;
  if (token) {
    window.localStorage.setItem(STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(STORAGE_KEY);
  }
}
