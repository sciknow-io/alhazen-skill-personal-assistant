import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Career Dashboard | Skillful-Alhazen",
  description: "Track job applications, analyze skill gaps, and manage your learning plan",
};

export default function CareerLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return <>{children}</>;
}
