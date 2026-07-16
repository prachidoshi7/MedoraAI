/**
 * MedoraAI — Auth Provider
 * Provides authentication state and login/logout actions.
 */

import React, { useState, useCallback, useEffect } from 'react';
import { login as apiLogin, logout as apiLogout, setAuthToken } from '../api/client';
import type { LoginRequest } from '../types';
import { AuthContext } from './authContext';

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem('medoraai_token')
  );
  const [username, setUsername] = useState<string | null>(
    localStorage.getItem('medoraai_username')
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (token) {
      setAuthToken(token);
    }
  }, [token]);

  const login = useCallback(async (data: LoginRequest) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiLogin(data);
      setToken(res.access_token);
      setUsername(data.username);
      localStorage.setItem('medoraai_username', data.username);
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Login failed. Please try again.';
      setError(message);
      throw new Error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setToken(null);
    setUsername(null);
    localStorage.removeItem('medoraai_username');
  }, []);

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated: !!token,
        username,
        token,
        login,
        logout,
        loading,
        error,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
