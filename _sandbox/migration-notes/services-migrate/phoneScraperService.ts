

import { BaseScraper as BaseScraperUtility } from './UniversalPeopleScraper.ts';
import type { PersonProfile, PhoneScrapingStrategy } from './UniversalPeopleScraper.ts';

// ----------------------------------------------------------------------------
// Base Class for Phone Scrapers
// ----------------------------------------------------------------------------

export abstract class BasePhoneScraper extends BaseScraperUtility implements PhoneScrapingStrategy {
  // BaseScraperUtility already has 'name' and 'scrape' methods, but for PhoneScrapingStrategy
  // 'scrape' has a different signature. We need to explicitly redefine it here.
  abstract name: string;
  abstract scrape(phone: string): Promise<PersonProfile[]>;

  // Reuse fetchWithProxy and parseHtml from BaseScraperUtility
  // Note: 'super' is typically used within a constructor or method of a derived class.
  // Here, we are assigning methods from the parent class directly.
  // We need to ensure that 'this' context is correctly bound if these methods depend on 'this.name', etc.
  // For simplicity and to avoid complex binding issues, we'll assume fetchWithProxy and parseHtml are generic enough.
  protected fetchWithProxy = (url: string) => BaseScraperUtility.prototype.fetchWithProxy.call(this, url);
  protected parseHtml = (html: string) => BaseScraperUtility.prototype.parseHtml.call(this, html);
}

// ----------------------------------------------------------------------------
// Strategy: Numlookup
// ----------------------------------------------------------------------------

class NumlookupStrategy extends BasePhoneScraper {
  name = 'Numlookup';

  async scrape(phone: string): Promise<PersonProfile[]> {
    const url = `https://www.numlookup.com/report?phone=${phone}`;

    // Note: Live scraping of Numlookup might be blocked by anti-bot measures or CAPTCHAs.
    // The parsing logic is developed based on the provided numlookup.html static file.
    // For production use, consider more robust proxy rotation, headless browser automation,
    // or CAPTCHA-solving services if direct fetching is consistently blocked.
    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = await this.parseHtml(html);
    return this.parseProfiles(doc);
  }

