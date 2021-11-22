"""
Send out random queries to crawl content in the Tribler network.
"""
import time
import urllib.parse
import random

import requests

from tribler_common.utilities import to_fts_query

# Get random words
word_site = "https://www.mit.edu/~ecprice/wordlist.10000"

response = requests.get(word_site)
WORDS = response.content.splitlines()
print("Loaded %d words..." % len(WORDS))

API_PORT = 52194
API_KEY = "e24a1283634ad97290a1ac4a361e3c04"

while True:
    search_query = random.choice(WORDS).decode()
    print("Searching for %s" % search_query)
    response = requests.put(
            "http://localhost:%d/remote_query?txt_filter=%s&hide_xxx=0" % (API_PORT, urllib.parse.quote_plus(to_fts_query(search_query))),
            headers={"X-Api-Key": API_KEY})
    result = response.json()
    time.sleep(10)
