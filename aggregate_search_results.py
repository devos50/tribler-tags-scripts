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

API_PORT = 52194
API_KEY = "e24a1283634ad97290a1ac4a361e3c04"
BATCH_SIZE = 50


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.search_query = None
        self.titles = {}
        self.ordered_data = {}

        uic.loadUi('qt/aggregated_search.ui', self) # Load the .ui file

        self.search_button.clicked.connect(self.search_button_pressed)
        self.show()

    def search_button_pressed(self, event):
        self.search_query = self.search_input.text()
        self.ordered_data = {}

        current_item = 1
        skipped_items = []
        has_results = True
        while has_results:
            response = requests.get(
                "http://localhost:%d/search?txt_filter=%s&first=%d&last=%d" % (
                API_PORT, urllib.parse.quote_plus(to_fts_query(self.search_query)), current_item,
                current_item + BATCH_SIZE - 1),
                headers={"X-Api-Key": API_KEY})
            results = response.json()
            if len(results["results"]) == 0:
                has_results = False
                break

            print("Received %d search results" % len(results["results"]))

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

    def fill_item(self, item, value):
        if type(value) is dict:
            for key, val in sorted(value.items()):
                child = QTreeWidgetItem()
                child.setText(0, key)
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
                    child.setText(0, val)
                child.setExpanded(True)
        else:
            child = QTreeWidgetItem()
            child.setText(0, value)
            item.addChild(child)

    def fill_widget(self, widget, value):
        widget.clear()
        self.fill_item(widget.invisibleRootItem(), value)


app = QApplication(sys.argv)
window = MainWindow()
app.exec_()
