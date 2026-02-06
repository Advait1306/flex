const AUTH_KEY = "flex_auth";

export function setAuth(username: string, password: string) {
  const token = btoa(`${username}:${password}`);
  sessionStorage.setItem(AUTH_KEY, token);
}

export function getAuth(): string | null {
  return sessionStorage.getItem(AUTH_KEY);
}

export function clearAuth() {
  sessionStorage.removeItem(AUTH_KEY);
}
