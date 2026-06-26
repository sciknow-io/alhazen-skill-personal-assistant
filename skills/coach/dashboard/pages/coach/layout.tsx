import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Health Coach",
  description: "Personal health & fitness monitoring dashboard",
};

export default function CoachLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