  private parseProfiles(doc: Document): PersonProfile[] {
    const profiles: PersonProfile[] = [];

    // --- Primary Owner ---
    const ownerNameElement = doc.querySelector('.card-basic-info .ownername-block .text-dark a');
    const ownerName = ownerNameElement?.textContent?.trim();
    console.log('Numlookup: Owner Name Element found:', !!ownerNameElement);
    console.log('Numlookup: Extracted Owner Name:', ownerName);

    if (ownerName) {
      profiles.push({
        id: 'numlookup-primary-owner',
        name: ownerName,
        source: this.name,
        phones: [],
        addresses: [],
      });
    }

    // --- Social Media Account (This data appears to be locked/obfuscated in the HTML) ---
    const socialCard = doc.querySelector('.social-card');
    console.log('Numlookup: Social Card found:', !!socialCard);
    if (socialCard) {
      const socialText = socialCard.textContent;
      if (socialText?.includes('Facebook Profile')) {
        // We can't get the actual link, but we know Facebook was found.
        console.log('Numlookup: Facebook Profile text found in social card.');
        profiles.push({
          id: 'numlookup-social-media-facebook',
          name: ownerName || 'Unknown', // Associate with owner if possible
          source: this.name,
          online_presence: [{ platform: 'Facebook', match_reason: 'Profile Found (Link Hidden)' }],
        });
      }
    }

    // --- Process general cards for "match" information ---
    doc.querySelectorAll('.card').forEach((card, index) => {
      const cardTitleElement = card.querySelector('.card-header .card-title');
      const cardTitle = cardTitleElement?.textContent?.trim();
      console.log(`Numlookup: Card ${index} Title: "${cardTitle}"`);

      // "Another possible X% match:"
      if (cardTitle?.includes('Another possible') && cardTitle.includes('% match')) {
        const profile: PersonProfile = { id: `numlookup-match-${profiles.length}`, source: this.name };
        
        const rows = card.querySelectorAll('.row.mb-2');
        rows.forEach(row => {
          const labelElement = row.querySelector('.h6');
          const valueElement = row.querySelector('.col-sm-9');
          const label = labelElement?.textContent?.trim();
          const value = valueElement?.textContent?.trim();
          
          if (label && value) {
            console.log(`Numlookup:    Card ${index} - Label: "${label}", Value: "${value}"`);
            switch (label) {
              case 'Name':
                profile.name = value;
                break;
              case 'Address':
                profile.addresses = profile.addresses || [];
                profile.addresses.push({ address: value, type: 'current' });
                break;
              case 'Birth Month':
                profile.age = value; // Store as is, needs further parsing if actual age is required
                break;
              case 'Gender':
                // Not directly mapped to PersonProfile for now
                break;
              // Add other fields as needed
            }
          }
        });
        if (profile.name) {
          profiles.push(profile);
        }
      } 
      // "Wow, more matches found: (~70% Match):"
      else if (cardTitle?.includes('more matches') && cardTitle.includes('% Match')) {
        console.log(`Numlookup: Card ${index} - Processing "more matches" section`);
        
        const rows = card.querySelectorAll('.card-body > div > .row.mb-2');
        let profilesInCard: PersonProfile[] = []; // Profiles extracted from this specific card
        let currentProfile: Partial<PersonProfile> = { source: this.name, phones: [], addresses: [] };
        let currentAddress: { address: string, city?: string, state?: string, zip?: string, type?: string } = { address: '' };

        rows.forEach(row => {
          const labelElement = row.querySelector('.h6');
          const valueElement = row.querySelector('.col-sm-9');
          const label = labelElement?.textContent?.trim();
          const value = valueElement?.textContent?.trim();

          if (label && value) {
            console.log(`Numlookup:    More Matches - Label: "${label}", Value: "${value}"`);
            switch (label) {
              case 'firstname':
              case 'full_name':
                // Check if this is a new person or if we should merge with existing
                if (currentProfile.name) {
                  // Finalize current address before pushing profile
                  if (currentAddress.address) {
                      currentProfile.addresses = currentProfile.addresses || [];
                      currentProfile.addresses.push(currentAddress);
                      currentAddress = { address: '' };
                  }
                  // Check for existing profile in this card's temporary list to merge
                  const existingProfileIndex = profilesInCard.findIndex(p => p.name === currentProfile.name);
                  if (existingProfileIndex > -1) {
                      profilesInCard[existingProfileIndex] = { ...profilesInCard[existingProfileIndex], ...currentProfile };
                  } else {
                      profilesInCard.push(currentProfile as PersonProfile);
                  }
                }
                currentProfile = { 
                    id: `numlookup-more-matches-${profiles.length + profilesInCard.length}`, 
                    source: this.name, 
                    phones: [], 
                    addresses: [] 
                };
                currentProfile.name = value;
                break;
              case 'lastname':
                if (currentProfile.name && !currentProfile.name.toLowerCase().includes(value.toLowerCase())) {
                  currentProfile.name = `${currentProfile.name} ${value}`.trim();
                } else if (!currentProfile.name) {
                    currentProfile.name = value;
                }
                break;
              case 'cell_phone':
              case 'work_phone':
                currentProfile.phones = currentProfile.phones || [];
                // Check for duplicates before pushing
                if (!currentProfile.phones.some(p => p.number === value)) {
                  currentProfile.phones.push({ number: value, type: label === 'work_phone' ? 'work' : 'cell' });
                }
                break;
              case 'birthday':
                currentProfile.age = value;
                break;
              case 'address':
                currentAddress.address = value;
                currentAddress.type = 'current';
                break;
              case 'city':
                currentAddress.city = value;
                break;
              case 'state':
                currentAddress.state = value;
                break;
              case 'zip':
                currentAddress.zip = value;
                // Combine address components robustly
                let fullAddress = currentAddress.address;
                const cityStateZipPart = [currentAddress.city, currentAddress.state, currentAddress.zip].filter(Boolean).join(' ');

                if (fullAddress && !fullAddress.includes(cityStateZipPart)) {
                    fullAddress = `${fullAddress}, ${cityStateZipPart}`;
                } else if (!fullAddress) {
                    fullAddress = cityStateZipPart;
                }
                currentAddress.address = fullAddress.trim();

                currentProfile.addresses = currentProfile.addresses || [];
                // Check for duplicates before pushing
                if (!currentProfile.addresses.some(a => a.address === currentAddress.address)) {
                    currentProfile.addresses.push(currentAddress);
                }
                // Also set city_state for the main profile
                if (currentAddress.city && currentAddress.state) {
                  currentProfile.city_state = `${currentAddress.city}, ${currentAddress.state}`;
                } else if (currentAddress.city) {
                  currentProfile.city_state = currentAddress.city;
                } else if (currentAddress.state) {
                  currentProfile.city_state = currentAddress.state;
                }
                currentAddress = { address: '' }; // Reset for next address
                break;
            }
          }
        });

        // Push the last accumulated profile from this card
        if (currentProfile.name) {
          if (currentAddress.address) {
            currentProfile.addresses = currentProfile.addresses || [];
            currentProfile.addresses.push(currentAddress);
          }
          const existingProfileIndex = profilesInCard.findIndex(p => p.name === currentProfile.name);
          if (existingProfileIndex > -1) {
              profilesInCard[existingProfileIndex] = { ...profilesInCard[existingProfileIndex], ...currentProfile };
          } else {
              profilesInCard.push(currentProfile as PersonProfile);
          }
        }
        profiles.push(...profilesInCard); // Add all unique profiles from this card to the main list
      }
    });
    console.log('Numlookup: Final profiles count:', profiles.length);
    return profiles;
  }



}

