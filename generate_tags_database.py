"""
This script takes a Tribler database as inputs, and ouputs a list of IMDB titles.
"""
import os
from binascii import hexlify, unhexlify
from pathlib import Path

import PTN

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.keyvault.private.libnaclkey import LibNaCLSK
from ipv8.messaging.serialization import default_serializer

from pony.orm import db_session

from tribler_core.components.metadata_store.db.store import MetadataStore
from tribler_core.components.tag.community.tag_payload import TagOperation
from tribler_core.components.tag.db.tag_db import TagDatabase, TagOperationEnum

METADATA_DB_PATH = Path("/Users/martijndevos/.Tribler/7.10/sqlite/metadata.db")
TAGS_DB_PATH = Path("./data/tags.db").absolute()
BATCH_SIZE = 100
MAX_TAGS_PER_INFOHASH = 10
NUM_KEYPAIRS = 1000

title_to_imdb_id_map = {}
imdb_keywords = {}
keypairs = []
current_key_ind = 0

if os.path.exists("data/keypairs.txt"):
    print("Loading existing keypairs...")
    with open("data/keypairs.txt") as keys_file:
        for line in keys_file.readlines():
            keypair = LibNaCLSK(unhexlify(line.strip()))
            keypairs.append(keypair)
else:
    print("Generating keypairs...")
    with open("data/keypairs.txt", "w") as keys_file:
        for _ in range(NUM_KEYPAIRS):
            keypair = default_eccrypto.generate_key("curve25519")
            keypairs.append(keypair)
            keys_file.write("%s\n" % hexlify(keypair.key_to_bin()).decode())

print("Loading IMDB keywords...")
with open("data/imdb_keywords.csv") as imdb_keywords_file:
    parsed_lines = 0
    for line in imdb_keywords_file.readlines():
        if parsed_lines % 1000000 == 0:
            print("Parsed %d lines with IMDB keywords" % parsed_lines)

        parts = line.strip().split(",")
        imdb_id = parts[0]
        if imdb_id not in imdb_keywords:
            imdb_keywords[imdb_id] = []
        elif len(imdb_keywords[imdb_id]) >= MAX_TAGS_PER_INFOHASH:
            parsed_lines += 1
            continue  # Do not add more tags

        imdb_keywords[imdb_id].append(parts[1].replace(' ', '-'))
        parsed_lines += 1

print("Loading checkpoint...")
current_id = 0
if not os.path.exists("data/current_rowid.txt"):
    with open("data/current_rowid.txt", "w") as out_file:
        out_file.write("0")
else:
    with open("data/current_rowid.txt", "r") as in_file:
        current_id = int(in_file.read().strip())

print("Current ID: %d" % current_id)

print("Loading IMDB titles...")
parsed_header = False
with open("data/imdb_titles.tsv") as imdb_titles_file:
    lines_read = 0
    for line in imdb_titles_file.readlines():
        if not parsed_header:
            parsed_header = True
            continue

        lines_read += 1
        if lines_read % 1000000 == 0:
            print("Parsed %d lines with IMDB titles" % lines_read)

        parts = line.split("\t")
        imdb_id = parts[0]
        primary_title = parts[2].lower().replace('é', 'e')
        original_title = parts[3].lower().replace('é', 'e')

        if primary_title not in title_to_imdb_id_map:
            title_to_imdb_id_map[primary_title] = imdb_id
        if original_title not in title_to_imdb_id_map:
            title_to_imdb_id_map[original_title] = imdb_id

print("Loading IMDB titles done, found %d mappings" % len(title_to_imdb_id_map.keys()))

print("Opening databases...")
key = default_eccrypto.generate_key("curve25519")
mds = MetadataStore(METADATA_DB_PATH, None, key)
tags_db = TagDatabase(str(TAGS_DB_PATH))

while True:
    if current_id % 1000 == 0:
        print("Parsed %d rows..." % current_id)

    with db_session:
        torrents = mds.TorrentMetadata.select(lambda g: g.metadata_type == 300).limit(BATCH_SIZE, offset=current_id)
        if not torrents:
            break

        for torrent in torrents:
            parsed_title = PTN.parse(torrent.title)["title"].lower().replace("é", "e")

            if parsed_title:
                if parsed_title in title_to_imdb_id_map:
                    if title_to_imdb_id_map[parsed_title] in imdb_keywords:
                        keywords_for_title = imdb_keywords[title_to_imdb_id_map[parsed_title]]
                        if len(keywords_for_title) > 0:
                            # Check if we already added tags for this particular infohash
                            existing_tags = tags_db.get_tags(torrent.infohash)
                            if existing_tags:
                                continue

                            # Add tags as operations to the database
                            for keyword in keywords_for_title:
                                current_key = keypairs[current_key_ind]
                                current_key_ind = (current_key_ind + 1) % 1000
                                operation = TagOperation(infohash=torrent.infohash, operation=TagOperationEnum.ADD, clock=0,
                                                         creator_public_key=current_key.pub().key_to_bin(), tag=keyword)
                                operation.clock = tags_db.get_clock(operation) + 1

                                # Sign
                                packed = default_serializer.pack_serializable(operation)
                                signature = default_eccrypto.create_signature(current_key, packed)

                                # Add to db
                                tags_db.add_tag_operation(operation, signature, is_local_peer=True)

    current_id += BATCH_SIZE
    with open("data/current_rowid.txt", "w") as counter_file:
        counter_file.write("%d" % current_id)
