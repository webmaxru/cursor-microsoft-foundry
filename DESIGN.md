---
name: Cursor + Microsoft Foundry
description: An independent technical field edition with explicit evidence boundaries.
colors:
  bg: "#fcfdfe"
  bg-soft: "#edf1f5"
  bg-code: "#f5f7f9"
  text: "#202c3a"
  muted: "#536476"
  border: "#d3dce5"
  accent: "#205a8a"
  accent-soft: "#e5edf4"
  rail: "#182a40"
  rail-text: "#f4f7fb"
  rail-muted: "#afc0d3"
  rail-hover: "#263e58"
  rail-border: "#42576e"
  verified: "#256548"
  partial: "#80520f"
  dark-bg: "#151e29"
  dark-bg-soft: "#202d3b"
  dark-bg-code: "#192432"
  dark-text: "#e0e8f0"
  dark-muted: "#a4b6c8"
  dark-border: "#3b4d5f"
  dark-accent: "#9ec6ec"
  dark-accent-soft: "#263c51"
  dark-rail: "#101b2a"
  dark-rail-hover: "#243a52"
  dark-verified: "#9dcdb4"
  dark-partial: "#e1be83"
typography:
  display:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "2.75rem"
    fontWeight: 600
    lineHeight: 1.13
    letterSpacing: "-0.035em"
  headline:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1.7rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "1.25rem"
    fontWeight: 650
    lineHeight: 1.4
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.75
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: "0.78rem"
    fontWeight: 500
  code:
    fontFamily: 'ui-monospace, "Cascadia Code", "SF Mono", Menlo, Consolas, monospace'
    fontSize: "0.8rem"
    lineHeight: 1.6
rounded:
  inline-control: "2px"
spacing:
  page-gutter: "3.5rem"
components:
  copy-button:
    textColor: "{colors.accent}"
    typography: "{typography.label}"
    rounded: "{rounded.inline-control}"
    padding: "0.2rem 0.55rem"
  navigation-link:
    textColor: "{colors.rail-text}"
    padding: "0.55rem 0.75rem"
  contents-link:
    textColor: "{colors.muted}"
    padding: "0.1rem 0"
  support-status:
    textColor: "{colors.muted}"
  code-block:
    backgroundColor: "{colors.bg-code}"
    textColor: "{colors.text}"
  evidence-header:
    backgroundColor: "{colors.bg-soft}"
    textColor: "{colors.text}"
    padding: "0.9rem 0.8rem"
  research-note:
    backgroundColor: "{colors.bg-soft}"
    textColor: "{colors.text}"
    padding: "1rem 1.25rem"
---

# Design System: Cursor + Microsoft Foundry

## Overview

**Creative North Star: "Research-institute field edition"**

A technical publication, not a software landing page. Navy navigation binds pale reading surfaces, open evidence tables and square-edged code. System sans typography uses weight and measure to distinguish research hierarchy without ornamental interface chrome.

The independent research and its confidence boundaries remain the subject. This records the implemented system in `site\assets\style.css`, `site\template.html` and `site\assets\site.js`; `PRODUCT.md` supplies the durable evidence and accessibility constraints.

**Key Characteristics:**
- Persistent navigation with a readable document body.
- Restrained links, structural rules and explicitly qualified support.
- Progressive enhancement without a JavaScript reading dependency.

## Colors

Cool neutrals separate reading material from a deep navy spine; blue identifies interaction.

### Primary

- **Research blue** (`accent`) colors links, copy actions and focus outlines; `accent-soft` supplies text-selection fill.
- **Evidence green / qualified amber** (`verified`, `partial`) supplement the support labels, not a second brand palette. Blueprint status uses `muted`.

### Neutral

- **Cool paper** (`bg`), **inset paper** (`bg-soft`) and **code paper** (`bg-code`) distinguish the page, notes/table headers/inline code, and code blocks.
- **Ink**, **secondary ink** and **rules** (`text`, `muted`, `border`) establish hierarchy.
- **Navy spine** (`rail`) has its own text, secondary text, hover and divider roles (`rail-text`, `rail-muted`, `rail-hover`, `rail-border`).

The unprefixed keys mirror CSS custom properties. `dark-` keys record their existing `prefers-color-scheme: dark` overrides, not additional CSS variables; roles without an override retain their values. There is no theme toggle.

Sidecar tonal ramps are derived preview metadata only, not additional site tokens or contrast guarantees.

**The Evidence Rule.** Status color supplements the written qualification; it never upgrades an untested path.

## Typography

Display and body share the system sans stack; commands use the system monospace stack. There are no downloaded fonts or inferred modular scale.

