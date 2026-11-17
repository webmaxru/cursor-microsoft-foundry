"""Regression checks for the Markdown-to-site reading interface."""

import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

import build


class PageStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []
        self.headings = []
        self.code = []
        self.in_code = False
        self.current_pages = []
        self.toolbars = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "section":
            self.sections.append(attrs.get("aria-labelledby"))
        if tag == "h2":
            self.headings.append(attrs.get("id"))
        if tag == "a" and attrs.get("aria-current") == "page":
            self.current_pages.append(attrs.get("href"))
        if tag == "div" and attrs.get("class") == "code-toolbar":
            self.toolbars += 1
        if tag == "pre":
            self.in_code = attrs.get("class") != "mermaid"
            if self.in_code:
                self.code.append("")

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_code = False

    def handle_data(self, data):
        if self.in_code:
            self.code[-1] += data


class SiteBuildTests(unittest.TestCase):
    def test_citations_link_individually_in_superscript_but_not_in_code_or_links(self):
        parser = build.make_parser()
        tokens = parser.parse("Claim [C1, F1 to F2]. `[C1]` [label [C1]](https://example.com)\n\n```\n[C1]\n```")
        build.link_citations(tokens, {"C1": "Official <docs>", "F1": "First", "F2": "Second"}, "docs/cli.md")
        page = parser.renderer.render(tokens, parser.options, {})
        self.assertEqual(page.count('<sup class="citation">'), 1)
        for key in ("c1", "f1", "f2"):
            self.assertIn(f'href="../SOURCES.md#source-{key}"', page)
        self.assertIn("Official &lt;docs&gt;", page)
        self.assertIn(">[C1]</code>", page)
        self.assertIn('href="https://example.com">label [C1]</a>', page)
        self.assertIn("[C1]\n</code>", page)

    def test_unknown_and_invalid_range_citations_fail_build(self):
        for text in ("[C99]", "[F2 to F1]", "[F1 to C2]"):
            with self.subTest(text=text), self.assertRaises(build.LinkError):
                build.link_citations(build.make_parser().parse(text), {"F1": "One"}, "docs/cli.md")

    def test_source_rows_supply_targets_for_all_citation_links(self):
        parser = build.make_parser()
        _, _, ids, body, _ = build.render_page(parser, "SOURCES.md", [])
        self.assertIn("source-c1", ids)
        self.assertIn('<tr id="source-c1">', body)
        checks = []
        _, _, _, page, _ = build.render_page(parser, "docs/cli.md", checks)
        self.assertIn('<sup class="citation">', page)
        self.assertTrue(checks)
        for _, output, fragment in checks:
            if output == "sources.html" and fragment.startswith("source-"):
                self.assertIn(fragment, ids)

    def test_sections_preserve_every_heading_and_copyable_code_block(self):
        parser = build.make_parser()
        for source, *_ in build.PAGES:
            with self.subTest(source=source):
                text = (build.ROOT / source).read_text(encoding="utf-8")
                tokens = parser.parse(text)
                expected_code = [t.content for t in tokens if t.type == "fence" and t.info.strip() != "mermaid"]
                _, toc, _, body, _ = build.render_page(parser, source, [])
                result = PageStructure()
                result.feed(body)
                self.assertEqual(result.headings, [item[0] for item in toc])
                self.assertEqual(result.sections, result.headings)
                self.assertEqual(result.code, expected_code)
                self.assertEqual(result.toolbars, len(expected_code))

    def test_code_toolbar_does_not_interpret_untrusted_fence_markup(self):
        parser = build.make_parser()
        page = parser.render('```<img src=x onerror=alert(1)>\n<script>alert("x")</script>\n```\n')
        result = PageStructure()
        result.feed(page)
        self.assertNotIn("<img ", page)
        self.assertNotIn("<script>", page)
        self.assertEqual(result.code, ['<script>alert("x")</script>\n'])

    def test_build_selects_exactly_the_current_page_in_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "site"
            build.build(out)
            for _, output, *_ in build.PAGES:
                with self.subTest(page=output):
                    result = PageStructure()
                    result.feed((out / output).read_text(encoding="utf-8"))
                    self.assertEqual(result.current_pages, [output])
                    self.assertTrue((out / "assets" / "site.js").is_file())
            self.assertIn("location.replace", (out / "guide.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
