import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/** Offline initials and full-pinyin support for local application-name searches. */
public final class LocalPinyin {
    private static final int MAX_LABEL = 256;
    private static final int MAX_QUERY = 64;
    private static final int MAX_CACHE = 1024;
    static final String[] NO_READINGS = new String[0];
    private static final NameForms NO_FORMS = new NameForms(new String[0][], new long[0], false);
    private static final Map<String, NameForms> CACHE = new LinkedHashMap<String, NameForms>(128, .75f, true) {
        @Override protected boolean removeEldestEntry(Map.Entry<String, NameForms> entry) {
            return size() > MAX_CACHE;
        }
    };

    private LocalPinyin() {}

    // pl7 is the original application's matcher. Its implementation is not replaced.
    public static int score(pl7 originalMatcher, String label, String query, String alias) {
        int original = originalMatcher.g(label, query, alias);
        try {
            return Math.max(original, Math.max(pinyinScore(label, query), pinyinScore(alias, query)));
        } catch (RuntimeException | LinkageError unavailable) {
            return original;
        }
    }

    static int pinyinScore(String label, String query) {
        if (label == null || query == null || label.isEmpty() || label.length() > MAX_LABEL
                || query.isEmpty() || query.length() > MAX_QUERY) return -1;
        String folded = foldQuery(query);
        if (folded == null || folded.isEmpty()) return -1;
        NameForms forms = forms(label);
        if (!forms.hasHan) return -1;
        return Math.max(initialScore(forms.initials, folded), fullScore(forms.tokens, folded));
    }

    private static int initialScore(long[] initials, String query) {
        int n = query.length();
        if (n > initials.length) return -1;
        for (int start = 0; start <= initials.length - n; start++) {
            boolean matches = true;
            for (int j = 0; j < n; j++) {
                if ((initials[start + j] & asciiMask(query.charAt(j))) == 0) {
                    matches = false;
                    break;
                }
            }
            if (matches) {
                if (start == 0 && n == initials.length) return 950;
                if (start == 0) return 940;
                return 900 - Math.min(start, 30) * 4;
            }
        }
        return -1;
    }

    private static int fullScore(String[][] tokens, String query) {
        for (int start = 0; start < tokens.length; start++) {
            int result = fullMatch(tokens, start, query);
            if (result == 2) return start == 0 ? 960 : 900 - Math.min(start, 30) * 4;
            if (result == 1) return start == 0 ? 930 : 880 - Math.min(start, 30) * 4;
        }
        return -1;
    }

    // 0=no match, 1=query is a prefix, 2=query exactly consumes all remaining tokens.
    private static int fullMatch(String[][] tokens, int start, String query) {
        boolean[] positions = new boolean[query.length() + 1];
        positions[0] = true;
        for (int token = start; token < tokens.length; token++) {
            String[] readings = tokens[token];
            if (readings.length == 0) return 0;
            boolean[] next = new boolean[positions.length];
            for (int pos = 0; pos < query.length(); pos++) {
                if (!positions[pos]) continue;
                int remaining = query.length() - pos;
                for (String reading : readings) {
                    int compare = Math.min(remaining, reading.length());
                    if (!query.regionMatches(pos, reading, 0, compare)) continue;
                    if (remaining <= reading.length())
                        return remaining == reading.length() && token == tokens.length - 1 ? 2 : 1;
                    next[pos + reading.length()] = true;
                }
            }
            positions = next;
        }
        return 0;
    }

    private static String foldQuery(String query) {
        StringBuilder folded = new StringBuilder(query.length());
        for (int i = 0; i < query.length(); i++) {
            char ch = query.charAt(i);
            if (ch >= 'A' && ch <= 'Z') ch = (char) (ch + 32);
            if (asciiMask(ch) != 0) folded.append(ch);
            else if (!Character.isWhitespace(ch)) return null;
        }
        return folded.toString();
    }

    private static long asciiMask(int ch) {
        if (ch >= 'a' && ch <= 'z') return 1L << (ch - 'a');
        if (ch >= '0' && ch <= '9') return 1L << (26 + ch - '0');
        return 0;
    }

    private static boolean isHan(int cp) {
        return cp == 0x3007 || cp >= 0x3400 && cp <= 0x9fff
                || cp >= 0xf900 && cp <= 0xfaff || cp >= 0x20000 && cp <= 0x3347f;
    }

    private static NameForms forms(String label) {
        synchronized (CACHE) {
            NameForms found = CACHE.get(label);
            if (found != null) return found;
        }
        int capacity = label.codePointCount(0, label.length());
        String[][] tokens = new String[capacity][];
        long[] initials = new long[capacity];
        int count = 0;
        boolean hasHan = false;
        for (int offset = 0; offset < label.length();) {
            int cp = label.codePointAt(offset);
            offset += Character.charCount(cp);
            if (cp >= 'A' && cp <= 'Z') cp += 32;
            long mask = asciiMask(cp);
            String[] readings;
            if (mask != 0) {
                readings = new String[] {new String(Character.toChars(cp))};
            } else if (isHan(cp)) {
                readings = LocalPinyinData.readings(cp);
                hasHan |= readings.length != 0;
                for (String reading : readings) mask |= asciiMask(reading.charAt(0));
            } else if (Character.isLetterOrDigit(cp)) {
                readings = NO_READINGS;
            } else {
                continue;
            }
            tokens[count] = readings;
            initials[count] = mask;
            count++;
        }
        NameForms result = hasHan ? new NameForms(Arrays.copyOf(tokens, count), Arrays.copyOf(initials, count), true) : NO_FORMS;
        synchronized (CACHE) { CACHE.put(label, result); }
        return result;
    }

    private static final class NameForms {
        final String[][] tokens;
        final long[] initials;
        final boolean hasHan;
        NameForms(String[][] tokens, long[] initials, boolean hasHan) {
            this.tokens = tokens;
            this.initials = initials;
            this.hasHan = hasHan;
        }
    }
}

