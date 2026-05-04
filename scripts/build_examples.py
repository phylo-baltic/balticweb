#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EXAMPLES_SRC = PROJECT_ROOT / "source" / "baltic-examples"          # input
SPHINX_SOURCE = PROJECT_ROOT / "source"
EXAMPLES_DOCS = SPHINX_SOURCE / "examples"                           # output rst
STATIC_EXAMPLES = SPHINX_SOURCE / "_static" / "examples"             # output images
DESC_FILE = SPHINX_SOURCE / "_data" / "examples_description.txt"     # manual text

IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8").strip()


def safe_read_code(p: Path, max_chars: int = 200_000) -> str:
    try:
        txt = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        txt = p.read_text(encoding="latin-1")
    if len(txt) > max_chars:
        txt = txt[:max_chars] + "\n# ... truncated ...\n"
    return txt


def indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.splitlines())


@dataclass
class ExampleItem:
    category_name: str
    category_slug: str
    example_name: str
    example_slug: str
    img_web: str | None          # _static/examples/<cat>/<file>.png
    rst_doc: str                 # <cat>/<example>
    html_href: str               # <cat>/<example>.html


def collect_items() -> tuple[list[ExampleItem], dict[str, list[ExampleItem]]]:
    items: list[ExampleItem] = []
    by_cat: dict[str, list[ExampleItem]] = {}

    if not EXAMPLES_SRC.exists():
        raise SystemExit(f"Missing input folder: {EXAMPLES_SRC}")

    categories = sorted([p for p in EXAMPLES_SRC.iterdir() if p.is_dir()], key=lambda p: p.name.lower())

    for cat_dir in categories:
        cat_name = cat_dir.name
        cat_slug = slugify(cat_name)

        # Expect example files inside category: <example>.py and <example>.png
        py_files = sorted(cat_dir.glob("*.py"), key=lambda p: p.name.lower())

        for py in py_files:
            ex_name = py.stem
            ex_slug = slugify(ex_name)

            # image with same stem (png preferred)
            img = None
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                cand = cat_dir / f"{ex_name}{ext}"
                if cand.exists():
                    img = cand
                    break

            img_web = None
            if img and img.suffix.lower() in IMG_EXTS:
                out_img_dir = STATIC_EXAMPLES / cat_slug
                ensure_dir(out_img_dir)
                dest = out_img_dir / img.name
                shutil.copy2(img, dest)
                img_web = f"_static/examples/{cat_slug}/{img.name}"

            # it = ExampleItem(
            #     category_name=cat_name,
            #     category_slug=cat_slug,
            #     example_name=ex_name,
            #     example_slug=ex_slug,
            #     img_web=img_web,
            #     # rst_doc=f"{cat_slug}/{ex_slug}",
            #     # html_href=f"{cat_slug}/{ex_slug}.html",
            #     rst_doc=f"{ex_slug}",
            #     html_href=f"{ex_slug}.html",
            # )
            doc_slug = f"{cat_slug}-{ex_slug}"

            it = ExampleItem(
                category_name=cat_name,
                category_slug=cat_slug,
                example_name=ex_name,
                example_slug=ex_slug,
                img_web=img_web,
                rst_doc=doc_slug,
                html_href=f"{doc_slug}.html",
            )
            items.append(it)
            by_cat.setdefault(cat_slug, []).append(it)

    # stable ordering
    for k in by_cat:
        by_cat[k].sort(key=lambda x: x.example_name.lower())

    return items, by_cat


def write_example_page(item: ExampleItem) -> None:
    # cat_dir = EXAMPLES_DOCS / item.category_slug
    # ensure_dir(cat_dir)
    ensure_dir(EXAMPLES_DOCS)


    # input .py path
    py_path = EXAMPLES_SRC / item.category_name / f"{item.example_name}.py"
    code = safe_read_code(py_path)

    hero = item.img_web or "_static/no_image.png"

    title = item.example_name.replace("-", " ")
    underline = "=" * len(title)

    rst = f"""\
{title}
{underline}

.. image:: /{hero}
   :alt: {item.example_name}
   :class: example-detail__hero-img

Code
----

.. code-block:: python

{indent(code.rstrip() + "\\n", 3)}
"""
    # (cat_dir / f"{item.example_slug}.rst").write_text(rst, encoding="utf-8")
    # (EXAMPLES_DOCS / f"{item.example_slug}.rst").write_text(rst, encoding="utf-8")
    (EXAMPLES_DOCS / f"{item.rst_doc}.rst").write_text(rst, encoding="utf-8")


