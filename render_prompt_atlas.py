#!/usr/bin/env python3
"""Render the prompt research repo into a self-contained HTML atlas.

Theme: Signal Archive
Palette direction: editorial paper + ocean-depth accents for long-form reading.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from markdown_it import MarkdownIt
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "markdown-it-py is required. Install it with "
        "`python -m pip install markdown-it-py` and rerun the script."
    ) from exc


ROOT = Path(__file__).resolve().parent
README_PATH = ROOT / "README.md"
DEFAULT_OUTPUT = ROOT / "prompt_atlas.html"
CATEGORY_BLURBS = {
    "Core Identity": "Base behavior, safety framing, and the prompt assembly contract.",
    "Orchestration": "How a coordinator delegates, synthesizes, and sequences worker tasks.",
    "Specialized Agents": "Dedicated agents for verification, exploration, and setup.",
    "Security and Permissions": "Approval heuristics, risk classification, and automation limits.",
    "Tool Descriptions": "How tools explain their own contracts and operating boundaries.",
    "Utility Patterns": "Smaller support prompts for labeling, search, memory, and summaries.",
    "Context Window Management": "Compression and recap patterns for long-running sessions.",
    "Dynamic Behaviors": "Adaptive runtime behaviors such as proactive mode and browser flows.",
    "Skill Patterns": "Reusable workflows packaged as task-oriented skills.",
}


@dataclass
class CatalogEntry:
    number: str
    title: str
    path: str
    description: str
    category: str


@dataclass
class PromptDoc:
    number: str
    title: str
    description: str
    category: str
    category_slug: str
    path: str
    anchor: str
    rendered_html: str
    raw_markdown: str
    headings: list[tuple[int, str, str]]
    word_count: int
    section_count: int
    code_block_count: int
    observed_in: str | None
    search_blob: str


def slugify(value: str) -> str:
    cleaned = re.sub(r"[`*_~]+", "", value)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"&[a-z]+;", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", cleaned)
    return cleaned.strip("-") or "section"


def strip_inline_markdown(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"\*([^*]+)\*", r"\1", value)
    value = re.sub(r"_([^_]+)_", r"\1", value)
    return value.strip()


def extract_catalog(readme_text: str) -> list[CatalogEntry]:
    entries: list[CatalogEntry] = []
    current_category: str | None = None
    in_catalog = False

    for line in readme_text.splitlines():
        if line.startswith("## Documented Patterns"):
            in_catalog = True
            continue
        if in_catalog and line.startswith("## Architectural Observations"):
            break
        if not in_catalog:
            continue
        if line.startswith("### "):
            current_category = line[4:].strip()
            continue
        if not current_category or not line.startswith("|"):
            continue
        if "[" not in line or "](" not in line:
            continue

        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not re.fullmatch(r"\d{2}", cells[0]):
            continue
        link_match = re.search(r"\[(.+?)\]\((.+?)\)", cells[1])
        if not link_match:
            continue

        entries.append(
            CatalogEntry(
                number=cells[0],
                title=link_match.group(1).strip(),
                path=link_match.group(2).strip(),
                description=cells[2],
                category=current_category,
            )
        )

    if not entries:
        raise ValueError("Could not parse any prompt catalog entries from README.md")
    return entries


def extract_section_markdown(text: str, heading: str) -> str:
    lines = text.splitlines()
    target = f"## {heading}"
    start: int | None = None
    for idx, line in enumerate(lines):
        if line.strip() == target:
            start = idx + 1
            break
    if start is None:
        return ""

    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return "\n".join(lines[start:end]).strip()


def extract_intro_markdown(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    start = 1 if lines[0].startswith("# ") else 0
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].startswith("## "):
            end = idx
            break
    return "\n".join(lines[start:end]).strip()


def build_markdown_renderer() -> MarkdownIt:
    md = MarkdownIt(
        "commonmark",
        {
            "html": False,
            "linkify": False,
            "typographer": False,
        },
    ).enable(["table"])

    base_render = md.renderer.renderToken

    def heading_open(tokens, idx, options, env):
        token = tokens[idx]
        inline = tokens[idx + 1] if idx + 1 < len(tokens) else None
        title = inline.content if inline and inline.type == "inline" else token.tag
        prefix = env.get("heading_prefix", "")
        token.attrSet("id", slugify(f"{prefix}-{title}"))
        token.attrJoin("class", "md-heading")
        return base_render(tokens, idx, options, env)

    def table_open(tokens, idx, options, env):
        tokens[idx].attrJoin("class", "md-table")
        return base_render(tokens, idx, options, env)

    def blockquote_open(tokens, idx, options, env):
        tokens[idx].attrJoin("class", "md-callout")
        return base_render(tokens, idx, options, env)

    def fence(tokens, idx, options, env):
        token = tokens[idx]
        info = (token.info or "").strip()
        language = info.split()[0] if info else ""
        label = language.upper() if language else "PROMPT BLOCK"
        code = html.escape(token.content)
        return (
            '<div class="code-shell">'
            '<div class="code-shell__header">'
            f"<span>{html.escape(label)}</span>"
            '<button class="copy-code" type="button">Copy</button>'
            "</div>"
            f"<pre><code>{code}</code></pre>"
            "</div>"
        )

    md.renderer.rules["heading_open"] = heading_open
    md.renderer.rules["table_open"] = table_open
    md.renderer.rules["blockquote_open"] = blockquote_open
    md.renderer.rules["fence"] = fence
    return md


def collect_headings(text: str, anchor_prefix: str) -> list[tuple[int, str, str]]:
    headings: list[tuple[int, str, str]] = []
    for line in text.splitlines():
        match = re.match(r"^(#{2,4})\s+(.*)$", line)
        if not match:
            continue
        level = len(match.group(1))
        title = strip_inline_markdown(match.group(2))
        if not title:
            continue
        headings.append((level, title, slugify(f"{anchor_prefix}-{title}")))
    return headings


def parse_prompt_docs(catalog: Iterable[CatalogEntry], md: MarkdownIt) -> list[PromptDoc]:
    docs: list[PromptDoc] = []
    for entry in catalog:
        path = ROOT / entry.path
        raw = path.read_text(encoding="utf-8")
        anchor = f"prompt-{entry.number}-{slugify(entry.title)}"
        headings = collect_headings(raw, anchor)
        observed_match = re.search(r"^\>\s+\*\*Observed in\*\*:\s*(.+)$", raw, re.MULTILINE)
        observed = observed_match.group(1).strip() if observed_match else None

        docs.append(
            PromptDoc(
                number=entry.number,
                title=entry.title,
                description=entry.description,
                category=entry.category,
                category_slug=slugify(entry.category),
                path=entry.path,
                anchor=anchor,
                rendered_html=md.render(raw, env={"heading_prefix": anchor}),
                raw_markdown=raw,
                headings=headings,
                word_count=len(re.findall(r"\b[\w'-]+\b", raw)),
                section_count=sum(1 for level, _, _ in headings if level == 2),
                code_block_count=len(re.findall(r"^```", raw, flags=re.MULTILINE)) // 2,
                observed_in=observed,
                search_blob=" ".join(
                    [entry.number, entry.title, entry.description, entry.category, raw]
                ).lower(),
            )
        )
    return docs


def render_markdown_fragment(md: MarkdownIt, text: str, prefix: str) -> str:
    if not text.strip():
        return ""
    return md.render(text.strip(), env={"heading_prefix": prefix})


def render_sidebar(categories: OrderedDict[str, list[PromptDoc]]) -> str:
    pills = [
        '<button class="filter-chip is-active" type="button" data-category="all">All prompts</button>'
    ]
    groups: list[str] = []

    for category, docs in categories.items():
        category_slug = slugify(category)
        pills.append(
            f'<button class="filter-chip" type="button" data-category="{category_slug}">'
            f"{html.escape(category)}"
            f"<span>{len(docs)}</span>"
            "</button>"
        )
        links = "\n".join(
            (
                f'<a class="nav-link" href="#{doc.anchor}" data-category="{category_slug}">'
                f'<span class="nav-link__number">{doc.number}</span>'
                f"<span>{html.escape(doc.title)}</span>"
                "</a>"
            )
            for doc in docs
        )
        groups.append(
            f"""
            <section class="nav-group" data-category="{category_slug}">
              <div class="nav-group__header">
                <h3>{html.escape(category)}</h3>
                <span>{len(docs)}</span>
              </div>
              <p>{html.escape(CATEGORY_BLURBS.get(category, "Prompt family."))}</p>
              <div class="nav-group__links">
                {links}
              </div>
            </section>
            """
        )

    return f"""
    <aside class="sidebar">
      <div class="brand-panel">
        <p class="brand-panel__eyebrow">Signal Archive</p>
        <h1>Prompt Atlas</h1>
        <p class="brand-panel__copy">
          A structured reading interface for reconstructed agentic AI prompts.
        </p>
      </div>

      <label class="search-shell" for="prompt-search">
        <span>Search the library</span>
        <input id="prompt-search" type="search" placeholder="Search titles, behaviors, tools, or security rules">
      </label>

      <section class="filter-panel">
        <div class="filter-panel__header">
          <h2>Categories</h2>
          <span id="results-summary">Showing all prompts</span>
        </div>
        <div class="filter-chip-row">
          {''.join(pills)}
        </div>
      </section>

      <nav class="nav-stack">
        {''.join(groups)}
      </nav>
    </aside>
    """


def render_prompt_outline(doc: PromptDoc) -> str:
    if not doc.headings:
        return ""
    items = [
        f'<a class="outline-link outline-link--l{level}" href="#{anchor}">{html.escape(title)}</a>'
        for level, title, anchor in doc.headings[:10]
    ]
    return f"""
    <div class="prompt-outline">
      <div class="prompt-outline__header">
        <span>Outline</span>
        <span>{len(doc.headings)} sections</span>
      </div>
      <div class="prompt-outline__links">
        {''.join(items)}
      </div>
    </div>
    """


def render_prompt_card(doc: PromptDoc) -> str:
    observed_html = ""
    if doc.observed_in:
        observed_html = (
            f'<span class="meta-pill meta-pill--observed">'
            f"Observed in: {html.escape(doc.observed_in)}"
            "</span>"
        )

    return f"""
    <article
      class="prompt-card"
      id="{doc.anchor}"
      data-category="{doc.category_slug}"
      data-search="{html.escape(doc.search_blob)}"
      data-view="rendered"
    >
      <header class="prompt-card__header">
        <div class="prompt-card__title-block">
          <div class="prompt-card__meta">
            <span class="meta-pill meta-pill--number">{doc.number}</span>
            <span class="meta-pill meta-pill--category">{html.escape(doc.category)}</span>
            {observed_html}
          </div>
          <h3>{html.escape(doc.title)}</h3>
          <p>{html.escape(doc.description)}</p>
        </div>
        <div class="prompt-card__tools">
          <div class="stat-strip">
            <span>{doc.word_count:,} words</span>
            <span>{doc.section_count} primary sections</span>
            <span>{doc.code_block_count} code blocks</span>
          </div>
          <div class="view-toggle" role="tablist" aria-label="Display mode">
            <button class="view-toggle__button is-active" type="button" data-view-target="rendered">Formatted</button>
            <button class="view-toggle__button" type="button" data-view-target="source">Source</button>
            <a class="source-link" href="{html.escape(doc.path)}">Open markdown</a>
          </div>
        </div>
      </header>

      <div class="prompt-card__body">
        {render_prompt_outline(doc)}
        <div class="prompt-card__content">
          <section class="markdown-body prompt-rendered">
            {doc.rendered_html}
          </section>
          <section class="prompt-source">
            <pre>{html.escape(doc.raw_markdown)}</pre>
          </section>
        </div>
      </div>
    </article>
    """


def render_category_sections(categories: OrderedDict[str, list[PromptDoc]]) -> str:
    sections: list[str] = []
    for category, docs in categories.items():
        category_slug = slugify(category)
        prompt_html = "".join(render_prompt_card(doc) for doc in docs)
        sections.append(
            f"""
            <section class="category-section" data-category="{category_slug}" id="category-{category_slug}">
              <header class="category-section__header">
                <div>
                  <p class="category-section__eyebrow">Prompt Family</p>
                  <h2>{html.escape(category)}</h2>
                  <p>{html.escape(CATEGORY_BLURBS.get(category, "Prompt family."))}</p>
                </div>
                <span class="category-section__count">{len(docs)} prompts</span>
              </header>
              <div class="prompt-stack">
                {prompt_html}
              </div>
            </section>
            """
        )
    return "".join(sections)


def build_html(
    title: str,
    intro_html: str,
    overview_html: str,
    non_goal_html: str,
    architecture_html: str,
    use_cases_html: str,
    disclaimer_html: str,
    categories: OrderedDict[str, list[PromptDoc]],
) -> str:
    prompt_count = sum(len(docs) for docs in categories.values())
    category_count = len(categories)
    total_words = sum(doc.word_count for docs in categories.values() for doc in docs)
    total_code_blocks = sum(doc.code_block_count for docs in categories.values() for doc in docs)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    overview_cards = []
    for label, body in [
        ("Project framing", overview_html),
        ("Scope boundary", non_goal_html),
        ("Architectural observations", architecture_html),
        ("Use cases", use_cases_html),
    ]:
        if not body:
            continue
        overview_cards.append(
            f"""
            <article class="overview-card">
              <p class="overview-card__eyebrow">{html.escape(label)}</p>
              <div class="markdown-body">
                {body}
              </div>
            </article>
            """
        )

    disclaimer_block = ""
    if disclaimer_html:
        disclaimer_block = f"""
        <section class="disclaimer-strip">
          <div class="markdown-body">
            {disclaimer_html}
          </div>
        </section>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23124559'/%3E%3Cpath d='M18 22h28v4H18zm0 8h18v4H18zm0 8h28v4H18z' fill='%23d8edf0'/%3E%3C/svg%3E">
  <style>
    :root {{
      --bg: #eef3f6;
      --bg-glow: rgba(18, 89, 110, 0.12);
      --panel: rgba(255, 255, 255, 0.82);
      --panel-solid: #fbfcfd;
      --ink: #10253a;
      --ink-soft: #46627a;
      --accent: #0b7285;
      --accent-strong: #124559;
      --accent-soft: #d8edf0;
      --edge: rgba(16, 37, 58, 0.12);
      --shadow: 0 24px 80px rgba(18, 48, 72, 0.12);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --font-ui: "Avenir Next", "Segoe UI", sans-serif;
      --font-body: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
      --font-mono: "SFMono-Regular", "JetBrains Mono", "Menlo", monospace;
      color-scheme: light;
    }}

    * {{
      box-sizing: border-box;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      margin: 0;
      font-family: var(--font-ui);
      background:
        radial-gradient(circle at top left, var(--bg-glow), transparent 30rem),
        radial-gradient(circle at top right, rgba(11, 114, 133, 0.08), transparent 32rem),
        linear-gradient(180deg, #f8fbfc 0%, var(--bg) 100%);
      color: var(--ink);
    }}

    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(18, 69, 89, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(18, 69, 89, 0.04) 1px, transparent 1px);
      background-size: 32px 32px;
      mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.32), transparent 60%);
      z-index: 0;
    }}

    a {{
      color: inherit;
      text-decoration: none;
    }}

    .page-shell {{
      position: relative;
      z-index: 1;
      display: grid;
      grid-template-columns: minmax(18rem, 23rem) minmax(0, 1fr);
      min-height: 100vh;
    }}

    .sidebar {{
      position: sticky;
      top: 0;
      align-self: start;
      height: 100vh;
      overflow: auto;
      padding: 1.5rem;
      border-right: 1px solid var(--edge);
      background: rgba(247, 250, 252, 0.78);
      backdrop-filter: blur(18px);
    }}

    .brand-panel,
    .filter-panel,
    .nav-group,
    .hero,
    .overview-card,
    .category-section__header,
    .prompt-card,
    .disclaimer-strip {{
      background: var(--panel);
      border: 1px solid var(--edge);
      box-shadow: var(--shadow);
      border-radius: var(--radius-xl);
    }}

    .brand-panel {{
      padding: 1.4rem 1.35rem;
      margin-bottom: 1rem;
    }}

    .brand-panel__eyebrow,
    .overview-card__eyebrow,
    .hero__eyebrow,
    .category-section__eyebrow {{
      margin: 0 0 0.55rem;
      font-size: 0.76rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: var(--accent);
      font-weight: 700;
    }}

    .brand-panel h1,
    .hero h1,
    .category-section__header h2,
    .prompt-card__title-block h3 {{
      margin: 0;
      line-height: 1.05;
      font-weight: 700;
    }}

    .brand-panel h1 {{
      font-size: 2rem;
    }}

    .brand-panel__copy,
    .filter-panel__header span,
    .nav-group p,
    .hero p,
    .category-section__header p,
    .prompt-card__title-block p,
    .stat-strip,
    .prompt-outline__header,
    .markdown-body,
    .source-link,
    .search-shell span {{
      color: var(--ink-soft);
    }}

    .search-shell {{
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
      margin-bottom: 1rem;
    }}

    .search-shell input {{
      width: 100%;
      padding: 0.95rem 1rem;
      border: 1px solid var(--edge);
      border-radius: 999px;
      font: inherit;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.95);
    }}

    .search-shell input:focus {{
      outline: 2px solid rgba(11, 114, 133, 0.18);
      border-color: rgba(11, 114, 133, 0.35);
    }}

    .filter-panel {{
      padding: 1rem;
      margin-bottom: 1rem;
    }}

    .filter-panel__header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      margin-bottom: 0.85rem;
    }}

    .filter-panel__header h2 {{
      margin: 0;
      font-size: 1rem;
    }}

    .filter-chip-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.55rem;
    }}

    .filter-chip {{
      border: 1px solid var(--edge);
      border-radius: 999px;
      padding: 0.55rem 0.85rem;
      font: inherit;
      font-size: 0.92rem;
      color: var(--ink);
      background: rgba(255, 255, 255, 0.88);
      cursor: pointer;
      transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
    }}

    .filter-chip span {{
      margin-left: 0.45rem;
      color: var(--ink-soft);
    }}

    .filter-chip:hover,
    .filter-chip.is-active {{
      transform: translateY(-1px);
      border-color: rgba(11, 114, 133, 0.36);
      background: var(--accent-soft);
    }}

    .nav-stack {{
      display: grid;
      gap: 1rem;
      padding-bottom: 2rem;
    }}

    .nav-group {{
      padding: 1rem;
    }}

    .nav-group__header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 1rem;
      margin-bottom: 0.5rem;
    }}

    .nav-group__header h3 {{
      margin: 0;
      font-size: 1rem;
    }}

    .nav-group__links {{
      display: grid;
      gap: 0.35rem;
    }}

    .nav-link {{
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 0.7rem;
      padding: 0.55rem 0.65rem;
      border-radius: 14px;
      color: var(--ink-soft);
      transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
    }}

    .nav-link:hover,
    .nav-link.is-current {{
      background: rgba(11, 114, 133, 0.12);
      color: var(--ink);
      transform: translateX(2px);
    }}

    .nav-link__number {{
      font-family: var(--font-mono);
      color: var(--accent);
    }}

    .content {{
      padding: 2rem;
      display: grid;
      gap: 1.6rem;
    }}

    .hero {{
      padding: 2rem;
      position: relative;
      overflow: hidden;
    }}

    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -6rem -8rem auto;
      width: 20rem;
      height: 20rem;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(11, 114, 133, 0.16) 0%, transparent 72%);
      pointer-events: none;
    }}

    .hero h1 {{
      max-width: 13ch;
      font-size: clamp(2.6rem, 4vw, 4.75rem);
      margin-bottom: 0.9rem;
    }}

    .hero__lede {{
      max-width: 68ch;
      font-size: 1.04rem;
      line-height: 1.75;
      font-family: var(--font-body);
    }}

    .hero__meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      margin-top: 1.2rem;
    }}

    .hero-stat {{
      min-width: 10rem;
      padding: 0.9rem 1rem;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.8);
      border: 1px solid var(--edge);
    }}

    .hero-stat strong {{
      display: block;
      font-size: 1.35rem;
      color: var(--ink);
    }}

    .overview-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 1.25rem;
    }}

    .overview-card {{
      padding: 1.35rem 1.45rem;
    }}

    .disclaimer-strip {{
      padding: 1rem 1.35rem;
      border-radius: var(--radius-lg);
      background: rgba(18, 69, 89, 0.92);
      color: #f4f8fb;
    }}

    .disclaimer-strip .markdown-body,
    .disclaimer-strip .markdown-body p,
    .disclaimer-strip .markdown-body li {{
      color: inherit;
    }}

    .category-section {{
      display: grid;
      gap: 1rem;
    }}

    .category-section__header {{
      padding: 1.5rem 1.6rem;
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 1rem;
    }}

    .category-section__count {{
      padding: 0.7rem 1rem;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent-strong);
      font-weight: 700;
    }}

    .prompt-stack {{
      display: grid;
      gap: 1.2rem;
    }}

    .prompt-card {{
      padding: 1.4rem;
      scroll-margin-top: 1.5rem;
      animation: lift-in 420ms ease both;
    }}

    @keyframes lift-in {{
      from {{
        opacity: 0;
        transform: translateY(10px);
      }}
      to {{
        opacity: 1;
        transform: translateY(0);
      }}
    }}

    .prompt-card__header {{
      display: flex;
      justify-content: space-between;
      gap: 1rem 1.4rem;
      align-items: start;
      margin-bottom: 1.15rem;
    }}

    .prompt-card__meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
      margin-bottom: 0.7rem;
    }}

    .meta-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.42rem 0.72rem;
      border-radius: 999px;
      font-size: 0.84rem;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid var(--edge);
      color: var(--ink-soft);
    }}

    .meta-pill--number {{
      background: var(--accent-strong);
      border-color: transparent;
      color: #f3f9fc;
      font-family: var(--font-mono);
    }}

    .meta-pill--category {{
      background: var(--accent-soft);
      color: var(--accent-strong);
    }}

    .meta-pill--observed {{
      background: rgba(16, 37, 58, 0.06);
    }}

    .prompt-card__title-block h3 {{
      font-size: clamp(1.5rem, 2vw, 2rem);
      margin-bottom: 0.4rem;
    }}

    .prompt-card__title-block p {{
      max-width: 70ch;
      font-size: 1rem;
      line-height: 1.65;
      margin: 0;
      font-family: var(--font-body);
    }}

    .prompt-card__tools {{
      display: grid;
      gap: 0.8rem;
      min-width: 18rem;
    }}

    .stat-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      justify-content: end;
      font-size: 0.9rem;
    }}

    .stat-strip span {{
      padding: 0.4rem 0.65rem;
      border-radius: 999px;
      background: rgba(16, 37, 58, 0.04);
      border: 1px solid var(--edge);
    }}

    .view-toggle {{
      display: flex;
      justify-content: end;
      align-items: center;
      gap: 0.55rem;
      flex-wrap: wrap;
    }}

    .view-toggle__button,
    .source-link,
    .copy-code {{
      border: 1px solid var(--edge);
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
      border-radius: 999px;
      padding: 0.55rem 0.85rem;
      font: inherit;
      cursor: pointer;
      transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
    }}

    .view-toggle__button.is-active,
    .view-toggle__button:hover,
    .source-link:hover,
    .copy-code:hover {{
      background: var(--accent-soft);
      border-color: rgba(11, 114, 133, 0.36);
      transform: translateY(-1px);
    }}

    .prompt-card__body {{
      display: grid;
      gap: 1rem;
    }}

    .prompt-outline {{
      padding: 1rem 1rem 0.15rem;
      border-radius: var(--radius-lg);
      background: rgba(248, 251, 252, 0.92);
      border: 1px solid var(--edge);
    }}

    .prompt-outline__header {{
      display: flex;
      justify-content: space-between;
      gap: 1rem;
      margin-bottom: 0.8rem;
      font-size: 0.9rem;
    }}

    .prompt-outline__links {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}

    .outline-link {{
      display: inline-flex;
      align-items: center;
      min-height: 2.1rem;
      padding: 0.45rem 0.75rem;
      border-radius: 999px;
      background: rgba(11, 114, 133, 0.08);
      color: var(--accent-strong);
      font-size: 0.9rem;
      line-height: 1.2;
    }}

    .outline-link--l3 {{
      background: rgba(18, 69, 89, 0.06);
      color: var(--ink-soft);
    }}

    .outline-link--l4 {{
      opacity: 0.82;
    }}

    .prompt-card__content {{
      border-radius: var(--radius-lg);
      overflow: hidden;
      border: 1px solid var(--edge);
      background: #fbfcfd;
    }}

    .prompt-rendered,
    .prompt-source {{
      padding: 1.35rem 1.45rem;
    }}

    .prompt-source {{
      display: none;
      background: #f7f9fb;
    }}

    .prompt-source pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: var(--font-mono);
      font-size: 0.92rem;
      line-height: 1.65;
      color: var(--ink);
    }}

    .prompt-card[data-view="source"] .prompt-source {{
      display: block;
    }}

    .prompt-card[data-view="source"] .prompt-rendered {{
      display: none;
    }}

    .markdown-body {{
      font-family: var(--font-body);
      font-size: 1.05rem;
      line-height: 1.82;
    }}

    .markdown-body > :first-child {{
      margin-top: 0;
    }}

    .markdown-body > :last-child {{
      margin-bottom: 0;
    }}

    .markdown-body h1,
    .markdown-body h2,
    .markdown-body h3,
    .markdown-body h4 {{
      color: var(--ink);
      line-height: 1.2;
      margin-top: 1.7em;
      margin-bottom: 0.65em;
      scroll-margin-top: 1.75rem;
      font-family: var(--font-ui);
    }}

    .markdown-body h1 {{
      font-size: 2rem;
    }}

    .markdown-body h2 {{
      font-size: 1.5rem;
    }}

    .markdown-body h3 {{
      font-size: 1.2rem;
    }}

    .markdown-body p,
    .markdown-body li {{
      color: var(--ink-soft);
    }}

    .markdown-body strong {{
      color: var(--ink);
    }}

    .markdown-body code {{
      font-family: var(--font-mono);
      font-size: 0.9em;
      background: rgba(18, 69, 89, 0.08);
      padding: 0.15rem 0.34rem;
      border-radius: 0.35rem;
      color: var(--accent-strong);
    }}

    .markdown-body pre code {{
      padding: 0;
      background: transparent;
      color: inherit;
    }}

    .markdown-body ul,
    .markdown-body ol {{
      padding-left: 1.45rem;
    }}

    .markdown-body li + li {{
      margin-top: 0.25rem;
    }}

    .markdown-body hr {{
      border: 0;
      border-top: 1px solid var(--edge);
      margin: 2rem 0;
    }}

    .md-callout {{
      margin: 1.3rem 0;
      padding: 0.9rem 1rem;
      border-left: 4px solid var(--accent);
      background: linear-gradient(90deg, rgba(11, 114, 133, 0.12), rgba(11, 114, 133, 0.04));
      border-radius: 0 16px 16px 0;
    }}

    .md-callout p {{
      margin: 0.2rem 0;
    }}

    .md-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 1.2rem 0;
      font-family: var(--font-ui);
      font-size: 0.95rem;
      border: 1px solid var(--edge);
      overflow: hidden;
    }}

    .md-table th,
    .md-table td {{
      padding: 0.8rem 0.9rem;
      border-bottom: 1px solid rgba(16, 37, 58, 0.08);
      vertical-align: top;
    }}

    .md-table th {{
      text-align: left;
      background: rgba(11, 114, 133, 0.08);
      color: var(--accent-strong);
    }}

    .code-shell {{
      margin: 1.4rem 0;
      border-radius: 20px;
      overflow: hidden;
      border: 1px solid rgba(12, 24, 38, 0.75);
      background: #102132;
    }}

    .code-shell__header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      padding: 0.75rem 0.9rem;
      font-family: var(--font-ui);
      font-size: 0.84rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: rgba(230, 244, 247, 0.74);
      background: rgba(255, 255, 255, 0.03);
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }}

    .copy-code {{
      padding: 0.38rem 0.72rem;
      color: #eaf5f7;
      border-color: rgba(255, 255, 255, 0.14);
      background: rgba(255, 255, 255, 0.08);
    }}

    .copy-code.is-copied {{
      background: rgba(0, 191, 165, 0.16);
      border-color: rgba(0, 191, 165, 0.4);
    }}

    .code-shell pre {{
      margin: 0;
      padding: 1rem 1.1rem 1.15rem;
      overflow: auto;
      color: #e4eef2;
      font-family: var(--font-mono);
      font-size: 0.92rem;
      line-height: 1.72;
    }}

    .prompt-card.is-hidden,
    .category-section.is-hidden,
    .nav-group.is-hidden,
    .nav-link.is-hidden {{
      display: none;
    }}

    @media (max-width: 1120px) {{
      .page-shell {{
        grid-template-columns: 1fr;
      }}

      .sidebar {{
        position: relative;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--edge);
      }}
    }}

    @media (max-width: 860px) {{
      .content {{
        padding: 1rem;
      }}

      .hero,
      .overview-card,
      .prompt-card,
      .category-section__header {{
        border-radius: 22px;
      }}

      .overview-grid {{
        grid-template-columns: 1fr;
      }}

      .hero h1 {{
        max-width: none;
      }}

      .prompt-card__header,
      .category-section__header,
      .filter-panel__header {{
        flex-direction: column;
        align-items: start;
      }}

      .prompt-card__tools,
      .stat-strip,
      .view-toggle {{
        justify-content: start;
        min-width: 0;
      }}

      .hero__meta {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 560px) {{
      .hero__meta {{
        grid-template-columns: 1fr;
      }}

      .prompt-rendered,
      .prompt-source,
      .overview-card,
      .prompt-card,
      .hero,
      .category-section__header {{
        padding-left: 1rem;
        padding-right: 1rem;
      }}

      .prompt-outline {{
        padding-left: 0.85rem;
        padding-right: 0.85rem;
      }}
    }}
  </style>
</head>
<body>
  <div class="page-shell">
    {render_sidebar(categories)}

    <main class="content">
      <section class="hero">
        <p class="hero__eyebrow">HTML Reading Edition</p>
        <h1>Claude Code Prompt Research Atlas</h1>
        <div class="hero__lede markdown-body">
          {intro_html}
        </div>
        <div class="hero__meta">
          <div class="hero-stat">
            <strong>{prompt_count}</strong>
            Prompt reconstructions
          </div>
          <div class="hero-stat">
            <strong>{category_count}</strong>
            Research categories
          </div>
          <div class="hero-stat">
            <strong>{total_words:,}</strong>
            Total source words
          </div>
          <div class="hero-stat">
            <strong>{total_code_blocks}</strong>
            Embedded prompt blocks
          </div>
          <div class="hero-stat">
            <strong>{generated_at}</strong>
            Generated locally
          </div>
        </div>
      </section>

      <section class="overview-grid">
        {''.join(overview_cards)}
      </section>

      {disclaimer_block}

      {render_category_sections(categories)}
    </main>
  </div>

  <script>
    const searchInput = document.getElementById("prompt-search");
    const cards = [...document.querySelectorAll(".prompt-card")];
    const sections = [...document.querySelectorAll(".category-section")];
    const navGroups = [...document.querySelectorAll(".nav-group")];
    const navLinks = [...document.querySelectorAll(".nav-link")];
    const filterChips = [...document.querySelectorAll(".filter-chip")];
    const resultsSummary = document.getElementById("results-summary");
    let activeCategory = "all";

    function updateResultsSummary(visibleCount) {{
      if (activeCategory === "all" && !searchInput.value.trim()) {{
        resultsSummary.textContent = "Showing all prompts";
        return;
      }}
      resultsSummary.textContent = `Showing ${{visibleCount}} of ${{cards.length}} prompts`;
    }}

    function applyFilters() {{
      const query = searchInput.value.trim().toLowerCase();
      let visibleCards = 0;

      cards.forEach((card) => {{
        const matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
        const matchesQuery = !query || card.dataset.search.includes(query);
        const visible = matchesCategory && matchesQuery;
        card.classList.toggle("is-hidden", !visible);
        if (visible) {{
          visibleCards += 1;
        }}
      }});

      sections.forEach((section) => {{
        const visibleChildren = section.querySelectorAll(".prompt-card:not(.is-hidden)").length;
        section.classList.toggle("is-hidden", visibleChildren === 0);
        const label = section.querySelector(".category-section__count");
        if (label) {{
          label.textContent = `${{visibleChildren}} prompt${{visibleChildren === 1 ? "" : "s"}}`;
        }}
      }});

      navGroups.forEach((group) => {{
        const links = [...group.querySelectorAll(".nav-link")];
        links.forEach((link) => {{
          const target = document.getElementById(link.getAttribute("href").slice(1));
          const visible = target && !target.classList.contains("is-hidden");
          link.classList.toggle("is-hidden", !visible);
        }});
        const visibleChildren = group.querySelectorAll(".nav-link:not(.is-hidden)").length;
        group.classList.toggle("is-hidden", visibleChildren === 0);
      }});

      updateResultsSummary(visibleCards);
    }}

    function scrollToActiveCategory() {{
      if (activeCategory === "all") {{
        window.scrollTo({{ top: 0, behavior: "smooth" }});
        return;
      }}
      const target = document.getElementById(`category-${{activeCategory}}`);
      if (target && !target.classList.contains("is-hidden")) {{
        target.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}
    }}

    filterChips.forEach((chip) => {{
      chip.addEventListener("click", () => {{
        activeCategory = chip.dataset.category;
        filterChips.forEach((item) => item.classList.toggle("is-active", item === chip));
        applyFilters();
        window.requestAnimationFrame(scrollToActiveCategory);
      }});
    }});

    searchInput.addEventListener("input", applyFilters);

    function fallbackCopy(text) {{
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }}

    document.addEventListener("click", async (event) => {{
      const toggle = event.target.closest("[data-view-target]");
      if (toggle) {{
        const card = toggle.closest(".prompt-card");
        if (card) {{
          card.dataset.view = toggle.dataset.viewTarget;
          card.querySelectorAll(".view-toggle__button").forEach((button) => {{
            button.classList.toggle("is-active", button === toggle);
          }});
        }}
      }}

      const copyButton = event.target.closest(".copy-code");
      if (copyButton) {{
        const code = copyButton.closest(".code-shell")?.querySelector("code");
        if (code) {{
          const text = code.innerText;
          if (navigator.clipboard && window.isSecureContext) {{
            await navigator.clipboard.writeText(text);
          }} else {{
            fallbackCopy(text);
          }}
          copyButton.classList.add("is-copied");
          const original = copyButton.textContent;
          copyButton.textContent = "Copied";
          window.setTimeout(() => {{
            copyButton.textContent = original;
            copyButton.classList.remove("is-copied");
          }}, 1200);
        }}
      }}
    }});

    const anchorToNav = new Map(
      navLinks.map((link) => [link.getAttribute("href").slice(1), link])
    );

    const observer = new IntersectionObserver(
      (entries) => {{
        entries.forEach((entry) => {{
          const link = anchorToNav.get(entry.target.id);
          if (!link) {{
            return;
          }}
          if (entry.isIntersecting) {{
            navLinks.forEach((item) => item.classList.remove("is-current"));
            link.classList.add("is-current");
          }}
        }});
      }},
      {{
        rootMargin: "-18% 0px -72% 0px",
        threshold: 0,
      }}
    );

    cards.forEach((card) => observer.observe(card));
    applyFilters();
  </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the prompt repo into a readable HTML atlas.")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output HTML path. Defaults to {DEFAULT_OUTPUT.name}",
    )
    parser.add_argument(
        "--title",
        default="Prompt Atlas",
        help="Document title for the generated HTML file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    readme_text = README_PATH.read_text(encoding="utf-8")
    catalog = extract_catalog(readme_text)
    markdown = build_markdown_renderer()
    docs = parse_prompt_docs(catalog, markdown)

    grouped_docs: dict[str, list[PromptDoc]] = defaultdict(list)
    for doc in docs:
        grouped_docs[doc.category].append(doc)

    categories: OrderedDict[str, list[PromptDoc]] = OrderedDict()
    for entry in catalog:
        if entry.category not in categories:
            categories[entry.category] = grouped_docs[entry.category]

    html_text = build_html(
        title=args.title,
        intro_html=render_markdown_fragment(markdown, extract_intro_markdown(readme_text), "overview-intro"),
        overview_html=render_markdown_fragment(markdown, extract_section_markdown(readme_text, "What This Project Is"), "overview-what"),
        non_goal_html=render_markdown_fragment(markdown, extract_section_markdown(readme_text, "What This Project Is Not"), "overview-not"),
        architecture_html=render_markdown_fragment(markdown, extract_section_markdown(readme_text, "Architectural Observations"), "overview-architecture"),
        use_cases_html=render_markdown_fragment(markdown, extract_section_markdown(readme_text, "Use Cases"), "overview-use-cases"),
        disclaimer_html=render_markdown_fragment(markdown, extract_section_markdown(readme_text, "Disclaimer"), "overview-disclaimer"),
        categories=categories,
    )

    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.write_text(html_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "output": str(output_path),
                "prompt_count": len(docs),
                "category_count": len(categories),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
