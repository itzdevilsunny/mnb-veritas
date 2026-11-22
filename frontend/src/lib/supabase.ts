import { createClient } from "@supabase/supabase-js";

const supabaseUrl =
  process.env.NEXT_PUBLIC_SUPABASE_URL ||
  "https://rzgbswkasiddobaaewrq.supabase.co";

const supabaseAnonKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ||
  "sb_publishable_CA1_Nrij5APfcsMIk0y1kA_zAgMLomo";

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
