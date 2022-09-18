import csv
import sys
import re
from pluralizer import Pluralizer
from spellchecker import SpellChecker
import classes.globals as g
from textblob import Word


class InterceptMessage(object):
    def __init__(self, term, message, genuine_term, typos_file_path):
        self.term = term
        self.message = message
        self.genuine_term = genuine_term
        self.typos_file_path = typos_file_path

        self.format_term()
        self.format_message()
        self.create_yaml()

    def format_term(self):
        self.term = self.term.strip()

    def format_message(self):
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
            if term.startswith("For"):
                term = "items " + term
                term = term.replace("items For", "items for")
            elif term.startswith("Under "):
                term = term[6:]

            term = g.decapitalise(term)
            tier = tiers[len(entity)]
            self.message = template.format(term=term, tier=tier, entity=entity)

    def replace_hmrc_shortcuts(self):
        # Headings
        # self.message = re.sub("([^0-9][0-9]{4})/([0-9]{4})/([0-9]{4})/([0-9]{4}[^0-9])", "\\1, \\2, \\3 or heading \\4", self.message)
        # self.message = re.sub("([^0-9][0-9]{4})/([0-9]{4})/([0-9]{4}[^0-9])", "\\1, \\2 or heading \\3", self.message)
        # self.message = re.sub("([^0-9][0-9]{4})/([0-9]{4}[^0-9])", "\\1 or heading \\2", self.message)

        for i in range(8, -1, -1):
            to_find = "([^0-9][0-9]{4})/" + ("([0-9]{4})/" * i) + "([0-9]{4}[^0-9])"
            to_replace = "\\1"
            for j in range(0, i):
                to_replace += ", \\" + str(j + 2)
            to_replace += " or heading \\" + str(i + 2)
            self.message = re.sub(to_find, to_replace, self.message)
        #     print(to_find)
        #     print(to_replace + "\n")
        # sys.exit()

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
        if self.genuine_term == "":
            term_pluralised = pluralizer.pluralize(self.term, 2, False).capitalize()
        else:
            term_pluralised = pluralizer.pluralize(self.genuine_term, 2, False).capitalize()

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

    def standardise_headings(self):
        self.message = re.sub(" +", " ", self.message)
        if self.term == "dungaree":
            a = 1
        # Go easy where the terms commodity, heading or subheading have been omitted
        self.message = re.sub("([^ye]) ([0-9]{10}[^0-9])", "\\1 commodity \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{8}[^0-9])", "\\1 subheading \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{6}[^0-9])", "\\1 subheading \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{4}[^0-9])", "\\1 heading \\2", self.message)
        self.message = re.sub("([^g]) ([0-9]{4}[^0-9])", "\\1 heading \\2", self.message)

        # Correct obvious misapplication of entity types
        self.message = re.sub(" heading ([0-9]{6}[^0-9])", " subheading \\1", self.message)
        self.message = re.sub(" heading ([0-9]{10})", " commodity \\1", self.message)
        self.message = re.sub(" headings ([0-9]{4}),", " heading \\1,", self.message)

    def final_message_tidy(self):
        self.message = self.message.replace("..", ".")
        self.message = self.message.replace("/", " / ")
        self.message = self.message.replace("to heading", "under heading")
        self.message = self.message.replace("to subheading", "under subheading")
        self.message = self.message.replace("to commodity", "under commodity")
        self.message = re.sub("\s+", " ", self.message)

    def correct_typos(self):
        self.correct_would_depend()
        with open(self.typos_file_path, 'r') as file:
            reader = csv.reader(file, quotechar='"')
            for row in reader:
                term_from = row[0]
                term_to = row[1]
                self.message = self.message.replace(term_from, term_to)

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
