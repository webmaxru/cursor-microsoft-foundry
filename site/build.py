"""Build the GitHub Pages site from the repository's Markdown files.

Usage: python site/build.py [--out DIR]

Links between published pages become .html links, links to
evidence-snapshot/ point at the copied evidence files, and links to any other
repository file point at GitHub. The build fails on a missing link target or
an unknown #fragment.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import struct
import sys
from pathlib import Path, PurePosixPath
from string import Template
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.attrs import attrs_block_plugin, attrs_plugin

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
REPO_URL = "https://github.com/webmaxru/cursor-microsoft-foundry"
SITE_NAME = "Cursor + Microsoft Foundry"
SITE_PATH = "/cursor-microsoft-foundry/"
SITE_URL = "https://salnikov.no" + SITE_PATH
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@12.3.0/dist/mermaid.esm.min.mjs"

# (source, output, navigation label, navigation group, meta description)
PAGES = [
    ("docs/index.md", "index.html", "Home", None,
     "Use OpenAI and Claude models deployed in Microsoft Foundry from the Cursor CLI, IDE and Cloud Agents: tested setup, guides and findings."),
    ("docs/cli.md", "cli.html", "CLI", "surface",
     "Use Microsoft Foundry OpenAI and Claude models from the Cursor CLI through a local MCP server, verified end to end."),
    ("docs/ide.md", "ide.html", "IDE", "surface",
     "Use Microsoft Foundry models in the Cursor IDE: MCP tools verified end to end, plus the Azure OpenAI and OpenAI API-key slots."),
    ("docs/cloud.md", "cloud.html", "Cloud", "surface",
     "Blueprint for reaching Microsoft Foundry models from Cursor Cloud Agents through an authenticated HTTP MCP service."),
    ("docs/setup.md", "setup.html", "Foundry setup", "shared",
     "Deploy OpenAI and Claude models in Microsoft Foundry, grant Entra ID access and test the MCP bridge before connecting Cursor."),
    ("FINDINGS.md", "findings.html", "Findings", "shared",
     "Source-cited investigation of the Cursor CLI, IDE and Cloud Agents with Microsoft Foundry inference."),
    ("docs/scripts.md", "scripts.html", "Scripts", "shared",
     "Reference for the scripts, MCP bridge, tests and configuration files."),
    ("docs/evidence.md", "evidence.html", "Evidence", "shared",
     "Redacted records from the live Cursor CLI, Cursor IDE and Microsoft Foundry runs."),
    ("SOURCES.md", "sources.html", "Sources", "shared",
     "Sources used in the investigation, with confidence notes."),
]
NAV_GROUPS = [
    ("surface", "Surface", "Cursor surfaces"),
    ("shared", None, "Pages for all surfaces"),
]
ALIASES = {"README.md": "index.html"}
EVIDENCE_DIR = "evidence-snapshot"
IMAGE_DIR = "docs/assets"
PAGE_OUTPUT = {src: out for src, out, *_ in PAGES} | ALIASES

# The single guide page was split up; keep its old section links working.
GUIDE_REDIRECTS = {
    "": "setup.html",
    "what-you-are-building": "setup.html#what-you-are-building",
    "choose-your-path": "index.html#choose-your-cursor-surface",
    "1-prerequisites": "setup.html#1-prerequisites",
    "2-get-the-code-and-create-your-configuration": "setup.html#2-get-the-code-and-create-your-configuration",
    "3-deploy-an-openai-model": "setup.html#3-deploy-an-openai-model",
    "4-deploy-a-claude-model": "setup.html#4-deploy-a-claude-model",
    "5-grant-yourself-inference-access": "setup.html#5-grant-yourself-inference-access",
    "6-install-the-bridge": "setup.html#6-install-the-bridge",
    "7-test-foundry-without-cursor": "setup.html#7-test-foundry-without-cursor",
    "8-connect-cursor-cli": "cli.html#2-connect-the-mcp-server",
    "9-ask-cursor-to-use-your-foundry-models": "cli.html#3-ask-cursor-to-use-your-foundry-models",
    "10-run-the-full-end-to-end-check": "cli.html#4-run-the-full-end-to-end-check",
    "11-use-it-in-your-own-project": "cli.html#5-use-it-in-your-own-project",
    "12-cursor-ide-and-cloud-agents": "index.html#choose-your-cursor-surface",
    "13-troubleshooting": "setup.html#8-troubleshooting",
    "14-clean-up": "setup.html#9-clean-up",
}


def github_slug(text: str) -> str:
    """Match the heading IDs GitHub generates, so links work in both places."""
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def make_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    anchors_plugin(md, min_level=1, max_level=6, slug_func=github_slug)
    attrs_plugin(md, after=("link_close",), spans=True, allowed=("class",))
    attrs_block_plugin(md, allowed=("class",))

    default_fence = md.renderer.rules["fence"]

    def fence(renderer, tokens, idx, options, env):
        token = tokens[idx]
        if token.info.strip() == "mermaid":
            env["mermaid"] = True
            return f'<pre class="mermaid">{html.escape(token.content)}</pre>\n'
        return default_fence(tokens, idx, options, env)

    md.add_render_rule("fence", fence)
    default_code_inline = md.renderer.rules["code_inline"]

    def code_inline(renderer, tokens, idx, options, env):
        # Keep short identifiers such as --endpoint whole; long paths may still wrap.
        if len(tokens[idx].content) <= 28:
            tokens[idx].attrJoin("class", "nw")
        return default_code_inline(tokens, idx, options, env)

    md.add_render_rule("code_inline", code_inline)
    md.add_render_rule("table_open", lambda *a: '<div class="table-wrap"><table>\n')
    md.add_render_rule("table_close", lambda *a: "</table></div>\n")
    return md


class LinkError(Exception):
    pass


def rewrite_href(href: str, source: str, fragment_checks: list) -> str:
    parts = urlsplit(href)
    if parts.scheme or href.startswith("//"):
        return href
    if not parts.path:
        fragment_checks.append((source, PAGE_OUTPUT[source], parts.fragment))
        return href

    target = PurePosixPath(source).parent / parts.path
    resolved = (ROOT / target).resolve()
    try:
        rel = resolved.relative_to(ROOT).as_posix()
    except ValueError:
        raise LinkError(f"{source}: link leaves the repository: {href}") from None
    if not resolved.exists():
        raise LinkError(f"{source}: missing link target: {href}")

    suffix = f"#{parts.fragment}" if parts.fragment else ""
    if rel in PAGE_OUTPUT:
        if parts.fragment:
            fragment_checks.append((source, PAGE_OUTPUT[rel], parts.fragment))
        return PAGE_OUTPUT[rel] + suffix
    if rel.startswith(EVIDENCE_DIR + "/") and resolved.is_file():
        return "evidence/" + rel[len(EVIDENCE_DIR) + 1:] + suffix
    if rel.startswith(IMAGE_DIR + "/") and resolved.is_file():
        return "img/" + rel[len(IMAGE_DIR) + 1:]
    kind = "tree" if resolved.is_dir() else "blob"
    return f"{REPO_URL}/{kind}/main/{rel}{suffix}"


def png_size(path: Path):
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", header[16:24])


def inline_text(token) -> str:
    return "".join(c.content for c in token.children or [] if c.type in ("text", "code_inline"))


def render_page(md: MarkdownIt, source: str, fragment_checks: list):
    text = (ROOT / source).read_text(encoding="utf-8")
    env: dict = {}
    tokens = md.parse(text, env)

    title, toc, ids = None, [], set()
    for i, token in enumerate(tokens):
        if token.type == "heading_open":
            heading_id = token.attrGet("id")
            ids.add(heading_id)
            label = inline_text(tokens[i + 1])
            if token.tag == "h1" and title is None:
                title = label
            elif token.tag == "h2":
                toc.append((heading_id, label))
        if token.type == "inline":
            for child in token.children or []:
                if child.type == "link_open":
                    child.attrSet("href", rewrite_href(child.attrGet("href"), source, fragment_checks))
                    if str(child.attrGet("href")).startswith("http"):
                        child.attrSet("rel", "noopener")
                elif child.type == "image":
                    src = child.attrGet("src")
                    child.attrSet("src", rewrite_href(src, source, fragment_checks))
                    if not str(child.attrGet("src")).startswith("img/"):
                        raise LinkError(f"{source}: images must live in {IMAGE_DIR}/: {src}")
                    size = png_size((ROOT / PurePosixPath(source).parent / src).resolve())
                    if size:
                        child.attrSet("width", str(size[0]))
                        child.attrSet("height", str(size[1]))
                    child.attrSet("loading", "lazy")
                    child.attrSet("decoding", "async")

    if title is None:
        raise LinkError(f"{source}: page has no level-1 heading")
    body = md.renderer.render(tokens, md.options, env)
    return title, toc, ids, body, env.get("mermaid", False)


def nav_html(current: str) -> str:
    groups = []
    for key, visible_label, accessible_label in NAV_GROUPS:
        links = []
        for _, out, label, group, _ in PAGES:
            if group != key:
                continue
            attr = ' aria-current="page"' if out == current else ""
            links.append(f'<a href="{out}"{attr}>{label}</a>')
        if key == "shared":
            links.append(f'<a href="{REPO_URL}" rel="noopener">GitHub</a>')
        label_html = f'<span class="nav-label" aria-hidden="true">{visible_label}</span>' if visible_label else ""
        groups.append(
            f'<div class="nav-group nav-{key}" role="group" aria-label="{accessible_label}">'
            f'{label_html}<div class="nav-links">{"".join(links)}</div></div>'
        )
    return "\n        ".join(groups)


def toc_links(toc) -> str:
    return "\n".join(
        f'        <li><a href="#{html.escape(i)}">{html.escape(label)}</a></li>' for i, label in toc
    )


def toc_html(toc) -> str:
    if len(toc) < 2:
        return ""
    return (
        '<nav class="toc" aria-label="On this page">\n'
        "      <h2>On this page</h2>\n"
        f"      <ol>\n{toc_links(toc)}\n      </ol>\n"
        "    </nav>"
    )


def with_inline_toc(body: str, toc) -> str:
    """Add a collapsible outline after the title for narrow screens."""
    if len(toc) < 2:
        return body
    inline = (
        '<details class="toc-inline">\n'
        "      <summary>On this page</summary>\n"
        f"      <ol>\n{toc_links(toc)}\n      </ol>\n"
        "    </details>\n"
    )
    return body.replace("</h1>\n", "</h1>\n" + inline, 1)


def mermaid_script(enabled: bool) -> str:
    if not enabled:
        return ""
    return (
        '<script type="module">\n'
        f"    import mermaid from \"{MERMAID_URL}\";\n"
        "    const blocks = [...document.querySelectorAll(\"pre.mermaid\")];\n"
        "    const sources = blocks.map((block) => block.textContent);\n"
        "    const scheme = matchMedia(\"(prefers-color-scheme: dark)\");\n"
        "    async function render() {\n"
        "      mermaid.initialize({ startOnLoad: false, theme: scheme.matches ? \"dark\" : \"default\", securityLevel: \"strict\" });\n"
        "      blocks.forEach((block, i) => { block.removeAttribute(\"data-processed\"); block.textContent = sources[i]; });\n"
        "      await mermaid.run({ nodes: blocks });\n"
        "    }\n"
        "    render();\n"
        "    scheme.addEventListener(\"change\", render);\n"
        "  </script>"
    )


def guide_redirect_html() -> str:
    """Old guide.html: send each former section to its new page."""
    targets = json.dumps(GUIDE_REDIRECTS, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex">
  <title>The guide has moved | {SITE_NAME}</title>
  <link rel="canonical" href="{SITE_URL}setup.html">
  <script>
    const targets = {targets};
    location.replace(targets[decodeURIComponent(location.hash.slice(1))] || targets[""]);
  </script>
  <meta http-equiv="refresh" content="0; url=setup.html">
</head>
<body>
  <p>The guide is now split into <a href="setup.html">Foundry setup</a> and pages for the
    <a href="cli.html">Cursor CLI</a>, <a href="ide.html">Cursor IDE</a> and <a href="cloud.html">Cloud Agents</a>.</p>
</body>
</html>
"""


