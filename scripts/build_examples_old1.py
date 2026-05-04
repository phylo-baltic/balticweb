#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# ----------------------------
# Configuration
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_SRC = PROJECT_ROOT / "source/baltic-examples"

SPHINX_SOURCE = PROJECT_ROOT / "source"
EXAMPLES_DOCS = SPHINX_SOURCE / "examples"
STATIC_EXAMPLES = SPHINX_SOURCE / "_static" / "examples"

# How many images per category card to rotate through
MAX_IMAGES_PER_CATEGORY = 12

# Valid image extensions
IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Category:
    name: str              # e.g. "SARS-CoV-2"
    slug: str              # e.g. "sars-cov-2"
    images: list[str]      # relative paths under _static/examples/<slug>/
    page_rel: str          # e.g. "sars-cov-2/index.html"


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\- ]+", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s


def find_images(folder: Path) -> list[Path]:
    imgs = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in IMG_EXTS:
            imgs.append(p)
    # stable ordering
    imgs.sort(key=lambda x: x.name.lower())
    return imgs


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def copy_images(category_folder: Path, slug: str, images: list[Path]) -> list[str]:
    """
    Copy images into source/_static/examples/<slug>/ and return list of
    web-relative image paths like "_static/examples/<slug>/<file>.png"
    (but in templates we’ll use paths relative to HTML root: "_static/...").
    """
    out_dir = STATIC_EXAMPLES / slug
    ensure_dir(out_dir)

    rels = []
    for img in images[:MAX_IMAGES_PER_CATEGORY]:
        dest = out_dir / img.name
        shutil.copy2(img, dest)
        rels.append(f"_static/examples/{slug}/{img.name}")
    return rels


def build_category_page(cat: Category) -> str:
    """
    A simple per-category page that shows all images and links to source code.
    You can later swap this to your “gallery item -> plot page” pattern.
    """
    title = cat.name
    underline = "=" * len(title)

    # Build a simple grid
    items_html = "\n".join(
        f"""<a class="gallery-item" href="#" title="{Path(img).name}">
  <img src="{img}" alt="{title} example image"/>
  <span>{Path(img).stem}</span>
</a>"""
        for img in cat.images
    )

    # Link to the GitHub folder if you want (optional)
    return f"""\
{title}
{underline}

.. raw:: html

   <p class="examples-lead">
     Examples for <strong>{title}</strong>.
   </p>

   <div class="gallery-grid">
{indent_html(items_html, 6)}
   </div>
"""


def indent_html(s: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in s.splitlines())


def build_landing_page(categories: list[Category]) -> str:
    title = "Examples"
    underline = "=" * len(title)

    # Pass categories to template via a JSON script tag
    data = [
        {"title": c.name, "slug": c.slug, "page": c.page_rel, "images": c.images}
        for c in categories
    ]
    data_json = json.dumps(data, ensure_ascii=False)

    return f"""\
{title}
{underline}

.. raw:: html

   <div class="examples-landing">
     <p class="examples-lead">
       Browse examples by dataset / project. Each card cycles through figures from that folder.
     </p>

     <script id="examples-data" type="application/json">{data_json}</script>

     <div id="examples-grid" class="examples-grid"></div>

   </div>
"""


def build_js() -> str:
    # Builds the cards dynamically and rotates images per card.
    return r"""\
(() => {
  const el = document.getElementById("examples-data");
  const grid = document.getElementById("examples-grid");
  if (!el || !grid) return;

  const categories = JSON.parse(el.textContent || "[]");

  function makeCard(cat) {
    const a = document.createElement("a");
    a.className = "examples-card";
    a.href = cat.page || "#";

    const img = document.createElement("img");
    img.className = "examples-card__img";
    img.alt = cat.title || "Example";
    img.loading = "lazy";

    const overlay = document.createElement("div");
    overlay.className = "examples-card__overlay";

    const h = document.createElement("div");
    h.className = "examples-card__title";
    h.textContent = cat.title || "";

    overlay.appendChild(h);

    // Set initial image
    const imgs = Array.isArray(cat.images) ? cat.images : [];
    let i = 0;
    img.src = imgs[0] || "_static/no_image.png";

    // Rotate on interval when hovered
    let timer = null;
    a.addEventListener("mouseenter", () => {
      if (imgs.length <= 1) return;
      timer = window.setInterval(() => {
        i = (i + 1) % imgs.length;
        img.src = imgs[i];
      }, 900);
    });
    a.addEventListener("mouseleave", () => {
      if (timer) window.clearInterval(timer);
      timer = null;
      i = 0;
      img.src = imgs[0] || "_static/no_image.png";
    });

    a.appendChild(img);
    a.appendChild(overlay);
    return a;
  }

  categories.forEach(cat => grid.appendChild(makeCard(cat)));
})();
"""


def main() -> None:
    if not EXAMPLES_SRC.exists():
        raise SystemExit(f"Missing folder: {EXAMPLES_SRC}")

    ensure_dir(EXAMPLES_DOCS)
    ensure_dir(STATIC_EXAMPLES)

    categories: list[Category] = []

    for folder in sorted([p for p in EXAMPLES_SRC.iterdir() if p.is_dir()], key=lambda p: p.name.lower()):
        imgs = find_images(folder)
        if not imgs:
            # skip folders without rendered images
            continue

        slug = slugify(folder.name)
        copied = copy_images(folder, slug, imgs)

        cat = Category(
            name=folder.name,
            slug=slug,
            images=copied,
            page_rel=f"examples/{slug}/index.html",
        )
        categories.append(cat)

        # write per-category page
        cat_dir = EXAMPLES_DOCS / slug
        write_text(cat_dir / "index.rst", build_category_page(cat))

    # write landing page
    write_text(EXAMPLES_DOCS / "index.rst", build_landing_page(categories))

    # write JS and CSS assets
    ensure_dir(SPHINX_SOURCE / "_static" / "js")
    ensure_dir(SPHINX_SOURCE / "_static" / "css")
    write_text(SPHINX_SOURCE / "_static" / "js" / "examples-grid.js", build_js())

    print(f"Generated {len(categories)} example categories.")
    print(f"- Landing: {EXAMPLES_DOCS / 'index.rst'}")
    print(f"- Category pages: {EXAMPLES_DOCS}/<slug>/index.rst")
    print(f"- Images: {STATIC_EXAMPLES}/<slug>/*")


if __name__ == "__main__":
    main()
