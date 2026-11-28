"""Split a baked model .bin into <=14 MB pieces (name.bin, name.1.bin, ...) and record "chunks" in its json.
Run after baking: python3 tools/bake/split_bin.py www/models/butcher"""
import json, sys
LIM = 14 * 1024 * 1024
for base in sys.argv[1:]:
    data = open(base + '.bin', 'rb').read()
    n = (len(data) + LIM - 1) // LIM
    for i in range(n):
        open(base + ('.%d' % i if i else '') + '.bin', 'wb').write(data[i * LIM:(i + 1) * LIM])
    m = json.load(open(base + '.json')); m['chunks'] = n
    json.dump(m, open(base + '.json', 'w'), separators=(',', ':'))
    print(base, n)