def write_category_index(cat_slug: str, cat_items: list[ExampleItem], cat_name: str) -> None:
    # Optional: category landing page (you can keep it minimal or hide it)
    cat_dir = EXAMPLES_DOCS / cat_slug
    ensure_dir(cat_dir)

    title = cat_name
    underline = "=" * len(title)

    # Hidden toctree of examples within category
    entries = "\n".join(f"   {it.example_slug}" for it in cat_items)

    rst = f"""\
{title}
{underline}

.. toctree::
   :maxdepth: 1
   :hidden:

{entries}
"""
    (cat_dir / "index.rst").write_text(rst, encoding="utf-8")


def write_examples_landing(by_cat: dict[str, list[ExampleItem]], items: list[ExampleItem]) -> None:
    ensure_dir(EXAMPLES_DOCS)

    desc = ""
    if DESC_FILE.exists():
        desc = read_text(DESC_FILE)

    # Build raw HTML sections per category
    sections_html: list[str] = []
    for cat_slug in sorted(by_cat.keys()):
        cat_items = by_cat[cat_slug]
        cat_name = cat_items[0].category_name if cat_items else cat_slug

        cards: list[str] = []
        for it in cat_items:
            img = it.img_web or "_static/no_image.png"
            cards.append(
                f"""
<a class="gallery-card" href="{it.html_href}">
  <div class="gallery-card__imgwrap">
    <img src="/{img}" alt="{it.example_name}">
    <div class="gallery-card__overlay">
      <div class="gallery-card__title">{it.example_name}</div>
    </div>
  </div>
</a>
""".strip()
            )

        section = f"""
<section class="examples-section">
  <h2 class="examples-section__title">{cat_name}</h2>
  <div class="gallery-grid">
    {''.join(cards)}
  </div>
</section>
""".strip()
        sections_html.append(section)

    # Sidebar navigation grouped by category WITHOUT category index pages.
    # Each category becomes a captioned toctree listing its examples directly.
    toc_blocks: list[str] = []
    for cat_slug in sorted(by_cat.keys()):
        cat_items = by_cat[cat_slug]
        if not cat_items:
            continue

        cat_name = cat_items[0].category_name if cat_items else cat_slug
        entries = "\n".join(f"   {it.rst_doc}" for it in cat_items)

        toc_blocks.append(
            f"""\
.. toctree::
   :caption: {cat_name}
   :maxdepth: 1
   :hidden:

{entries}
"""
        )

    toc_text = "\n".join(toc_blocks)

    title = "Examples"
    underline = "=" * len(title)

    rst = f"""\
{title}
{underline}

{desc}

.. raw:: html

{indent("\n".join(sections_html), 3)}

{toc_text}
"""
    (EXAMPLES_DOCS / "index.rst").write_text(rst, encoding="utf-8")

def main() -> None:
    items, by_cat = collect_items()

    # clean output docs folder (optional: you can comment this out if you prefer)
    ensure_dir(EXAMPLES_DOCS)
    ensure_dir(STATIC_EXAMPLES)

    # write pages
    for it in items:
        write_example_page(it)

    # write per-category index.rst (optional but recommended)
    # for cat_slug, cat_items in by_cat.items():
    #     cat_name = cat_items[0].category_name if cat_items else cat_slug
    #     write_category_index(cat_slug, cat_items, cat_name)

    # write landing page
    write_examples_landing(by_cat, items)

    print(f"Generated {len(by_cat)} categories, {len(items)} example pages.")
    print(f"- Landing: {EXAMPLES_DOCS / 'index.rst'}")
    print(f"- Category dirs: {EXAMPLES_DOCS}/<category>/")
    print(f"- Images: {STATIC_EXAMPLES}/<category>/*")


if __name__ == "__main__":
    main()
