# Tax burden equity website

The standalone Next.js frontend for the Tax Burden Equity Analyzer. It calls
the companion analysis service and leaves all feature construction, model
loading, prediction, contribution, and twin logic behind that boundary.

## Run locally

```bash
npm ci
cp .env.example .env.local
npm run dev
```

The site opens at `http://localhost:3000`. The analysis service must be running
at the URL configured by `NEXT_PUBLIC_API_URL`.

## Design tokens

`npm run tokens:sync` reads `../design/tokens.json` and regenerates
`src/styles/generated-tokens.css`. The command runs automatically before local
development and production builds.

## Component sources

The site adapts these restrained, open-source foundations:

- [Animated hero by Tommy Jepsen](https://21st.dev/@tommyjepsen/components/animated-hero)
  and [Header by Tommy Jepsen](https://21st.dev/community/components/tommyjepsen/header),
  from the MIT-licensed TWBlocks project.
- [shadcn Button](https://21st.dev/community/components/shadcn/button) and
  [shadcn Card](https://21st.dev/@shadcn/components/card), MIT licensed.
- [Motion Primitives In View](https://21st.dev/community/components/ibelick/in-view/default)
  and [Scroll Progress](https://21st.dev/community/components/ibelick/scroll-progress),
  MIT licensed.

The final site uses its own project copy, visual tokens, and content rather than
the source components’ demo styling.
