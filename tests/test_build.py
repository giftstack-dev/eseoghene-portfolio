"""Automated tests for the static portfolio generator and dist/ output."""

from __future__ import annotations

import json
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path

import pytest

from build import DATA_FILE, DIST_DIR, STATIC_DIR, build_site

# Unicode ranges covering emoji and pictographs that are disallowed in output
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


class PageInspector(HTMLParser):
    """Collect structural HTML tags, attributes, and links for verification."""

    def __init__(self) -> None:
        super().__init__()
        self.script_count = 0
        self.inline_style_count = 0
        self.h1_count = 0
        self.meta_descriptions: list[str] = []
        self.hrefs: list[str] = []
        self.srcs: list[str] = []
        self.imgs_without_alt: list[str] = []
        self.imgs_missing_dimensions: list[str] = []
        self.links: list[dict[str, str]] = []
        self.canonicals: list[str] = []
        self.og_urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "script":
            self.script_count += 1
        if "style" in attr_map:
            self.inline_style_count += 1
        if tag == "h1":
            self.h1_count += 1
        if tag == "meta" and attr_map.get("name") == "description":
            self.meta_descriptions.append(attr_map.get("content") or "")
        if tag == "meta" and attr_map.get("property") == "og:url":
            self.og_urls.append(attr_map.get("content") or "")
        if tag == "link" and attr_map.get("rel") == "canonical":
            self.canonicals.append(attr_map.get("href") or "")
        if tag == "a":
            self.links.append({k: (v or "") for k, v in attrs})
        if "href" in attr_map and attr_map["href"] is not None:
            self.hrefs.append(attr_map["href"])
        if "src" in attr_map and attr_map["src"] is not None:
            self.srcs.append(attr_map["src"])
        if tag == "img":
            src = attr_map.get("src") or "<unknown>"
            alt = attr_map.get("alt")
            if alt is None or not alt.strip():
                self.imgs_without_alt.append(src)
            if not attr_map.get("width") or not attr_map.get("height"):
                self.imgs_missing_dimensions.append(src)


@pytest.fixture(scope="module")
def built_site() -> tuple[dict, list[Path]]:
    """Run the build once before verifying generated files."""
    site = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    pages = build_site()
    return site, pages


def _all_html_files(base_dir: Path = DIST_DIR) -> list[Path]:
    return sorted(base_dir.rglob("*.html"))


def test_expected_pages_and_assets_exist(built_site: tuple[dict, list[Path]]) -> None:
    site, _ = built_site
    expected = [
        DIST_DIR / "index.html",
        DIST_DIR / "projects.html",
        DIST_DIR / "about.html",
        DIST_DIR / "skills.html",
        DIST_DIR / "contact.html",
        DIST_DIR / "resume.html",
        DIST_DIR / "404.html",
        DIST_DIR / "sitemap.xml",
        DIST_DIR / "robots.txt",
        DIST_DIR / ".nojekyll",
        DIST_DIR / "static" / "style.css",
        DIST_DIR / "static" / "images" / "profile.jpg",
    ]
    for project in site["projects"]:
        expected.append(DIST_DIR / "projects" / f"{project['slug']}.html")
        real_img = DIST_DIR / "static" / "images" / str(project.get("screenshot") or "")
        fallback_svg = DIST_DIR / "static" / "images" / f"card-{project['slug']}.svg"
        assert real_img.is_file(), f"Missing real screenshot asset for {project['slug']}: {real_img}"
        assert not fallback_svg.exists(), f"Unexpected fallback SVG generated for {project['slug']}: {fallback_svg}"

    for path in expected:
        assert path.is_file(), f"Missing generated file: {path}"


def test_no_scripts_inline_styles_or_emoji(built_site: tuple[dict, list[Path]]) -> None:
    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        inspector = PageInspector()
        inspector.feed(content)

        assert inspector.script_count == 0, f"<script> found in {html_file}"
        assert inspector.inline_style_count == 0, f"Inline style attribute found in {html_file}"
        assert not inspector.imgs_without_alt, f"Images missing alt text in {html_file}: {inspector.imgs_without_alt}"
        assert not inspector.imgs_missing_dimensions, f"Images missing width/height in {html_file}: {inspector.imgs_missing_dimensions}"
        assert not EMOJI_PATTERN.search(content), f"Emoji character found in {html_file}"


