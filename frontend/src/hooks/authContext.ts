import { createContext } from 'react';
import type { LoginRequest, RegisterRequest, UserSummary } from '../types';

export interface AuthContextType {
  isAuthenticated: boolean;
  username: string | null;
  user: UserSummary | null;
  token: string | null;
  login: (data: LoginRequest) => Promise<void>;
  register: (data: RegisterRequest) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined);
