import { supabase } from './supabase';
import type { 
  Campaign, 
  CampaignMetrics,
  DrilledDownLead,
  AnalyticsFilters
} from '../types';

// New types to match your actual schema
export interface CompanyData {
  uuid: string;
  created_at: string;
  updated_at: string;
  company_name: string;
  state?: string;
  company_url?: string;
  domain?: string;
  email_structure?: string;
  phone?: string;
  city?: string;
  industry?: string;
  category?: string;
  service_type?: string;
  strategic_target?: string;
  company_li_url?: string;
  linkedin_desc?: string;
  company_sales_type?: string;
  company_group?: string;
  funnel_status?: string;
}

export interface PeopleData {
  uuid: string;
  created_at: string;
  updated_at: string;
  data_source?: string;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  contact_company?: string;
  company_uuid?: string;
  contact_title?: string;
  contact_email?: string;
  phone_number?: string;
  company_url?: string;
  li_profile_url?: string;
  li_company_url?: string;
  contact_type?: string;
  contact_group?: string;
  contact_level?: string;
  email_enrich_status?: string;
  email_validation?: string;
}

export interface DealData {
  id: string;
  primary_contact_id: string;
  company_id: string;
  title: string;
  stage: any;
  value: number;
  currency: string;
  target_close_date?: string;
  created_by: string;
  created_at: string;
  updated_at?: string;
}

export interface CampaignAnalyticsData {
  uuid: string;
  created_at: string;
  campaign_name?: string;
  campaign_uuid?: string;
  contact_uuid?: string;
  contact_company?: string;
  contact_name?: string;
  contact_title?: string;
  contact_email?: string;
  send_date?: string;
  sent_status?: string;
  deliver_status?: string;
  bounce_status?: string;
  open_status?: string;
  respond_status?: string;
}