def test_no_disallowed_words_dates_or_location(built_site: tuple[dict, list[Path]]) -> None:
    disallowed_anywhere = ("ozoro", "asaba", "©", "&copy;", "notification of result", "student", "certificate")
    for dist_file in sorted(DIST_DIR.rglob("*")):
        if not dist_file.is_file() or dist_file.suffix not in {".html", ".xml", ".txt"}:
            continue
        text = dist_file.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "ozoro" not in lowered, f"Found 'Ozoro' in {dist_file}"
        assert "asaba" not in lowered, f"Found 'Asaba' in {dist_file}"
        if dist_file.suffix == ".html":
            for term in disallowed_anywhere:
                assert term not in lowered, f"Disallowed term '{term}' found in {dist_file}"


def test_single_h1_and_meta_description_on_every_page(built_site: tuple[dict, list[Path]]) -> None:
    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        inspector = PageInspector()
        inspector.feed(content)

        assert inspector.h1_count == 1, f"Expected 1 H1 in {html_file}, found {inspector.h1_count}"
        assert len(inspector.meta_descriptions) == 1, f"Missing meta description in {html_file}"
        assert inspector.meta_descriptions[0].strip(), f"Empty meta description in {html_file}"


def test_every_project_has_title_repo_live_links_and_diagram_caption(built_site: tuple[dict, list[Path]]) -> None:
    site, _ = built_site
    projects_html = (DIST_DIR / "projects.html").read_text(encoding="utf-8")
    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")

    expected_live_urls = {
        "https://debudgetbuddy.netlify.app",
        "https://frontdoortemplates.netlify.app",
        "https://sarahfashionhub.netlify.app",
        "https://thevybeplayer.netlify.app",
    }

    for live_url in expected_live_urls:
        for html_source in (index_html, projects_html):
            inspector = PageInspector()
            inspector.feed(html_source)
            matched = [link for link in inspector.links if link.get("href") == live_url]
            assert matched, f"Missing live URL {live_url}"
            assert all(link.get("rel") == "noopener noreferrer" for link in matched)

    for project in site["projects"]:
        assert project["title"] in projects_html
        assert f"projects/{project['slug']}.html" in projects_html
        assert project["github_url"] in projects_html

        detail_html = (DIST_DIR / "projects" / f"{project['slug']}.html").read_text(encoding="utf-8")
        assert project["title"] in detail_html
        assert project["github_url"] in detail_html

    cicd_detail = (DIST_DIR / "projects" / "ci-cd-pipeline-showcase.html").read_text(encoding="utf-8")
    assert "Pipeline diagram" in index_html
    assert "Pipeline diagram" in projects_html
    assert "Pipeline diagram" in cicd_detail
    assert "View live" not in cicd_detail
    assert "Live demo" not in cicd_detail


def test_empty_links_are_not_rendered(built_site: tuple[dict, list[Path]]) -> None:
    site, _ = built_site

    resume_html = (DIST_DIR / "resume.html").read_text(encoding="utf-8")
    if not site["cv_link"]:
        assert "Download CV" not in resume_html
        assert "CV coming soon" in resume_html

    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        inspector = PageInspector()
        inspector.feed(content)
        for href in inspector.hrefs:
            assert href.strip() != "", f"Empty href rendered in {html_file}"
        if not site["upwork"]:
            assert "Upwork" not in content, f"Empty Upwork link rendered in {html_file}"


def test_internal_links_and_images_resolve_to_existing_files(built_site: tuple[dict, list[Path]]) -> None:
    external_prefixes = ("http://", "https://", "mailto:", "data:")

    for html_file in _all_html_files():
        inspector = PageInspector()
        inspector.feed(html_file.read_text(encoding="utf-8"))

        for target in inspector.hrefs + inspector.srcs:
            if target.startswith(external_prefixes) or target.startswith("#"):
                continue
            clean_target = target.split("#", 1)[0]
            if not clean_target:
                continue
            resolved = (html_file.parent / clean_target).resolve()
            assert resolved.is_file(), f"Broken target '{target}' in {html_file} (expected {resolved})"


def test_contact_and_social_links_match_site_json(built_site: tuple[dict, list[Path]]) -> None:
    site, _ = built_site
    contact_html = (DIST_DIR / "contact.html").read_text(encoding="utf-8")
    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")

    for page_content in (contact_html, index_html):
        assert f'href="mailto:{site["email"]}"' in page_content
        assert f'href="{site["github"]}"' in page_content
        assert f'href="{site["linkedin"]}"' in page_content


