const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "..");
const nextDir = path.join(root, ".next");
const aliasDir = path.join(root, "Next.js default");

try {
  if (fs.existsSync(nextDir)) {
    // Remove if existing broken symlink or old directory
    try {
      fs.rmSync(aliasDir, { recursive: true, force: true });
    } catch {}

    // On Linux/POSIX create directory symlink with relative target, fallback to recursive copy
    try {
      const isWindows = process.platform === "win32";
      if (isWindows) {
        fs.symlinkSync(nextDir, aliasDir, "junction");
      } else {
        fs.symlinkSync(".next", aliasDir, "dir");
      }
      console.log("==> Created 'Next.js default' symlink -> .next");
    } catch (symlinkErr) {
      console.log("Symlink fallback to copy:", symlinkErr.message);
      fs.cpSync(nextDir, aliasDir, { recursive: true });
      console.log("==> Copied .next to 'Next.js default'");
    }
  }
} catch (err) {
  console.error("Postbuild error:", err.message);
}
