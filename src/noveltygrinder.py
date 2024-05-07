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


from enum import Enum
from optparse import OptionParser
from pathlib import Path
from typing import Iterable
import berserk
import berserk.clients.opening_explorer
import berserk.exceptions
import chess
import chess.engine
import chess.pgn
import chess.svg
import datetime
import json
import logging
import os
import sys
import time
import traceback

VERSION="0.1-dev"


def getDefaultEngineConfPath():
    if os.name == 'nt':
        return str(Path.home() / "AppData" / "Roaming" / "Nibbler" / "engines.json")
    else:
        return str(Path.home() / ".config" / "Nibbler" / "engines.json")


def enable_debug_logging(option, opt, value, parser):
    logging.basicConfig(level=logging.DEBUG)

def processarguments():
    parser = OptionParser(
        version="novelty-grinder " + VERSION,
        usage = 'usage: novelty-grinder [options] FILE.pgn',
        description = '''The Grand Novelty Grinder
searches for surprise moves and novelties with Lc0 and Lichess.''',
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
        default=getDefaultEngineConfPath())

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
        "",  "--pv-plies", dest="pvPlies",
        help="Number of PV plies (half-moves) to add in PGN variations for surprise moves. [default: %default]",
        type="int",
        default=1,
        metavar='NUM')

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
        "",  "--include-input", dest="includeInput", default=False,
        help="Include input moves in analysis.",
        action="store_true")

    parser.add_option(
        "",  "--summary", dest="summary", default=False,
        help="Produce a summary of potential surprise moves.",
        action="store_true")

    parser.add_option(
        "",  "--diagrams", dest="diagramPattern", default=None,
        help="Produce diagrams from positions where moves were found. In PATTERN, '{}' " +
        "is replaced with move number and side to move. For example: `--diagrams=ANALYZED-{}.svg`. " +
        "Formats supported: svg",
        type="string",
        metavar="PATTERN")

    (options, args) = parser.parse_args()

    if options.engine and options.whiteEngine:
        parser.error('--engine and --white-engine are mutually exclusive')

    if options.engine and options.blackEngine:
        parser.error('--engine and --black-engine are mutually exclusive')

    if not options.enginesJsonPath:
        parser.error('--engines-json must be especified')

    if not (options.engine or options.whiteEngine or options.blackEngine):
        parser.error('An analysis engine must be specified. Try -h for help.')

    if len(args) == 0:
        parser.error('No input PGN was specified')

    if options.doubleCheckNodes == -1:
        options.doubleCheckNodes = -(options.analysisNodes // -10) # ceiling division

    # check that diagram pattern is parseable
    if options.diagramPattern is not None:
        parseDiagramPattern(options.diagramPattern)

    if options.pvPlies < 1:
        parser.error('--pvPlies: Must be at least 1')

    return (options, args)


class DiagramFormat(Enum):
    SVG = 1


def parseDiagramPattern(pattern : str) -> (str, DiagramFormat):
    # check that we have the movenum+color substitution
    if '{}' not in pattern:
        raise ValueError('Bad diagram pattern (missing {})')

    # determine format
    suffix = pattern.upper().split('.')[-1]

    if suffix not in ('SVG'):
        raise ValueError(f"Bad diagram format: {suffix}")

    return pattern, DiagramFormat[suffix]


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

    return fullName, engineConfigs[fullName]


def initializeEngines(options):

    whiteEngine = None
    blackEngine = None

    sys.stderr.write(f"Engine configuration file: {options.enginesJsonPath}\n")
    with open(options.enginesJsonPath) as f:
        engineConfigs = json.load(f)

    if options.engine:
        fullPath, conf = getEngineConf(engineConfigs, options.engine)
        whiteEngine = initializeSingleEngine(fullPath, conf)
        blackEngine = whiteEngine

    if options.whiteEngine:
        fullPath, conf = getEngineConf(engineConfigs, options.whiteEngine)
        whiteEngine = initializeSingleEngine(fullPath, conf)

    if options.blackEngine:
        fullPath, conf = getEngineConf(engineConfigs, options.blackEngine)
        blackEngine = initializeSingleEngine(fullPath, conf)

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
    def __init__(self, evalCp, nodes, pv):
        self.move = pv[0]
        self.evalCp = evalCp
        self.nodes = nodes
        self.freq = 0
        self.novelty = True
        self.inputMove = False
        self.strongMove = True
        self.unpopularMove = True
        self.pv = pv


class AnalysisSummaryBookStats:
    def __init__(self, totalGames : int):
        self.totalGames = totalGames


class AnalysisSummary:
    def __init__(self):
        self.surpriseMoves = dict()
        self.bookStats : dict[int, AnalysisSummaryBookStats] = dict()
        self.analyzedLineStr = ""

    def addBookStats(self, ply : int, stats : AnalysisSummaryBookStats):
        self.bookStats[ply] = stats

    def addSurpriseMove(self, curBoard, pv, freq, novelty, inputMove):
        if curBoard.ply() not in self.surpriseMoves:
            self.surpriseMoves[curBoard.ply()] = list()

        summaryStr = curBoard.variation_san(pv[0:1])
        forceMoveNumber = False

        if inputMove:
            summaryStr += '!'

        if novelty:
            summaryStr += 'N'
        else:
            summaryStr += f" Popularity={100 * freq:.2f}%"
            forceMoveNumber = True

        stackMoves = 0
        remainingMoves = pv # remaining moves including the previous moves (for stack pushes)

        # print first remaining move without move number?
        if (len(remainingMoves) > 1) and (curBoard.turn == chess.WHITE) and (not forceMoveNumber):

            summaryStr += ' '
            curBoard.push(remainingMoves[0])
            stackMoves += 1

            summaryStr += curBoard.san(remainingMoves[1])
            remainingMoves = remainingMoves[1:]

        # still moves remaining to print?
        if len(remainingMoves) > 1:
            summaryStr += ' '
            curBoard.push(remainingMoves[0])
            stackMoves += 1

            summaryStr += curBoard.variation_san(remainingMoves[1:])

        for i in range(0, stackMoves):
            curBoard.pop()

        self.surpriseMoves[curBoard.ply()].append(summaryStr)


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
                    i['score'].relative.score(mate_score=1000000),
                    i['nodes'],
                    i['pv']))

    # engine produced any moves?
    if len(analysisMoves) == 0:
        return [ ], 0

    # determine threshold for candidate moves
    evalThresholdCp = analysisMoves[0].evalCp - options.evalThresholdCp

    return analysisMoves, evalThresholdCp