def test_navigation_skills_education_experience_and_ai_rule(built_site: tuple[dict, list[Path]]) -> None:
    site, _ = built_site
    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    about_html = (DIST_DIR / "about.html").read_text(encoding="utf-8")
    skills_html = (DIST_DIR / "skills.html").read_text(encoding="utf-8")
    resume_html = (DIST_DIR / "resume.html").read_text(encoding="utf-8")
    sitemap_xml = (DIST_DIR / "sitemap.xml").read_text(encoding="utf-8")

    for label in ("About me", "Skills", "Portfolio", "Resume", "CONTACT ME"):
        assert label in index_html

    assert "skills.html" in sitemap_xml
    for skill_name in ("HTML", "CSS", "Python", "Java"):
        assert skill_name in skills_html
    assert "Self-taught, learning" in skills_html
    assert "Learning Java on my own." in skills_html
    assert "TypeScript" not in skills_html

    expected_edu = "B.Sc. Software Engineering, Southern Delta University. Graduated with Second Class Honours (Upper Division), CGPA 4.30."
    assert expected_edu in index_html
    assert expected_edu in about_html
    assert expected_edu in resume_html
    assert "CGPA 4.30" in about_html

    for page_html in (index_html, resume_html):
        assert "Experience" in page_html
        assert "Delta State Innovation Hub" in page_html
        assert "AI and Data Intern and Substitute Tutor" in page_html
        assert "Cavista Technologies" in page_html
        assert "Software Engineering Intern" in page_html

    assert "Full experience" in index_html
    assert resume_html.index("Experience") < resume_html.index("Education")

    # No dates shown for the two roles or award date
    month_year_pattern = re.compile(
        r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b\s+\d{4}|\b20(?:2[0-9]|1[0-9])\b",
        flags=re.IGNORECASE,
    )
    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        assert not month_year_pattern.search(content), f"Found unexpected date/year in {html_file}"

    assert "I use AI tools as a secondary aid for routine work. I write, review and test the code myself." in about_html
    assert "AI tools" not in index_html
    assert "AI tools" not in skills_html
    assert "AI tools" not in resume_html

    # Footer rules: EA monogram, email/GitHub/LinkedIn links, Built line only; no nav links or copyright
    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        footer_html = content.split("<footer", 1)[1].split("</footer>", 1)[0]
        inspector = PageInspector()
        inspector.feed(footer_html)
        for forbidden_nav in ("about.html", "skills.html", "projects.html", "resume.html", "contact.html"):
            assert forbidden_nav not in inspector.hrefs, f"Forbidden nav link '{forbidden_nav}' in footer of {html_file}"
        assert f"mailto:{site['email']}" in inspector.hrefs
        assert site["github"] in inspector.hrefs
        assert site["linkedin"] in inspector.hrefs
        assert site["email"] in footer_html
        assert "Built with Python, HTML and CSS" in footer_html
        assert "©" not in footer_html and "&copy;" not in footer_html


def test_portrait_attributes_and_placement(built_site: tuple[dict, list[Path]]) -> None:
    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    about_html = (DIST_DIR / "about.html").read_text(encoding="utf-8")
    resume_html = (DIST_DIR / "resume.html").read_text(encoding="utf-8")

    for page_html in (index_html, about_html):
        assert 'src="static/images/profile.jpg"' in page_html
        assert 'alt="Portrait of Eseoghene Asisisi"' in page_html
        assert 'width="1054"' in page_html
        assert 'height="1456"' in page_html
        assert 'loading="eager"' in page_html
        assert 'fetchpriority="high"' in page_html

    resume_body = resume_html.split("<body", 1)[1]
    assert "profile.jpg" not in resume_body
    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        footer_part = content.split("<footer", 1)[1]
        assert "profile.jpg" not in footer_part, f"Portrait appeared in footer of {html_file}"


def test_build_passes_and_falls_back_when_profile_image_removed(tmp_path: Path) -> None:
    tmp_static = tmp_path / "static"
    shutil.copytree(STATIC_DIR, tmp_static)
    profile_path = tmp_static / "images" / "profile.jpg"
    if profile_path.exists():
        profile_path.unlink()

    tmp_dist = tmp_path / "dist"
    outputs = build_site(static_dir=tmp_static, dist_dir=tmp_dist)
    assert outputs

    fallback_index = (tmp_dist / "index.html").read_text(encoding="utf-8")
    fallback_about = (tmp_dist / "about.html").read_text(encoding="utf-8")
    assert "Add profile.jpg to static/images/" in fallback_index
    assert "Add profile.jpg to static/images/" in fallback_about


def test_home_css_only_viewport_reveal_and_reduced_motion(built_site: tuple[dict, list[Path]]) -> None:
    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    css = (DIST_DIR / "static" / "style.css").read_text(encoding="utf-8")

    assert index_html.count("reveal-section") == 5
    assert "animation-timeline: view()" in css
    assert "@media (prefers-reduced-motion: no-preference)" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "animation: none !important;" in css


