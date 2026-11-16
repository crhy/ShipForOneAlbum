#!/usr/bin/env bash
set -euo pipefail

# Stage the public rhYmusic.com site of this album into build/website.
#
# Only website/ is published. Never SleepTight/ (348M of session stems),
# never .git, never the repository root: the page links to those files where
# they already live on GitHub, so the bundle stays small and the audio stays
# in one place.

cd "$(dirname "$0")/.."

src=website
out=build/website

rm -rf -- "$out"
mkdir -p "$out"

cp -R "$src"/. "$out"/

# Development-only files that must not ship.
rm -f -- "$out/dev-server.mjs" "$out/package.json" "$out/check.py" \
  "$out/README.md" "$out/.gitignore" "$out/.dev.vars"
find "$out" -name node_modules -prune -exec rm -rf -- {} +
find "$out" -name '.DS_Store' -delete

# Required public files.
for file in index.html 404.html styles.css script.js _headers _redirects; do
  if [ ! -f "$out/$file" ]; then
    echo "staging failed: $out/$file is missing" >&2
    exit 1
  fi
done

# Nothing unpublished may enter the bundle.
if find "$out" \( -name '.git' -o -name '.git*' -o -name 'SleepTight' \
  -o -iname '*.wav' -o -iname '*.mp3' -o -iname '*.flac' -o -iname '*.ardour' \
  -o -iname '*.7z' -o -iname '*.zip' -o -iname '*.pdf' \
  -o -iname '*credential*' -o -iname '*token*' -o -iname '*.pem' \
  -o -iname '*.key' -o -name 'check.py' -o -name 'dev-server.mjs' \
  -o -name 'package.json' \) -print -quit | grep -q .; then
  echo "staging failed: unpublished files are present in $out" >&2
  exit 1
fi

# Every staged file must have come from website/.
if [ -e "$out/SleepTight" ] || [ -e "$out/.git" ] || [ -e "$out/Track List" ]; then
  echo "staging failed: repository sources leaked into $out" >&2
  exit 1
fi

echo "staged $(find "$out" -type f | wc -l) file(s), $(du -sh "$out" | cut -f1) in $out"
echo "deploy only $out/ - not the repository root, not the SleepTight stems"
