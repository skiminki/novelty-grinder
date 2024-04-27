==============================================================================
Novelty Grinder analysis on 2024 World Chess candidates
==============================================================================

Version: Novelty Grinder 0.1-dev (781e822)
Engine:  v0.32.0-dev+git.8587433 built Mar 29 2024
Net:     BT4-1024x15x32h-swa-6147500
EGTB:    Syzygy 7-men

Analysis parameters:
- Common:
  - first move: 3
  - evaluation threshold: 100 (= 1.00%)
  - rarity threshold: 0.05 (= 5%)
    (moves less popular than 5% are considered for surprise moves)
  - book cutoff: 1
    (stop analysis when out of database)
- Contempt 0:
  - initial search: 1M nodes
  - second stage search: 100k nodes per candidate move
- Contempt 150:
  - initial search: 200k nodes
  - second stage search: 20k nodes per candidate move
- Contempt 250:
  - initial search: 100k nodes
  - second stage search: 20k nodes per candidate move

Analysis time: approx 20 hours for the whole tournament (AMD 7950x + RTX 4090)

==============================================================================

PGN annotations
----------------

Mainline move comments
- N: Number of games in the database before the next move
- Eval: Engine evaluation before the next move

Example: "3. Bb5 { N=135315 Eval=32.49% }"


Mainline NAGs (numeric annotation glyphs):
- Exclamation mark (!): Script-suggested surprise move was played
- Novelty (N): Move is not found in the database

Examples:
- 4... f5!
- 10... d6!N


Variations and their comments:
- Script-suggested surprise moves with their evaluation and popularity, or 'N'
  if the move is not found in the database

Examples:
- (4... Be7 Eval=33.24% Popularity=0.15% )
- (6... Nge7N Eval=38.53% )


Arrow diagram annotations on mainline moves:
- Green arrow: surprise move that has been previously played
- Red arrow: surprise novelty move


==============================================================================

Analysis commands: (single game)

./novelty-grinder \
    "--white-engine=lc0-no-contempt" \
    "--nodes=1000000" \
    "--double-check-nodes=100000" \
    --arrows \
    --summary \
    --first-move=3 \
    --book-cutoff=1 \
    --eval-threshold=100 \
    --include-input \
    "examples/2024-candidates/wchcand24-01.1.pgn"  >> "examples/2024-candidates/wchcand24-01.1-annotated.pgn"

./novelty-grinder \
    "--white-engine=lc0-contempt-white-150" \
    "--nodes=200000" \
    "--double-check-nodes=20000" \
    --arrows \
    --summary \
    --first-move=3 \
    --book-cutoff=1 \
    --eval-threshold=100 \
    --include-input \
    "examples/2024-candidates/wchcand24-01.1.pgn"  >> "examples/2024-candidates/wchcand24-01.1-annotated.pgn"

./novelty-grinder \
    "--white-engine=lc0-contempt-white-250" \
    "--nodes=100000" \
    "--double-check-nodes=20000" \
    --arrows \
    --summary \
    --first-move=3 \
    --book-cutoff=1 \
    --eval-threshold=100 \
    --include-input \
    "examples/2024-candidates/wchcand24-01.1.pgn"  >> "examples/2024-candidates/wchcand24-01.1-annotated.pgn"

./novelty-grinder \
    "--black-engine=lc0-no-contempt" \
    "--nodes=1000000" \
    "--double-check-nodes=100000" \
    --arrows \
    --summary \
    --first-move=3 \
    --book-cutoff=1 \
    --eval-threshold=100 \
    --include-input \
    "examples/2024-candidates/wchcand24-01.1.pgn"  >> "examples/2024-candidates/wchcand24-01.1-annotated.pgn"

./novelty-grinder \
    "--black-engine=lc0-contempt-black-150" \
    "--nodes=200000" \
    "--double-check-nodes=20000" \
    --arrows \
    --summary \
    --first-move=3 \
    --book-cutoff=1 \
    --eval-threshold=100 \
    --include-input \
    "examples/2024-candidates/wchcand24-01.1.pgn"  >> "examples/2024-candidates/wchcand24-01.1-annotated.pgn"

./novelty-grinder \
    "--black-engine=lc0-contempt-black-250" \
    "--nodes=100000" \
    "--double-check-nodes=20000" \
    --arrows \
    --summary \
    --first-move=3 \
    --book-cutoff=1 \
    --eval-threshold=100 \
    --include-input \
    "examples/2024-candidates/wchcand24-01.1.pgn"  >> "examples/2024-candidates/wchcand24-01.1-annotated.pgn"
