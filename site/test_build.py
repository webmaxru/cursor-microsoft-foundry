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