def forceAddInputMoves(analysisMoves, node, curBoard):
    ret = [ ]
    for v in node.variations:
        am = AnalysisMoveInfo(
                0,
                0,
                [ v.move ])
        am.inputMove = True
        ret.append(am)
    numInputs = len(ret)

    for am in analysisMoves:
        doAppend = True
        for i in range(0, numInputs):
            if curBoard.san(ret[i].move) == curBoard.san(am.move):
                ret[i] = am
                am.inputMove = True
                doAppend = False

        if doAppend:
            ret.append(am)

    return ret


# remove non-input moves that don't have big enough score
def pruneWeakMoves(analysisMoves, evalThresholdCp):
    ret = [ ]
    for am in analysisMoves:
        am.strongMove = (am.evalCp >= evalThresholdCp)

        if am.strongMove or am.inputMove:
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
            am.pv = info[0]['pv']

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
def filterOutPopularMovesAddFreq(curBoard : chess.Board, analysisMoves, openingStats, gamesThreshold, totalGames):

    ret = [ ]
    uciStrToNumGames = dict()

    # create lookup dict
    for statMove in openingStats['moves']:
        normalizedBookMove = curBoard.san(chess.Move.from_uci(statMove['uci']))
        uciStrToNumGames[normalizedBookMove] = (
            statMove['white'] + statMove['draws'] + statMove['black'] )

    for am in analysisMoves:
        # check for novelty?
        normalizedEngineMove = curBoard.san(am.move)

        if normalizedEngineMove in uciStrToNumGames:
            # not a novelty
            am.unpopularMove = uciStrToNumGames[normalizedEngineMove] <= gamesThreshold

            if am.unpopularMove or am.inputMove:
                am.freq = uciStrToNumGames[normalizedEngineMove] / totalGames
                am.novelty = False
                ret.append(am)
        else:
            # novelty
            am.freq = 0
            am.novelty = True
            am.unpopularMove = True
            ret.append(am)

    return ret


