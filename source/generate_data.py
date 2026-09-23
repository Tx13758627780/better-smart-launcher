"""Compile public pinyin data into an offline multi-reading table."""
import base64
import gzip
import hashlib
import json
import struct
import unicodedata
from pathlib import Path

root = Path(__file__).resolve().parent
source = (root / 'pinyin_dict.json').read_bytes()
dictionary = json.loads(source)
entries = []
for key, raw_readings in dictionary.items():
    codepoint = int(key)
    if not (codepoint == 0x3007 or 0x3400 <= codepoint <= 0x9fff or 0xf900 <= codepoint <= 0xfaff or 0x20000 <= codepoint <= 0x3347f):
        continue
    readings = set()
    for raw in raw_readings.split(','):
        normalized = unicodedata.normalize('NFD', raw.lower().replace('ü', 'u'))
        spelling = ''.join(c for c in normalized if 'a' <= c <= 'z')
        if spelling:
            readings.add(spelling)
    if readings:
        entries.append((codepoint, sorted(readings)))
entries.sort()

payload = bytearray()
offsets = []
for codepoint, readings in entries:
    offsets.append((codepoint, len(payload)))
    if len(readings) > 255:
        raise ValueError('Too many readings')
    payload.append(len(readings))
    for reading in readings:
        encoded_reading = reading.encode('ascii')
        if len(encoded_reading) > 255:
            raise ValueError('Reading too long')
        payload.append(len(encoded_reading))
        payload.extend(encoded_reading)
binary = struct.pack('>II', len(entries), len(payload))
binary += b''.join(struct.pack('>II', codepoint, offset) for codepoint, offset in offsets)
binary += payload
encoded = base64.b64encode(gzip.compress(binary, mtime=0)).decode('ascii')
chunks = [encoded[i:i + 30000] for i in range(0, len(encoded), 30000)]

code = '''// Generated from python-pinyin data. See bundled MIT license.
import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.zip.GZIPInputStream;

final class LocalPinyinData {
    private static final Table TABLE = read();
    static String[] readings(int cp) {
        int low = 0, high = TABLE.codepoints.length - 1;
        while (low <= high) {
            int mid = (low + high) >>> 1;
            int found = TABLE.codepoints[mid];
            if (found < cp) low = mid + 1;
            else if (found > cp) high = mid - 1;
            else return decode(TABLE.offsets[mid]);
        }
        return LocalPinyin.NO_READINGS;
    }
    private static String[] decode(int offset) {
        byte[] data = TABLE.payload;
        int count = data[offset++] & 255;
        String[] result = new String[count];
        for (int i = 0; i < count; i++) {
            int size = data[offset++] & 255;
            result[i] = new String(data, offset, size, StandardCharsets.US_ASCII);
            offset += size;
        }
        return result;
    }
    private static Table read() {
        StringBuilder text = new StringBuilder();
'''
code += ''.join('        text.append("' + chunk + '");\n' for chunk in chunks)
code += '''        try (DataInputStream in = new DataInputStream(new GZIPInputStream(
                new ByteArrayInputStream(Base64.getDecoder().decode(text.toString()))))) {
            int count = in.readInt(), payloadSize = in.readInt();
            if (count <= 0 || count > 100000 || payloadSize <= 0 || payloadSize > 4000000)
                throw new IOException("Invalid pinyin table");
            int[] codepoints = new int[count], offsets = new int[count];
            int previous = -1, previousOffset = -1;
            for (int i = 0; i < count; i++) {
                int cp = in.readInt(), offset = in.readInt();
                if (cp <= previous || cp > 0x10ffff || offset <= previousOffset || offset >= payloadSize)
                    throw new IOException("Invalid pinyin index");
                codepoints[i] = cp;
                offsets[i] = offset;
                previous = cp;
                previousOffset = offset;
            }
            byte[] payload = new byte[payloadSize];
            in.readFully(payload);
            if (in.read() != -1) throw new IOException("Trailing pinyin data");
            validatePayload(payload, offsets);
            return new Table(codepoints, offsets, payload);
        } catch (IOException | IllegalArgumentException e) {
            throw new IllegalStateException("Cannot read local pinyin data", e);
        }
    }
    private static void validatePayload(byte[] payload, int[] offsets) throws IOException {
        for (int offset : offsets) {
            if (offset >= payload.length) throw new IOException("Invalid entry offset");
            int count = payload[offset++] & 255;
            if (count == 0) throw new IOException("Empty pinyin entry");
            for (int i = 0; i < count; i++) {
                if (offset >= payload.length) throw new IOException("Truncated pinyin entry");
                int size = payload[offset++] & 255;
                if (size == 0 || offset + size > payload.length) throw new IOException("Invalid pinyin reading");
                for (int j = 0; j < size; j++) {
                    int c = payload[offset + j] & 255;
                    if (c < 'a' || c > 'z') throw new IOException("Invalid pinyin letter");
                }
                offset += size;
            }
        }
    }
    private static final class Table {
        final int[] codepoints, offsets;
        final byte[] payload;
        Table(int[] codepoints, int[] offsets, byte[] payload) {
            this.codepoints = codepoints;
            this.offsets = offsets;
            this.payload = payload;
        }
    }
}
'''
(root / 'LocalPinyinData.java').write_text(code, encoding='utf-8')
metadata = {
    'source': 'https://raw.githubusercontent.com/mozillazg/python-pinyin/master/pypinyin/pinyin_dict.json',
    'source_sha256': hashlib.sha256(source).hexdigest(),
    'mapped_characters': len(entries),
    'total_readings': sum(len(readings) for _, readings in entries),
    'uncompressed_bytes': len(binary),
    'base64_characters': len(encoded),
    'license': 'MIT',
}
(root / 'data-build.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata, indent=2))

