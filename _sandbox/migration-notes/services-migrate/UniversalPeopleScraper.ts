
import { zabasearchService } from './zabasearchService.ts';
import type { ZabasearchProfile } from './zabasearchService.ts';

// ----------------------------------------------------------------------------
// Exported Types & Interfaces for consistent use across modules
// ----------------------------------------------------------------------------

export interface Phone {
  number: string;
  type?: string;
  primary?: boolean;
}

export interface Email {
  email: string;
  type?: string;
}

export interface Address {
  address: string;
  city?: string;
  state?: string;
  zip?: string;
  type?: string;
}

export interface Relative {
  name: string;
  relationship?: string;
  age?: string;
}

export interface Alias {
  alias: string;
}

export interface Job {
  company: string;
  title?: string;
  location?: string;
}

export interface OnlinePresence {
  platform: string;
  handle?: string;
  match_reason?: string;
}

export interface FamilyRecord {
  name: string;
  age?: string;
}

export interface PersonProfile {
  id: string;
  name: string;
  age?: string;
  phone_snippet?: string;
  city_state?: string;
  detail_link?: string; // Link to the full profile
  
  // Detailed scraped data
  phones?: Phone[];
  emails?: Email[];
  addresses?: Address[];
  relatives?: Relative[];
  aliases?: Alias[];
  jobs?: Job[];
  
  // New fields for detailed scraping
  online_presence?: OnlinePresence[];
  family_records?: FamilyRecord[];
  legal_records?: string[]; // Placeholders for now
  background_records?: string[];
  professional_records?: string[];
  assets?: string[];
  
  source: string; // To track where the data came from
}

export interface ScrapingStrategy {
  name: string;
  scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]>;
}

export interface PhoneScrapingStrategy {
  name: string;
  scrape(phone: string): Promise<PersonProfile[]>;
}

// ----------------------------------------------------------------------------
// Base Class for Shared Logic (CORS, Fetching)
// ----------------------------------------------------------------------------

export abstract class BaseScraper implements ScrapingStrategy {
  abstract name: string;
  
  // Shared CORS proxies
  protected corsProxies = [
    'https://corsproxy.io/?',
    'https://api.codetabs.com/v1/proxy?quest=',
    'https://api.allorigins.win/raw?url='
  ];

  abstract scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]>;

  protected formatNameForUrl(name: string): string {
    return name.toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '');
  }

  protected async fetchWithProxy(targetUrl: string): Promise<string | null> {
    console.log(`🔍 ${this.name} - Target URL:`, targetUrl);

    for (let i = 0; i < this.corsProxies.length; i++) {
      const proxy = this.corsProxies[i];
      const proxyUrl = `${proxy}${encodeURIComponent(targetUrl)}`;
      
      console.log(`🔍 ${this.name} - Trying proxy ${i + 1}/${this.corsProxies.length}:`, proxy);
      
      try {
        const response = await fetch(proxyUrl, {
          method: 'GET',
          headers: {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
          }
        });

        if (!response.ok) {
          console.log(`🔍 ${this.name} - Proxy ${i + 1} failed with status:`, response.status);
          continue;
        }

        const html = await response.text();
        
        // Check for common blocking patterns
        if (html.includes('Just a moment...') || html.includes('Checking your browser') || html.includes('Access denied')) {
          console.log(`🔍 ${this.name} - Proxy ${i + 1} got blocked/challenge page, trying next...`);
          continue;
        }
        
        console.log(`🔍 ${this.name} - Proxy ${i + 1} success! HTML length:`, html.length);
        return html;
        
      } catch (error) {
        console.error(`🔍 ${this.name} - Proxy ${i + 1} error:`, error);
        continue;
      }
    }
    
    console.log(`🔍 ${this.name} - All proxies failed`);
    return null;
  }



  protected async parseHtml(html: string): Promise<Document> {
    if (typeof window === 'undefined' || typeof (global as any).DOMParser === 'undefined') {
      // Running in Node.js, use jsdom
      const { JSDOM } = await import('jsdom');
      const dom = new JSDOM(html);
      return dom.window.document;
    } else {
      // Running in a browser, use native DOMParser
      const parser = new DOMParser();
      return parser.parseFromString(html, 'text/html');
    }
  }
}

