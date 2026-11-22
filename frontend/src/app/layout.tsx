import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MNB Veritas v1.4 | Evidence Engine",
  description: "Not a Score. The Source. Multi-Model AI Verification & Anti-Hallucination Middleware Layer",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                function isExtensionError(event) {
                  var file = (event && event.filename) || '';
                  var msg = (event && event.message) || '';
                  var err = event && event.error;
                  var stack = (err && err.stack) || '';
                  if (file.indexOf('chrome-extension://') !== -1 || stack.indexOf('chrome-extension://') !== -1 || msg.indexOf('M_ID') !== -1 || msg.indexOf('bis_skin_checked') !== -1) {
                    return true;
                  }
                  if (event && event.reason) {
                    var rStack = (event.reason && event.reason.stack) || '';
                    var rMsg = (event.reason && event.reason.message) || '';
                    if (rStack.indexOf('chrome-extension://') !== -1 || rMsg.indexOf('M_ID') !== -1) {
                      return true;
                    }
                  }
                  return false;
                }

                // Intercept console.error to prevent extension bugs from triggering Next.js dev overlay
                if (typeof window !== 'undefined' && console && console.error) {
                  var origError = console.error;
                  console.error = function() {
                    var args = Array.prototype.slice.call(arguments);
                    var joined = args.map(function(a) { return String(a || ''); }).join(' ');
                    if (
                      joined.indexOf('chrome-extension://') !== -1 ||
                      joined.indexOf('M_ID') !== -1 ||
                      joined.indexOf('bis_skin_checked') !== -1 ||
                      joined.indexOf('hydration-mismatch') !== -1
                    ) {
                      return;
                    }
                    origError.apply(console, arguments);
                  };
                }

                window.addEventListener('error', function(e) {
                  if (isExtensionError(e)) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return true;
                  }
                }, true);

                window.addEventListener('unhandledrejection', function(e) {
                  if (isExtensionError(e)) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                  }
                }, true);
              })();
            `,
          }}
        />
      </head>
      <body
        suppressHydrationWarning
        className="min-h-screen bg-[#0B0F12] text-zinc-100 antialiased selection:bg-emerald-500/30 selection:text-emerald-200"
      >
        {children}
      </body>
    </html>
  );
}