- **Display / headline / title:** frontmatter roles map to article headings h1 / h2 / h3. Headings balance wrapping; article h1 measure is capped (23ch).
- **Body:** paragraphs and top-level section lists are capped (72ch). Intro text is slightly larger (1.075rem, line-height 1.8).
- **Label / code:** copy labels and code-block text use the frontmatter roles. Inline code instead uses relative sizing (0.86em), so it follows its surrounding text.
- **Overview exception:** its h1 uses a larger, lighter setting (3.5rem, weight 550, line-height 1.1, 22ch); this is not a replacement for article headings.

## Layout

- **Desktop:** fixed, independently scrolling left spine (15rem); the page offsets by that width. The centered layout is capped (82rem), with the recorded page gutter, top/bottom padding (3.7rem / 5rem) and grid gap (3rem).
- **Guides:** flexible article plus a sticky contents rail (12rem); rail top offset (3.7rem), maximum height (`calc(100dvh - 6rem)`). The overview instead uses a reading spread (1.5fr / 1fr), with full-width introduction and subsequent shared sections.
- **Rhythm:** paragraph/list spacing (1.25rem); article sections use top margin (3.5rem), inset (2rem) and a thin rule (1px).
- **At or below 1250px:** spine (13.5rem), gutter (2.5rem), layout gap (2rem); guide contents move into an inline native disclosure.
- **At or below 1000px:** the overview becomes one column; its h1 reduces (3rem).
- **At or below 760px:** the spine becomes a static header; Overview / CLI / IDE / Cloud remain visible. Setup/reference uses a native disclosure. Gutter becomes (1.5rem), article text (1rem), article h1 (2.35rem), overview h1 (2.65rem), h2 (1.5rem) and h3 (1.2rem). Footer and shared links stack.
- **At or below 380px:** gutter (1.1rem), both h1 treatments (2.2rem).
- **At or above 1600px:** layout top padding and sticky contents offset increase (5rem).
- **Print:** navigation, contents, copy controls and page-source links are hidden; the document becomes one column, with visible table/code overflow and wrapping code.

## Elevation & Depth

No shadows are defined. Tonal surfaces and thin rules separate content; fixed navigation and sticky contents provide orientation, not floating panel effects. Navigation hover is the only CSS transition (`background-color 150ms ease-out`), disabled for reduced-motion preference.

## Shapes

Code containers/toolbars, notes and tables are square-edged. Inline code and copy controls retain the small frontmatter radius; this is not a universal zero-radius rule. Tables use open horizontal rules, not enclosing cards or vertical cell grids. Real screenshots keep their proportions and a thin border.

## Components

- **Navigation — persistent, explicit.** Current page reverses to light fill with navy text and stronger weight (650); hover uses the rail hover role. Ordinary links are underlined, thickening on hover (1px to 2px). Keyboard focus is an outline (2px, offset 4px), light on the spine. The skip link reveals on focus.
- **Contents — quiet orientation.** Muted links become blue and underlined on hover. JavaScript marks the intersecting heading with blue, stronger weight (650) and `aria-current="location"`; the native anchor links work without it.
- **Code and copy — practical, not simulated terminal chrome.** The square toolbar has a lower rule and wraps its contents. JavaScript adds Copy only when Clipboard API support exists, disables it during writing, and announces `Copied` or `Copy failed. Select and copy the code.` through `role="status"`; feedback clears after (4000ms). Hover reveals a border and page-colored fill. Copy minimum height grows from (2rem) to (2.75rem) on mobile.
- **Support ledger — ruled rows, plain-text status.** Preserve `Verified`, `Partly verified` and `Blueprint` with their surrounding caveats. CLI and IDE MCP evidence does not establish an own-key test; the Cloud blueprint remains unexecuted. The text link's arrow is a navigation affordance, not an illustration.
- **Evidence tables and diagrams — information before compression.** Tables retain full columns in horizontal overflow. JavaScript labels overflowing table/code/diagram regions and makes them keyboard-focusable; visible scroll hints are added for tables and diagrams only. Resize observation updates that state when available.
- **Research notes — inset explanation.** Muted paper, thin border and compact text (0.93rem) distinguish blockquotes without making a card hierarchy.

Native setup/reference disclosure remains usable without JavaScript. With enhancement it starts open above the mobile breakpoint, closed below, and updates on breakpoint changes. Reading, links and source anchors do not depend on copy, scroll hints or contents highlighting.

## Do's and Don'ts

### Do:
- Do keep support labels, caveats, evidence links and source anchors intact.
- Do preserve visible keyboard focus, native disclosure controls and reading/navigation without JavaScript.
- Do reuse the measured type, gutter and color roles; honor dark-system and reduced-motion preferences.

### Don't:
- Don't replace the open document structure with cards, gradients, glass or ornamental motion.
- Don't add invented metrics, decorative section numbers, synthetic illustrations or fake terminal chrome.
- Don't remove real screenshots, diagrams or structural rules in the name of minimalism.
