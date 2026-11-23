const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const nextDir = path.join(root, ".next");
const aliasDir = path.join(root, "Next.js default");

try {
  if (fs.existsSync(nextDir)) {
    // If Vercel has "Next.js default" set as output directory, provide it
    try {
      if (!fs.existsSync(aliasDir)) {
        fs.symlinkSync(nextDir, aliasDir, "junction");
        console.log("==> Created Next.js default alias symlink for Vercel output directory.");
      }
    } catch {
      if (!fs.existsSync(aliasDir)) {
        fs.cpSync(nextDir, aliasDir, { recursive: true });
        console.log("==> Copied .next to Next.js default directory for Vercel.");
      }
    }
  }
} catch (err) {
  console.log("Postbuild notice:", err.message);
}