// ----------------------------------------------------------------------------
// Strategy: TruePeopleSearch (Phone)
// ----------------------------------------------------------------------------

class TruePeopleSearchPhoneStrategy extends BasePhoneScraper {
  name = 'TruePeopleSearchPhone';

  async scrape(phone: string): Promise<PersonProfile[]> {
    const url = `https://www.truepeoplesearch.com/resultphone?phoneno=${phone}`;

    // Note: Live scraping of TruePeopleSearch might be blocked by anti-bot measures or CAPTCHAs.
    // The parsing logic is developed based on the provided TPS.html static file.
    // For production use, consider more robust proxy rotation, headless browser automation,
    // or CAPTCHA-solving services if direct fetching is consistently blocked.
    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = await this.parseHtml(html);
    return this.parseProfiles(doc);
  }

  private parseProfiles(doc: Document): PersonProfile[] {
    const profiles: PersonProfile[] = [];
    const cards = doc.querySelectorAll('.card-summary');

    cards.forEach((card, index) => {
      const nameElement = card.querySelector('.content-header');
      const name = nameElement?.textContent?.trim();

      if (name) {
        const ageElement = card.querySelector('span.content-value');
        const age = ageElement?.textContent?.trim();

        const locationElement = card.querySelectorAll('span.content-value')[1];
        const location = locationElement?.textContent?.trim();

        const pastAddressElement = card.querySelector('.mt-2 .content-value');
        const pastAddress = pastAddressElement?.textContent?.trim();

        const relatedToElement = card.querySelector('.mt-2 + div .content-value');
        const relatedTo = relatedToElement?.textContent?.trim();

        const detailLinkElement = card.querySelector('a.detail-link');
        let detailLink = detailLinkElement?.getAttribute('href');
        if (detailLink && detailLink.startsWith('/')) {
            detailLink = `https://www.truepeoplesearch.com${detailLink}`;
        }
        
        const relativesElement = card.querySelector('div:has(span.content-label:contains("Related to")) .content-value');
        const relativesText = relativesElement?.textContent?.trim();
        const relatives = relativesText ? relativesText.split(', ').map(name => ({ name: name.replace(/\.\.\.$/, '') })) : [];

        const profile: PersonProfile = {
          id: `tps-phone-${index}`,
          name: name,
          age: age,
          city_state: location,
          source: this.name,
          addresses: pastAddress ? [{ address: pastAddress, type: 'past' }] : [],
          relatives: relatives,
          detail_link: detailLink,
        };

        profiles.push(profile);
      }
    });

    return profiles;
  }
}

