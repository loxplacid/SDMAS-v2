/** Auth API types matching the FastAPI backend schemas. */

export interface UserLogin {
  login: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserResponse {
  id: number;
  email: string;
  username: string;
  display_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export interface UserUpdate {
  display_name?: string;
  email?: string;
}
