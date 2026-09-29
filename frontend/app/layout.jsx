import "./globals.css";
import Navbar from "../components/Navbar";

export const metadata = {
  title: "Calling Agent — AI Outbound Calls",
  description: "AI-powered two-way outbound calling agent for commercial RO systems",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        {children}
      </body>
    </html>
  );
}
