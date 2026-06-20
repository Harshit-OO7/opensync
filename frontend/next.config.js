/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ["avatars.githubusercontent.com"],
  },
  env: {
    NEXT_PUBLIC_API_URL: "https://opensync-api.onrender.com",
  },
};

module.exports = nextConfig;