def build(out_dir: Path) -> int:
    template = Template((SITE_DIR / "template.html").read_text(encoding="utf-8"))
    md = make_parser()
    fragment_checks: list = []
    page_ids: dict[str, set] = {}
    rendered = []

    for source, output, _, _, description in PAGES:
        title, toc, ids, body, has_mermaid = render_page(md, source, fragment_checks)
        if output == "index.html":
            toc = []
        page_ids[output] = ids
        page_title = SITE_NAME if output == "index.html" else f"{title} | {SITE_NAME}"
        rendered.append((output, template.substitute(
            page_title=html.escape(page_title),
            description=html.escape(description),
            canonical=SITE_URL + ("" if output == "index.html" else output),
            page_class="page-" + output.removesuffix(".html"),
            nav=nav_html(output),
            toc=toc_html(toc),
            layout="with-toc" if len(toc) >= 2 else "no-toc",
            content=with_inline_toc(body, toc),
            source_url=f"{REPO_URL}/blob/main/{source}",
            repo_url=REPO_URL,
            mermaid=mermaid_script(has_mermaid),
            base="",
        )))

    for fragment, target in GUIDE_REDIRECTS.items():
        output, _, target_fragment = target.partition("#")
        fragment_checks.append(("guide.html redirect", output, target_fragment or None))

    errors = [
        f"{source}: unknown fragment #{fragment} on {output}"
        for source, output, fragment in fragment_checks
        if fragment and fragment not in page_ids[output]
    ]
    if errors:
        raise LinkError("\n".join(errors))

    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for output, page in rendered:
        (out_dir / output).write_text(page, encoding="utf-8", newline="\n")
    shutil.copytree(SITE_DIR / "assets", out_dir / "assets")
    shutil.copytree(ROOT / EVIDENCE_DIR, out_dir / "evidence")
    shutil.copytree(ROOT / IMAGE_DIR, out_dir / "img")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    (out_dir / "guide.html").write_text(guide_redirect_html(), encoding="utf-8", newline="\n")

    not_found = template.substitute(
        page_title=html.escape(f"Page not found | {SITE_NAME}"),
        description="Page not found.",
        canonical=SITE_URL,
        page_class="page-404",
        nav=nav_html(""),
        toc="",
        layout="no-toc",
        content='<h1>Page not found</h1>\n<p><a href="index.html">Go to the home page</a>.</p>\n',
        source_url=REPO_URL,
        repo_url=REPO_URL,
        mermaid="",
        base=f'<base href="{SITE_PATH}">',
    )
    (out_dir / "404.html").write_text(not_found, encoding="utf-8", newline="\n")
    print(f"Built {len(rendered)} pages and {len(list((out_dir / 'evidence').iterdir()))} evidence files in {out_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    try:
        return build(args.out.resolve())
    except LinkError as error:
        print(f"Build failed:\n{error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