// ----------------------------------------------------------------------------
// Strategy: ZabaSearch (Wrapper around existing service)
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Strategy: ZabaSearch
// ----------------------------------------------------------------------------

class ZabaSearchStrategy extends BaseScraper {
  name = 'ZabaSearch';

  async scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    const formattedName = `${this.formatNameForUrl(firstName)}-${this.formatNameForUrl(lastName)}`;
    let url = `https://www.zabasearch.com/people/${formattedName}`;
    
    // ZabaSearch uses state in URL: /people/john-smith/missouri
    if (state) {
      // Basic state mapping or slugification
      const stateSlug = state.toLowerCase().replace(/\s+/g, '-');
      url += `/${stateSlug}`;
    }

    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = this.parseHtml(html);
    return this.parseProfiles(doc);
  }

  private parseProfiles(doc: Document): PersonProfile[] {
    const profiles: PersonProfile[] = [];
    
    // Try multiple selectors for person divs
    const selectors = ['div.person', '.result-item', '[data-person]', '.listing', '.record', '.entry', '.profile-card'];
    let personDivs: Element[] = [];
    
    for (const selector of selectors) {
      const found = doc.querySelectorAll(selector);
      if (found.length > 0) {
        personDivs = Array.from(found);
        break;
      }
    }

    personDivs.forEach((div, index) => {
      try {
        // Name
        const nameElement = div.querySelector('#container-name h2 a, #container-name h2');
        const name = nameElement?.textContent?.trim() || '';
        if (!name) return;

        // Age
        const dataAge = div.getAttribute('data-age');
        const age = dataAge || div.querySelector('.flex > div:nth-child(2) h3')?.textContent?.trim() || undefined;

        // Location
        let location = div.getAttribute('data-location') || '';
        if (!location) {
            const addressElement = div.querySelector('.section-box:has(h3:contains("Last Known Address")) p');
            if (addressElement) {
                const lines = (addressElement.textContent || '').split('\n');
                if (lines.length > 1) location = lines[1].trim();
            }
        }

        // Phone
        let phone = undefined;
        const phoneElements = div.querySelectorAll('h4');
        for (const phoneEl of phoneElements) {
            const phoneText = phoneEl.textContent?.trim() || '';
            if (phoneText.match(/\(\d{3}\)\s\d{3}-\d{4}/)) {
                phone = phoneText.split(' ')[0];
                break;
            }
        }

        // Detailed Data Extraction (Phones, Emails, etc.)
        const details = this.extractDetailedData(div);

        profiles.push({
          id: `zs-${index}`,
          name: name,
          age: age,
          city_state: location,
          phone_snippet: phone,
          phones: details.phones,
          emails: details.emails,
          addresses: details.addresses,
          relatives: details.relatives,
          aliases: details.aliases,
          jobs: details.jobs,
          source: 'ZabaSearch'
        });

      } catch (e) {
        console.error(`Error parsing ZabaSearch card ${index}:`, e);
      }
    });

    return profiles;
  }

  private extractDetailedData(div: Element) {
    const phones: Array<{number: string, type?: string, primary?: boolean}> = [];
    const emails: Array<{email: string, type?: string}> = [];
    const addresses: Array<{address: string, city?: string, state?: string, zip?: string, type?: string}> = [];
    const relatives: Array<{name: string, relationship?: string, age?: string}> = [];
    const aliases: Array<{alias: string}> = [];
    const jobs: Array<{company: string, title?: string, location?: string}> = [];

    // Phones
    const phoneLinks = div.querySelectorAll('a[href*="/phone/"]');
    phoneLinks.forEach(link => {
        const txt = link.textContent?.trim();
        if (txt && txt.match(/\(\d{3}\)\s\d{3}-\d{4}/)) {
            phones.push({ number: txt, type: 'unknown' });
        }
    });

    // Emails
    const emailElements = div.querySelectorAll('li');
    emailElements.forEach(li => {
        if (li.querySelector('.blur') && li.textContent?.includes('@')) {
            emails.push({ email: li.textContent.trim(), type: 'unknown' });
        }
    });

    // Relatives
    const h3Elements = div.querySelectorAll('h3');
    let relativesSection = null;
    for (const h3 of h3Elements) {
        if (h3.textContent?.includes('Possible Relatives')) {
            relativesSection = h3;
            break;
        }
    }
    if (relativesSection) {
        const links = relativesSection.parentElement?.querySelectorAll('a');
        links?.forEach(link => {
            if (link.textContent) relatives.push({ name: link.textContent.trim() });
        });
    }

    // Addresses (Last Known)
    let addressSection = null;
    for (const h3 of h3Elements) {
        if (h3.textContent?.includes('Last Known Address')) {
            addressSection = h3;
            break;
        }
    }
    if (addressSection) {
        const p = addressSection.parentElement?.querySelector('.flex p');
        if (p && p.textContent) {
            addresses.push({ address: p.textContent.trim(), type: 'current' });
        }
    }

    return { phones, emails, addresses, relatives, aliases, jobs };
  }
}

