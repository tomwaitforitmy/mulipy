import datetime
import pprint

import trackopy
import json

import xlsxwriter


class Mulligan(object):
    """A class to compute the performance of cards in certain match ups. The goal is to improve your mulligan and/or to
        identify cards that are weak against certain match ups in order to find room for tech cards. The Mulligan class
        has the following properties:

    Attributes:
        data_source: System path to your track-o-bot history in .json format. E.g. 'C:\\Users\\tommy\\history.json'
            Alternatively, you can insert your track-o-bot account data as dictionary. E.g.
            {"username": "YourAccount", "password": "YourPassword"}

        deck_type: Deck type in tuple format from track-o-bot. E.g. ("Miracle", "Rogue")

        opponent_deck_type_tuples_list: List of opponents you are interested in. E.g.:
        [("Aggro", "Shaman"), ("Midrange", "Shaman"), ("Reno", "Warlock")]
        
        deck_list: List (or single card) you want to evaluate. E.g.
            deck_list = ["Counterfeit Coin", "Backstab", "Preparation", "Small-Time Buccaneer"]
    """

    def __init__(self, data_source, deck_type: tuple, opponent_deck_type_tuples_list: list, deck_list: list):
        # Check if the user supplied data in .json format.
        pages = []  # contains the data page(s)
        if '.json' in data_source:
            with open(data_source) as file:
                page = json.load(file)
            # Standard history page contains stuff we don't need. Here we get rid of it. Todo: adapt for multiple pages.
            if 'history' in page:
                pages.append(page['history'])
            else:
                pages.append(page)
        # Check if we can connect to track-o-bot with the data
        elif {'username', 'password'}.issubset(data_source):
            print("Found username and password. Connecting to track-o-bot.com ...")
            pages = self.get_pages_from_trackobot(data_source['username'], data_source['password'])

        else:
            raise Warning("From mulligan.__init__: misuse of data_source.\
                          Please supply a path to a .json file (e.g. 'C:\history.json')\
                          or username and password for track-o-bot\
                          (e.g. {'username': 'your_name', 'password': 'your_passowrd'}")

        self.data = pages
        self.deck_type = deck_type
        self.opponent_deck_type_tuples_list = opponent_deck_type_tuples_list
        if not self.opponent_deck_type_tuples_list:
            print("No match-ups given. Data from track-o-bot will be loaded.")
            self.opponent_deck_type_tuples_list = self.load_decktypes_from_json("testdata\\track-o"
                                                                                "-bot_decklists_16022017.json")
            # Todo: we could create a user here or ask for pw/user, but the list does not contain 'Other' decks
            # user = trackopy.Trackobot.create_user()
            # trackobot = trackopy.Trackobot(user['username'], user['password'])
            # decks = trackobot.decks()

        if not deck_list:
            raise TypeError("From mulligan.__init__: misuse of variable.\
                          Please insert at least one card to evaluate. E.g. ['Coin']")
        self.deck_list = deck_list
        # We use a big value here that can never be reached due to fatigue in Hearthstone
        self.max_turn = 9999

    def set_max_turn(self, max_turn: int):
        """
        Setter for the maximum turn you want to evaluate.
        :param self: The mulligan class.
        :param max_turn: A positive integer to limit the card search to a certain turn.
            Until which turn you want to check your games? Games are often decided until turn 5 or 6 so if you set
            this to 5 all cards that are played after turn 5 will be ignored.
        """
        if max_turn > 0:
            self.max_turn = max_turn
        else:
            raise TypeError("From mulligan.setMaxTurn(): The maximum turn must be a positive integer!")

    def get_pages_from_trackobot(self, username: str, password: str, date: object = datetime.datetime.now()) -> list:
        """
        Receive history pages from track-o-bot.com from your profile.
        :param username: Your track-o-bot username as string. E.g. wandering-dust-devil-1234
        :param password: Your track-o-bot password as string. E.g. 123abc123a
        You access your data in track-o-bot via: Settings... -> Account -> Export
        :param date: Todo: Implement date restriction
        :return: A list of pages (of track-o-bot history) ready for evaluation.
        """
        pages = []
        trackobot = trackopy.Trackobot(username, password)
        # Track-o-bot only saves the card history for 10 days.
        # Therefore, we only search for games in last 10 days.
        minus_ten_days = date - datetime.timedelta(days=10)

        i = 1
        page = trackobot.history(i)['history']

        while self.search_pages_younger_than(page, minus_ten_days):
            pages.append(page)
            i += 1
            page = trackobot.history(i)['history']
        return pages

    def search_pages_younger_than(self, pages: list, date: object):
        """
        Looks for history pages that are younger than a certain date.
        :param pages: A list of history pages from track-o-bot.
        :param date: The point in time before you would like to find data.
        :return: All pages before a certain date.
        """
        pages_younger_than = []
        for page in pages:
            if page['added'] > date.isoformat():
                pages_younger_than.append(page)
        if not pages_younger_than:
            print("Page older than 10 days. No card data available.", page['added'])
        return pages_younger_than

    def find_card(self, card: object, game: object) -> object:
        """
        Checks if a card was played in a game by YOU or not.
        :param card: Card you are looking for in the game.
        :param game: A game to be checked if the card was played.
        :return: The game data if the card was played else False.
        """
        for cards in game['card_history']:
            # check that "me" played the card and not opponent
            if (cards['player'] == 'me') and (card in cards['card'].values()) and (cards['turn'] <= self.max_turn):
                return game
        return False

    def find_hero_deck(self, pages: list, hero: str, hero_deck: str) -> list:
        """
        Finds a list where you played a certain deck.
        :param pages: Track-o-bot history pages to search for your deck type.
        :param hero: Your hero class. E.g. 'Shaman' or 'Warrior' or any other class from Hearthstone.
        :param hero_deck: Your deck. E.g. 'Pirate' or 'Reno'. See track-o-bot website for available options.
        :return: A list of games where your deck was used.
        """
        result_games = []
        for page in pages:
            for game in page:
                if (game["hero"] == hero) and (game["hero_deck"] == hero_deck):
                    result_games.append(game)
        return result_games

    def find_opponent_deck(self, page: list, opponent: str, opponent_deck: str) -> list:
        """
        Finds a list of games of a certain match up.
        :param page: List of games from a track-o-bot history page.
        :param opponent: Opponents hero class. E.g. 'Shaman' or 'Warrior' or any other class from Hearthstone.
        :param opponent_deck: Opponents deck. E.g. 'Pirate' or 'Reno'. See track-o-bot website for available options.
        :return: A list of games where the opponent played a certain deck.
        """
        result_games = []
        for game in page:
            if (game["opponent"] == opponent) and (game["opponent_deck"] == opponent_deck):
                result_games.append(game)
        return result_games

    def times_played(self, card: object, valid_games: list) -> object:
        """
        Counts how often a card was played.
        :param card: Card you are looking for.
        :param valid_games: Games the card was played in.
        :return: Number the card was played as integer.
        """
        number_card_was_played = 0
        for game in valid_games:
            for cards in game['card_history']:
                # check that "me" played the card and not opponent
                if (cards['player'] == 'me') and (card in cards['card'].values()) and (cards['turn'] <= self.max_turn):
                    number_card_was_played += 1
        return number_card_was_played

    def count_wins(self, games: list) -> int:
        """
        Counts the wins in a list of games.
        :param games: List of games.
        :return: Number of wins as integer.
        """
        number_of_wins = 0
        for game in games:
            if game['result'] == "win":
                number_of_wins += 1
        return number_of_wins

    def find_games_with_card(self, card: object, games: list) -> list:
        """
        Finds a list of games where the card was played.
        :param card: Card you want to evaluate.
        :param games: List of games.
        :return: List of games where the card was played.
        """
        games_with_card_played = []
        for game in games:
            if self.find_card(card, game):
                games_with_card_played.append(self.find_card(card, game))

        return games_with_card_played

    def evaluate_deck_list(self, deck_list: list, games: list) -> dict:
        """
        Evaluates a complete deck list.
        :param deck_list: A list of cards you want to check. E.g. ["Counterfeit Coin", "Backstab"]
        :param games: A list of games you want to check.
        :return: A dictionary with results for all cards.
            It includes the card name, the number of wins with the card, the number of games with the card and
            the number of times the card was played.
        """
        result_list = []
        for card in deck_list:
            games_with_card_played = self.find_games_with_card(card, games)
            card_result = {'card': card,
                           'number of wins with card': self.count_wins(games_with_card_played),
                           'number of games with card': len(games_with_card_played),
                           'times played': self.times_played(card, games_with_card_played)}
            result_list.append(card_result)
        return result_list

    def print_result(self, result_list: list):
        """
        Convience function to print results to the console.
        :param result_list: Results generated by Mulligan.evaluate()
        """
        for result in result_list:
            print("----------------------------------------")
            if result['number of games'] > 0:
                print("Result for", result['opponent_deck'], result['opponent'])
                print("Number of games:", result['number of games'])
                print("Number of wins:", result['number of wins'])
                print("Win %: {0:.2f}".format((result['number of wins'] / result['number of games']) * 100))
                for cards in result['cards_evaluated']:
                    if cards['times played'] > 0:
                        print("Number of games with card:", cards['number of games with card'])
                        print(cards['card'], "was played", cards['times played'])
                        print("Number of wins with:", cards['card'], cards['number of wins with card'])
                        print("Win %: {0:.2f}".format((cards['number of wins with card'] / cards['number of games with '
                                                                                                 'card']) * 100))
            else:
                print("No games against", result['opponent_deck'], result['opponent'])

    def print_result_to_xlsx(self, result_list: list, filename: object = "mullipy_results.xlsx"):
        """
        Creates an Excel sheet for the result data.
        :param result_list: Results generated by Mulligan.evaluate().
        :param filename: Optional file name for the excel file. Default mullipy_results.xlsx.
        """
        workbook = xlsxwriter.Workbook(filename)
        worksheet = workbook.add_worksheet(self.deck_type[1] + " " + self.deck_type[0])

        # Start from the first cell. Rows and columns are zero indexed.
        row = 0
        col = 0
        # headlines
        worksheet.write(0, 0, "Opponent Hero")
        worksheet.write(0, 1, "Opponent Deck")
        worksheet.write(0, 2, "Wins")
        worksheet.write(0, 3, "Losses")
        worksheet.write(0, 4, "Win %")
        worksheet.write(0, 5, "Card")
        worksheet.write(0, 6, "Times played")
        worksheet.write(0, 7, "Wins with card")
        worksheet.write(0, 8, "Losses with card")
        worksheet.write(0, 9, "Win % with card played")

        for result in result_list:
            if result['number of games'] > 0:
                row += 1
                if not result['opponent_deck']:
                    readable_deck = "Other"
                else:
                    readable_deck = result['opponent_deck']
                worksheet.write(row, col, result['opponent'])
                worksheet.write(row, col + 1, readable_deck)
                worksheet.write(row, col + 2, result['number of wins'])
                worksheet.write(row, col + 3, result['number of games'] - result['number of wins'])
                worksheet.write(row, col + 4, result['number of wins'] / result['number of games'] * 100)
                for cards in result['cards_evaluated']:
                    row += 1
                    worksheet.write(row, col + 5, cards['card'])
                    worksheet.write(row, col + 6, cards['times played'])
                    worksheet.write(row, col + 7, cards['number of wins with card'])
                    worksheet.write(row, col + 8,
                                    cards['number of games with card'] - cards['number of wins with card'])
                    if cards['number of games with card'] > 0:
                        worksheet.write(row, col + 9, cards['number of wins with card'] / cards['number of games with '
                                                                                                'card'] * 100)
                    else:
                        worksheet.write(row, col + 9, "N/A")
        workbook.close()

    def load_decktypes_from_json(self, path: str) -> list:
        """
        Loads deck types from JSON file. Todo: better load from internet.
        :param path: Path to the file.
        :return: List of deck types. E.g. [('Aggro', 'Shaman'), ('Jade', 'Shaman'), ...]
        """
        with open(path) as file:
            data = json.load(file)

        opponent_deck_type_tuples_list = []
        for deck in data['decks']:
            if deck['active']:
                opponent_deck_type_tuples_list.append((deck['name'], deck['hero']))
        return opponent_deck_type_tuples_list

    def evaluate(self):

        """
        Evaluates the complete input of the Mulligan class.
        :return: Afterwards, choose your favorite way to print results. E.g. print_result_to_xlsx() or print_result().
        """
        pages = self.data
        deck_list = self.deck_list

        # our deck
        hero = self.deck_type[1]
        hero_deck = self.deck_type[0]

        result_list = []
        # result type example: [{'opponent': 'Shaman', 'opponent_deck': 'Aggro' 'number of games': 3, 'number of
        # wins': 2, 'cards_evaluated': [{'card': 'Eviscerate', 'number of wins with card': 2, 'number of games': 2,
        # 'times played': 1}, {'card': 'Backstab', 'number of wins with card': 1, 'number of games': 1,
        # 'times played': 1}] }]

        valid_games = self.find_hero_deck(pages, hero, hero_deck)

        # opponent deck(s)
        opponent_deck_type_tuples_list = self.opponent_deck_type_tuples_list

        for deck_types in opponent_deck_type_tuples_list:
            opponent = deck_types[1]
            opponent_deck = deck_types[0]

            # get all games vs one archetype
            games_vs_opponent = self.find_opponent_deck(valid_games, opponent, opponent_deck)

            result = {'opponent': opponent, 'opponent_deck': opponent_deck,
                      'number of games': len(games_vs_opponent),
                      'number of wins': self.count_wins(games_vs_opponent),
                      'cards_evaluated': self.evaluate_deck_list(deck_list, games_vs_opponent)}

            result_list.append(result)

        return result_list
