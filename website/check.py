#!/usr/bin/env python3
"""Offline check for the rhYmusic.com site source of ShipForOneAlbum.

Standard library only, no network, no npm. Run from the repository root:

    python3 website/check.py

Fails with a message for anything that would break the published site:
missing pages, broken or insecure links, a GitHub link that names a file
this repository does not contain, a stem that is committed but not linked,
an invented or missing track name, audio staged inside the site, a dev
server declared in package.json that is not the one shipped, or a deploy
workflow that embeds a credential instead of reading it from GitHub secrets.
"""

import html
import html.parser
import json
import posixpath
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "website"
PAGES = ["index.html", "404.html"]
TEXT_FILES = ["index.html", "404.html", "styles.css", "script.js"]
AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".aiff", ".ardour", ".7z", ".zip"}
TRACK_LIST = ROOT / "Track List"
STEM_BASE = ("https://raw.githubusercontent.com/crhy/ShipForOneAlbum"
             "/main/SleepTight/")

# Files under website/ that are not expected to be linked from a page.
NOT_LINKED = {"404.html", "_headers", "_redirects", "index.html",
              "dev-server.mjs", "package.json", "check.py", ".gitignore",
              "README.md"}

problems = []


def fail(message):
    problems.append(message)


def rel(path):
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail("%s is not valid UTF-8 text" % rel(path))
    except OSError:
        fail("%s could not be read" % rel(path))
    return ""


