#!/usr/bin/env bash
# Rebuilds assets/fonts/*.subset.woff2 from JetBrains Mono (SIL OFL 1.1).
# Only needed if a graphic starts drawing a character outside the subset;
# the daily workflow just reads the committed files.
#
#   pip install fonttools brotli
#   scripts/subset_fonts.sh path/to/JetBrainsMono-2.304/fonts/ttf
set -euo pipefail

src=${1:?usage: subset_fonts.sh <dir with JetBrainsMono-*.ttf>}
out=$(dirname "$0")/../assets/fonts

# printable ASCII, middle dot, em dash, ellipsis, arrows, box-drawing horizontal
unicodes="U+0020-007E,U+00B7,U+2014,U+2026,U+2190-2193,U+2500"

for weight in Regular Bold; do
  pyftsubset "$src/JetBrainsMono-$weight.ttf" \
    --unicodes="$unicodes" --flavor=woff2 --layout-features= \
    --no-hinting --desubroutinize \
    --output-file="$out/JetBrainsMono-$weight.subset.woff2"
done