// ----------------------------------------------------------------------------
// Strategy: FastPeopleSearch
// ----------------------------------------------------------------------------

class FastPeopleSearchStrategy extends BaseScraper {
  name = 'FastPeopleSearch';

  async scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    const formattedName = `${this.formatNameForUrl(firstName)}-${this.formatNameForUrl(lastName)}`;
    let url = `https://www.fastpeoplesearch.com/name/${formattedName}`;
    
    if (city && state) {
      const formattedCity = this.formatNameForUrl(city);
      const formattedState = this.formatNameForUrl(state);
      url = `https://www.fastpeoplesearch.com/name/${formattedName}_${formattedCity}-${formattedState}`;
    }

    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = this.parseHtml(html);
    const profiles: PersonProfile[] = [];

    // Selectors based on typical FastPeopleSearch structure (may need adjustment)
    // They often use schema.org microdata
    const peopleCards = doc.querySelectorAll('div[itemtype="http://schema.org/Person"], .people-list-item, .card');

    peopleCards.forEach((card, index) => {
      try {
        const nameEl = card.querySelector('[itemprop="name"], .name, h2');
        const name = nameEl?.textContent?.trim() || '';
        
        if (!name) return;

        const ageEl = card.querySelector('[itemprop="birthDate"], .age'); // Often just "Age: 50" text
        const age = ageEl?.textContent?.replace('Age:', '').trim();

        const addressEl = card.querySelector('[itemprop="address"], .address');
        const cityState = addressEl?.textContent?.trim();

        // Phones
        const phones: Array<{number: string, type?: string, primary?: boolean}> = [];
        const phoneEls = card.querySelectorAll('[itemprop="telephone"], a[href^="tel:"]');
        phoneEls.forEach(el => {
          phones.push({ number: el.textContent?.trim() || '', type: 'unknown' });
        });

        profiles.push({
          id: `fps-${index}`,
          name,
          age,
          city_state: cityState,
          phones,
          source: 'FastPeopleSearch'
        });
      } catch (e) {
        console.error(`Error parsing FastPeopleSearch card ${index}:`, e);
      }
    });

    return profiles;
  }
}

// ----------------------------------------------------------------------------
// Strategy: TruePeopleSearch
// ----------------------------------------------------------------------------

class TruePeopleSearchStrategy extends BaseScraper {
  name = 'TruePeopleSearch';

  async scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    const nameParam = encodeURIComponent(`${firstName} ${lastName}`);
    let url = `https://www.truepeoplesearch.com/results?name=${nameParam}`;
    
    if (city && state) {
      const locParam = encodeURIComponent(`${city}, ${state}`);
      url += `&citystatezip=${locParam}`;
    }

    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = this.parseHtml(html);
    const profiles: PersonProfile[] = [];

    // TruePeopleSearch often uses cards with class .card or similar structure
    const cards = doc.querySelectorAll('.card, .card-summary');

    cards.forEach((card, index) => {
      try {
        const name = card.querySelector('.h4, .card-title')?.textContent?.trim() || '';
        if (!name) return;

        const ageStr = card.querySelector('span:contains("Age"), .age-text')?.textContent || '';
        const age = ageStr.replace(/\D/g, '');

        const location = card.querySelector('.content-value, .address')?.textContent?.trim();

        const phones: Array<{number: string, type?: string, primary?: boolean}> = [];
        // Look for phone links
        const phoneLinks = card.querySelectorAll('a[href^="tel:"]');
        phoneLinks.forEach(link => {
          phones.push({ number: link.textContent?.trim() || '', type: 'unknown' });
        });

        profiles.push({
          id: `tps-${index}`,
          name,
          age,
          city_state: location,
          phones,
          source: 'TruePeopleSearch'
        });
      } catch (e) {
        console.error(`Error parsing TruePeopleSearch card ${index}:`, e);
      }
    });

