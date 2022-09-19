erroneous_digits = []
incorrect_commodities = []
useless_messages = []
commodities = []
commodities_dict = {}
country_failures = []
typos = []


def decapitalise(s):
    return s[:1].lower() + s[1:] if s else ''