def writeDiagram(diagramPattern : str, curNode : chess.pgn.GameNode, analysisMoves : Iterable[AnalysisMoveInfo]):
    curBoard = curNode.board()

    pattern, fmt = parseDiagramPattern(diagramPattern)
    fileName = pattern.replace('{}', currentMoveNumStr(curBoard).rjust(3, '0'), 1)

    sys.stderr.write(f"- writing diagram file: {fileName}\n")

    unpopularArrows : list[chess.svg.Arrow] = list()
    noveltyArrows : list[chess.svg.Arrow] = list()
    primaryInputMoveDrawn = False

    for am in analysisMoves:
        if not (am.strongMove and am.unpopularMove):
            continue

        primaryInputMove = False

        if (len(curNode.variations) > 0):
            if am.move == curNode.variations[0].move:
                primaryInputMove = True
                primaryInputMoveDrawn = True

        if am.novelty:
            if primaryInputMove:
                noveltyArrows.append(
                    chess.svg.Arrow(am.move.from_square, am.move.to_square, color="#ffa0a0d0"))
            else:
                noveltyArrows.append(
                    chess.svg.Arrow(am.move.from_square, am.move.to_square, color="#ff0000c0"))
        else:
            if primaryInputMove:
                unpopularArrows.append(
                    chess.svg.Arrow(am.move.from_square, am.move.to_square, color="#a0ffa0d0"))
            else:
                unpopularArrows.append(
                    chess.svg.Arrow(am.move.from_square, am.move.to_square, color="#00ff00c0"))

    allArrows : list[chess.svg.Arrow] = list()

    if (curNode.move):
        allArrows.append(
            chess.svg.Arrow(curNode.move.from_square, curNode.move.to_square, color="#2020b060")
        )

    if (len(curNode.variations) > 0) and (not primaryInputMoveDrawn):
        nextNode = curNode.variations[0]
        allArrows.append(
            chess.svg.Arrow(nextNode.move.from_square, nextNode.move.to_square, color="#40404060")
        )

    allArrows.extend(unpopularArrows)
    allArrows.extend(noveltyArrows)

    outputDiagram = chess.svg.board(
        curBoard,
        arrows=allArrows,
        orientation=curBoard.turn,
        size=480
    )

    with open(fileName, "w") as svgFile:
        svgFile.write(outputDiagram)


def analysisMoveListToString(analysisMoves, board):
    moveStrList = [ ]
    for am in analysisMoves:
        moveStr = board.san(am.move)

        # debugging for move classification
        if False:
            moveStr += '['

            if am.inputMove:
                moveStr += 'I'

            if am.strongMove:
                moveStr += 'S'

            if am.unpopularMove:
                moveStr += 'U'

            moveStr += ']'

        moveStrList.append(moveStr)

    return " ".join(moveStrList)


def getOpeningStats(openingExplorer : berserk.clients.opening_explorer.OpeningExplorer, curBoard : chess.Board):

    # get opening stats from Lichess
    fen = curBoard.fen()

    i = 0
    while True:
        try:
            i = i + 1
            return openingExplorer.get_masters_games(fen, top_games=0, moves=30)
        except berserk.exceptions.ApiError as ex:
            sys.stderr.write(f"Lichess DB query error: {ex}\n")
            if (i < 3):
                sleepSecs = 1 + i * 2
                sys.stderr.write(f"Retrying after {sleepSecs} secs...\n")
                time.sleep(sleepSecs)
            else:
                raise


