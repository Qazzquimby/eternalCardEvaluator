import pandas as pd


class CardCopy(pd.DataFrame):
    SET_NUM_NAME = "set_num"
    CARD_NUM_NAME = "card_num"
    COUNT_IN_DECK_NAME = "count_in_deck"

    def __init__(self, *args):
        pd.DataFrame.__init__(self, *args)
        self.set_num = self.set_num
        self.card_num = self.card_num
        self.count_in_deck = self.count_in_deck
        self.set_index([self.set_num, self.card_num, self.count_in_deck], inplace=True)


class CardDetails(pd.DataFrame):
    SET_NUM_NAME = "set_num"
    CARD_NUM_NAME = "card_num"

    RARITY_NAME = "rarity"
    IMAGE_URL_NAME = "image_url"
    DETAILS_URL_NAME = "details_url"
    IS_IN_DRAFT_PACK_NAME = "is_in_drat_pack"

    def __init__(self, *args):
        pd.DataFrame.__init__(self, *args)
        self.set_num = self.set_num
        self.card_num = self.card_num
        self.set_index([self.set_num, self.card_num], inplace=True)

        self.rarity = self.rarity
        self.image_url = self.image_url
        self.details_url = self.details_url
        self.is_in_draft_pack = self.is_in_draft_pack
