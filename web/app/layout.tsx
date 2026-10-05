import type { Metadata, Viewport } from 'next';
import '@fontsource/noto-sans-devanagari/400.css';
import '@fontsource/noto-sans-devanagari/700.css';
import './globals.css';
export const metadata: Metadata = { title: 'Pi | Your shop, planned', description: 'AI for merchants: grounded inventory insights and a digital twin of your shop. Ask, test, then decide.', manifest: '/manifest.json' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#071c36' };
export default function Layout({ children }: { children: React.ReactNode }) { return <html lang="en"><body>{children}</body></html>; }
