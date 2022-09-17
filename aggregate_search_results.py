"""
Test searching torrents and aggregating them, using the PTN library.
"""
import sys
from dataclasses import dataclass

import requests
import urllib.parse

import PTN
from PyQt5 import uic
from PyQt5.QtWidgets import QMainWindow, QApplication, QTreeWidgetItem

from tribler_common.utilities import to_fts_query

import numpy as np
from sklearn.cluster import AffinityPropagation
import distance

from mergedeep import merge

API_PORT = 52194
API_KEY = "e24a1283634ad97290a1ac4a361e3c04"
BATCH_SIZE = 50


def merge_dicts(dict1, dict2):
    for k in set(dict1.keys()).union(dict2.keys()):
        if k in dict1 and k in dict2:
            if isinstance(dict1[k], dict) and isinstance(dict2[k], dict):
                yield (k, dict(merge_dicts(dict1[k], dict2[k])))
            else:
                # If one of the values is not a dict, you can't continue merging it.
                # Value from second dict overrides one in first and we move on.
                yield (k, dict2[k])
                # Alternatively, replace this with exception raiser to alert you of value conflicts
        elif k in dict1:
            yield (k, dict1[k])
        else:
            yield (k, dict2[k])


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.search_query = None
        self.titles = {}
        self.ordered_data = {}

        uic.loadUi('qt/aggregated_search.ui', self)

        self.search_button.clicked.connect(self.search_button_pressed)
        self.show()

    def search_button_pressed(self, event):
        self.search_query = self.search_input.text()
        self.ordered_data = {}

        current_item = 1
        skipped_items = []
        num_results = 0
        while True:
            try:
                response = requests.get(
                    "http://localhost:%d/search?txt_filter=%s&first=%d&last=%d" %
                    (API_PORT, urllib.parse.quote_plus(to_fts_query(self.search_query)), current_item,
                     current_item + BATCH_SIZE - 1),
                    headers={"X-Api-Key": API_KEY})
                results = response.json()
                num_results += len(results["results"])
                if len(results["results"]) == 0:
                    break
            except requests.exceptions.ConnectionError:
                self.num_search_results_label.setText("Error - Tribler core not running?")
                return

            print("Received %d search results" % len(results["results"]))
            self.num_search_results_label.setText("%d search results" % num_results)

            current_item += BATCH_SIZE

            for result in results["results"]:
                torrent_info = PTN.parse(result["name"])
                if not torrent_info["title"]:
                    skipped_items.append(result["name"])
                    continue  # Skip torrents of which we cannot determine the title

                title = torrent_info["title"].lower().title()
                if title not in self.ordered_data:
                    self.ordered_data[title] = {}

                # Sort based on season
                season = "Season %s" % torrent_info["season"] if "season" in torrent_info else "All Seasons"
                if season not in self.ordered_data[title]:
                    self.ordered_data[title][season] = {}

                # Sort based on episode
                episode = "Episode %s" % torrent_info["episode"] if "episode" in torrent_info else "All Episodes"
                if episode not in self.ordered_data[title][season]:
                    self.ordered_data[title][season][episode] = []

                self.ordered_data[title][season][episode].append(result["name"])

        # # Determine counts of top-level items
        # keys = list(self.ordered_data.keys())
        # item_counts = {}
        # for key in keys:
        #     item_counts[key] = self.count_torrents(self.ordered_data[key])
        #
        # # Cluster the first level based on similarity
        # words = list(self.ordered_data.keys())
        # words = np.asarray(words)
        # lev_similarity = -1 * np.array([
        #     [distance.levenshtein(w1, w2) for w1 in words]
        #     for w2 in words
        # ])
        #
        # affprop = AffinityPropagation(affinity="precomputed", damping=0.5)
        # affprop.fit(lev_similarity)
        # for cluster_id in np.unique(affprop.labels_):
        #     cluster = np.unique(words[np.nonzero(affprop.labels_ == cluster_id)])
        #
        #     # Find the item with the most results and merge the other items in the cluster into it
        #     representative = None
        #     representative_count = 0
        #     for item in cluster:
        #         if item_counts[item] > representative_count:
        #             representative = item
        #             representative_count = item_counts[item]
        #
        #     for item in cluster:
        #         if item != representative:
        #             # Merge
        #             print("Merging %s into %s" % (item, representative))
        #             self.ordered_data[representative] = merge(self.ordered_data[representative], self.ordered_data[item])
        #             self.ordered_data.pop(item)

        # Add it to the widget view
        self.fill_widget(self.search_results_tree, self.ordered_data)

    def print_results(self):
        print("--- Search results for %s ---" % self.search_query)

        for title in self.ordered_data.keys():
            print(title)
            for season in self.ordered_data[title].keys():
                print("  Season %s" % season)
                for episode in self.ordered_data[title][season]:
                    print("    Episode %s" % episode)
                    for torrent in self.ordered_data[title][season][episode]:
                        print("      %s" % torrent)

    def count_torrents(self, item):
        if type(item) is str:
            return 1
        elif type(item) is list:
            return sum([self.count_torrents(subitem) for subitem in item])
        elif type(item) is dict:
            return sum([self.count_torrents(subitem) for subitem in item.values()])

    def fill_item(self, item, value):
        if type(value) is dict:
            # For each key, determine the number of sub-items
            keys = list(value.keys())
            item_counts = {}
            for key in keys:
                item_counts[key] = self.count_torrents(value[key])

            keys.sort(key=lambda k: item_counts[k], reverse=True)

            for key in keys:
                val = value[key]
                child = QTreeWidgetItem()
                child.setText(0, key)
                child.setText(1, "%d item(s)" % item_counts[key])
                item.addChild(child)
                self.fill_item(child, val)
        elif type(value) is list:
            for val in value:
                child = QTreeWidgetItem()
                item.addChild(child)
                if type(val) is dict:
                    child.setText(0, '[dict]')
                    self.fill_item(child, val)
                elif type(val) is list:
                    child.setText(0, '[list]')
                    self.fill_item(child, val)
                else:
                    child.setText(0, str(val))
                child.setExpanded(True)
        else:
            child = QTreeWidgetItem()
            child.setText(0, str(value))
            item.addChild(child)

    def fill_widget(self, widget, value):
        widget.clear()
        self.fill_item(widget.invisibleRootItem(), value)


app = QApplication(sys.argv)
window = MainWindow()
app.exec_()