# returns True if analysis should continue (i.e., no cut-off)
def analyzePosition(
        options,
        engine,
        openingExplorer : berserk.clients.opening_explorer.OpeningExplorer,
        game : chess.pgn.Game,
        curBoard : chess.Board,
        node,    # in:     game node
        retNode, # in-out: analysis variations and comments to be added here
        summary : AnalysisSummary):

    sys.stderr.write(f"- move {currentMoveNumStr(curBoard)}\n")

    # do a lichess query on the position
    openingStats = getOpeningStats(openingExplorer, curBoard)

    # compute book opening thresholds
    totalGames = openingStats['white'] + openingStats['draws'] + openingStats['black']
    gamesThreshold = totalGames * options.rarityThresholdFreq
    if gamesThreshold < options.rarityThresholdCount:
        gamesThreshold = options.rarityThresholdCount

    # annotate number of book entries for this position
    retNode.comment += f"N={totalGames}"

    # book cut-off?
    if totalGames < options.bookCutoff:
        sys.stderr.write(f"  - book cut-off triggered: book_N={totalGames}\n")
        return False

    analysisMoves, evalThresholdCp = engineAnalysis(curBoard, game, engine, options)

    if options.includeInput:
        analysisMoves = forceAddInputMoves(analysisMoves, node, curBoard)

    # filter out moves that don't have big enough score
    analysisMoves = pruneWeakMoves(
        analysisMoves,
        evalThresholdCp - options.initialEvalMarginCp)

    if len(analysisMoves) > 0:
        retNode.comment += f" Eval={scoreToString(analysisMoves[0].evalCp, node.turn())}"

    sys.stderr.write(f"  - initial analysis: candidate moves: {analysisMoveListToString(analysisMoves, curBoard)}\n")

    if not options.includeInput:
        analysisMoves = filterOutVariations(analysisMoves, node)

    # store number of games to summary
    summary.addBookStats(curBoard.ply(), AnalysisSummaryBookStats(totalGames))

    # go through reported book moves, filter out popular moves
    analysisMoves = filterOutPopularMovesAddFreq(curBoard, analysisMoves, openingStats, gamesThreshold, totalGames)

    sys.stderr.write(f"  - moves after book and input move reduction: {analysisMoveListToString(analysisMoves, curBoard)}; book_N={totalGames}\n")

    # double-check the suggestions
    analysisMoves = engineAnalysisDoubleCheck(curBoard, game, engine, options, analysisMoves)

    # filter out moves that don't have big enough score
    analysisMoves = pruneWeakMoves(analysisMoves, evalThresholdCp)

    sys.stderr.write(f"  - moves after final analysis: {analysisMoveListToString(analysisMoves, curBoard)}\n")

    # PGN arrow strings sets
    unpopularArrowStrings = set()
    noveltyArrowStrings = set()

    # Add variations from unpopular engine-approved moves
    enableDiagram = False
    for m in analysisMoves:
        comment = f"Eval={scoreToString(m.evalCp, node.turn())}"
        nags = set()
        if m.novelty:
            # Note: 146 is numeric annotation glyph for novelty
            # See https://en.wikipedia.org/wiki/Numeric_Annotation_Glyphs
            nags.add(146)
            if m.strongMove:
                noveltyArrowStrings.add(f"R{m.move.uci()}")
        else:
            comment = comment + f" Popularity={m.freq * 100:.2f}%"
            if m.unpopularMove and m.strongMove:
                unpopularArrowStrings.add(f"G{m.move.uci()}")

        if m.inputMove and m.unpopularMove and m.strongMove:
            nags.add(1)  # add '!'

        varNode = retNode.add_variation(
            m.move,
            comment = comment,
            nags = nags)

        if (not m.inputMove) and (options.pvPlies > 1):
            varNode.add_line(m.pv[1:options.pvPlies])

        if m.unpopularMove and m.strongMove:
            enableDiagram = True
            if len(varNode.variations) > 0:
                pvMoves = [varNode.move]
                pvMoves.extend(varNode.mainline_moves())
            else:
                pvMoves = [varNode.move]

            summary.addSurpriseMove(
                curBoard,
                pvMoves,
                m.freq,
                m.novelty,
                m.inputMove)

    # Add the arrow strings. Note: we'll add the arrows for
    # unpopular moves before novelties. Some GUIs (e.g.,
    # chessx) draw the arrows in order, and we want to
    # highlight the novelties in case the arrows overlap.
    if options.arrows and ((len(unpopularArrowStrings) + len(noveltyArrowStrings) > 0)):
        arrowStrings = [ ]
        arrowStrings += unpopularArrowStrings
        arrowStrings += noveltyArrowStrings
        retNode.comment = retNode.comment + " [%cal " + ",".join(arrowStrings) + "]"

    if enableDiagram and options.diagramPattern:
        writeDiagram(options.diagramPattern, node, analysisMoves)

    return True


def analyzeGame(whiteEngine, blackEngine, game, num, options, openingExplorer : berserk.clients.opening_explorer.OpeningExplorer):
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

        if not retNode.comment:
            retNode.comment = ''
        else:
            retNode.comment += '; '

        if curBoard.fullmove_number < options.firstMove:
            skip = True

        if node.turn() == chess.WHITE:
            engine = whiteEngine
        else:
            engine = blackEngine

        if (not skip) and (engine is not None):
            stopAnalysis = not analyzePosition(
                options,
                engine,
                openingExplorer,
                game,
                curBoard,
                node,
                retNode,
                summary)

        # next mainline move
        if (len(node.variations) > 0):
            node = node.variations[0]

            if retNode.has_variation(node.move):
                retNode.promote_to_main(node.move)
                retNode = retNode.variations[0]
            else:
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

            for moveDesc in summary.surpriseMoves[ply]:
                sys.stderr.write(f"{moveDesc}\n")

            sys.stderr.write(f"(N={summary.bookStats[ply].totalGames})\n")

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
        sys.stderr.write(f"Error: {traceback.format_exc()}\n")
        closeEngines(whiteEngine, blackEngine)


if __name__ == "__main__":
    main()
