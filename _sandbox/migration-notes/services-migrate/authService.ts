import { supabase } from './supabase';
import { User, Session } from '@supabase/supabase-js';

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string;
}

export interface SignUpData {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
}

export interface SignInData {
  email: string;
  password: string;
}

export interface AuthState {
  user: AuthUser | null;
  session: Session | null;
  loading: boolean;
  error: string | null;
}

class AuthService {
  private currentUser: AuthUser | null = null;
  private currentSession: Session | null = null;

  constructor() {
    this.initializeAuth();
  }

  private async initializeAuth() {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      this.currentSession = session;
      await this.setCurrentUser(session.user);
    }

    supabase.auth.onAuthStateChange(async (_event, session) => {
      this.currentSession = session;
      if (session) {
        await this.setCurrentUser(session.user);
      } else {
        this.currentUser = null;
      }
    });
  }

  private async setCurrentUser(user: User) {
    this.currentUser = {
      id: user.id,
      email: user.email || '',
      full_name: user.user_metadata?.full_name || ''
    };
  }

  async signUp(data: SignUpData): Promise<{ user: AuthUser | null; error: string | null }> {
    try {
      console.log('Starting signup process for:', data.email);

      // Determine the redirect URL for email confirmation
      const redirectTo = typeof window !== 'undefined' 
        ? `${window.location.origin}/auth/callback`
        : undefined;

      const { data: authData, error } = await supabase.auth.signUp({
        email: data.email,
        password: data.password,
        options: {
          data: {
            full_name: `${data.first_name} ${data.last_name}`.trim()
          },
          emailRedirectTo: redirectTo
        }
      });

      if (error) {
        console.error('Auth signup error:', error);
        return { user: null, error: error.message };
      }

      // When email confirmations are enabled, the user will be created but not confirmed
      // They need to click the link in their email to confirm
      if (authData.user) {
        const user: AuthUser = {
          id: authData.user.id,
          email: authData.user.email || '',
          full_name: authData.user.user_metadata?.full_name || `${data.first_name} ${data.last_name}`.trim()
        };

        // Note: user.email_confirmed_at will be null until they click the confirmation link
        return { user, error: null };
      }

      return { user: null, error: 'Sign up failed' };
    } catch (error) {
      console.error('Unexpected error during signup:', error);
      return { user: null, error: (error as Error).message };
    }
  }

  async signIn(data: SignInData): Promise<{ user: AuthUser | null; error: string | null }> {
    try {
      const { data: authData, error } = await supabase.auth.signInWithPassword({
        email: data.email,
        password: data.password
      });

      if (error) {
        return { user: null, error: error.message };
      }

      if (authData.user) {
        await this.setCurrentUser(authData.user);
        this.currentSession = authData.session;
        return { user: this.currentUser, error: null };
      }

      return { user: null, error: 'Sign in failed' };
    } catch (error) {
      return { user: null, error: (error as Error).message };
    }
  }

  async sendMagicLink(email: string, redirectTo?: string): Promise<{ error: string | null }> {
    try {
      const redirectTarget =
        redirectTo || (typeof window !== 'undefined' ? `${window.location.origin}/dashboard` : undefined);

      const { error } = await supabase.auth.signInWithOtp({
        email,
        options: {
          emailRedirectTo: redirectTarget,
          shouldCreateUser: true
        }
      });

      return { error: error?.message || null };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }

  async signOut(): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) {
        return { error: error.message };
      }

      this.currentUser = null;
      this.currentSession = null;
      return { error: null };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }

  async resetPassword(email: string): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`
      });

      if (error) {
        return { error: error.message };
      }

      return { error: null };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }

  async updatePassword(newPassword: string): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword
      });

      if (error) {
        return { error: error.message };
      }

      return { error: null };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }

  async signUpWithEmailConfirmation(email: string, password: string, metadata?: any): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: metadata,
          emailRedirectTo: undefined // Disable redirect, use email confirmation
        }
      });
      
      return { error: error?.message || null };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }

  async verifyOTP(email: string, token: string): Promise<{ user: AuthUser | null; error: string | null }> {
    try {
      const { data, error } = await supabase.auth.verifyOtp({
        email,
        token,
        type: 'signup'
      });

      if (error) {
        return { user: null, error: error.message };
      }

      if (data.user) {
        await this.setCurrentUser(data.user);
        this.currentSession = data.session;
        return { user: this.currentUser, error: null };
      }

      return { user: null, error: 'Verification failed' };
    } catch (error) {
      return { user: null, error: (error as Error).message };
    }
  }

  async resendOTP(email: string): Promise<{ error: string | null }> {
    try {
      const { error } = await supabase.auth.resend({
        type: 'signup',
        email: email
      });

      return { error: error?.message || null };
    } catch (error) {
      return { error: (error as Error).message };
    }
  }



  getCurrentUser(): AuthUser | null {
    return this.currentUser;
  }

  getCurrentSession(): Session | null {
    return this.currentSession;
  }

  isAuthenticated(): boolean {
    return !!this.currentUser;
  }

  async refreshSession(): Promise<void> {
    const { data: { session } } = await supabase.auth.getSession();
    if (session) {
      this.currentSession = session;
      await this.setCurrentUser(session.user);
    }
  }
}

export const authService = new AuthService();