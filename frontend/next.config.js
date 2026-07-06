/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  reactStrictMode: true,
  images: {
    unoptimized: true, // required for static export — Next Image optimiser needs a Node server
    domains: ['localhost'],
  },
}

module.exports = nextConfig
