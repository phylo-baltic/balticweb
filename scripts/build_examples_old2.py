#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

# ----------------------------
# Configuration
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_SRC = PROJECT_ROOT / "source" / "baltic-examples"

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
    images: list[str]      # web-relative paths: "_static/examples/<slug>/<file>.png"
    page_doc: str          # docname for toctree: "<slug>/index"
    page_href: str         # href used in raw html landing: "<slug>/"


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\- ]+", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def indent(s: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in s.splitlines())


def find_images(folder: Path) -> list[Path]:
    imgs = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXTS]
    imgs.sort(key=lambda x: x.name.lower())
    return imgs


def find_py_files(folder: Path) -> list[Path]:
    pys = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".py"]
    pys.sort(key=lambda x: x.name.lower())
    return pys


def safe_read_text(p: Path, max_chars: int = 200_000) -> str:
    """
    Read a text file safely. Truncates very large files to keep builds sane.
    """
    try:
        txt = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        txt = p.read_text(encoding="latin-1")

    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n\n# ... (truncated)\n"
    return txt


def copy_images(slug: str, images: list[Path]) -> list[str]:
    """
    Copy images into source/_static/examples/<slug>/ and return web-relative
    paths like "_static/examples/<slug>/<file>.png".
    """
    out_dir = STATIC_EXAMPLES / slug
    ensure_dir(out_dir)

    rels: list[str] = []
    for img in images[:MAX_IMAGES_PER_CATEGORY]:
        dest = out_dir / img.name
        shutil.copy2(img, dest)
        rels.append(f"_static/examples/{slug}/{img.name}")
    return rels


def build_category_page(cat: Category, py_files: list[Path]) -> str:
    """
    Per-example page:
    - Main image (first)
    - optional grid of all images
    - code block (first .py or concatenated)
    """
    title = cat.name
    underline = "=" * len(title)

    # Hero image (first one)
    hero_img = cat.images[0] if cat.images else "_static/no_image.png"

    # Small gallery (all copied images)
    thumbs_html = "\n".join(
        f"""<a class="gallery-item" href="{img}" target="_blank" rel="noopener">
  <img src="{img}" alt="{title} figure"/>
  <span>{Path(img).stem}</span>
</a>"""
        for img in cat.images
    )

    # Code: by default, show first .py (you can switch to join all)
    code_block = ""
    if py_files:
        code = safe_read_text(py_files[0])
        code_block = (
            "\n\nCode\n----\n\n.. code-block:: python\n\n"
            + indent(code.rstrip() + "\n", 3)
        )
    else:
        code_block = "\n\n.. note::\n\n   No ``.py`` file was found in this example folder.\n"

    return f"""\
{title}
{underline}

.. raw:: html

   <div class="example-detail">

     <div class="example-detail__hero">
       <img class="example-detail__hero-img" src="{hero_img}" alt="{title} main figure"/>
     </div>

     <div class="gallery-grid">
{indent(thumbs_html, 7)}
     </div>

   </div>
{code_block}
"""


def build_landing_page(categories: list[Category]) -> str:
    """
    Landing page with:
    - dynamic card grid (JS reads JSON)
    - hidden toctree including all child pages (fixes toc.not_included)
    """
    title = "Examples"
    underline = "=" * len(title)

    data = [
        {
            "title": c.name,
            "slug": c.slug,
            "page": c.page_href,     # IMPORTANT: relative to /examples/
            "images": c.images,
        }
        for c in categories
    ]
    data_json = json.dumps(data, ensure_ascii=False)

    # Hidden toctree (so Sphinx includes all example pages)
    toctree_entries = "\n".join(f"   {c.page_doc}" for c in categories)

    return f"""\
{title}
{underline}

.. raw:: html

   <div class="examples-landing">
     <p class="examples-lead">
       Browse examples. Each card cycles through figures from that folder.
     </p>

     <script id="examples-data" type="application/json">{data_json}</script>

     <div id="examples-grid" class="examples-grid"></div>
   </div>

.. toctree::
   :maxdepth: 1
   :hidden:

{toctree_entries}
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
    // page is relative to /examples/ (because we are on examples/index.html)
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

    const imgs = Array.isArray(cat.images) ? cat.images : [];
    let i = 0;
    img.src = imgs[0] || "_static/no_image.png";

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

    # Each folder inside baltic-examples is one example "category/page"
    folders = sorted([p for p in EXAMPLES_SRC.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    for folder in folders:
        imgs = find_images(folder)
        py_files = find_py_files(folder)

        # If folder has neither image nor python, skip it
        if not imgs and not py_files:
            continue

        slug = slugify(folder.name)

        copied_imgs = copy_images(slug, imgs) if imgs else []

        cat = Category(
            name=folder.name,
            slug=slug,
            images=copied_imgs,
            page_doc=f"{slug}/index",
            page_href=f"{slug}/",  # relative to examples/
        )
        categories.append(cat)

        # Write per-example page
        cat_dir = EXAMPLES_DOCS / slug
        write_text(cat_dir / "index.rst", build_category_page(cat, py_files))

    # Write landing page (with hidden toctree)
    write_text(EXAMPLES_DOCS / "index.rst", build_landing_page(categories))

    # Write JS
    ensure_dir(SPHINX_SOURCE / "_static" / "js")
    write_text(SPHINX_SOURCE / "_static" / "js" / "examples-grid.js", build_js())

    print(f"Generated {len(categories)} examples.")
    print(f"- Landing: {EXAMPLES_DOCS / 'index.rst'}")
    print(f"- Example pages: {EXAMPLES_DOCS}/<slug>/index.rst")
    print(f"- Images: {STATIC_EXAMPLES}/<slug>/*")
    print(f"- JS: {SPHINX_SOURCE / '_static/js/examples-grid.js'}")


if __name__ == "__main__":
    main()
