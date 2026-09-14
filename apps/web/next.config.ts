import { config as loadEnv } from "dotenv";
import type { NextConfig } from "next";

// The canonical env file lives at the repo root (shared with the FastAPI
// service, which loads it through pydantic-settings). Next.js only auto-loads
// .env files from the app directory, so without this every NEXT_PUBLIC_* value
// is missing at build and runtime and Supabase auth silently disables itself:
// the login page shows "Authentication is not configured on the client" and the
// middleware lets unauthenticated requests through untouched.
loadEnv({ path: "../../.env" });

const nextConfig: NextConfig = {
  /* config options here */
};

export default nextConfig;
