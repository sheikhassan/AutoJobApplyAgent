import type {NextConfig} from 'next';
const nextConfig: NextConfig={
	output:'standalone',
	reactStrictMode:true,
	poweredByHeader:false,
	async rewrites(){
		return [{source:'/api/:path*',destination:'http://localhost:8000/api/:path*'},{source:'/auth/:path*',destination:'http://localhost:8000/auth/:path*'},{source:'/health',destination:'http://localhost:8000/health'},{source:'/ready',destination:'http://localhost:8000/ready'}];
	},
};
export default nextConfig;