class ZabasearchPhoneStrategy extends BasePhoneScraper {
  name = 'ZabasearchPhone';

  async scrape(phone: string): Promise<PersonProfile[]> {
    const url = `https://www.zabasearch.com/phone/${phone}`;

    // Note: Live scraping of Zabasearch might be blocked by anti-bot measures or CAPTCHAs.
    // The parsing logic is developed based on the provided zabasearchPhone.html static file.
    // For production use, consider more robust proxy rotation, headless browser automation,
    // or CAPTCHA-solving services if direct fetching is consistently blocked.
    const html = await this.fetchWithProxy(url);
    if (!html) return [];

    const doc = await this.parseHtml(html);
    return this.parseProfiles(doc);
  }

  private parseProfiles(doc: Document): PersonProfile[] {
    const profiles: PersonProfile[] = [];

    // Main profile from #phone-number-result
    const mainResultSection = doc.querySelector('#phone-number-result');
    if (mainResultSection) {
      const profile: PersonProfile = {
        id: 'zabasearch-phone-main',
        source: this.name,
        phones: [],
        addresses: [],
        aliases: [],
        relatives: [],
      };

      // Phone Number (from H1)
      const phoneNumberElement = doc.querySelector('h1 span[itemprop="telephone"]');
      const phoneNumber = phoneNumberElement?.textContent?.trim();
      if (phoneNumber) {
        profile.phones?.push({ number: phoneNumber, type: 'searched' });
      }

      // Name
      const nameElement = mainResultSection.querySelector('h3');
      profile.name = nameElement?.textContent?.trim() || 'Unknown';

      // Age and Birth Year
      const ageElement = mainResultSection.querySelector('tr.column-2 td:nth-child(1)');
      const age = ageElement?.textContent?.trim();
      const birthYearElement = mainResultSection.querySelector('tr.column-2 td:nth-child(2)');
      const birthYear = birthYearElement?.textContent?.trim();
      if (age && birthYear) {
        profile.age = `${age} (Born ${birthYear})`;
      } else if (age) {
        profile.age = age;
      }

      // Location snippet from table (often empty)
      const locationElement = mainResultSection.querySelector('tr:has(th:contains("Location")) td');
      let cityState = locationElement?.textContent?.trim().replace(/, \s*$/, '');
      if (cityState) {
        profile.city_state = cityState;
      }


      // Description
      const descriptionElement = mainResultSection.querySelector('.description p');
      // This often contains snippets about addresses, phones, relatives counts.
      // We'll extract more specific details below.

      profiles.push(profile);
    }

    // Aliases
    const aliasesSection = doc.querySelector('#phone-number-names ul');
    if (aliasesSection) {
      const mainProfile = profiles[0]; // Assume first profile is the main one
      if (mainProfile) {
        aliasesSection.querySelectorAll('li').forEach(li => {
          const alias = li.textContent?.trim();
          if (alias && alias !== mainProfile.name) {
            mainProfile.aliases?.push({ alias });
          }
        });
      }
    }

    // Possible Related Persons
    const relatedPersonsSection = doc.querySelector('#phone-number-related ul');
    if (relatedPersonsSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        relatedPersonsSection.querySelectorAll('li a').forEach(a => {
          const name = a.textContent?.trim();
          if (name) {
            mainProfile.relatives?.push({ name, relationship: 'possible' });
          }
        });
      }
    }

