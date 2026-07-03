import { supabase } from './supabase';

/**
 * Converts quickscan JSONB data to onboarding format
 * This is used when a user signs up after completing a quickscan
 */
export interface QuickScanOnboardingData {
  legalName?: string;
  age?: { value: string; status?: 'pending' | 'confirmed' };
  primaryMobile?: { value: string; status?: 'pending' | 'confirmed' };
  primaryResidence?: { value: string; status?: 'pending' | 'confirmed' };
  primaryEmail?: { value: string; status?: 'pending' | 'confirmed' };
}

/**
 * Fetches quickscan data and converts it to onboarding format
 * @param scanId The UUID from quick_scans table
 * @returns Onboarding data ready to be used in BasicInformation component
 */
export async function convertQuickScanToOnboarding(
  scanId: string
): Promise<QuickScanOnboardingData | null> {
  try {
    // Fetch the quickscan data
    const { data: scanData, error: scanError } = await supabase
      .from('quick_scans')
      .select('search_input, profile_data')
      .eq('id', scanId)
      .single();

    if (scanError || !scanData) {
      console.error('Error fetching quickscan data:', scanError);
      return null;
    }

    const profileData = scanData.profile_data as any;
    const searchInput = scanData.search_input as any;

    // Extract and format data for onboarding
    const onboardingData: QuickScanOnboardingData = {};

    // Legal Name (from profile_data or search_input)
    const firstName = profileData?.first_name || searchInput?.first_name || '';
    const lastName = profileData?.last_name || searchInput?.last_name || '';
    if (firstName || lastName) {
      onboardingData.legalName = `${firstName} ${lastName}`.trim();
    }

    // Age (from profile_data)
    if (profileData?.age) {
      onboardingData.age = {
        value: profileData.age.toString(),
        status: 'pending',
      };
    }

    // Primary Mobile (from profile_data phones array or search_input)
    const primaryPhone =
      profileData?.phones?.[0]?.number ||
      profileData?.phone ||
      searchInput?.phone ||
      '';
    if (primaryPhone) {
      // Format phone number if needed
      const formattedPhone = formatPhoneNumber(primaryPhone);
      onboardingData.primaryMobile = {
        value: formattedPhone,
        status: 'pending',
      };
    }

    // Primary Residence (from profile_data addresses array)
    const currentAddress = profileData?.addresses?.find(
      (a: any) => a.is_current === true
    ) || profileData?.addresses?.[0];
    if (currentAddress) {
      const addressParts = [
        currentAddress.street,
        currentAddress.city,
        currentAddress.state,
        currentAddress.zip,
      ].filter(Boolean);
      if (addressParts.length > 0) {
        onboardingData.primaryResidence = {
          value: addressParts.join(', '),
          status: 'pending',
        };
      }
    } else if (searchInput?.city && searchInput?.state) {
      // Fallback to search input
      const locationParts = [searchInput.city, searchInput.state].filter(Boolean);
      if (locationParts.length > 0) {
        onboardingData.primaryResidence = {
          value: locationParts.join(', '),
          status: 'pending',
        };
      }
    }

    // Primary Email (from search_input, as that's what was entered)
    if (searchInput?.email) {
      onboardingData.primaryEmail = {
        value: searchInput.email,
        status: 'pending',
      };
    }

    return onboardingData;
  } catch (error) {
    console.error('Error converting quickscan to onboarding data:', error);
    return null;
  }
}

/**
 * Formats a phone number to (XXX) XXX-XXXX format
 */
function formatPhoneNumber(phone: string): string {
  if (!phone) return '';
  // Remove all non-digits
  const digits = phone.replace(/\D/g, '');
  // Format as (XXX) XXX-XXXX
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return phone;
}

/**
 * Gets the pending scanId from localStorage (set during signup)
 * @returns The scanId if found, null otherwise
 */
export function getPendingScanId(): string | null {
  return localStorage.getItem('pending_scan_id');
}

/**
 * Clears the pending scanId from localStorage (after successful conversion)
 */
export function clearPendingScanId(): void {
  localStorage.removeItem('pending_scan_id');
}
