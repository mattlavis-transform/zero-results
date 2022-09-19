import requests
import csv
import sys
import re
from pluralizer import Pluralizer
from spellchecker import SpellChecker
import classes.globals as g
from textblob import Word


class InterceptMessage(object):
    def __init__(self, term, message, typos_file_path):
        self.term = term
        self.is_valid = True
        self.is_country = False
        # print(self.term)
        self.message = message
        self.typos_file_path = typos_file_path

        self.format_term()
        self.format_message()
        self.create_yaml()

    def format_term(self):
        self.term = self.term.strip()

    def format_message(self):
        self.replace_countries()
        self.message = self.message.strip()
        self.message = self.message.replace('"', "'")
        self.message = self.message.replace(' ,', ",")
        self.message = self.message.replace('\xa0', " ")

        self.deal_with_pipes()
        if self.message[-1] != ".":
            self.message += "."
        self.message = self.message.replace("\n", "\n              ")

        self.check_for_odd_numbers_of_digits()
        self.correct_typos()
        self.standardise_shorthand()
        self.replace_hmrc_shortcuts()
        self.standardise_headings()
        self.check_code_validity()
        self.final_message_tidy()
        self.insert_atar()
        self.check_usefulness()

    def replace_countries(self):
        template = "See more information about trading with [{country}](https://www.gov.uk/world/organisations/department-for-international-trade-{country2})"
        if "COUNTRY" in self.message:
            if self.term not in g.country_failures:
                self.is_country = True
                tmp = self.term.lower()
                tmp = tmp.replace(" ", "-")
                self.message = template.format(country=self.term, country2=tmp)
            else:
                self.is_valid = False

    def deal_with_pipes(self):
        tiers = {
            4: "heading",
            6: "subheading",
            8: "subheading",
            10: "commodity"
        }
        if "|" in self.message:
            parts = self.message.split("|")
            template = "Based on your search, we believe you are looking for {term} under {tier} {entity}."
            entity = parts[0].strip()
            term = parts[1].strip()
            # if term.startswith("For"):
            #     term = "items " + term
            #     term = term.replace("items For", "items for")
            if term.startswith("For"):
                term = term[4:]
            elif term.startswith("Under "):
                term = term[6:]

            term = g.decapitalise(term)
            tier = tiers[len(entity)]
            self.message = template.format(term=term, tier=tier, entity=entity)

    def replace_hmrc_shortcuts(self):
        if self.term == "aerosol can":
            a = 1
        self.message = re.sub("([^0-9][0-9]{4}), ([0-9]{4}[^0-9])", "\\1/\\2", self.message)
        for i in range(8, -1, -1):
            to_find = "([^0-9][0-9]{4})/" + ("([0-9]{4})/" * i) + "([0-9]{4}[^0-9])"
            to_replace = "\\1"
            for j in range(0, i):
                to_replace += ", \\" + str(j + 2)
            to_replace += " or heading \\" + str(i + 2)
            self.message = re.sub(to_find, to_replace, self.message)

    def check_code_validity(self):
        self.check_headings("heading ([0-9]{4})[^0-9]")
        self.check_headings("subheading ([0-9]{6})[^0-9]")
        self.check_headings("subheading ([0-9]{8})[^0-9]")
        self.check_headings("commodity ([0-9]{10})[^0-9]")

    def check_headings(self, substring):
        if "subheading" in substring:
            claimed_entity = "subheading"
        elif "heading" in substring:
            claimed_entity = "heading"
        elif "commodity" in substring:
            claimed_entity = "commodity"
        else:
            claimed_entity = ""

        matches = re.search(substring, self.message, re.IGNORECASE)
        if matches:
            groups = list(matches.groups())
            for group in groups:
                code = group.ljust(10, "0")
                if code not in g.commodities:
                    obj = {
                        self.term: {
                            "verbatim": group,
                            "commodity": code
                        }
                    }
                    g.incorrect_commodities.append(obj)
                else:
                    actual_entity = g.commodities_dict[code]
                    if claimed_entity != "":
                        if claimed_entity != actual_entity:
                            a = 1
                            if self.term == "face paint":
                                a = 1
                            if claimed_entity == "heading":
                                if actual_entity == "commodity":
                                    self.message = self.message.replace("heading " + group, "commodity " + code)
                                elif actual_entity == "subheading":
                                    self.message = self.message.replace("heading " + group, "subheading " + group)
                            elif claimed_entity == "subheading":
                                if actual_entity == "commodity":
                                    self.message = self.message.replace("subheading " + group, "commodity " + code)
                                    a = 1
                                else:
                                    a = 1
                            elif claimed_entity == "commodity":
                                a = 1

    def check_for_odd_numbers_of_digits(self):
        self.erroneous_digits = False
        self.erroneous_digit = None
        odd_digits = [5, 7, 9]
        for digit in odd_digits:
            substring = "[^0-9][0-9]{" + str(digit) + "}[^0-9]"
            matches = re.search(substring, self.message, re.IGNORECASE)
            if matches is not None:
                self.erroneous_digits = True
                self.erroneous_digit = digit
                obj = {
                    self.term: self.erroneous_digit
                }
                g.erroneous_digits.append(obj)
                break

    def standardise_shorthand(self):
        pluralizer = Pluralizer()
        term_pluralised = pluralizer.pluralize(self.term, 2, False).capitalize()

        self.message = self.message.replace("TERMS CLASS", term_pluralised + " are classified under")
        self.message = self.message.replace("TERM CLASS", self.term.capitalize() + " is classified under")

        self.message = self.message.replace("TERM CCHAP", self.term.capitalize() + " is classified under chapter")
        self.message = self.message.replace("TERM CHEAD", self.term.capitalize() + " is classified under heading")
        self.message = self.message.replace("TERM CSHEAD", self.term.capitalize() + " is classified under subheading")
        self.message = self.message.replace("TERM CCOMM", self.term.capitalize() + " is classified under commodity")

        self.message = self.message.replace("TERMS", term_pluralised)
        self.message = self.message.replace("TERM", self.term.capitalize())

        self.message = self.message.replace("CCHAP", "are classified under chapter")
        self.message = self.message.replace("CHEAD", "are classified under heading")
        self.message = self.message.replace("CSHEAD", "are classified under subheading")
        self.message = self.message.replace("CCOMM", "are classified under commodity")

        self.message = re.sub("(classified under chapter) ([0-9]{2})/([0-9]{2})/([0-9]{2})/([0-9]{2})", "\\1 \\2, chapter \\3, chapter \\4 or chapter \\5", self.message)
        self.message = re.sub("(classified under chapter) ([0-9]{2})/([0-9]{2})/([0-9]{2})", "\\1 \\2, chapter \\3 or chapter \\4", self.message)
        self.message = re.sub("(classified under chapter) ([0-9]{2})/([0-9]{2})", "\\1 \\2 or chapter \\3", self.message)

        self.message = self.message.replace("PRECISE", "The full commodity code")
        self.message = self.message.replace("TOO GENERIC", "The search term entered is too generic. Please enter the specific type of goods.")
        self.message = self.message.replace("NOT PHYSICAL", "The search term entered is not a physical item")
        self.message = self.message.replace("NOT REQUIRED", "A commodity code is not required for this item")
        self.message = re.sub("heading([^ ])", "heading \\1", self.message)

    def standardise_headings(self):
        self.message = re.sub("\s+", " ", self.message)
        # Go easy where the terms commodity, heading or subheading have been omitted
        self.message = re.sub("([^ye]) ([0-9]{10}[^0-9])", "\\1 commodity \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{8}[^0-9])", "\\1 subheading \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{6}[^0-9])", "\\1 subheading \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{4}[^0-9])", "\\1 heading \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{4}[^0-9])", "\\1 heading \\2", self.message)

        # Correct obvious misapplication of entity types
        self.message = re.sub(" heading ([0-9]{6}[^0-9])", " subheading \\1", self.message)
        self.message = re.sub(" heading ([0-9]{8}[^0-9])", " subheading \\1", self.message)
        self.message = re.sub(" heading ([0-9]{10})", " commodity \\1", self.message)
        self.message = re.sub(" headings ([0-9]{4}),", " heading \\1,", self.message)

    def final_message_tidy(self):
        self.message = self.message.replace("..", ".")
        self.message = re.sub("\s+", " ", self.message)
        if "http" not in self.message:
            self.message = self.message.replace("/", " / ")
        self.message = self.message.replace("to heading", "under heading")
        self.message = self.message.replace("to subheading", "under subheading")
        self.message = self.message.replace("to commodity", "under commodity")
        self.message = self.message.replace("heading commodity", "commodity")
        self.message = self.message.replace(", then", " then")
        self.message = self.message.replace("then, dependent", ", then the full commodity code is dependent")
        self.message = self.message.replace(" if of ", " if the item is of ")
        self.message = self.message.replace(" if a ", " if the item is a ")
        self.message = self.message.replace(" if an ", " if the item is an ")
        self.message = self.message.replace(" then The ", " then the ")
        self.message = self.message.replace("dependent on what it's used for", "dependent on what the item is used for")

        self.message = self.message.replace(" ,", ",")
        self.message = self.message.replace(",", ", ")
        self.message = self.message.replace(" .", ".")
        self.message = self.message.replace(",.", ".")
        self.message = self.message.replace("?.", "?")

        self.message = re.sub("([0-9])or ", "\\1, or ", self.message)
        self.message = re.sub(", or ", " or ", self.message)
        self.message = re.sub("([0-9]) then", "\\1, then", self.message)
        self.message = re.sub("([^,]) as long as", "\\1, as long as", self.message)
        self.message = re.sub("([0-9]) dependent", "\\1, dependent", self.message)
        self.message = re.sub("is dependent if", "depends whether", self.message)
        self.message = re.sub("is dependent on", "depends on", self.message)
        self.message = re.sub("are dependent on", "depend on", self.message)
        self.message = re.sub("dependent on", "depending on", self.message)
        # self.message = re.sub("dependent if ", "depending whether the item is ", self.message)

        self.message = re.sub("([^,]) then ", "\\1, then ", self.message)

        self.message = re.sub("\s+", " ", self.message)
        self.message = self.message[0].upper() + self.message[1:]

    def correct_typos(self):
        self.correct_would_depend()
        with open(self.typos_file_path, 'r') as file:
            reader = csv.reader(file, quotechar='"')
            for row in reader:
                term_from = row[0]
                term_to = row[1]
                self.message = self.message.replace(term_from, term_to)

    def check_usefulness(self):
        if self.is_valid:
            value_count = 0
            value_count += self.check_contains("chapter [0-9]{1,2}[^0-9]")
            value_count += self.check_contains("heading [0-9]{4}[^0-9]")
            value_count += self.check_contains("subheading [0-9]{6}[^0-9]")
            value_count += self.check_contains("subheading [0-9]{8}[^0-9]")
            value_count += self.check_contains("commodity [0-9]{10}[^0-9]")
            value_count += self.check_contains("section [A-Z]{1,2}[A-Z]")
            value_count += self.check_contains("http")
            value_count += self.check_contains("too generic")
            value_count += self.check_contains("too many")
            value_count += self.check_contains("not a physical item")
            value_count += self.check_contains("not required for this item")
            value_count += self.check_contains("ATAR")

            if "heading ," in self.message:
                value_count = 0

            if value_count == 0:
                obj = {
                    self.term: self.message
                }
                g.useless_messages.append(obj)

    def insert_atar(self):
        if self.term == "bedroom furnitu":
            a = 1
        atar_message = "See more information on [ATAR rulings](https://www.gov.uk/guidance/apply-for-an-advance-tariff-ruling)."
        if "ATAR" in self.message.upper():
            self.message += " " + atar_message
            a = 1

    def check_contains(self, substring):
        matches = re.search(substring, self.message, re.IGNORECASE)
        if matches:
            return 1
        else:
            return 0

    def correct_would_depend(self):
        if self.term == "safety footwear":
            a = 1
        # Chapter 64 Would depend on the material of the soles and uppers and whether waterproof
        self.message = re.sub("([0-9]{2,10})\sWould depend", "\\1. PRECISE would depend", self.message)

    def create_yaml(self):
        self.yaml = ""
        self.yaml += "  " + self.term + ":\n"
        self.yaml += "    title: \"" + self.term + "\"\n"
        self.yaml += "    message: \"" + self.message + "\"\n\n"
