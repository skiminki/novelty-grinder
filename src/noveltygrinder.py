#!/usr/bin/python3
#
# Copyright 2024 Sami Kiminki
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from optparse import OptionParser
from pathlib import Path
import berserk
import chess
import chess.engine
import chess.pgn
import datetime
import json
import logging
import sys

VERSION="0.1-dev"


def enable_debug_logging(option, opt, value, parser):
    logging.basicConfig(level=logging.DEBUG)

def processarguments():
    parser = OptionParser(
        version="novelty-grinder " + VERSION,
        usage = 'usage: novelty-grinder [options] FILE.pgn',
        description = '''The Grand Novelty Grinder
searches for suprise moves and novelties with Lc0 and Lichess.''',
        epilog='''Quick instructions:
(1) Configure Lc0 for Nibbler. When using contempt, configure both colors
separately.
(2) Prepare lines or games to analyze in FILE.pgn.
(3) Run the novelty grinder to find interesting novelties and rarities.
Annotated PGN is written in stdout.''')

    parser.add_option(
        "-E", "--engines-json", dest="enginesJsonPath",
        help="Nibbler engines.json file [default: %default]",
        metavar="FILE",
        type="string",
        default=str(Path.home() / ".config" / "Nibbler" / "engines.json"))

    parser.add_option(
        "-T", "--lichess-token-file", dest="lichessTokenFile",
        help="Lichess API token file. Optional, may help in case of getting " +
        "API rate-limited. [default: %default]",
        metavar="FILE",
        type="string")

    parser.add_option(
        "-w", "--white-engine", dest="whiteEngine",
        help="Engine for white side analysis. Full path can be omitted as long as " +
        "the engine is unambiguous.",
        type="string",
        metavar="STR")

    parser.add_option(
        "-b", "--black-engine", dest="blackEngine",
        help="Engine for black side analysis. Full path can be omitted as long as " +
        "the engine is unambiguous.",
        metavar="STR")

    parser.add_option(
        "-e", "--engine", dest="engine",
        help="Analysis engine for both sides. Full path can be omitted as long as " +
        "the engine is unambiguous.",
        type="string",
        metavar="STR")

    parser.add_option(
        "-n", "--nodes", dest="analysisNodes",
        help="Nodes per move to analyze. [default: %default]",
        type="int",
        metavar="NODES",
        default=100000)

    parser.add_option(
        "",  "--eval-threshold", dest="evalThresholdCp",
        help="Engine evaluation score threshold for considering novelties. Moves with at least " +
        "(FIRST_PV_SCORE - EVAL_DIFF) evaluation score are considered for novelties. In centipawns. " +
        "Note: Comparison is against the first PV move, not the highest PV evaluation. "
        "[default: %default]",
        type="int",
        metavar="EVAL_DIFF",
        default=200)

    parser.add_option(
        "",  "--rarity-threshold-freq", dest="rarityThresholdFreq",
        help="Book moves that are played at most FREQ frequency are considered 'rare' moves. " +
        "[default: %default]",
        type="float",
        metavar="FREQ",
        default=0.05)

    parser.add_option(
        "",  "--rarity-threshold-count", dest="rarityThresholdCount",
        help="Book move that is played at most NUM times total are considered 'rare' moves " +
        "regardless of the frequency. [default: %default]",
        type="int",
        metavar="NUM",
        default=0)

    parser.add_option(
        "",  "--first-move", dest="firstMove",
        help="First move to analyze (skip previous). [default: %default]",
        type="int",
        metavar="MOVE_NUM",
        default=1)

    parser.add_option(
        "",  "--book-cutoff", dest="bookCutoff",
        help="Stop analysis when the book has fewer than at most NUM games. " +
        "[default: %default]",
        type="int",
        metavar="NUM",
        default=2)

    parser.add_option(
        "",  "--arrows", dest="arrows", default=False,
        help="Add arrows in the annotated PGN: red = novelty; green = unpopular move.",
        action="store_true")

    parser.add_option(
        "",  "--debug",
        help="Enable debug mode",
        action="callback",
        callback=enable_debug_logging)

    parser.add_option(
        "", "--double-check-nodes", dest="doubleCheckNodes",
        help="After initial analysis, do focused analysis on candidate moves until they have at least NUM nodes. " +
        "This improves quality of suggested alternative moves. Default (-1) stands for 10% of NODES as specified with --nodes. " +
        "[default: %default]",
        type="int",
        metavar="NUM",
        default=-1)

    parser.add_option(
        "",  "--initial-eval-margin", dest="initialEvalMarginCp",
        help="Extra margin for initial analysis score threshold. In centipawns. " +
        "The extra margin allows considering moves that have lower score with low node count but "
        "improved score with more nodes. "
        "[default: %default]",
        type="int",
        metavar="EVAL_DIFF",
        default=300)

    parser.add_option(
        "",  "--summary", dest="summary", default=False,
        help="Produce a summary of potential surprise moves.",
        action="store_true")

    (options, args) = parser.parse_args()

    if options.engine and options.whiteEngine:
        parser.error('--engine and --white-engine are mutually exclusive')

    if options.engine and options.blackEngine:
        parser.error('--engine and --black-engine are mutually exclusive')

    if not options.enginesJsonPath:
        parser.error('--engines-json must be especified')

    if not (options.engine or options.whiteEngine or options.blackEngine):
        parser.error('An analysis engine must be specified')

    if len(args) == 0:
        parser.error('No input PGN was specified')

    if options.doubleCheckNodes == -1:
        options.doubleCheckNodes = -(options.analysisNodes // -10) # ceiling division

    return (options, args)


def closeSingleEngine(engine):
    if engine is not None:
        try:
            engine.close()
        except:
            sys.stderr.write(f"Failed to close engine\n")
            sys.stderr.write(sys.exception())


def initializeSingleEngine(exePath, conf):
    sys.stderr.write(f"Initializing {exePath}\n")

    engineArgs = [ exePath ]
    engineArgs.extend(conf['args'])

    engine = chess.engine.SimpleEngine.popen_uci(engineArgs)

    try:
        engine.configure(conf['options'])

        # Lc0-specific configuration. This needs to be revised when
        # adding support for other engines.
        engine.configure(
            {
                # Don't stop early, we want all the nodes for the PVs,
                # regardless of whether the top move has been decided
                'SmartPruningFactor' : 0,

                # Expected score output. Range is 0..10000 for 0..100%
                'ScoreType' : 'win_percentage',

                # For per-PV number of nodes
                'PerPVCounters' : True
            })

        engine.ping()

    except:
        sys.stderr.write(f"Failed to configure engine: {exePath}\n")
        sys.stderr.write(repr(sys.exception()))
        closeSingleEngine(engine)
        raise

    return engine


def getEngineConf(engineConfigs, engineName):
    if engineName in engineConfigs:
        return engineConfigs[engineName]

    fullName = None

    for i in engineConfigs:
        enginePath = Path(i)
        if engineName == enginePath.name:
            if fullName is not None:
                raise KeyError(f"Ambiguous engine name '{engineName}' can resolve to '{fullName}' or '{i}'")

            fullName = i

    if fullName is None:
        raise KeyError(f"Engine not found: '{engineName}'")

    return engineConfigs[fullName]


def initializeEngines(options):

    whiteEngine = None
    blackEngine = None

    with open(options.enginesJsonPath) as f:
        engineConfigs = json.load(f)

    if options.engine:
        conf = getEngineConf(engineConfigs, options.engine)
        whiteEngine = initializeSingleEngine(options.engine, conf)
        blackEngine = whiteEngine

    if options.whiteEngine:
        conf = getEngineConf(engineConfigs, options.whiteEngine)
        whiteEngine = initializeSingleEngine(options.whiteEngine, conf)

    if options.blackEngine:
        conf = getEngineConf(engineConfigs, options.blackEngine)
        blackEngine = initializeSingleEngine(options.blackEngine, conf)

    return whiteEngine, blackEngine


def closeEngines(whiteEngine, blackEngine):
    sys.stderr.write('Closing engines...\n')

    if whiteEngine is not None:
        closeSingleEngine(whiteEngine)

    if (blackEngine is not None) and (blackEngine is not whiteEngine):
        closeSingleEngine(blackEngine)


def scoreToString(cp, turn):
    if turn == chess.WHITE:
        return f"{cp / 100.0:.2f}%"
    else:
        return f"{(10000 - cp) / 100.0:.2f}%"


class AnalysisMoveInfo:
    def __init__(self, move, evalCp, nodes):
        self.move = move
        self.evalCp = evalCp
        self.nodes = nodes
        self.freq = 0
        self.novelty = True


class AnalysisSummary:
    def __init__(self):
        self.surpriseMoves = dict()
        self.analyzedLineStr = ""

    def addSurpriseMove(self, ply, moveStr, freq, novelty):
        if ply not in self.surpriseMoves:
            self.surpriseMoves[ply] = list()

        if novelty:
            self.surpriseMoves[ply].append(moveStr + 'N')
        else:
            self.surpriseMoves[ply].append(f"{moveStr} Popularity={100 * freq:.2f}%")


def currentMoveNumStr(board):
    if board.turn == chess.WHITE:
        return str(board.fullmove_number) + "w"
    else:
        return str(board.fullmove_number) + "b"


# returns a list of AnalysisMoveInfo
def engineAnalysis(board, game, engine, options):
    # run the analysis
    info = engine.analyse(
        board, chess.engine.Limit(nodes=options.analysisNodes), game = game, multipv = 100)

    analysisMoves = [ ]

    # include only PVs that have the evaluation score and move
    for i in info:
        if ('score' in i) and ('pv' in i) and (len(i['pv']) > 0):
            analysisMoves.append(
                AnalysisMoveInfo(
                    i['pv'][0],
                    i['score'].relative.score(mate_score=1000000),
                    i['nodes']))

    # engine produced any moves?
    if len(analysisMoves) == 0:
        return [ ], 0

    # determine threshold for candidate moves
    evalThresholdCp = analysisMoves[0].evalCp - options.evalThresholdCp

    return analysisMoves, evalThresholdCp

# remove moves that don't have big enough score
def pruneWeakMoves(analysisMoves, evalThresholdCp):
    ret = [ ]
    for am in analysisMoves:
        if am.evalCp >= evalThresholdCp:
            ret.append(am)

    return ret


def engineAnalysisDoubleCheck(board, game, engine, options, analysisMoves):
    tempOptions = dict()
    tempOptions['PerPVCounters'] = False
    ret = [ ]

    for am in analysisMoves:
        # query the total moves so far
        info = engine.analyse(
            board, chess.engine.Limit(nodes=0), game = game, multipv = 100, root_moves = [ am.move ], options = tempOptions)
        totalNodes = info[0]['nodes']

        # need more nodes?
        if am.nodes < options.doubleCheckNodes:
            newNodes = options.doubleCheckNodes - am.nodes

            info = engine.analyse(
                board, chess.engine.Limit(nodes=(totalNodes + newNodes)), game = game, multipv = 100, root_moves = [ am.move ])
            am.move = info[0]['pv'][0]
            am.nodes = info[0]['nodes']
            am.evalCp = info[0]['score'].relative.score(mate_score=1000000)

        ret.append(am)

    return ret


# prune out moves that are in the original PGN variations
def filterOutVariations(analysisMoves, node):
    ret = [ ]

    for am in analysisMoves:
        if not node.has_variation(am.move):
            ret.append(am)

    return ret


# filter out popular moves and add frequency/novelty info
def filterOutPopularMovesAddFreq(analysisMoves, openingStats, gamesThreshold, totalGames):

    ret = [ ]
    uciStrToNumGames = dict()

    # create lookup dict
    for statMove in openingStats['moves']:
        uciStrToNumGames[statMove['uci']] = (
            statMove['white'] + statMove['draws'] + statMove['black'] )

    for am in analysisMoves:
        # check for novelty?
        if am.move.uci() in uciStrToNumGames:
            # not a novelty
            if uciStrToNumGames[am.move.uci()] <= gamesThreshold:
                am.freq = uciStrToNumGames[am.move.uci()] / totalGames
                am.novelty = False
                ret.append(am)
        else:
            # novelty
            am.freq = 0
            am.novelty = True
            ret.append(am)

    return ret


def analysisMoveListToString(analysisMoves, board):
    moveStrList = [ ]
    for am in analysisMoves:
        moveStrList.append(board.san(am.move))

    return " ".join(moveStrList)


def analyzeGame(whiteEngine, blackEngine, game, num, options, openingExplorer):
    sys.stderr.write(f"Analyzing game {num}\n")

    ret = chess.pgn.Game.from_board(game.board())
    ret.headers = game.headers.copy()

    annotatorParts = [ "Novelty Grinder " + VERSION ]
    summaryAnnotatorParts = ""
    if options.engine:
        annotatorParts.append("White: " + options.engine)
        annotatorParts.append("Black: " + options.engine)
        summaryAnnotator = options.engine
    if options.whiteEngine:
        annotatorParts.append("White: " + options.whiteEngine)
        summaryAnnotator = options.whiteEngine
    if options.blackEngine:
        annotatorParts.append("Black: " + options.blackEngine)
        summaryAnnotator = options.blackEngine
    annotatorParts.append("Lichess Masters DB")
    annotatorParts.append(datetime.datetime.today().strftime('%Y-%m-%d'))

    ret.headers['Annotator'] = "; ".join(annotatorParts)

    node = game
    retNode = ret
    stopAnalysis = False

    summary = AnalysisSummary()

    while True:
        info = None
        engine = None
        skip = stopAnalysis
        curBoard = node.board()

        if curBoard.fullmove_number < options.firstMove:
            skip = True

        if node.turn() == chess.WHITE:
            engine = whiteEngine
        else:
            engine = blackEngine

        if (not skip) and (engine is not None):
            sys.stderr.write(f"- move {currentMoveNumStr(curBoard)}\n")

            analysisMoves, evalThresholdCp = engineAnalysis(curBoard, game, engine, options)

            # filter out moves that don't have big enough score
            analysisMoves = pruneWeakMoves(
                analysisMoves,
                evalThresholdCp - options.initialEvalMarginCp)

            if len(analysisMoves) > 0:
                retNode.comment = f"Eval={scoreToString(analysisMoves[0].evalCp, node.turn())}"

            sys.stderr.write(f"  - initial analysis: candidate moves: {analysisMoveListToString(analysisMoves, curBoard)}\n")

            analysisMoves = filterOutVariations(analysisMoves, node)

            # do a lichess query on the position
            fen = curBoard.fen()
            openingStats = openingExplorer.get_masters_games(fen, top_games=0, moves=30)

            # compute book opening thresholds
            totalGames = openingStats['white'] + openingStats['draws'] + openingStats['black']
            gamesThreshold = totalGames * options.rarityThresholdFreq
            if gamesThreshold < options.rarityThresholdCount:
                gamesThreshold = options.rarityThresholdCount

            # out of book? stop analyzing after this move
            if totalGames < options.bookCutoff:
                stopAnalysis = True

            # annotate number of book entries for this position
            retNode.comment = retNode.comment + " N=" + str(totalGames)

            # go through reported book moves, filter out popular moves
            analysisMoves = filterOutPopularMovesAddFreq(analysisMoves, openingStats, gamesThreshold, totalGames)

            sys.stderr.write(f"  - moves after book and input move reduction: {analysisMoveListToString(analysisMoves, curBoard)}\n")

            # double-check the suggestions
            analysisMoves = engineAnalysisDoubleCheck(curBoard, game, engine, options, analysisMoves)

            # filter out moves that don't have big enough score
            analysisMoves = pruneWeakMoves(analysisMoves, evalThresholdCp)

            sys.stderr.write(f"  - moves after final analysis: {analysisMoveListToString(analysisMoves, curBoard)}\n")

            # PGN arrow strings sets
            unpopularArrowStrings = set()
            noveltyArrowStrings = set()

            # Add variations from unpopular engine-approved moves
            for m in analysisMoves:
                comment = f"Eval={scoreToString(m.evalCp, node.turn())}"
                nags = set()
                if m.novelty:
                    # Note: 146 is numeric annotation glyph for novelty
                    # See https://en.wikipedia.org/wiki/Numeric_Annotation_Glyphs
                    nags.add(146)
                    noveltyArrowStrings.add(f"R{m.move.uci()}")
                else:
                    comment = comment + f" Popularity={m.freq * 100:.2f}%"
                    unpopularArrowStrings.add(f"G{m.move.uci()}")

                retNode.add_variation(
                    m.move,
                    comment = comment,
                    nags = nags)

                summary.addSurpriseMove(
                    curBoard.ply(),
                    curBoard.san(m.move),
                    m.freq,
                    m.novelty)

            # Add the arrow strings. Note: we'll add the arrows for
            # unpopular moves before novelties. Some GUIs (e.g.,
            # chessx) draw the arrows in order, and we want to
            # highlight the novelties in case the arrows overlap.
            if options.arrows and ((len(unpopularArrowStrings) + len(noveltyArrowStrings) > 0)):
                arrowStrings = [ ]
                arrowStrings += unpopularArrowStrings
                arrowStrings += noveltyArrowStrings
                retNode.comment = retNode.comment + " [%cal " + ",".join(arrowStrings) + "]"

        # next mainline move
        if (len(node.variations) > 0):
            node = node.variations[0]
            retNode = retNode.add_main_variation(move=node.move)
            if not skip:
                summary.analyzedLineStr = ret.board().variation_san(ret.mainline_moves())
        else:
            node = None
            break

    print(str(ret) + "\n")
    sys.stdout.flush()

    if options.summary:
        sys.stderr.write("==================================\n")
        sys.stderr.write("Summary:\n\n")
        sys.stderr.write(f"Engine: {summaryAnnotator}\n")
        sys.stderr.write(f"Round {game.headers['Round']}: {game.headers['White']} - {game.headers['Black']}\n\n")
        sys.stderr.write(f"{summary.analyzedLineStr}\n")

        for ply in summary.surpriseMoves:
            sys.stderr.write("\n")

            moveNumStr = str(1 + (ply // 2))
            if ply % 2 == 0:
                moveNumStr = moveNumStr + "."
            else:
                moveNumStr = moveNumStr + "..."

            for moveDesc in summary.surpriseMoves[ply]:
                sys.stderr.write(f"{moveNumStr} {moveDesc}\n")

        sys.stderr.write("\n==================================\n")


def main():
    options, inputPgns = processarguments()

    whiteEngine = None
    blackEngine = None

    if options.lichessTokenFile:
        with open(options.lichessTokenFile) as f:
            lichessApiToken = f.read()
            lichessSession = berserk.TokenSession(lichessApiToken)
            lichessClient = berserk.Client(session=lichessSession)
    else:
        lichessClient = berserk.Client()


    openingExplorer = lichessClient.opening_explorer

    try:
        whiteEngine, blackEngine = initializeEngines(options)

        for inputPgn in inputPgns:
            with open(inputPgn) as pgnFile:
                num = 0
                while True:
                    num = num + 1
                    game = chess.pgn.read_game(pgnFile)
                    if game is None:
                        break

                    analyzeGame(whiteEngine, blackEngine, game, num, options, openingExplorer)

        closeEngines(whiteEngine, blackEngine)

    except Exception as ex:
        sys.stderr.write(f"Error: {ex}\n")
        closeEngines(whiteEngine, blackEngine)


if __name__ == "__main__":
    main()
