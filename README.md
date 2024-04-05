Novelty Grinder
===============

Novelty Grinder is a tool to find potential surprise moves. This is
done by analyzing games (or lines) as follows:

1. Position is analyzed with an engine for *initial candidate* moves.
   - Initial search node count is specified with `--nodes`
   - Candidate move minimum score is
     `TOP_MOVE_EVAL - eval-threshold - initial-eval-margin`.
2. Moves in the input PGN (including variations) are removed from
   candidate moves.
3. Lichess master database is queried for *popular* moves.
4. Popular moves are removed from the candidate moves set.
5. Remaining candidate moves are analyzed until they have a sufficient
   number of nodes for minimum analysis quality.
   - Minimum number of nodes is specified with `--double-check-nodes`.
     By default, this is 10% of the initial search node count.
   - After analysis, candidate move minimum score is
     `TOP_MOVE_EVAL - eval-threshold`.
6. The final candidate moves are the potential surprise moves.

PGN output is then produced with annotations.


Installation
------------

Prerequisites
- Python 3.8+ (or possibly a newer version is required)
- Lc0, version 0.31+ is suggested for contempt
- [Nibbler](https://github.com/rooklift/nibbler/). Optional, but
  highly recommended for Lc0 configuration.

Configuration
- Run `setup-python-venv.sh`. This creates a Python virtual
  environment and fetches dependencies


Running
-------

Run `./novelty-grinder` without parameters for the built-in help.

For example:

    ./novelty-grinder --engine=lc0 --nodes=100000 --eval-threshold=100 --arrows --first-move=4 --book-cutoff=40 input-games.pgn | tee annotated-games.pgn

This command uses engine `lc0` to analyze the game:
- The full path in engines.json can be omitted.
- Initial search is 100 kN per move, starting from move 4.
- Moves less than 4% from the top move are considered *initial candidate*
  moves. That's 1% plus the default 3% initial margin.
- Default popularity cutoff is used. That is, moves with at most 5%
  popularity are considered for surprises.
- Unpopular alternative moves and novelties are analyzed further until
  they have at least 10 kN each. Suggested moves are those that
  are less than 1% from the top move.
- Arrows are added in the PGN annotation for visualization. Red arrow
  = novelty; green arrow = unpopular engine move
- Analysis is stopped when less than 40 games are in the database.


Tips
----

For proper surprises, configure Lc0 contempt. Contempt can find sharp
moves that may not be objectively the best, but instead, they provide
the best winning chances. A bit of experimentation with Nibbler is
recommended to find suitable settings. See
https://lczero.org/blog/2024/03/gm-matthew-sadler-on-wdl-contempt/ for
further information.

**Windows users!** [Issue 3](https://github.com/skiminki/novelty-grinder/issues/3)
tracks an issue related to running the Novelty Grinder in
Windows. Until the issue is fixed, there is a workaround:
https://matthewsadler.me.uk/openings/the-mrbdzz-novelty-grinder/
