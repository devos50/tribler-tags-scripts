"""
Test the PTN library on a Tribler metadata database.
"""
from pathlib import Path

import PTN

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.components.metadata_store.db.store import MetadataStore

BATCH_SIZE = 100
METADATA_DB_PATH = Path("/Users/martijndevos/.Tribler/7.10/sqlite/metadata.db")

print("Opening databases...")
key = default_eccrypto.generate_key("curve25519")
mds = MetadataStore(METADATA_DB_PATH, None, key)

titles = set()
start_id = 120000
current_id = start_id
success = 0
failure = 0

while True:
    if current_id % 1000 == 0:
        success_ratio = success / (success + failure) * 100 if success > 0 else 0
        print("Parsed %d rows... (success: %d, failure: %d - %.2f)" % (current_id, success, failure, success_ratio))

    if current_id == start_id + 10000:
        break

    with db_session:
        torrents = mds.TorrentMetadata.select(lambda g: g.metadata_type == 300).limit(BATCH_SIZE, offset=current_id)
        if not torrents:
            break

        with open("data/failed_titles.txt", "a") as failed_file:
            for torrent in torrents:
                torrent_info = PTN.parse(torrent.title)
                parsed_title = torrent_info["title"]
                if not parsed_title:
                    failure += 1
                    failed_file.write("%s\n" % torrent.title)
                else:
                    print(torrent.title)
                    print(torrent_info)
                    titles.add(parsed_title)
                    success += 1

        current_id += BATCH_SIZE

for title in titles:
    print(title)