    return profiles;
  }
}

// ----------------------------------------------------------------------------
// Strategy: ClustrMaps
// ----------------------------------------------------------------------------

class ClustrMapsStrategy extends BaseScraper {
  name = 'ClustrMaps';

  async scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    // Direct person URL pattern: https://clustrmaps.com/persons/John-Smith
    const formattedName = `${firstName}-${lastName}`;
    const url = `https://clustrmaps.com/persons/${formattedName}`;

    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = this.parseHtml(html);
    const profiles: PersonProfile[] = [];

    // Based on inspection:
    // Container seems to be related to schema.org/Person or just a list of divs
    // The subagent saw "a.persons" containing the name.
    
    // We'll look for containers that have "itemtype='http://schema.org/Person'" or similar
    // Or iterate through elements that look like cards.
    
    // ClustrMaps structure often looks like:
    // <div class="row" itemtype="http://schema.org/Person" itemscope>
    //   <div class="col-md-8">
    //      <a class="persons" itemprop="url" href="..."> <span itemprop="name">Name</span> </a>
    //      ...
    
    const personContainers = doc.querySelectorAll('[itemtype="http://schema.org/Person"], .person-container'); // Fallback class

    // If schema.org selector fails, try finding the 'a.persons' and going up to parent
    let containersToProcess = Array.from(personContainers);
    if (containersToProcess.length === 0) {
      const nameLinks = doc.querySelectorAll('a.persons');
      nameLinks.forEach(link => {
        // Go up to a reasonable container (e.g., a div wrapper)
        const container = link.closest('div.row') || link.parentElement;
        if (container) containersToProcess.push(container as Element);
      });
    }

    containersToProcess.forEach((container, index) => {
      try {
        const nameEl = container.querySelector('[itemprop="name"], a.persons span');
        const name = nameEl?.textContent?.trim() || '';
        if (!name) return;

        // Age often next to name or in a separate span
        // "John Smith 50" -> sometimes text node next to name
        const ageEl = container.querySelector('.age, [itemprop="age"]'); // Hypothetical class
        let age = ageEl?.textContent?.trim();
        
        // Address
        const addressEl = container.querySelector('[itemprop="address"], .address');
        const cityState = addressEl?.textContent?.trim();

        profiles.push({
          id: `cm-${index}`,
          name,
          age,
          city_state: cityState,
          source: 'ClustrMaps'
        });
      } catch (e) {
        console.error(`Error parsing ClustrMaps card ${index}:`, e);
      }
    });

    return profiles;
  }
}

// ----------------------------------------------------------------------------
// Strategy: AnyWho
// ----------------------------------------------------------------------------

class AnyWhoStrategy extends BaseScraper {
  name = 'AnyWho';

