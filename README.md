Novelty Grinder
===============

Novelty Grinder is a tool to find potential surprise moves. This is
done by analyzing games (or lines) as follows:

- Position is analyzed with an engine for *candidate* moves
- Game database is queried for *popular* moves
- Popular moves are removed from the candidate moves set
- The remaining candidate moves are the potential surprise moves

PGN output is then produced with annotations.


Installation
------------

Prerequisites
- Python 3.8+ (or possibly a newer version is required)
- Lc0, version 0.31+ is suggested for contempt
- [Nibbler](https://github.com/rooklift/nibbler/). Optional, but
  highly recommended for Lc0 configuration.

Configuration
-# Run `setup-python-venv.sh`. This creates a Python virtual
   environment and fetches dependencies


Running
-------

Run `./novelty-grinder` without parameters for the built-in help.

For example:

    ./novelty-grinder --engine=/usr/local/bin/lc0 --nodes=100000 --eval-threshold=100 --arrows --first-move=4 --book-cutoff=40 input-games.pgn | tee annotated-games.pgn

This command uses engine `/usr/local/bin/lc0` to analyze the game:
- 100 kN per move, starting from move 4
- Moves less than 1% from the top move are considered *candidate*
  moves
- Default popularity cutoff is used. That is, moves with at most 5%
  popularity are considered for surprises
- Analysis is stopped when less than 40 games are in the database.
- Arrows are added in the PGN annotation for visualization. Red arrow
  = novelty; green arrow = unpopular engine move


Tips
----

For proper surprises, configure Lc0 contempt. Contempt can find sharp
moves that may not be objectively the best, but instead, they provide
the best winning chances. A bit of experimentation with Nibbler is
recommended to find suitable settings. See
https://lczero.org/blog/2024/03/gm-matthew-sadler-on-wdl-contempt/ for
further information.
