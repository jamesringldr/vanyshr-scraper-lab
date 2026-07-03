import { createClient } from '@supabase/supabase-js';
import * as dotenv from 'dotenv';
dotenv.config();

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables');
}

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function testConnection() {
  try {
    const { data, error } = await supabase.from('profiles').select('count').single();
    
    if (error) {
      console.error('Connection error:', error.message);
      return;
    }
    
    console.log('Successfully connected to Supabase!');
    console.log('Database is ready to use.');
  } catch (err) {
    console.error('Unexpected error:', err);
  }
}

testConnection();