  private stateNames: {[key: string]: string} = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas', 'CA': 'california',
    'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware', 'DC': 'district-of-columbia',
    'FL': 'florida', 'GA': 'georgia', 'HI': 'hawaii', 'ID': 'idaho', 'IL': 'illinois',
    'IN': 'indiana', 'IA': 'iowa', 'KS': 'kansas', 'KY': 'kentucky', 'LA': 'louisiana',
    'ME': 'maine', 'MD': 'maryland', 'MA': 'massachusetts', 'MI': 'michigan', 'MN': 'minnesota',
    'MS': 'mississippi', 'MO': 'missouri', 'MT': 'montana', 'NE': 'nebraska', 'NV': 'nevada',
    'NH': 'new-hampshire', 'NJ': 'new-jersey', 'NM': 'new-mexico', 'NY': 'new-york',
    'NC': 'north-carolina', 'ND': 'north-dakota', 'OH': 'ohio', 'OK': 'oklahoma', 'OR': 'oregon',
    'PA': 'pennsylvania', 'RI': 'rhode-island', 'SC': 'south-carolina', 'SD': 'south-dakota',
    'TN': 'tennessee', 'TX': 'texas', 'UT': 'utah', 'VT': 'vermont', 'VA': 'virginia',
    'WA': 'washington', 'WV': 'west-virginia', 'WI': 'wisconsin', 'WY': 'wyoming'
  };

  async scrape(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    // URL Pattern: https://www.anywho.com/people/james+oehring/missouri/cameron
    const formattedName = `${this.formatNameForUrl(firstName)}+${this.formatNameForUrl(lastName)}`;
    let url = `https://www.anywho.com/people/${formattedName}`;
    
    if (state) {
      const stateName = this.stateNames[state.toUpperCase()] || state.toLowerCase();
      url += `/${stateName}`;
      
      if (city) {
        const formattedCity = this.formatNameForUrl(city);
        url += `/${formattedCity}`;
      }
    }

    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = this.parseHtml(html);
    const profiles: PersonProfile[] = [];

    // Strategy: Find all h2 elements (names usually) and traverse up to find the card container.
    const h2Elements = Array.from(doc.querySelectorAll('h2'));
    
    const cards = h2Elements.map(h2 => {
      const h2Text = h2.textContent?.trim() || '';
      // Filter out UI headers: Must contain at least part of the name we're looking for
      if (!h2Text.toLowerCase().includes(firstName.toLowerCase()) && 
          !h2Text.toLowerCase().includes(lastName.toLowerCase())) {
        return null;
      }

      // Go up to find the container that has "Lives in:"
      let parent = h2.parentElement;
      let attempts = 0;
      while (parent && attempts < 5) {
        if (parent.textContent?.includes('Lives in:')) {
          return { card: parent, nameH2: h2 };
        }
        parent = parent.parentElement;
        attempts++;
      }
      return null;
    }).filter(item => item !== null);

    // Deduplicate cards based on the card element
    const uniqueItems = [];
    const seenCards = new Set();
    
    for (const item of cards) {
      if (item && !seenCards.has(item.card)) {
        seenCards.add(item.card);
        uniqueItems.push(item);
      }
    }

    uniqueItems.forEach((item, index) => {
      try {
        const card = item!.card;
        const text = card.textContent || '';
        
        // Name: Use the h2 we validated
        let name = item!.nameH2.textContent?.trim() || '';
        
        // Age: Look for "Age X" pattern
        const ageMatch = text.match(/Age\s+(\d+)/);
        const age = ageMatch ? ageMatch[1] : undefined;

        // Address ("Lives in:")
        let cityState = undefined;
        // Match "Lives in:" followed by text until "Used to live" or "Phone" or end of line
        // The text often contains the full address "413 Lovers Ln, Cameron, MO"
        const addressMatch = text.match(/Lives in:\s*([^]+?)(?:Used to live|Phone|Email|Related to|$)/);
        if (addressMatch) {
            // Clean up the address string
            let addr = addressMatch[1].trim();
            // If it's too long or contains newlines, take the first line or reasonable chunk
            const lines = addr.split('\n');
            if (lines.length > 0) addr = lines[0].trim();
            cityState = addr;
        }

        // Phone
        const phones: Array<{number: string, type?: string, primary?: boolean}> = [];
        const phoneMatch = text.match(/Phone number\(s\):\s*(\(\d{3}\)\s*\d{3}-\d{4})/);
        if (phoneMatch) {
            phones.push({ number: phoneMatch[1], type: 'unknown', primary: true });
        }

        // AKA (Aliases)
        const aliases: Array<{alias: string}> = [];
        // Match "AKA:" followed by text until "Lives in" or "Related to" or end
        const akaMatch = text.match(/AKA:\s*([^]+?)(?:Lives in|Related to|Phone|Email|$)/);
        if (akaMatch) {
            const akaText = akaMatch[1].trim();
            // Split by "•" or ","
            const names = akaText.split(/[•,]/).map(n => n.trim()).filter(n => n.length > 0);
            names.forEach(alias => aliases.push({ alias }));
        }

        // Relatives
        const relatives: Array<{name: string, relationship?: string, age?: string}> = [];
        // Match "Related to:" or "May be related to:"
        const relMatch = text.match(/(?:Related to|May be related to):\s*([^]+?)(?:Lives in|Phone|Email|AKA|$)/);
        if (relMatch) {
            const relText = relMatch[1].trim();
            // Split by "•" or ","
            const names = relText.split(/[•,]/).map(n => n.trim()).filter(n => n.length > 0);
            names.forEach(name => relatives.push({ name, relationship: 'Possible Relative' }));
        }

        // Extract "View Details" link
        let detailLink = undefined;
        const links = card.querySelectorAll('a');
        for (const link of links) {
          if (link.textContent?.includes('View Details')) {
            const href = link.getAttribute('href');
            if (href) {
              detailLink = href.startsWith('http') ? href : `https://www.anywho.com${href}`;
            }
            break;
          }
        }

        profiles.push({
          id: `aw-${index}`,
          name: name || `${firstName} ${lastName}`,
          age,
          city_state: cityState,
          phones,
          aliases,
          relatives,
          detail_link: detailLink,
          source: 'AnyWho'
        });
      } catch (e) {
        console.error(`Error parsing AnyWho card ${index}:`, e);
      }
    });

    return profiles;
  }

  /**
   * Scrape detailed profile from a specific URL.
   */
  async scrapeDetails(url: string): Promise<PersonProfile | null> {
    console.log(`🔍 AnyWho - Scraping details from: ${url}`);
    const html = await this.fetchWithProxy(url);
    if (!html) return null;

    const doc = this.parseHtml(html);
    
    // Extract Name and Age from header
    const nameEl = doc.querySelector('h1, .profile-name'); // Heuristic
    const name = nameEl?.textContent?.trim() || '';
    
    // Initialize profile structure
    const profile: PersonProfile = {
      id: 'details',
      name: name,
      source: 'AnyWho',
      phones: [],
      emails: [],
      addresses: [],
      online_presence: [],
      family_records: [],
      legal_records: [],
      background_records: [],
      professional_records: [],
      assets: []
    };

    // Helper to find section by ID or Header text
    const findSection = (id: string, headerText: string) => {
      let section = doc.getElementById(id);
      if (!section) {
        // Try finding by header text
        const headers = Array.from(doc.querySelectorAll('h2, h3, h4'));
        const header = headers.find(h => h.textContent?.toLowerCase().includes(headerText.toLowerCase()));
        if (header) {
          // Return the container (often parent or next sibling)
          return header.parentElement; 
        }
      }
      return section;
    };

    // 1. Contact Numbers
    const phoneSection = findSection('phones', 'Phone Numbers');
    if (phoneSection) {
      const phoneItems = phoneSection.querySelectorAll('.phone-item, li, div'); // Generic selectors
      phoneItems.forEach(item => {
        const text = item.textContent?.trim();
        const match = text?.match(/\(\d{3}\)\s*\d{3}-\d{4}/);
        if (match) {
           profile.phones?.push({ number: match[0], type: 'unknown' });
        }
      });
    }

    // 2. Emails
    const emailSection = findSection('emails', 'Email Addresses');
    if (emailSection) {
      const emailItems = emailSection.querySelectorAll('li, div');
      emailItems.forEach(item => {
        const text = item.textContent?.trim();
        if (text && text.includes('@')) {
          profile.emails?.push({ email: text, type: 'unknown' });
        }
      });
    }

    // 3. Address History
    const addressSection = findSection('addresses', 'Address History');
    if (addressSection) {
      // Look for current and previous
      const addressItems = addressSection.querySelectorAll('.address-item, li, div');
      addressItems.forEach(item => {
        const text = item.textContent?.trim();
        if (text && text.length > 10 && /\d+/.test(text)) { // Basic validation
           profile.addresses?.push({ address: text, type: 'history' });
        }
      });
    }

    // 4. Online Presence
    const socialSection = findSection('social-media', 'Social Media');
    if (socialSection) {
      const items = socialSection.querySelectorAll('li, div');
      items.forEach(item => {
        const text = item.textContent?.trim() || '';
        // Example: "Twitter - Matched by Username: joehring"
        // Or just "Twitter" then "Matched by..."
        if (text.includes('Matched by')) {
          // Try to split "Platform - Matched by..."
          const parts = text.split('-');
          if (parts.length >= 2) {
             const platform = parts[0].trim();
             const matchReason = parts.slice(1).join('-').trim();
             // Avoid adding duplicates or garbage
             if (platform.length < 20 && !platform.includes('Matched')) {
                 profile.online_presence?.push({ platform, match_reason: matchReason });
             }
          } else {
             // Fallback if no hyphen
             profile.online_presence?.push({ platform: 'Unknown', match_reason: text });
          }
        }
      });
    }

    // 5. Family Records
    const familySection = findSection('family', 'Possible Relatives');
    if (familySection) {
      // Look for specific relative cards or list items
      // Structure seems to be: "Relative data result: NameGender•Age..."
      const items = familySection.querySelectorAll('li, div');
      const seenNames = new Set<string>();
      
      items.forEach(item => {
        const text = item.textContent?.trim() || '';
        
        if (text.includes('Relative data result:')) {
           // Extract "Rickilinda Oehring" from "Relative data result: Rickilinda OehringFemale•64..."
           const cleanText = text.replace('Relative data result:', '').trim();
           // Split by "Female" or "Male" or "•"
           const nameMatch = cleanText.match(/^([^•]+?)(?:Female|Male|•|$)/);
           
           if (nameMatch) {
             const name = nameMatch[1].trim();
             // Try to find age
             const ageMatch = cleanText.match(/•\s*(\d+)/);
             const age = ageMatch ? ageMatch[1] : undefined;
             
             if (name && !seenNames.has(name)) {
               seenNames.add(name);
               profile.family_records?.push({ name, age });
             }
           }
        }
      });
    }

    // 6. Other Records (Placeholders as specific structure is vague without deep inspection)
    // Just capturing presence for now
    if (findSection('court-records', 'Criminal')) profile.legal_records?.push('Found Criminal/Traffic Records');
    if (findSection('personal-history', 'Background')) profile.background_records?.push('Found Background Info');
    
    return profile;
  }
}

