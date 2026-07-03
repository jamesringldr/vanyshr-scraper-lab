import * as dotenv from 'dotenv';
dotenv.config();

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseAnonKey = process.env.VITE_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables');
}

const supabase = createClient(supabaseUrl, supabaseAnonKey);

async function testAuth() {
  try {
    // Test signup
    console.log('Testing signup...');
    const { data: signupData, error: signupError } = await supabase.auth.signUp({
      email: 'test.user2@gmail.com', // Changed email
      password: 'testPassword123!',
      options: {
        data: {
          full_name: 'Test User Two'
        }
      }
    });

    if (signupError) {
      throw new Error(`Signup failed: ${signupError.message}`);
    }
    console.log('Signup successful:', signupData);

    // Wait a moment for the trigger to execute
    console.log('\nWaiting for profile creation...');
    await new Promise(resolve => setTimeout(resolve, 2000));

    // Check if profile was created
    if (signupData.user) {
      console.log('\nChecking for profile...');
      const { data: profile, error: profileError } = await supabase
        .from('profiles')
        .select('*')
        .eq('auth_user_id', signupData.user.id)
        .single();

      if (profileError) {
        console.error('Error fetching profile:', profileError);
      } else {
        console.log('Profile created:', profile);
      }
    }

    console.log('\nAuth flow test completed successfully!');
  } catch (error) {
    console.error('Test failed:', error);
  }
}

testAuth();