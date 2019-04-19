from eternal_collection_guide.deck import DeckLearner
from eternal_collection_guide.deck_searches import get_deck_searches
from generate_overall_value import file_prefix

if __name__ == '__main__':
    deck_searches = get_deck_searches()
    for deck_search in deck_searches:
        deck_learner = DeckLearner(file_prefix, deck_search)
        deck_learner.update()