// ----------------------------------------------------------------------------
// Universal Factory / Context
// ----------------------------------------------------------------------------

export class UniversalPeopleScraper {
  private strategies: {[key: string]: ScrapingStrategy} = {};

  constructor() {
    this.registerStrategy(new ZabaSearchStrategy());
    this.registerStrategy(new FastPeopleSearchStrategy());
    this.registerStrategy(new TruePeopleSearchStrategy());
    this.registerStrategy(new ClustrMapsStrategy());
    this.registerStrategy(new AnyWhoStrategy());
  }

  registerStrategy(strategy: ScrapingStrategy) {
    this.strategies[strategy.name.toLowerCase()] = strategy;
  }

  /**
   * Main entry point for scraping.
   * @param siteName The name of the site to scrape (e.g., "zabasearch", "fastpeoplesearch")
   * @param firstName Target first name
   * @param lastName Target last name
   * @param city Optional city
   * @param state Optional state
   */
  async scrape(siteName: string, firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    const strategy = this.strategies[siteName.toLowerCase()];
    
    if (!strategy) {
      console.error(`No strategy found for site: ${siteName}`);
      return [];
    }

    console.log(`🚀 Starting scrape for ${siteName} -> ${firstName} ${lastName}`);
    return await strategy.scrape(firstName, lastName, city, state);
  }

  /**
   * Scrape all registered sites in parallel (Use with caution!)
   */
  async scrapeAll(firstName: string, lastName: string, city?: string, state?: string): Promise<PersonProfile[]> {
    const promises = Object.values(this.strategies).map(strategy => 
      strategy.scrape(firstName, lastName, city, state)
        .catch(err => {
          console.error(`Error scraping ${strategy.name}:`, err);
          return [];
        })
    );

    const results = await Promise.all(promises);
    return results.flat();
  }
  
  /**
   * Scrape detailed profile from a specific URL.
   */
  async scrapeDetails(siteName: string, url: string): Promise<PersonProfile | null> {
    const strategy = this.strategies[siteName.toLowerCase()];
    if (!strategy) return null;
    
    // Check if the strategy supports detailed scraping
    if ('scrapeDetails' in strategy) {
      return await (strategy as any).scrapeDetails(url);
    }
    
    console.warn(`Strategy ${siteName} does not support detailed scraping.`);
    return null;
  }
  
  getAvailableSites(): string[] {
    return Object.keys(this.strategies);
  }
}

// Export a singleton instance
export const universalPeopleScraper = new UniversalPeopleScraper();
