"""Static site generator for Eseoghene Gift-Asisisi Asisisi's portfolio.

Reads data/site.json and images.json, renders Jinja2 templates in templates/ into
plain HTML files inside dist/, copies static assets, generates monochrome fallback
SVG covers if an image file is missing, and writes sitemap.xml and robots.txt.
"""

from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT_DIR = Path(__file__).resolve().parent
DATA_FILE = ROOT_DIR / "data" / "site.json"
IMAGES_FILE = ROOT_DIR / "images.json"
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
DIST_DIR = ROOT_DIR / "dist"


def load_site_data(data_path: Path = DATA_FILE) -> dict[str, Any]:
    """Load portfolio content from the single JSON data file."""
    with data_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_images_manifest(images_path: Path = IMAGES_FILE) -> dict[str, Any]:
    """Load image metadata (alt text, dimensions, captions) from images.json."""
    if not images_path.is_file():
        return {}
    with images_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def generate_project_card_svg(project: dict[str, Any], out_path: Path) -> None:
    """Create a monochrome + green SVG preview if a screenshot file is missing."""
    slug = str(project.get("slug") or "project")
    title = html.escape(str(project.get("title") or "Project"))
    number = html.escape(str(project.get("number") or "00"))

    if slug == "budget-buddy":
        motif = (
            '<rect x="52" y="52" width="536" height="276" rx="8" fill="#161616" stroke="#2E2E2E" stroke-width="2"/>'
            '<rect x="100" y="210" width="44" height="84" rx="4" fill="#4A4A4A"/>'
            '<rect x="172" y="176" width="44" height="118" rx="4" fill="#9A9A9A"/>'
            '<rect x="244" y="130" width="44" height="164" rx="4" fill="#0E7C66"/>'
            '<rect x="316" y="188" width="44" height="106" rx="4" fill="#D6D6D6"/>'
        )
    elif slug == "ci-cd-pipeline-showcase":
        motif = (
            '<path d="M120 190 H520" stroke="#4A4A4A" stroke-width="4"/>'
            '<circle cx="150" cy="190" r="24" fill="#D6D6D6"/>'
            '<circle cx="320" cy="190" r="24" fill="#FFFFFF"/>'
            '<circle cx="490" cy="190" r="24" fill="#0E7C66"/>'
        )
    else:
        motif = (
            '<rect x="52" y="48" width="536" height="284" rx="8" fill="#161616" stroke="#2E2E2E" stroke-width="2"/>'
            '<rect x="84" y="90" width="220" height="18" rx="4" fill="#FFFFFF"/>'
            '<rect x="84" y="122" width="320" height="12" rx="4" fill="#9A9A9A"/>'
            '<rect x="84" y="156" width="136" height="32" rx="16" fill="#0E7C66"/>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 380" role="img" aria-label="{title}">
  <rect width="640" height="380" fill="#0A0A0A"/>
  {motif}
  <text x="52" y="346" font-family="Raleway, Arial, sans-serif" font-size="22" font-weight="800" fill="#FFFFFF">{number} / {title}</text>
</svg>
"""
    out_path.write_text(svg, encoding="utf-8")


def prepare_dist(dist_dir: Path = DIST_DIR) -> None:
    """Reset dist/ so stale files from earlier builds never linger."""
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    (dist_dir / "projects").mkdir(parents=True, exist_ok=True)
    (dist_dir / "static" / "images").mkdir(parents=True, exist_ok=True)


def copy_static_assets(static_dir: Path = STATIC_DIR, dist_dir: Path = DIST_DIR) -> None:
    """Copy CSS and image assets into dist/static/."""
    target_static = dist_dir / "static"
    css_src = static_dir / "style.css"
    if css_src.exists():
        shutil.copy2(css_src, target_static / "style.css")

    images_src = static_dir / "images"
    images_dst = target_static / "images"
    if images_src.exists():
        for item in images_src.iterdir():
            if item.is_file():
                shutil.copy2(item, images_dst / item.name)

    files_src = static_dir / "files"
    files_dst = target_static / "files"
    if files_src.exists():
        shutil.copytree(files_src, files_dst, dirs_exist_ok=True)


def resolve_project_images(
    projects: list[dict[str, Any]],
    images_manifest: dict[str, Any],
    dist_dir: Path = DIST_DIR,
) -> None:
    """Use real screenshots/diagrams from static/images/ or generate fallback SVGs."""
    images_dst = dist_dir / "static" / "images"
    for project in projects:
        screenshot = str(project.get("screenshot") or "").strip()
        meta = images_manifest.get(screenshot, {}) if screenshot else {}
        if screenshot and (images_dst / screenshot).is_file():
            project["resolved_image"] = screenshot
            project["has_real_image"] = True
            project["image_width"] = int(meta.get("width") or 1280)
            project["image_height"] = int(meta.get("height") or 720)
            project["image_alt"] = str(meta.get("alt") or f"Preview of {project['title']}")
        else:
            svg_name = f"card-{project['slug']}.svg"
            generate_project_card_svg(project, images_dst / svg_name)
            project["resolved_image"] = svg_name
            project["has_real_image"] = False
            project["image_width"] = 640
            project["image_height"] = 380
            project["image_alt"] = f"Fallback preview illustration for {project['title']}"


def write_sitemap_and_robots(site: dict[str, Any], url_paths: list[str], dist_dir: Path = DIST_DIR) -> None:
    """Generate sitemap.xml, robots.txt, and .nojekyll for GitHub Pages and Netlify."""
    base_url = str(site.get("site_url") or "https://eseogheneportfolio.netlify.app/").rstrip("/")
    urls = "\n".join(
        f"  <url>\n    <loc>{html.escape(base_url)}{html.escape(path)}</loc>\n  </url>"
        for path in url_paths
        if path != "/404/"
    )
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )
    (dist_dir / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    robots = f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"
    (dist_dir / "robots.txt").write_text(robots, encoding="utf-8")

    # Disable Jekyll processing so GitHub Pages serves dist/ directly
    (dist_dir / ".nojekyll").write_text("", encoding="utf-8")


def write_redirects(projects: list[dict[str, Any]], dist_dir: Path = DIST_DIR) -> None:
    """Write Netlify permanent 301 _redirects rules from legacy .html routes to clean URLs."""
    lines = [
        "/index.html / 301",
        "/about.html /about/ 301",
        "/skills.html /skills/ 301",
        "/projects.html /projects/ 301",
        "/resume.html /resume/ 301",
        "/contact.html /contact/ 301",
    ]
    for project in projects:
        slug = project["slug"]
        lines.append(f"/projects/{slug}.html /projects/{slug}/ 301")
    (dist_dir / "_redirects").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_site(
    data_path: Path = DATA_FILE,
    templates_dir: Path = TEMPLATES_DIR,
    static_dir: Path = STATIC_DIR,
    dist_dir: Path = DIST_DIR,
    images_path: Path = IMAGES_FILE,
) -> list[Path]:
    """Build the entire static portfolio site and return generated HTML file paths."""
    site = load_site_data(data_path)
    images_manifest = load_images_manifest(images_path)
    projects: list[dict[str, Any]] = site.get("projects", [])

    prepare_dist(dist_dir)
    copy_static_assets(static_dir, dist_dir)
    resolve_project_images(projects, images_manifest, dist_dir)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    projects_by_slug = {p["slug"]: p for p in projects}
    category_counts = {
        "python": sum(1 for p in projects if p.get("category") == "python"),
        "html-css": sum(1 for p in projects if p.get("category") == "html-css"),
        "other": sum(1 for p in projects if p.get("category") == "other"),
    }

    images_dst = dist_dir / "static" / "images"
    profile_image = str(site.get("profile_image") or "").strip()
    profile_image_exists = bool(profile_image and (images_dst / profile_image).is_file())
    profile_meta = images_manifest.get(profile_image, {}) if profile_image else {}

    default_og_image = (
        profile_image
        if profile_image_exists
        else (projects[0]["resolved_image"] if projects else "")
    )

    generated_files: list[Path] = []
    sitemap_paths: list[str] = []

    top_pages = [
        {
            "template": "index.html",
            "output": "index.html",
            "url_path": "/",
            "active_nav": "home",
            "title": f"{site['name']} — {site['title']}",
            "description": site["hero_sentence"],
        },
        {
            "template": "projects.html",
            "output": "projects/index.html",
            "url_path": "/projects/",
            "active_nav": "projects",
            "title": f"Portfolio — {site['name']}",
            "description": "Projects built with Python, HTML, CSS, TypeScript, and GitHub Actions by Eseoghene Gift-Asisisi Asisisi.",
        },
        {
            "template": "about.html",
            "output": "about/index.html",
            "url_path": "/about/",
            "active_nav": "about",
            "title": f"About me — {site['name']}",
            "description": f"About {site['name']}, {site['title']} from {site['university']}.",
        },
        {
            "template": "skills.html",
            "output": "skills/index.html",
            "url_path": "/skills/",
            "active_nav": "skills",
            "title": f"Skills — {site['name']}",
            "description": f"Core skills and tools used by {site['name']}: HTML, CSS, Python, and Java.",
        },
        {
            "template": "contact.html",
            "output": "contact/index.html",
            "url_path": "/contact/",
            "active_nav": "contact",
            "title": f"Contact — {site['name']}",
            "description": f"Contact {site['name']} by email, GitHub, or LinkedIn.",
        },
        {
            "template": "resume.html",
            "output": "resume/index.html",
            "url_path": "/resume/",
            "active_nav": "resume",
            "title": f"Resume — {site['name']}",
            "description": f"Resume overview, skills, education, and projects for {site['name']}.",
        },
        {
            "template": "404.html",
            "output": "404.html",
            "url_path": "/404/",
            "active_nav": "",
            "title": f"Page Not Found — {site['name']}",
            "description": "The requested portfolio page could not be found.",
        },
    ]

    base_url = str(site.get("site_url") or "https://eseogheneportfolio.netlify.app/").rstrip("/")

    shared_context = {
        "site": site,
        "site_base_url": base_url,
        "projects_by_slug": projects_by_slug,
        "category_counts": category_counts,
        "profile_image_exists": profile_image_exists,
        "profile_meta": profile_meta,
        "default_og_image": default_og_image,
    }

    for page in top_pages:
        template = env.get_template(page["template"])
        url_path = page["url_path"]
        canonical_url = f"{base_url}/" if page["output"] == "404.html" else f"{base_url}{url_path}"
        rendered = template.render(
            **shared_context,
            root="/",
            page_path=url_path,
            canonical_url=canonical_url,
            active_nav=page["active_nav"],
            page_title=page["title"],
            page_description=page["description"],
            og_image=default_og_image,
        )
        out_file = dist_dir / page["output"]
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered, encoding="utf-8")
        generated_files.append(out_file)
        if page["output"] != "404.html":
            sitemap_paths.append(url_path)

    detail_template = env.get_template("project_detail.html")
    for idx, project in enumerate(projects):
        prev_project = projects[idx - 1] if idx > 0 else None
        next_project = projects[idx + 1] if idx < len(projects) - 1 else None
        output_rel = f"projects/{project['slug']}/index.html"
        url_path = f"/projects/{project['slug']}/"

        rendered = detail_template.render(
            **shared_context,
            root="/",
            page_path=url_path,
            canonical_url=f"{base_url}{url_path}",
            active_nav="projects",
            page_title=f"{project['title']} — {site['name']}",
            page_description=project["one_line_summary"],
            og_image=project["resolved_image"],
            project=project,
            prev_project=prev_project,
            next_project=next_project,
        )
        out_file = dist_dir / output_rel
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(rendered, encoding="utf-8")
        generated_files.append(out_file)
        sitemap_paths.append(url_path)

    write_sitemap_and_robots(site, sitemap_paths, dist_dir)
    write_redirects(projects, dist_dir)
    return generated_files


if __name__ == "__main__":
    outputs = build_site()
    print(f"Built {len(outputs)} HTML pages into {DIST_DIR}")
