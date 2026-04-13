"""Template handlers registry.

Keys are lowercase template type names as written in the markdown '##' heading.
"""

from . import (
    anagram,
    balloon_pop,
    crossword,
    gameshow_quiz,
    hangman,
    image_quiz,
    matching_pairs,
    matchup,
    wordsearch,
)

TEMPLATE_HANDLERS: dict[str, object] = {
    "hangman": hangman.create,
    "match up": matchup.create,
    "anagram": anagram.create,
    "crossword": crossword.create,
    "image quiz": image_quiz.create,
    "wordsearch": wordsearch.create,
    "word search": wordsearch.create,
    "gameshow quiz": gameshow_quiz.create,
    "gameshow": gameshow_quiz.create,
    "balloon pop": balloon_pop.create,
    "matching pairs": matching_pairs.create,
}