    // Previous Phone Numbers
    const previousPhonesSection = doc.querySelector('#phone-number-previous ul');
    if (previousPhonesSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        previousPhonesSection.querySelectorAll('li a').forEach(a => {
          const number = a.textContent?.trim();
          if (number) {
            mainProfile.phones?.push({ number, type: 'previous' });
          }
        });
      }
    }

    // Possible Emails
    const emailsSection = doc.querySelector('#phone-number-emails ul');
    if (emailsSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        emailsSection.querySelectorAll('li').forEach(li => {
          const emailText = li.textContent?.trim();
          if (emailText && emailText.includes('@')) {
            mainProfile.emails?.push({ email: emailText, type: 'possible' });
          }
        });
      }
    }

    // Locations (Addresses)
    const locationsSection = doc.querySelector('#phone-number-locations');
    if (locationsSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        // Most Recent
        const mostRecentAddress = locationsSection.querySelector('h5:contains("Most Recent") + ul li');
        if (mostRecentAddress) {
          mainProfile.addresses?.push({ address: mostRecentAddress.textContent?.trim() || '', type: 'current' });
        }
        // Possible Previous Locations
        const previousLocations = locationsSection.querySelectorAll('h5:contains("Possible Previous Locations") + ul li');
        previousLocations.forEach(li => {
          mainProfile.addresses?.push({ address: li.textContent?.trim() || '', type: 'past' });
        });
      }
    }
    
    // Professional Licenses
    const licensesSection = doc.querySelector('#phone-number-licenses ul');
    if (licensesSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        licensesSection.querySelectorAll('li').forEach(li => {
          const license = li.textContent?.trim();
          if (license) {
            mainProfile.professional_records = mainProfile.professional_records || [];
            mainProfile.professional_records.push(license);
          }
        });
      }
    }

    // Jobs
    const jobsSection = doc.querySelector('#phone-number-jobs ul');
    if (jobsSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        jobsSection.querySelectorAll('li').forEach(li => {
          const job = li.textContent?.trim();
          if (job) {
            mainProfile.jobs = mainProfile.jobs || [];
            mainProfile.jobs.push({ company: job, title: 'unknown' });
          }
        });
      }
    }

    // Associated Social Media
    const socialMediaSection = doc.querySelector('#phone-number-socialmedia ul');
    if (socialMediaSection) {
      const mainProfile = profiles[0];
      if (mainProfile) {
        socialMediaSection.querySelectorAll('li').forEach(li => {
          const link = li.querySelector('a');
          if (link) {
            const platform = new URL(link.href).hostname;
            mainProfile.online_presence = mainProfile.online_presence || [];
            mainProfile.online_presence.push({ platform, handle: link.href });
          } else {
            // Some social media are listed as plain text without links
            const platform = li.textContent?.trim();
            if (platform) {
                mainProfile.online_presence = mainProfile.online_presence || [];
                mainProfile.online_presence.push({ platform, handle: 'unknown' });
            }
          }
        });
      }
    }

    return profiles;
  }
}

// ----------------------------------------------------------------------------
// Universal Phone Scraper Factory
// ----------------------------------------------------------------------------

// ----------------------------------------------------------------------------
// Universal Phone Scraper Factory
// ----------------------------------------------------------------------------

export class UniversalPhoneScraper {
  private strategies: {[key: string]: PhoneScrapingStrategy} = {};

  constructor() {
    this.registerStrategy(new NumlookupStrategy());
    this.registerStrategy(new TruePeopleSearchPhoneStrategy());
    // Register the new ZabasearchPhoneStrategy
    this.registerStrategy(new ZabasearchPhoneStrategy());
  }

  registerStrategy(strategy: PhoneScrapingStrategy) {
    this.strategies[strategy.name.toLowerCase()] = strategy;
  }

  async scrape(siteName: string, phone: string): Promise<PersonProfile[]> {
    const strategy = this.strategies[siteName.toLowerCase()];
    
    if (!strategy) {
      console.error(`No strategy found for site: ${siteName}`);
      return [];
    }

    console.log(`🚀 Starting phone scrape for ${siteName} -> ${phone}`);
    return await strategy.scrape(phone);
  }

  async scrapeAll(phone: string): Promise<PersonProfile[]> {
    const promises = Object.values(this.strategies).map(strategy => 
      strategy.scrape(phone)
        .catch(err => {
          console.error(`Error scraping ${strategy.name}:`, err);
          return [];
        })
    );

    const results = await Promise.all(promises);
    return results.flat();
  }
  
  getAvailableSites(): string[] {
    return Object.keys(this.strategies);
  }
}

// Export a singleton instance
export const universalPhoneScraper = new UniversalPhoneScraper();


