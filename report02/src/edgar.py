"""Fetch real public filings from SEC EDGAR for T2 (10-K Item 1A) and T4 (8-K earnings releases).

EDGAR fair access: every request declares a User-Agent with a name and contact email, and
the client stays well under 10 requests per second. Raw HTML is cached under
sources/edgar/raw/ so the corpus can be rebuilt without refetching.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import warnings
from pathlib import Path

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "sources" / "edgar" / "raw"
USER_AGENT = os.environ["EDGAR_USER_AGENT"]  # SEC asks for "Name email@example.com"
MIN_INTERVAL = 0.25  # seconds between requests: 4 per second, under the 10/s limit

_last_request = 0.0
_client = httpx.Client(
    headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
    timeout=60.0,
    follow_redirects=True,
)


def get(url: str, cache_name: str | None = None) -> bytes:
    global _last_request
    if cache_name:
        cached = RAW / cache_name
        if cached.exists():
            return cached.read_bytes()
    wait = MIN_INTERVAL - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    resp = _client.get(url)
    resp.raise_for_status()
    if cache_name:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(resp.content)
    return resp.content


def ticker_map() -> dict[str, int]:
    data = json.loads(get("https://www.sec.gov/files/company_tickers.json", "company_tickers.json"))
    return {row["ticker"].upper(): int(row["cik_str"]) for row in data.values()}


def submissions(cik: int) -> dict:
    return json.loads(
        get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", f"submissions/CIK{cik:010d}.json")
    )


def recent_filings(cik: int) -> list[dict]:
    rec = submissions(cik)["filings"]["recent"]
    keys = list(rec.keys())
    return [dict(zip(keys, vals)) for vals in zip(*(rec[k] for k in keys))]


def archive_url(cik: int, accession: str, name: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{name}"


def filing_exhibit(cik: int, accession: str, exhibit: str) -> str | None:
    """Return the file name of an exhibit (e.g. EX-99.1) from the filing index page."""
    idx = get(
        archive_url(cik, accession, f"{accession}-index.htm"),
        f"index/{cik}_{accession}.htm",
    )
    soup = BeautifulSoup(idx, "lxml")
    for row in soup.select("table.tableFile tr"):
        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
        if len(cells) >= 4 and cells[3].upper().startswith(exhibit.upper()):
            link = row.find("a")
            if link and link.get("href"):
                return link["href"].rsplit("/", 1)[-1]
    return None


# --- HTML to structured text --------------------------------------------------------------

BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "table"}


def _is_bold(tag: Tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    return tag.name in {"b", "strong"} or "font-weight:bold" in style or "font-weight:700" in style


def _is_italic(tag: Tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    return tag.name in {"i", "em"} or "font-style:italic" in style


def _text_runs(node: Tag, bold: bool = False, italic: bool = False) -> list[tuple[str, bool, bool]]:
    runs: list[tuple[str, bool, bool]] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            if child.strip() or child:
                runs.append((str(child), bold, italic))
        elif isinstance(child, Tag):
            if child.name in {"script", "style"} or child.name.startswith("ix:header"):
                continue
            style = (child.get("style") or "").replace(" ", "").lower()
            if "display:none" in style:
                continue
            runs.extend(_text_runs(child, bold or _is_bold(child), italic or _is_italic(child)))
    return runs


def _clean(text: str) -> str:
    text = text.replace("\xa0", " ").replace("​", "")
    return re.sub(r"\s+", " ", text).strip()


def html_to_blocks(html: bytes) -> list[dict]:
    """Flatten a filing into paragraphs, each marked as heading-like if fully bold or italic.

    Tables become one block per row with cells joined by ' | '.
    """
    try:
        markup = html.decode("utf-8")
    except UnicodeDecodeError:
        markup = html.decode("cp1252", errors="replace")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(markup, "lxml")
    for bad in soup(["script", "style", "head"]):
        bad.decompose()
    for hidden in soup.find_all(style=re.compile(r"display:\s*none", re.I)):
        hidden.decompose()
    body = soup.body or soup
    blocks: list[dict] = []

    def emit(text: str, *, bold: bool, italic: bool, kind: str) -> None:
        text = _clean(text)
        if not text:
            return
        blocks.append({"text": text, "bold": bold, "italic": italic, "kind": kind})

    def walk(node: Tag) -> None:
        for child in node.children:
            if not isinstance(child, Tag):
                if isinstance(child, NavigableString) and child.strip():
                    emit(str(child), bold=False, italic=False, kind="p")
                continue
            if child.name == "table":
                for tr in child.find_all("tr"):
                    cells = [_clean(td.get_text(" ", strip=True)) for td in tr.find_all(["td", "th"])]
                    cells = [c for c in cells if c and c not in {"$", "%", ")", "("}]
                    if cells:
                        emit(" | ".join(cells), bold=False, italic=False, kind="row")
                continue
            has_block_child = any(
                isinstance(c, Tag) and c.name in BLOCK_TAGS for c in child.children
            )
            if child.name in BLOCK_TAGS and not has_block_child:
                runs = _text_runs(child, _is_bold(child), _is_italic(child))
                text = "".join(r[0] for r in runs)
                visible = [r for r in runs if r[0].strip()]
                bold = bool(visible) and all(r[1] for r in visible)
                italic = bool(visible) and all(r[2] for r in visible)
                emit(text, bold=bold, italic=italic, kind="p")
            else:
                walk(child)

    walk(body)
    return blocks


# --- 10-K Item 1A --------------------------------------------------------------------------

ITEM_1A = re.compile(r"^item\s*1a\.?\s*[:.\-]?\s*risk\s+factors\.?$", re.I)
ITEM_1B = re.compile(r"^item\s*(1b|1c|2)\.?\s*[:.\-]?\s*(unresolved|cybersecurity|properties)", re.I)


def extract_item_1a(blocks: list[dict]) -> list[dict]:
    """Return the blocks of Item 1A, skipping the table-of-contents mention."""
    starts = [i for i, b in enumerate(blocks) if ITEM_1A.match(b["text"])]
    ends = [i for i, b in enumerate(blocks) if ITEM_1B.match(b["text"])]
    best: tuple[int, int] | None = None
    for s in starts:
        e = next((e for e in ends if e > s), None)
        if e is None:
            continue
        if best is None or (e - s) > (best[1] - best[0]):
            best = (s, e)
    if best is None:
        raise ValueError("Item 1A not found")
    return blocks[best[0] + 1 : best[1]]


def fetch_10k_pair(ticker: str, tmap: dict[str, int]) -> dict:
    cik = tmap[ticker]
    tenks = [f for f in recent_filings(cik) if f["form"] == "10-K"][:2]
    if len(tenks) < 2:
        raise ValueError(f"{ticker}: fewer than two 10-K filings in recent list")
    out = {"ticker": ticker, "cik": cik, "filings": []}
    for f in tenks:
        name = f["primaryDocument"]
        url = archive_url(cik, f["accessionNumber"], name)
        html = get(url, f"10k/{ticker}_{f['accessionNumber']}.htm")
        item = extract_item_1a(html_to_blocks(html))
        out["filings"].append(
            {
                "accession": f["accessionNumber"],
                "filing_date": f["filingDate"],
                "report_date": f["reportDate"],
                "url": url,
                "blocks": item,
                "words": sum(len(b["text"].split()) for b in item),
            }
        )
    return out


# --- 8-K earnings releases -----------------------------------------------------------------


def fetch_earnings_release(ticker: str, tmap: dict[str, int], after: str, before: str) -> dict:
    cik = tmap[ticker]
    cands = [
        f
        for f in recent_filings(cik)
        if f["form"] == "8-K" and "2.02" in (f.get("items") or "") and after <= f["filingDate"] <= before
    ]
    if not cands:
        raise ValueError(f"{ticker}: no Item 2.02 8-K between {after} and {before}")
    f = cands[0]
    ex = filing_exhibit(cik, f["accessionNumber"], "EX-99.1")
    if ex is None:
        raise ValueError(f"{ticker}: no EX-99.1 in {f['accessionNumber']}")
    url = archive_url(cik, f["accessionNumber"], ex)
    html = get(url, f"8k/{ticker}_{f['accessionNumber']}_{ex}")
    blocks = html_to_blocks(html)
    return {
        "ticker": ticker,
        "cik": cik,
        "accession": f["accessionNumber"],
        "filing_date": f["filingDate"],
        "report_date": f.get("reportDate", ""),
        "url": url,
        "blocks": blocks,
        "words": sum(len(b["text"].split()) for b in blocks),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["10k", "8k"])
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--after", default="2026-07-01")
    ap.add_argument("--before", default="2026-09-21")
    args = ap.parse_args()

    tmap = ticker_map()
    outdir = ROOT / "sources" / "edgar" / args.mode
    outdir.mkdir(parents=True, exist_ok=True)
    for t in args.tickers:
        try:
            rec = (
                fetch_10k_pair(t, tmap)
                if args.mode == "10k"
                else fetch_earnings_release(t, tmap, args.after, args.before)
            )
        except Exception as exc:  # noqa: BLE001 - report and continue across issuers
            print(f"{t}: FAILED {type(exc).__name__}: {exc}")
            continue
        (outdir / f"{t}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
        if args.mode == "10k":
            print(t, [(f["report_date"], f["words"]) for f in rec["filings"]])
        else:
            print(t, rec["filing_date"], rec["words"], "words")


if __name__ == "__main__":
    main()
