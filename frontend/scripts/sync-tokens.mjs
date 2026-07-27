import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const tokenPath = resolve(projectRoot, "../design/tokens.json");
const outputPath = resolve(projectRoot, "src/styles/generated-tokens.css");
const tokens = JSON.parse(await readFile(tokenPath, "utf8"));

const palette = (values) => `
  --background: ${values.background};
  --surface: ${values.surface};
  --ink: ${values.ink};
  --muted: ${values.muted};
  --hairline: ${values.hairline};
  --shape: ${values.shape};
  --accent: ${values.accent};
  --raised: ${values.raised};`;

const css = `/* Generated from ../design/tokens.json. Run npm run tokens:sync. */
:root,
html.dark {
  --font-sans: ${tokens.fontSans};
  --font-mono: ${tokens.fontMono};
  --font-serif: ${tokens.fontSerif};
  --radius: ${tokens.radius}px;
${palette(tokens.dark)}
}

html.light {
${palette(tokens.light)}
}
`;

await writeFile(outputPath, css);