def test_cv_pdf_copied_valid_and_linked_with_download_attribute(built_site: tuple[dict, list[Path]]) -> None:
    site, _ = built_site
    pdf_path = DIST_DIR / "static" / "files" / "Eseoghene_CV.pdf"
    assert pdf_path.is_file(), f"Missing built CV PDF at {pdf_path}"
    assert pdf_path.read_bytes().startswith(b"%PDF"), "Eseoghene_CV.pdf does not start with %PDF"

    expected_href = site["cv_link"]
    assert expected_href == "static/files/Eseoghene_CV.pdf"

    for page_name in ("resume.html", "index.html", "contact.html"):
        page_file = DIST_DIR / page_name
        html_text = page_file.read_text(encoding="utf-8")
        inspector = PageInspector()
        inspector.feed(html_text)
        dl_links = [
            link for link in inspector.links
            if link.get("href") == expected_href and "download" in link
        ]
        assert dl_links, f"Missing CV link with download attribute on {page_name}"
        for link in dl_links:
            assert link["download"] == "Eseoghene_Asisisi_CV.pdf"
            assert link.get("aria-label") == "Download Eseoghene Asisisi's CV as a PDF"
            assert (page_file.parent / link["href"]).resolve() == pdf_path.resolve()

    resume_html = (DIST_DIR / "resume.html").read_text(encoding="utf-8")
    assert "Download CV" in resume_html
    assert "PDF, 3 pages" in resume_html
    assert "View in browser" in resume_html
    assert "CV coming soon" not in resume_html

    index_html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
    contact_html = (DIST_DIR / "contact.html").read_text(encoding="utf-8")
    assert "Download CV" in index_html
    assert "Download my CV" in index_html
    assert "Download my CV" in contact_html

    # Keep header navigation and footer free of CV links
    for html_file in _all_html_files():
        text = html_file.read_text(encoding="utf-8")
        header_html = text.split("<header", 1)[1].split("</header>", 1)[0]
        footer_html = text.split("<footer", 1)[1].split("</footer>", 1)[0]
        for region in (header_html, footer_html):
            assert "Eseoghene_CV.pdf" not in region
            assert "Download CV" not in region
            assert "Download my CV" not in region


def test_cv_links_hidden_when_cv_link_empty(tmp_path: Path) -> None:
    site = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    site["cv_link"] = ""
    tmp_data = tmp_path / "site.json"
    tmp_data.write_text(json.dumps(site), encoding="utf-8")

    tmp_dist = tmp_path / "dist"
    build_site(data_path=tmp_data, dist_dir=tmp_dist)

    resume_html = (tmp_dist / "resume.html").read_text(encoding="utf-8")
    assert "CV coming soon" in resume_html
    for forbidden in ("Download CV", "Download my CV", "PDF, 3 pages", "View in browser", "Eseoghene_CV.pdf"):
        assert forbidden not in resume_html

    for html_file in _all_html_files(tmp_dist):
        if html_file.name == "resume.html":
            continue
        content = html_file.read_text(encoding="utf-8")
        for forbidden in ("Download CV", "Download my CV", "CV coming soon", "Eseoghene_CV.pdf"):
            assert forbidden not in content, f"Unexpected '{forbidden}' in {html_file}"


def test_sitemap_robots_and_canonical_use_netlify_portfolio_url(built_site: tuple[dict, list[Path]]) -> None:
    expected_base = "https://eseogheneportfolio.netlify.app/"
    sitemap_xml = (DIST_DIR / "sitemap.xml").read_text(encoding="utf-8")
    robots_txt = (DIST_DIR / "robots.txt").read_text(encoding="utf-8")

    assert f"<loc>{expected_base}</loc>" in sitemap_xml
    assert f"<loc>{expected_base}resume.html</loc>" in sitemap_xml
    assert f"Sitemap: {expected_base}sitemap.xml" in robots_txt
    assert "giftstack-dev.github.io" not in sitemap_xml
    assert "giftstack-dev.github.io" not in robots_txt

    for html_file in _all_html_files():
        content = html_file.read_text(encoding="utf-8")
        inspector = PageInspector()
        inspector.feed(content)
        assert len(inspector.canonicals) == 1, f"Expected 1 canonical tag in {html_file}"
        assert inspector.canonicals[0].startswith(expected_base), f"Unexpected canonical URL in {html_file}: {inspector.canonicals[0]}"
        assert len(inspector.og_urls) == 1, f"Expected 1 og:url meta tag in {html_file}"
        assert inspector.og_urls[0].startswith(expected_base), f"Unexpected og:url in {html_file}: {inspector.og_urls[0]}"
