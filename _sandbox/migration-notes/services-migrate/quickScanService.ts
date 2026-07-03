import { supabase } from './supabase';

// New JSONB-based interfaces matching quick_scans table
export interface QuickScan {
  id: string;
  search_input: {
    first_name: string;
    last_name: string;
    email?: string;
    phone?: string;
    zip?: string;
    city?: string;
    state?: string;
  };
  status: 'pending' | 'searching' | 'matches_found' | 'no_matches' | 'completed' | 'expired' | 'failed';
  profile_data?: QuickScanProfileData;
  candidate_matches?: ProfileMatch[];
  selected_match_id?: string;
  scraper_runs?: ScraperRunResult[];
  created_at: string;
  expires_at: string;
}

export interface ProfileMatch {
  id: string;
  name: string;
  age?: string;
  city_state?: string;
  phone_snippet?: string;
  detail_link?: string;
  source?: string;
}

export interface QuickScanProfileData {
  name?: string;
  age?: string;
  phones?: Array<{ number: string; type?: string; provider?: string }>;
  emails?: Array<{ email: string; type?: string }>;
  addresses?: Array<{
    street?: string;
    city?: string;
    state?: string;
    zip?: string;
    full_address?: string;
    is_current?: boolean;
  }>;
  relatives?: Array<{ name: string; relationship?: string; age?: string }>;
  aliases?: Array<{ alias: string }>;
  jobs?: Array<{ company?: string; title?: string; current?: boolean }>;
  education?: Array<{ school?: string; degree?: string }>;
}

export interface ScraperRunResult {
  scraper: string;
  status: 'success' | 'no_results' | 'failed';
  profiles_found?: number;
  duration_ms?: number;
  error?: string;
}

export class QuickScanService {
  /**
   * Create a new quick scan record
   */
  async createQuickScan(data: {
    first_name: string;
    last_name: string;
    phone?: string;
    email?: string;
    zip?: string;
  }): Promise<{ data: QuickScan | null; error: string | null }> {
    try {
      const { data: scanData, error } = await supabase
        .from('quick_scans')
        .insert([{
          search_input: {
            first_name: data.first_name,
            last_name: data.last_name,
            phone: data.phone,
            email: data.email,
            zip: data.zip,
          },
          status: 'pending'
        }])
        .select()
        .single();

      if (error) {
        return { data: null, error: error.message };
      }

      return { data: scanData, error: null };
    } catch (error) {
      return { data: null, error: (error as Error).message };
    }
  }

  /**
   * Get a quick scan by ID
   */
  async getQuickScan(scanId: string): Promise<{ data: QuickScan | null; error: string | null }> {
    try {
      const { data, error } = await supabase
        .from('quick_scans')
        .select('*')
        .eq('id', scanId)
        .single();

      if (error) {
        return { data: null, error: error.message };
      }

      return { data, error: null };
    } catch (error) {
      return { data: null, error: (error as Error).message };
    }
  }

  /**
   * Run the quick scan by invoking the Edge Function
   */
  async runQuickScan(scanId: string): Promise<{ error: string | null; data?: any }> {
    try {
      console.log('🔧 QuickScanService: Calling Edge Function with scanId:', scanId);

      const { data, error } = await supabase.functions.invoke('run-quick-scan', {
        body: { scan_id: scanId }
      });

      console.log('📡 Edge Function raw response:', { data, error });

      if (error) {
        console.error('❌ Edge Function error:', error);
        return { error: error.message };
      }

      console.log('✅ Edge Function success, data:', data);
      return { error: null, data };
    } catch (error) {
      console.error('💥 QuickScanService exception:', error);
      return { error: (error as Error).message };
    }
  }

  /**
   * Select a profile match to get full details
   */
  async selectProfile(
    scanId: string,
    selectedProfile: ProfileMatch
  ): Promise<{ success: boolean; error?: string; data?: any }> {
    try {
      console.log('🔧 QuickScanService: Selecting profile:', selectedProfile.name);

      const { data, error } = await supabase.functions.invoke('run-quick-scan', {
        body: {
          scan_id: scanId,
          selected_profile: selectedProfile
        }
      });

      if (error) {
        return { success: false, error: error.message };
      }

      return { success: true, data };
    } catch (error) {
      console.error('Error selecting profile:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to select profile'
      };
    }
  }

  /**
   * Subscribe to realtime changes for a specific scan
   */
  subscribeToScanStatus(
    scanId: string,
    callback: (scan: QuickScan) => void
  ) {
    return supabase
      .channel(`quick_scans_${scanId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'quick_scans',
          filter: `id=eq.${scanId}`
        },
        (payload) => {
          if (payload.new) {
            callback(payload.new as QuickScan);
          }
        }
      )
      .subscribe();
  }

  /**
   * Fallback polling method for scan status
   */
  async pollScanStatus(
    scanId: string,
    onStatusChange: (scan: QuickScan) => void,
    intervalMs: number = 2000,
    maxAttempts: number = 60
  ): Promise<void> {
    let attempts = 0;

    const poll = async () => {
      if (attempts >= maxAttempts) {
        onStatusChange({
          id: scanId,
          search_input: { first_name: '', last_name: '' },
          status: 'failed',
          created_at: '',
          expires_at: ''
        });
        return;
      }

      const { data, error } = await this.getQuickScan(scanId);

      if (error) {
        console.error('Polling error:', error);
        attempts++;
        setTimeout(poll, intervalMs);
        return;
      }

      if (data) {
        onStatusChange(data);

        // Stop polling if scan is complete or failed
        if (['completed', 'failed', 'expired', 'no_matches'].includes(data.status)) {
          return;
        }
      }

      attempts++;
      setTimeout(poll, intervalMs);
    };

    poll();
  }

  /**
   * Get candidate matches from a scan
   */
  async getCandidateMatches(scanId: string): Promise<{ data: ProfileMatch[] | null; error: string | null }> {
    try {
      const { data, error } = await supabase
        .from('quick_scans')
        .select('candidate_matches')
        .eq('id', scanId)
        .single();

      if (error) {
        return { data: null, error: error.message };
      }

      return { data: data?.candidate_matches || [], error: null };
    } catch (error) {
      return { data: null, error: (error as Error).message };
    }
  }

  /**
   * Get profile data from a completed scan
   */
  async getProfileData(scanId: string): Promise<{ data: QuickScanProfileData | null; error: string | null }> {
    try {
      const { data, error } = await supabase
        .from('quick_scans')
        .select('profile_data')
        .eq('id', scanId)
        .single();

      if (error) {
        return { data: null, error: error.message };
      }

      return { data: data?.profile_data || null, error: null };
    } catch (error) {
      return { data: null, error: (error as Error).message };
    }
  }
}

export const quickScanService = new QuickScanService();
