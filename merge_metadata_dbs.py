"""
Merge two metadata databases.
"""
from binascii import hexlify
from pathlib import Path

from ipv8.keyvault.crypto import default_eccrypto

from tribler_core.components.metadata_store.db.store import MetadataStore

from pony.orm import db_session

BATCH_SIZE = 500
existing_torrents = 0
new_torrents = 0
start_id = 0
current_id = start_id

print("Opening databases...")
key = default_eccrypto.generate_key("curve25519")
mds1 = MetadataStore(Path("./data/metadata.db").absolute(), None, key)
mds2 = MetadataStore(Path("./data/metadata_johan.db").absolute(), None, key, check_tables=False)

while True:
    print("Parsed %d rows (new torrents: %d)..." % (current_id, new_torrents))
    with db_session:
        torrents = mds2.TorrentMetadata.select(lambda g: g.metadata_type == 300).limit(BATCH_SIZE, offset=current_id)
        if not torrents:
            break
        for torrent in torrents:
            existing = mds1.TorrentMetadata.select(infohash=torrent.infohash)
            if not existing:
                metadata_dict = torrent.to_dict()
                metadata_dict.pop('rowid', None)
                metadata_dict.pop('health', None)
                mds1.TorrentMetadata.from_dict(metadata_dict)
                new_torrents += 1
            else:
                existing_torrents += 1

        current_id += BATCH_SIZE

print("Merge complete - existing torrents: %d, new torrents: %d" % (existing_torrents, new_torrents))
