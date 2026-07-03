import { supabase } from "./supabase";
import { PersonProfile } from "./UniversalPeopleScraper";

/**
 * Service for interacting with the UniversalPeopleScraper edge functions
 */
export class UniversalScraperService {
  /**
   * Search for profiles across multiple data brokers
   * Returns summary profiles (Name, Age, Aliases, Address, Relatives) from search results
   * @param scanId The scan ID (from quick_scans table) or profile ID (from qs_profile table for legacy)
   * @param firstName Target first name
   * @param lastName Target last name
   * @param city Optional city filter
   * @param state Optional state filter
   * @param siteName Optional specific site to search (defaults to 'AnyWho')
   * @param useNewSchema Whether to use new quick_scans schema (defaults to true)
   * @returns Array of summary profiles
   */
  async searchProfiles(
    scanId: string,
    firstName: string,
    lastName: string,
    city?: string,
    state?: string,
    siteName: string = "AnyWho",
    useNewSchema: boolean = true,
  ): Promise<{ profiles: PersonProfile[]; error: string | null }> {
    try {
      console.log("🔍 UniversalScraperService: Searching profiles...", {
        scanId,
        firstName,
        lastName,
        city,
        state,
        siteName,
        useNewSchema,
      });

      const requestBody: any = {
        firstName,
        lastName,
        city,
        state,
        siteName,
      };

      if (useNewSchema) {
        requestBody.scan_id = scanId;
        requestBody.use_new_schema = true;
      } else {
        requestBody.profile_id = scanId;
        requestBody.use_new_schema = false;
      }

      const { data, error } = await supabase.functions.invoke(
        "universal-search",
        {
          body: requestBody,
        },
      );

      if (error) {
        console.error("❌ UniversalScraperService search error:", error);
        return { profiles: [], error: error.message };
      }

      console.log("✅ UniversalScraperService: Search completed", {
        count: data?.profiles?.length || 0,
      });

      // Convert ProfileMatch[] to PersonProfile[] for backward compatibility
      // The new schema returns ProfileMatch[], but frontend expects PersonProfile[]
      const profiles: PersonProfile[] = (data?.profiles || []).map((match: any) => {
        // If it's already a PersonProfile, return as-is
        if (match.phones || match.addresses || match.relatives) {
          return match;
        }
        // If fullProfile is available (e.g., from ZabaSearch), use it
        if (match.fullProfile) {
          return match.fullProfile as PersonProfile;
        }
        // Convert ProfileMatch to PersonProfile (basic fields only)
        return {
          id: match.id,
          name: match.name,
          age: match.age,
          phone_snippet: match.phone_snippet,
          city_state: match.city_state,
          detail_link: match.detail_link,
          source: match.source,
        } as PersonProfile;
      });

      return {
        profiles,
        error: null,
      };
    } catch (error) {
      console.error("💥 UniversalScraperService search exception:", error);
      return {
        profiles: [],
        error: (error as Error).message,
      };
    }
  }

  /**
   * Scrape detailed profile information from a specific URL
   * @param profileId The database profile ID to update
   * @param siteName The name of the site (e.g., 'AnyWho')
   * @param detailLink The URL to scrape details from
   * @param existingProfile Optional existing profile data to preserve/merge
   * @returns The scraped profile data and save result
   */
  async scrapeDetails(
    id: string, // Can be profileId or scanId
    siteName: string,
    detailLink: string,
    existingProfile?: Partial<PersonProfile>,
    use_new_schema: boolean = false,
  ): Promise<
    { profile: PersonProfile | null; saveResult: any; error: string | null }
  > {
    try {
      console.log("🔍 UniversalScraperService: Scraping details...", {
        id,
        siteName,
        detailLink,
        use_new_schema,
        hasExistingProfile: !!existingProfile,
      });

      const body: any = {
        siteName,
        detailLink,
        selected_profile: existingProfile,
      };

      if (use_new_schema) {
        body.scan_id = id;
        body.use_new_schema = true;
      } else {
        body.profile_id = id;
      }

      const { data, error } = await supabase.functions.invoke(
        "universal-details",
        { body },
      );

      if (error) {
        console.error("❌ UniversalScraperService details error:", error);
        return { profile: null, saveResult: null, error: error.message };
      }

      console.log("✅ UniversalScraperService: Details scraped and saved");

      return {
        profile: data?.profile || null,
        saveResult: data?.save_result || null,
        error: null,
      };
    } catch (error) {
      console.error("💥 UniversalScraperService details exception:", error);
      return {
        profile: null,
        saveResult: null,
        error: (error as Error).message,
      };
    }
  }
}

// Export singleton instance
export const universalScraperService = new UniversalScraperService();
