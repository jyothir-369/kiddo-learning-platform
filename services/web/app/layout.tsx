import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Kiddo Assist",
  description: "A friend AI for children — learn, play, and grow.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}