// Company Data Services
export const companyDataService = {
  async getAll(): Promise<CompanyData[]> {
    const { data, error } = await supabase
      .from('company_data')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  },

  async getById(uuid: string): Promise<CompanyData | null> {
    const { data, error } = await supabase
      .from('company_data')
      .select('*')
      .eq('uuid', uuid)
      .single();

    if (error) throw error;
    return data || null;
  },

  async create(company: Omit<CompanyData, 'uuid' | 'created_at' | 'updated_at'>): Promise<CompanyData> {
    const { data, error } = await supabase
      .from('company_data')
      .insert(company)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async update(uuid: string, updates: Partial<CompanyData>): Promise<CompanyData> {
    const { data, error } = await supabase
      .from('company_data')
      .update(updates)
      .eq('uuid', uuid)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async delete(uuid: string): Promise<void> {
    const { error } = await supabase
      .from('company_data')
      .delete()
      .eq('uuid', uuid);

    if (error) throw error;
  }
};

// People Data Services
export const peopleDataService = {
  async getAll(): Promise<PeopleData[]> {
    const { data, error } = await supabase
      .from('people_data')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  },

  async getByCompanyId(companyUuid: string): Promise<PeopleData[]> {
    const { data, error } = await supabase
      .from('people_data')
      .select('*')
      .eq('company_uuid', companyUuid)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  },

  async getById(uuid: string): Promise<PeopleData | null> {
    const { data, error } = await supabase
      .from('people_data')
      .select('*')
      .eq('uuid', uuid)
      .single();

    if (error) throw error;
    return data || null;
  },

  async create(person: Omit<PeopleData, 'uuid' | 'created_at' | 'updated_at'>): Promise<PeopleData> {
    const { data, error } = await supabase
      .from('people_data')
      .insert(person)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async update(uuid: string, updates: Partial<PeopleData>): Promise<PeopleData> {
    const { data, error } = await supabase
      .from('people_data')
      .update(updates)
      .eq('uuid', uuid)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async delete(uuid: string): Promise<void> {
    const { error } = await supabase
      .from('people_data')
      .delete()
      .eq('uuid', uuid);

    if (error) throw error;
  }
};

// Deal Services
export const dealService = {
  async getAll(): Promise<DealData[]> {
    const { data, error } = await supabase
      .from('deals')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  },

  async getByCompanyId(companyId: string): Promise<DealData[]> {
    const { data, error } = await supabase
      .from('deals')
      .select('*')
      .eq('company_id', companyId)
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data || [];
  },

  async getById(id: string): Promise<DealData | null> {
    const { data, error } = await supabase
      .from('deals')
      .select('*')
      .eq('id', id)
      .single();

    if (error) throw error;
    return data || null;
  },

  async create(deal: Omit<DealData, 'id' | 'created_at' | 'updated_at'>): Promise<DealData> {
    const { data, error } = await supabase
      .from('deals')
      .insert(deal)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async update(id: string, updates: Partial<DealData>): Promise<DealData> {
    const { data, error } = await supabase
      .from('deals')
      .update(updates)
      .eq('id', id)
      .select()
      .single();

    if (error) throw error;
    return data;
  },

  async delete(id: string): Promise<void> {
    const { error } = await supabase
      .from('deals')
      .delete()
      .eq('id', id);

    if (error) throw error;
  }
};

// Campaign Services
export const campaignService = {
  async getAll(): Promise<Campaign[]> {
    const { data, error } = await supabase
      .from('campaigns')
      .select('*')
      .order('created_at', { ascending: false });

    if (error) throw error;
    return data?.map(transformCampaignFromDB) || [];
  },

  async getById(id: string): Promise<Campaign | null> {
    const { data, error } = await supabase
      .from('campaigns')
      .select('*')
      .eq('id', id)
      .single();

    if (error) throw error;
    return data ? transformCampaignFromDB(data) : null;
  },

  async create(campaign: Omit<Campaign, 'id' | 'createdAt' | 'updatedAt'>): Promise<Campaign> {
    const { data, error } = await supabase
      .from('campaigns')
      .insert(transformCampaignToDB(campaign))
      .select()
      .single();

    if (error) throw error;
    return transformCampaignFromDB(data);
  },

  async update(id: string, updates: Partial<Campaign>): Promise<Campaign> {
    const { data, error } = await supabase
      .from('campaigns')
      .update(transformCampaignToDB(updates))
      .eq('id', id)
      .select()
      .single();

    if (error) throw error;
    return transformCampaignFromDB(data);
  },

  async delete(id: string): Promise<void> {
    const { error } = await supabase
      .from('campaigns')
      .delete()
      .eq('id', id);

    if (error) throw error;
  }
};

// Campaign Analytics Services
export const campaignAnalyticsService = {
  async getAnalyticsData(filters: AnalyticsFilters): Promise<CampaignAnalyticsData> {
    // Query campaign_analytics table to get real data
    let query = supabase
      .from('campaign_analytics')
      .select('*');
    
    // Filter by campaign if specified
    if (filters.campaignId && filters.campaignId !== '') {
      query = query.eq('campaign_uuid', filters.campaignId);
    }

    const { data: analyticsData, error } = await query;

    if (error) throw error;

    // Aggregate the analytics data
    // const totalRecords = analyticsData?.length || 0;
    const totalSends = analyticsData?.filter(d => d.sent_status?.toLowerCase() === 'y').length || 0;
    const unsent = analyticsData?.filter(d => d.sent_status?.toLowerCase() === 'n').length || 0;
    const delivered = analyticsData?.filter(d => d.deliver_status?.toLowerCase() === 'y').length || 0;
    const opens = analyticsData?.filter(d => d.open_status?.toLowerCase() === 'y').length || 0;
    const responses = analyticsData?.filter(d => d.respond_status?.toLowerCase() === 'y').length || 0;
    const bounces = analyticsData?.filter(d => d.bounce_status?.toLowerCase() === 'y').length || 0;
    
    const metrics: CampaignMetrics = {
      totalSends,
      unsent,
      opens,
      responses,
      bounces,
      clicks: 0, // Not tracked in your schema
      unsubscribes: 0, // Not tracked in your schema
      delivered, // Add delivered to the metrics
    };

    // Transform analytics data to drill-down leads
    const deliveredLeads: DrilledDownLead[] = analyticsData
      ?.filter(d => d.deliver_status?.toLowerCase() === 'y')
      .map(d => ({
        id: d.uuid,
        name: d.contact_name || 'Unknown',
        company: d.contact_company || 'Unknown',
        email: d.contact_email || '',
      })) || [];

    const openedLeads: DrilledDownLead[] = analyticsData
      ?.filter(d => d.open_status?.toLowerCase() === 'y')
      .map(d => ({
        id: d.uuid,
        name: d.contact_name || 'Unknown',
        company: d.contact_company || 'Unknown',
        email: d.contact_email || '',
      })) || [];

    const respondedLeads: DrilledDownLead[] = analyticsData
      ?.filter(d => d.respond_status?.toLowerCase() === 'y')
      .map(d => ({
        id: d.uuid,
        name: d.contact_name || 'Unknown',
        company: d.contact_company || 'Unknown',
        email: d.contact_email || '',
      })) || [];

    const bouncedLeads: DrilledDownLead[] = analyticsData
      ?.filter(d => d.bounce_status?.toLowerCase() === 'y')
      .map(d => ({
        id: d.uuid,
        name: d.contact_name || 'Unknown',
        company: d.contact_company || 'Unknown',
        email: d.contact_email || '',
      })) || [];

    return {
      metrics,
      deliveredLeads,
      openedLeads,
      respondedLeads,
      interactedLeads: [], // Not tracked in your schema
      bouncedLeads,
    };
  },

  async getCampaignAnalytics(campaignName?: string): Promise<CampaignAnalyticsData[]> {
    const { data, error } = await supabase
      .from('campaign_analytics')
      .select('*')
      .eq('campaign_name', campaignName || '');

    if (error) throw error;
    return data || [];
  }
};

// Verification Code Services
export const verificationCodeService = {
  async cleanupOldCodes(): Promise<void> {
    // Delete codes older than 1 hour that are unused
    const { error } = await supabase
      .from('verification_codes')
      .delete()
      .lt('created_at', new Date(Date.now() - 60 * 60 * 1000).toISOString())
      .eq('used', false);

    if (error) {
      console.error('Failed to cleanup old verification codes:', error);
    }
  },

  async cleanupUsedCodes(): Promise<void> {
    // Delete used codes older than 24 hours
    const { error } = await supabase
      .from('verification_codes')
      .delete()
      .lt('created_at', new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString())
      .eq('used', true);

    if (error) {
      console.error('Failed to cleanup used verification codes:', error);
    }
  }
};

// Campaign transformation helpers (keeping these for the Campaign interface compatibility)
function transformCampaignFromDB(dbCampaign: any): Campaign {
  return {
    id: dbCampaign.id,
    name: dbCampaign.name,
    type: dbCampaign.type,
    status: dbCampaign.status,
    startDate: dbCampaign.start_date,
    endDate: dbCampaign.end_date,
  };
}

function transformCampaignToDB(campaign: Partial<Campaign>): any {
  return {
    name: campaign.name,
    type: campaign.type,
    status: campaign.status,
    start_date: campaign.startDate,
    end_date: campaign.endDate,
  };
}
