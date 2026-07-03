import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables. Please set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY');
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey);

// Database types based on your actual schema
export interface Database {
  public: {
    Tables: {
      profiles: {
        Row: {
          id: string;
          auth_user_id: string;
          full_name: string | null;
          email: string;
          subscription_tier: string | null;
          subscription_status: 'active' | 'inactive' | 'cancelled' | 'past_due';
          stripe_customer_id: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          auth_user_id: string;
          full_name?: string | null;
          email: string;
          subscription_tier?: string | null;
          subscription_status?: 'active' | 'inactive' | 'cancelled' | 'past_due';
          stripe_customer_id?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          auth_user_id?: string;
          full_name?: string | null;
          email?: string;
          subscription_tier?: string | null;
          subscription_status?: 'active' | 'inactive' | 'cancelled' | 'past_due';
          stripe_customer_id?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      family_members: {
        Row: {
          id: string;
          profile_id: string;
          full_name: string;
          relationship: string | null;
          date_of_birth: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          profile_id: string;
          full_name: string;
          relationship?: string | null;
          date_of_birth?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          profile_id?: string;
          full_name?: string;
          relationship?: string | null;
          date_of_birth?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      scans: {
        Row: {
          id: string;
          profile_id: string;
          status: 'pending' | 'in_progress' | 'completed' | 'failed';
          started_at: string;
          completed_at: string | null;
          results_count: number;
          data_types: string[];
          error_message: string | null;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          profile_id: string;
          status?: 'pending' | 'in_progress' | 'completed' | 'failed';
          started_at?: string;
          completed_at?: string | null;
          results_count?: number;
          data_types?: string[];
          error_message?: string | null;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          profile_id?: string;
          status?: 'pending' | 'in_progress' | 'completed' | 'failed';
          started_at?: string;
          completed_at?: string | null;
          results_count?: number;
          data_types?: string[];
          error_message?: string | null;
          created_at?: string;
          updated_at?: string;
        };
      };
      scan_results: {
        Row: {
          id: string;
          scan_id: string;
          data_type: string;
          source: string;
          content: string | null;
          url: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          scan_id: string;
          data_type: string;
          source: string;
          content?: string | null;
          url?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          scan_id?: string;
          data_type?: string;
          source?: string;
          content?: string | null;
          url?: string | null;
          created_at?: string;
        };
      };
      removal_requests: {
        Row: {
          id: string;
          scan_result_id: string;
          profile_id: string;
          status: 'requested' | 'in_progress' | 'completed' | 'failed';
          requested_at: string;
          completed_at: string | null;
          error_message: string | null;
          notes: string | null;
          updated_at: string;
        };
        Insert: {
          id?: string;
          scan_result_id: string;
          profile_id: string;
          status?: 'requested' | 'in_progress' | 'completed' | 'failed';
          requested_at?: string;
          completed_at?: string | null;
          error_message?: string | null;
          notes?: string | null;
          updated_at?: string;
        };
        Update: {
          id?: string;
          scan_result_id?: string;
          profile_id?: string;
          status?: 'requested' | 'in_progress' | 'completed' | 'failed';
          requested_at?: string;
          completed_at?: string | null;
          error_message?: string | null;
          notes?: string | null;
          updated_at?: string;
        };
      };
      notifications: {
        Row: {
          id: string;
          profile_id: string;
          title: string;
          message: string;
          type: string;
          read: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          profile_id: string;
          title: string;
          message: string;
          type: string;
          read?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          profile_id?: string;
          title?: string;
          message?: string;
          type?: string;
          read?: boolean;
          created_at?: string;
        };
      };
    };
  };
}