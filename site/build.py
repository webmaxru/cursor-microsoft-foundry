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
import re
import shutil
import sys
from pathlib import Path, PurePosixPath
from string import Template
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.attrs import attrs_plugin

ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = ROOT / "site"
REPO_URL = "https://github.com/webmaxru/cursor-microsoft-foundry"
SITE_NAME = "Cursor + Microsoft Foundry"
SITE_PATH = "/cursor-microsoft-foundry/"
MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@12.3.0/dist/mermaid.esm.min.mjs"

# (source, output, navigation label, meta description)
PAGES = [
    ("docs/index.md", "index.html", "Home",
     "Use OpenAI and Claude models deployed in Microsoft Foundry from Cursor CLI: tested setup, guide and findings."),
    ("docs/guide.md", "guide.html", "Guide",
     "Step-by-step guide to connecting Cursor CLI to OpenAI and Claude models in Microsoft Foundry."),
    ("FINDINGS.md", "findings.html", "Findings",
     "Source-cited investigation of Cursor CLI, the Cursor IDE and Cloud Agents with Microsoft Foundry inference."),
    ("docs/scripts.md", "scripts.html", "Scripts",
     "Reference for the scripts, MCP bridge, tests and configuration files."),
    ("docs/evidence.md", "evidence.html", "Evidence",
     "Redacted records from the live Cursor CLI and Microsoft Foundry runs."),
    ("SOURCES.md", "sources.html", "Sources",
     "Sources used in the investigation, with confidence notes."),
]
ALIASES = {"README.md": "index.html"}
EVIDENCE_DIR = "evidence-snapshot"
PAGE_OUTPUT = {src: out for src, out, _, _ in PAGES} | ALIASES


def github_slug(text: str) -> str:
    """Match the heading IDs GitHub generates, so links work in both places."""
    return re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")


def make_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    anchors_plugin(md, min_level=1, max_level=6, slug_func=github_slug)
    attrs_plugin(md, after=("link_close",))

    default_fence = md.renderer.rules["fence"]

    def fence(renderer, tokens, idx, options, env):
        token = tokens[idx]
        if token.info.strip() == "mermaid":
            env["mermaid"] = True
            return f'<pre class="mermaid">{html.escape(token.content)}</pre>\n'
        return default_fence(tokens, idx, options, env)

    md.add_render_rule("fence", fence)
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
    kind = "tree" if resolved.is_dir() else "blob"
    return f"{REPO_URL}/{kind}/main/{rel}{suffix}"


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
                    child.attrSet("src", rewrite_href(child.attrGet("src"), source, fragment_checks))

    if title is None:
        raise LinkError(f"{source}: page has no level-1 heading")
    body = md.renderer.render(tokens, md.options, env)
    return title, toc, ids, body, env.get("mermaid", False)


def nav_html(current: str) -> str:
    items = []
    for _, out, label, _ in PAGES:
        attr = ' aria-current="page"' if out == current else ""
        items.append(f'<a href="{out}"{attr}>{label}</a>')
    items.append(f'<a href="{REPO_URL}" rel="noopener">GitHub</a>')
    return "\n        ".join(items)


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


def build(out_dir: Path) -> int:
    template = Template((SITE_DIR / "template.html").read_text(encoding="utf-8"))
    md = make_parser()
    fragment_checks: list = []
    page_ids: dict[str, set] = {}
    rendered = []

    for source, output, _, description in PAGES:
        title, toc, ids, body, has_mermaid = render_page(md, source, fragment_checks)
        if output == "index.html":
            toc = []
        page_ids[output] = ids
        page_title = SITE_NAME if output == "index.html" else f"{title} | {SITE_NAME}"
        rendered.append((output, template.substitute(
            page_title=html.escape(page_title),
            description=html.escape(description),
            nav=nav_html(output),
            toc=toc_html(toc),
            layout="with-toc" if len(toc) >= 2 else "no-toc",
            content=with_inline_toc(body, toc),
            source_url=f"{REPO_URL}/blob/main/{source}",
            repo_url=REPO_URL,
            mermaid=mermaid_script(has_mermaid),
            base="",
        )))

    errors = [
        f"{source}: unknown fragment #{fragment} on {output}"
        for source, output, fragment in fragment_checks
        if fragment not in page_ids[output]
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
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    not_found = template.substitute(
        page_title=html.escape(f"Page not found | {SITE_NAME}"),
        description="Page not found.",
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
