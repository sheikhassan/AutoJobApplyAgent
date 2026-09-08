import type {NextConfig} from 'next';
const nextConfig: NextConfig={
	reactStrictMode:true,
	poweredByHeader:false,
	...(process.env.VERCEL ? {} : {output:'standalone'}),
};
export default nextConfig;
