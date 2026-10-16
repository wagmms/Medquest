import type { Metadata, Viewport } from "next";
import { ClerkProvider, SignIn } from '@clerk/nextjs';
import { ptBR } from '@clerk/localizations';
import { auth } from '@clerk/nextjs/server';
import { cookies } from 'next/headers';
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";
import TopNav from "@/components/TopNav";
import { Toaster } from "react-hot-toast";
import { DemoButton } from "@/components/DemoButton";
import { DemoBanner } from "@/components/DemoBanner";
import { SyncProvider } from "@/components/SyncProvider";
import { OnboardingTour } from "@/components/OnboardingTour";
import { WebVitals } from "@/components/WebVitals";
import { AuthSync } from "@/components/AuthSync";

export const viewport: Viewport = {
  themeColor: "#0ea5e9",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  interactiveWidget: "resizes-visual",
};

export const metadata: Metadata = {
  title: "MedQuest",
  description: "A melhor plataforma de estudos para a Residência Médica da USP, com planejamento anual inteligente.",
  manifest: "/manifest.json",
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/icon-192x192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512x512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [
      { url: "/icon-192x192.png", sizes: "192x192", type: "image/png" },
    ],
    shortcut: ["/icon-192x192.png"],
  },
  openGraph: {
    title: "MedQuest",
    description: "A melhor plataforma de estudos para a Residência Médica da USP, com planejamento anual inteligente.",
    url: "https://medquest.live",
    siteName: "MedQuest",
    locale: "pt_BR",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "MedQuest",
    description: "A melhor plataforma de estudos para a Residência Médica da USP, com planejamento anual inteligente.",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "MedQuest",
  },
  formatDetection: {
    telephone: false,
  },
};

import { BottomNav } from "@/components/BottomNav";
import { ClinicalIcon } from "@/components/ui/ClinicalIcon";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { userId } = await auth();
  const cookieStore = await cookies();
  const isDemoMode = cookieStore.get("medquest_demo")?.value === "1";

  return (
    <ClerkProvider localization={ptBR}>
      <html
        lang="pt-BR"
        className="font-sans h-full antialiased"
        suppressHydrationWarning
      >
        <head>
          <script
            dangerouslySetInnerHTML={{
              __html: `
                try {
                  if (localStorage.theme === 'dark' || (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                    document.documentElement.classList.add('dark')
                  } else {
                    document.documentElement.classList.remove('dark')
                  }
                } catch (_) {}
              `
            }}
          />
        </head>
        <body className="h-screen flex overflow-hidden bg-background text-on-background selection:bg-accent/20 selection:text-accent">
          <WebVitals />
          <a href="#conteudo-principal" className="skip-link">Pular para o conteúdo principal</a>
          {!userId && !isDemoMode ? (
            <AuthSync ssrAuthenticated={false}>
              <div className="flex w-full h-full items-start justify-center p-6 bg-background relative overflow-y-auto">
                <div className="relative z-10 flex flex-col items-center max-w-md w-full bg-surface p-6 sm:p-8 rounded-sm border border-line-subtle shadow-lg my-auto">
                  <div className="w-12 h-12 bg-ink-primary text-surface rounded-xs flex items-center justify-center mb-4 shadow-2xs">
                    <ClinicalIcon name="local_hospital" className="w-6 h-6 text-canvas" strokeWidth={2.2} />
                  </div>
                  <h1 className="text-xl font-bold text-ink-primary text-center mb-1">MedQuest Clinical Workspace</h1>
                  <p className="text-ink-secondary text-center mb-6 text-xs">A melhor plataforma de estudos e raciocínio clínico para a Residência Médica.</p>
                  <div className="w-full flex justify-center border-b border-line-subtle pb-6 mb-4">
                    <SignIn routing="hash" fallbackRedirectUrl="/" forceRedirectUrl="/" />
                  </div>
                  <DemoButton />
                </div>
              </div>
            </AuthSync>
          ) : (
            <div className="flex flex-col w-full h-full">
              <DemoBanner />
              <div className="flex flex-1 min-h-0 w-full overflow-hidden">
                <Sidebar />
                <div className="flex-1 flex flex-col w-full min-w-0 bg-background overflow-y-auto overflow-x-hidden">
                  <TopNav />
                  <main id="conteudo-principal" tabIndex={-1} className="flex-1 max-w-[1440px] mx-auto w-full min-w-0 p-3 sm:p-gutter md:p-margin gap-stack-lg flex flex-col pb-20 md:pb-margin relative focus:outline-none overflow-x-hidden">
                    {children}
                  </main>
                  <BottomNav />
                </div>
              </div>
              <OnboardingTour />
            </div>
          )}
          <SyncProvider guestMode={!userId} />
          <Toaster position="top-right" />
        </body>
      </html>
    </ClerkProvider>
  );
}
