import "./globals.css";
import Navbar from "../components/Navbar";

export const metadata = {
  title: "SERP Hawk — AI Calling Agent",
  description: "AI-Powered Two-Way Outbound Calling Agent for Commercial RO Systems",
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
