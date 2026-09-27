import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const publicDir = join(process.cwd(), "public");
const iconSvgContent = readFileSync(join(publicDir, "icon.svg"), "utf-8");

// Maskable version: full-bleed background without rounded corners (Android trims to its own adaptive shape)
const maskableSvgContent = iconSvgContent.replace('rx="112"', 'rx="0"');

// Android notification badge: 96x96 monochrome white silhouette with transparent background
const badgeSvgContent = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" width="96" height="96">
  <!-- Medical Cross silhouette -->
  <rect x="41" y="20" width="14" height="56" rx="5" fill="#ffffff"/>
  <rect x="20" y="41" width="56" height="14" rx="5" fill="#ffffff"/>
  <!-- ECG Pulse line -->
  <path
    d="M 16 48 L 32 48 L 36 43 L 40 48 L 44 52 L 48 30 L 52 66 L 56 48 L 60 44 L 64 48 L 80 48"
    fill="none"
    stroke="#090e17"
    stroke-width="3"
    stroke-linecap="round"
    stroke-linejoin="round"
  />
  <path
    d="M 16 48 L 32 48 L 36 43 L 40 48 L 44 52 L 48 30 L 52 66 L 56 48 L 60 44 L 64 48 L 80 48"
    fill="none"
    stroke="#ffffff"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  />
</svg>`;

async function generateIcons() {
  console.log("Launching headless browser for icon rendering...");
  const browser = await chromium.launch();
  const page = await browser.newPage();

  async function renderSvgToPng(svgString, size, outputPath) {
    const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    html, body {
      width: ${size}px;
      height: ${size}px;
      background: transparent;
      overflow: hidden;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    svg {
      width: ${size}px;
      height: ${size}px;
      display: block;
    }
  </style>
</head>
<body>
  ${svgString}
</body>
</html>`;

    await page.setViewportSize({ width: size, height: size });
    await page.setContent(html, { waitUntil: "networkidle" });
    const buffer = await page.screenshot({ omitBackground: true, type: "png" });
    writeFileSync(outputPath, buffer);
    console.log(`✓ Generated ${outputPath} (${size}x${size})`);
  }

  // 1. Standard 512x512
  await renderSvgToPng(iconSvgContent, 512, join(publicDir, "icon-512x512.png"));

  // 2. Standard 192x192
  await renderSvgToPng(iconSvgContent, 192, join(publicDir, "icon-192x192.png"));

  // 3. Android Maskable 512x512
  await renderSvgToPng(maskableSvgContent, 512, join(publicDir, "icon-maskable-512x512.png"));

  // 4. Android Status Bar Notification Badge (96x96)
  await renderSvgToPng(badgeSvgContent, 96, join(publicDir, "badge-96x96.png"));

  await browser.close();
  console.log("All PWA icons generated successfully!");
}

generateIcons().catch((err) => {
  console.error("Error generating icons:", err);
  process.exit(1);
});
