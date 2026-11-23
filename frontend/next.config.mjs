/** @type {import('next').NextConfig} */
const nextConfig = {
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
  reactStrictMode: true,
  eslint: {
    // Prevents ESLint deprecation notices or peer conflicts from breaking production builds
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
