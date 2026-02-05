from pathlib import Path
import nbformat
from nbclient import NotebookClient
from PIL import Image
import base64
import textwrap

SOURCE_DIR = Path("source")
GALLERY_SECTIONS = [
    SOURCE_DIR / "plot_types",
    SOURCE_DIR / "examples",
    SOURCE_DIR / "analysis",
    SOURCE_DIR / "tutorials",
]

IMAGE_DIR_NAME = "images"
NOTEBOOK_DIR_NAME = "notebooks"


def title_from_slug(slug):
    return slug.replace("_", " ").replace("-", " ").title()


def extract_notebook_assets(nb_path, output_dir):
    nb = nbformat.read(nb_path, as_version=4)

    client = NotebookClient(nb, timeout=600, kernel_name="python3")
    client.execute()

    # --- extract first code cell ---
    code_snippet = None
    for cell in nb.cells:
        if cell.cell_type == "code" and cell.source.strip():
            code_snippet = cell.source
            break

    # --- extract first image output ---
    image_path = None
    for cell in nb.cells:
        for output in cell.get("outputs", []):
            data = output.get("data", {})
            if "image/png" in data:
                raw = base64.b64decode(data["image/png"])
                image_path = output_dir / f"{nb_path.stem}.png"
                Image.open(Path(image_path).with_suffix(".png").open("wb"))
                image_path.write_bytes(raw)
                return code_snippet, image_path

    return code_snippet, None


def write_plot_page(section_dir, slug, title, image_rel, code):
    rst = f"""{title}
{'=' * len(title)}

.. image:: {image_rel}
   :align: center
   :class: plot-thumbnail

Example code
------------

.. code-block:: python

{textwrap.indent(code or '# No code available', '   ')}
"""
    out = section_dir / f"{slug}.rst"
    out.write_text(rst)
    print(f"✔ Generated {out}")


def build_gallery(section_dir):
    notebooks = section_dir / NOTEBOOK_DIR_NAME
    images = section_dir / IMAGE_DIR_NAME
    images.mkdir(exist_ok=True)

    items = []

    if notebooks.exists():
        for nb in notebooks.glob("*.ipynb"):
            slug = nb.stem
            title = title_from_slug(slug)

            code, img_path = extract_notebook_assets(nb, images)
            if img_path:
                write_plot_page(
                    section_dir,
                    slug,
                    title,
                    f"images/{img_path.name}",
                    code,
                )
                items.append({
                    "title": title,
                    "image": f"images/{img_path.name}",
                    "link": f"{slug}.html",
                })

    return items


def write_index_rst(section_dir, items):
    title = section_dir.name.replace("_", " ").title()
    rst = f"""{title}
{'=' * len(title)}

.. raw:: html

   {{% set items = {items!r} %}}
   {{% include "gallery.html" %}}
"""
    (section_dir / "index.rst").write_text(rst)


def main():
    for root in GALLERY_SECTIONS:
        for section in root.iterdir():
            if not section.is_dir():
                continue
            items = build_gallery(section)
            if items:
                write_index_rst(section, items)


if __name__ == "__main__":
    main()
