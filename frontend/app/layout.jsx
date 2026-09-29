import "./globals.css";

export const metadata = {
  title: "SERP Hawk — Live Call",
  description: "Realtime AI calling agent demo",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