class LinkCollector(html.parser.HTMLParser):
    """Collect href and src values from one HTML file."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name in ("href", "src") and value:
                self.links.append(value)


def looks_external(url):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:", url)) or url.startswith("//")


def resolve_target(page, url):
    """Resolve an internal link to a path under website/, or None."""
    target = url.split("#", 1)[0].split("?", 1)[0]
    if target == "":
        return None  # same-page fragment
    page_dir = posixpath.dirname(page)
    if target.startswith("/"):
        candidate = target[1:]
    else:
        candidate = posixpath.join(page_dir, target) if page_dir else target
    candidate = posixpath.normpath(candidate)
    if candidate in ("", "."):
        candidate = "index.html"
    if candidate.endswith("/"):
        candidate += "index.html"
    if candidate.startswith("..") or posixpath.isabs(candidate):
        return None
    return candidate


GITHUB_RE = re.compile(
    r"https://(?:raw\.githubusercontent\.com|github\.com)/crhy/ShipForOneAlbum"
    r"/([^#\s\"'<>]+)"
)


def repo_path(raw):
    """Percent-decode a link into this repository and name the path it points at."""
    path = urllib.parse.unquote(raw.split("#", 1)[0].split("?", 1)[0]).strip("/")
    for prefix in ("tree/", "blob/", "raw/"):
        if path.startswith(prefix):
            path = path[len(prefix):]
    if path.startswith("main/"):
        path = path[len("main/"):]
    return path


def check_required_files():
    required = [
        "website/index.html",
        "website/404.html",
        "website/_headers",
        "website/_redirects",
        "website/styles.css",
        "website/script.js",
        "website/dev-server.mjs",
        "website/package.json",
        "website/check.py",
        "scripts/build-website.sh",
        ".github/workflows/deploy-website.yml",
    ]
    for name in required:
        if not (ROOT / name).is_file():
            fail("missing required file: %s" % name)


def check_package_json():
    path = SITE / "package.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail("website/package.json is not valid JSON: %s" % exc)
        return
    if data.get("private") is not True:
        fail('website/package.json must set "private": true (never published to npm)')
    dev = (data.get("scripts") or {}).get("dev")
    if dev != "node dev-server.mjs":
        fail('website/package.json scripts.dev must be "node dev-server.mjs", found: %r' % dev)
    if not (SITE / "dev-server.mjs").is_file():
        fail("website/package.json runs dev-server.mjs, which is missing")
    for key in ("dependencies", "devDependencies"):
        if data.get(key):
            fail("website/package.json must declare no %s (no npm install offline)" % key)


def check_no_audio_in_site():
    for path in sorted(SITE.rglob("*")):
        if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
            fail("%s: audio or session media inside website/; the site only links "
                 "to files hosted in the repository" % rel(path))


def collect_links():
    per_page = {}
    for page in PAGES:
        path = SITE / page
        if not path.is_file():
            continue
        collector = LinkCollector()
        try:
            collector.feed(read_text(path))
        except Exception as exc:  # noqa: BLE001 - report, do not crash the gate
            fail("%s could not be parsed: %s" % (rel(path), exc))
        per_page[page] = collector.links
    return per_page


def check_links(per_page):
    referenced = set()
    for page, links in sorted(per_page.items()):
        for url in links:
            if url.lower().startswith("http://"):
                fail("%s: insecure link (use https): %s" % (page, url))
                continue
            if url.startswith("#") or url.split("#", 1)[0].split("?", 1)[0] == "":
                continue  # same-page fragment
            if looks_external(url):
                if not url.lower().startswith("https://"):
                    fail("%s: unsupported external link: %s" % (page, url))
                continue
            target = resolve_target(page, url)
            if target is None:
                fail("%s: link escapes website/: %s" % (page, url))
                continue
            referenced.add(target)
            if not (SITE / target).exists():
                fail("%s: broken link to %s (not a file in the repository)" % (page, url))
    return referenced


def check_orphans(referenced):
    for path in sorted(SITE.rglob("*")):
        if not path.is_file():
            continue
        candidate = path.relative_to(SITE).as_posix()
        if candidate in NOT_LINKED:
            continue
        if candidate in referenced:
            continue
        if path.suffix.lower() in (".css", ".js", ".html", ".svg", ".png", ".jpg"):
            fail("orphan: %s is committed under website/ but no page links to it"
                 % candidate)


def check_github_paths():
    """Every link into this repository must name a path that exists here."""
    text = read_text(SITE / "index.html") + read_text(SITE / "404.html")
    found = set()
    for match in GITHUB_RE.finditer(text):
        path = repo_path(match.group(1))
        if path:
            found.add(path)
    for path in sorted(found):
        if not (ROOT / path).exists():
            fail("the page links to %s, which is not a path in this checkout" % path)
    if not found:
        fail("the page links to no file in this repository; the track and stem "
             "links are expected")


def read_track_names():
    if not TRACK_LIST.is_file():
        fail("Track List is missing from the repository root")
        return []
    return [line.rstrip("\n") for line in TRACK_LIST.open(encoding="utf-8")
            if line.strip()]


def check_track_names(names):
    text = read_text(SITE / "index.html")
    for name in names:
        if name not in text:
            fail("Track List line is not shown on the page: %r" % name)
    shown = [html.unescape(m) for m in re.findall(
        r'<span class="track-name">(.*?)</span>', text, re.S)]
    if not names:
        return
    if len(shown) != len(names):
        fail("the page shows %d track name(s), Track List has %d"
             % (len(shown), len(names)))
    for name in [name for name in shown if name not in names]:
        fail("invented track name on the page: %r" % name)
    for name in [name for name in names if name not in shown]:
        fail("Track List name is not marked as a track on the page: %r" % name)


def check_unresolved_licences(names):
    text = read_text(SITE / "index.html")
    rows = re.split(r"<tr\b", text)
    unresolved = [name for name in names if "Can we?" in name]
    if len(unresolved) < 2:
        fail("Track List is expected to carry the two \"Can we?\" tracks")
    for name in unresolved:
        row = [chunk for chunk in rows if name in chunk]
        if not row:
            fail("no table row shows the track %r" % name)
            continue
        for chunk in row:
            if "licensing unresolved" not in chunk:
                fail("the page must mark %r as licensing unresolved, in the "
                     "owner's own words" % name)
    if text.count("licensing unresolved") < len(unresolved):
        fail("the page must mark each \"Can we?\" track as licensing unresolved")
    for pattern, label in (
        (r"licensing\s+(?:cleared|resolved|complete)", "licensing cleared"),
        (r"(?i)\b(royalty-free|copyright-free|cleared for (?:use|release))\b",
         "a claim that a track is cleared"),
    ):
        if re.search(pattern, text):
            fail("the page must not contain %s" % label)


def check_stems():
    stems = sorted(p.name for p in (ROOT / "SleepTight").glob("*.wav"))
    if not stems:
        fail("SleepTight/ holds no WAV stems; the page is expected to link them")
        return
    text = read_text(SITE / "index.html")
    for name in stems:
        if STEM_BASE + urllib.parse.quote(name, safe="") not in text:
            fail("committed stem is not linked from the page: %s" % name)
    for match in re.finditer(re.escape(STEM_BASE) + r"([^\"\s]+)", text):
        target = ROOT / "SleepTight" / urllib.parse.unquote(match.group(1))
        if not target.exists():
            fail("the page links to a stem that is not committed: %s" % match.group(1))
    if any("%" in name for name in stems) and "%25" not in text:
        fail("stem names containing % must be percent-encoded as %25 in links")


def check_text_hygiene():
    for name in TEXT_FILES:
        path = SITE / name
        if not path.is_file():
            continue
        text = read_text(path)
        for pattern, label in (
            (r"/home/[A-Za-z0-9_.-]", "an absolute local path (/home/...)"),
            (r"\b[A-Za-z]:[\\/]{1,2}[A-Za-z0-9_.-]", "a Windows absolute path (C:...)"),
            (r"\bfile://", "a file:// URL"),
            (r"\bhttp://", "an http:// URL (HTTPS only)"),
        ):
            if re.search(pattern, text):
                fail("%s contains %s" % (rel(path), label))


def check_headers():
    path = SITE / "_headers"
    if not path.is_file():
        return
    text = read_text(path)
    directives = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )
    for header in ("Strict-Transport-Security", "X-Content-Type-Options", "Referrer-Policy"):
        if header not in directives:
            fail("website/_headers must set %s to enforce HTTPS and refuse sniffing" % header)
    if re.search(r"frame-allow-from", directives, re.IGNORECASE):
        fail("website/_headers must not use frame-allow-from")
    for line in directives.splitlines():
        if re.search(r"frame-ancestors\s+[^;]*\*", line):
            fail("website/_headers frame-ancestors must not use a wildcard: %s" % line.strip())
    if re.search(r"media-src|autoplay", directives, re.IGNORECASE):
        fail("website/_headers should not open media-src: the site links to audio, "
             "it does not embed or play it")


def check_redirects():
    path = SITE / "_redirects"
    if not path.is_file():
        return
    for number, raw in enumerate(read_text(path).splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            fail("website/_redirects line %d is not \"from to status\": %s" % (number, stripped))
            continue
        target = parts[1]
        path_part = target.split("#", 1)[0]
        if path_part in ("", "/"):
            continue
        if not path_part.startswith("/"):
            fail("website/_redirects line %d has a non-absolute target: %s" % (number, target))
            continue
        if not re.search(r"\.(html|css|js|pdf|png|jpe?g|svg)$", path_part):
            fail("website/_redirects line %d points at an unknown path: %s" % (number, target))
            continue
        if not (SITE / path_part.lstrip("/")).is_file():
            fail("website/_redirects line %d points at a missing file: %s" % (number, target))


def check_workflow():
    path = ROOT / ".github/workflows/deploy-website.yml"
    if not path.is_file():
        return
    text = read_text(path)
    for var in ("CF_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):
        if "secrets.%s" % var not in text:
            fail("the deploy workflow must read %s from secrets." % var)
        for raw in text.splitlines():
            if var in raw:
                tail = raw.split(var, 1)[1]
                match = re.match(r"\s*:\s*(.*)$", tail)
                if match and match.group(1).strip() and "secrets." not in match.group(1):
                    fail("the deploy workflow embeds a value for %s instead of secrets: %s"
                         % (var, raw.strip()))
    if not re.search(r"secrets\.CF_ACCOUNT_ID\s*!=\s*''", text):
        fail("the deploy workflow must skip the Cloudflare step when "
             "secrets.CF_ACCOUNT_ID is empty, so a clone without credentials "
             "cannot deploy or fail")
    for raw in text.splitlines():
        match = re.match(r"\s*(accountId|apiToken|account-id|api-token)\s*:\s*(.*)$", raw)
        if not match:
            continue
        value = match.group(2).strip()
        if not re.fullmatch(r"\$\{\{\s*secrets\.[A-Za-z_][A-Za-z0-9_]*\s*\}\}", value):
            fail("the deploy workflow sets %s to something other than a GitHub "
                 "secret: %s" % (match.group(1), raw.strip()))
    if re.search(r"\b[0-9a-f]{20,}\b", text):
        fail("the deploy workflow contains a long hex value that looks like an account id")
    if re.search(r"(?i)cloudflare[_-]?api[_-]?token\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{20,}", text):
        fail("the deploy workflow looks like it embeds a Cloudflare API token")
    for needle in ("scripts/build-website.sh", "website/check.py", "build/website"):
        if needle not in text:
            fail("the deploy workflow must reference %s" % needle)


def check_build_script():
    path = ROOT / "scripts/build-website.sh"
    if not path.is_file():
        return
    text = read_text(path)
    if "set -euo pipefail" not in text:
        fail("scripts/build-website.sh must use set -euo pipefail")
    if "build/website" not in text:
        fail("scripts/build-website.sh must stage the site into build/website")
    if re.search(r"^\s*cp\b.*\bSleepTight\b", text, re.MULTILINE):
        fail("scripts/build-website.sh must not copy SleepTight/ audio into the site")
    staged = ROOT / "build/website"
    if staged.is_dir():
        for found in staged.rglob("*"):
            if not found.is_file():
                continue
            if found.suffix.lower() in AUDIO_SUFFIXES:
                fail("staged bundle contains audio: %s" % rel(found))
            if found.name in (".gitignore", "check.py", "dev-server.mjs", "package.json"):
                fail("staged bundle contains a development-only file: %s" % rel(found))
    rootignore = ROOT / ".gitignore"
    if not rootignore.is_file():
        fail("root .gitignore is missing; build/ must never be committed")
    elif "build/" not in read_text(rootignore):
        fail("root .gitignore must ignore build/")


def main():
    check_required_files()
    check_package_json()
    check_no_audio_in_site()
    referenced = check_links(collect_links())
    check_orphans(referenced)
    check_github_paths()
    names = read_track_names()
    check_track_names(names)
    check_unresolved_licences(names)
    check_stems()
    check_text_hygiene()
    check_headers()
    check_redirects()
    check_workflow()
    check_build_script()

    if problems:
        for problem in problems:
            print("FAIL: %s" % problem)
        print("\n%d problem(s) found in the rhYmusic.com site source." % len(problems))
        return 1

    stems = len(list((ROOT / "SleepTight").glob("*.wav")))
    print("OK: %d page(s), %d track name(s) matching Track List exactly, "
          "%d stem link(s) resolving to committed files, all internal links "
          "resolve, HTTPS-only, no audio staged in the site, deploy workflow "
          "reads Cloudflare credentials from secrets."
          % (len(PAGES), len(names), stems))
    return 0


if __name__ == "__main__":
    sys.exit(main())
