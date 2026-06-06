const refreshTokenKey = "scrapegpt_refresh_token";
const userEmailKey = "scrapegpt_user_email";

export function getStoredRefreshToken(): string | null {
  return window.localStorage.getItem(refreshTokenKey);
}

export function setStoredRefreshToken(token: string): void {
  window.localStorage.setItem(refreshTokenKey, token);
}

export function clearStoredRefreshToken(): void {
  window.localStorage.removeItem(refreshTokenKey);
}

export function getStoredUserEmail(): string | null {
  return window.localStorage.getItem(userEmailKey);
}

export function setStoredUserEmail(email: string): void {
  window.localStorage.setItem(userEmailKey, email);
}

export function clearStoredUserEmail(): void {
  window.localStorage.removeItem(userEmailKey);
}
