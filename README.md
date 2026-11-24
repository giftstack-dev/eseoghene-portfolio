# Developer Portfolio — Eseoghene Gift-Asisisi Asisisi (`giftstack-dev`)

A static personal developer portfolio built with Python, Jinja2, HTML5, and CSS3. It compiles `data/site.json` and the templates in `templates/` into a plain, dependency-free `dist/` folder using clean URLs for Netlify and local HTTP preview.

## Features

- Zero JavaScript, zero inline styles, zero emoji, and a strict Content Security Policy.
- CSS-only mobile navigation drawer (checkbox), project filter tabs (radio inputs), and native `<details>` accordions.
- Single inline SVG icon sprite reused with `<use>`, plus flat inline SVG illustrations and auto-generated SVG preview cards when a project has no screenshot.
- Responsive layout across 360px, 768px, and 1280px+ viewports.

## How to build locally

### Windows (PowerShell or Command Prompt)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r py-requirements.txt
python build.py
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r py-requirements.txt
python build.py
```

After running `python build.py`, preview locally with:

```bash
python -m http.server 8000 --directory dist
```

Then open `http://localhost:8000` in your browser.

## How to edit `data/site.json`

All personal details, skills, and projects live in `data/site.json`:

- Update `email`, `github_url`, `linkedin_url`, `upwork_url`, or `cv_url` at the top of `data/site.json`.
- Any empty string (`""`) for `cv_url`, `upwork_url`, or a project's `live_url` is hidden automatically during the build so broken links never appear.
- After editing `data/site.json`, run `python build.py` again to refresh `dist/`.

## How to add a project and a screenshot

1. Save a screenshot image (for example `my-project.png`) inside `static/images/`.
2. Add a new object inside the `"projects"` array in `data/site.json` with:
   - `slug`: URL-safe folder name (e.g. `"my-project"` creates `dist/projects/my-project/index.html` served at `/projects/my-project/`)
   - `title`, `category` (`"python"`, `"html-css"`, or `"other"`), `one_line_summary`
   - `problem`, `what_i_built`, `tech_list`, `languages`, `role`, `what_i_learned`
   - `github_url`, `live_url` (optional), `screenshot`: `"my-project.png"` (or `""` to auto-generate a clean SVG card with `color` and `initials`)
   - `status`, `color`, `initials`, `illustration`, `featured`
3. Run `python build.py`.

## How to run the tests

Install `pytest` alongside the project requirements and run:

```bash
pip install pytest
pytest
```

The test suite in `tests/test_build.py` verifies that the build succeeds, every expected file exists, there are no `<script>` tags, inline `style` attributes, or emoji characters, every page has one `<h1>` and a meta description, empty links are omitted, and all internal links resolve.

## How to deploy to GitHub Pages

1. Push this repository to GitHub on the `main` branch.
2. In your GitHub repository, open **Settings > Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Every push to `main` runs `.github/workflows/deploy.yml`, which installs dependencies, executes `pytest`, runs `python build.py`, and deploys `dist/` to GitHub Pages.
