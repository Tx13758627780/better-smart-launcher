import java.lang.reflect.Field;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.atomic.AtomicReference;

public final class PinyinTest {
    private static int checks;
    private static void check(boolean condition, String message) {
        checks++;
        if (!condition) throw new AssertionError(message);
    }
    private static void matches(String label, String query) {
        check(LocalPinyin.pinyinScore(label, query) > 0, label + " should match " + query);
    }
    private static void misses(String label, String query) {
        check(LocalPinyin.pinyinScore(label, query) == -1, label + " should not match " + query);
    }
    public static void main(String[] args) throws Exception {
        // Full pinyin, any incomplete prefix, initials, case and spaces.
        for (String query : new String[] {"w", "we", "wei", "weix", "weixi", "weixin", "WEIXIN", "wx", " w x "})
            matches("微信", query);
        matches("微信", "x"); matches("微信", "xi"); matches("微信", "xin");
        for (String query : new String[] {"y", "yu", "yuan", "yuanb", "yuanba", "yuanbao", "yb", " Y B "})
            matches("元宝", query);
        matches("元宝", "bao");
        matches("腾讯元宝", "tengxun"); matches("腾讯元宝", "tengxunyuanbao");
        matches("腾讯元宝", "yuanbao"); matches("腾讯元宝", "tx"); matches("腾讯元宝", "txyb");
        matches("支付宝", "zhi"); matches("支付宝", "zhif"); matches("支付宝", "zhifubao"); matches("支付宝", "zfb");
        matches("阿里云", "aliyun"); matches("阿里云", "aly");
        matches("QQ音乐", "qqyinyue"); matches("QQ音乐", "qqyy");
        matches("网易云音乐", "wangyiyunyinyue"); matches("网易云音乐", "wyyyy");
        matches("中国银行", "zhongguoyinhang"); matches("中国银行", "zgyh");
        matches("重庆银行", "chongqingyinhang"); matches("重庆银行", "cqyh");
        matches("重慶銀行", "chongqingyinhang"); matches("重慶銀行", "cqyh");
        matches("長安", "changan"); matches("長安", "ca");
        matches("哔哩哔哩", "bilibili"); matches("哔哩哔哩", "blbl");
        matches("元-宝 AI", "yuanbaoai"); matches("元-宝 AI", "ybai");
        matches("12306铁路", "12306tielu"); matches("12306铁路", "12306tl");
        matches("铁路12306", "tielu12306"); matches("铁路12306", "tl12306");
        matches("🌟元宝", "yuanbao"); matches("🌟元宝", "yb");

        misses("微信", "wex"); misses("微信", "weixn"); misses("微信", "xy");
        misses("元宝", "wx"); misses("元支付宝", "yb"); misses("元宝", "ybb");
        misses("Calendar", "c"); misses("元宝", ""); misses("元宝", "   ");
        misses("元宝", "元"); misses("元Ω宝", "yuanbao");
        misses(null, "yb"); misses("元宝", null);

        check(LocalPinyin.pinyinScore("微信", "weixin") > LocalPinyin.pinyinScore("微信助手", "weixin"), "full exact before prefix");
        check(LocalPinyin.pinyinScore("元宝", "yb") > LocalPinyin.pinyinScore("元宝助手", "yb"), "initial exact before prefix");
        check(LocalPinyin.pinyinScore("元宝助手", "yb") > LocalPinyin.pinyinScore("腾讯元宝", "yb"), "prefix before embedded");
        pl7 matcher = new pl7();
        check(LocalPinyin.score(matcher, "微信", "weixin", null) == 960, "new full-pinyin result");
        check(LocalPinyin.score(matcher, "微信", "wx", null) == 950, "new initials result");
        matcher.result = 1004;
        check(LocalPinyin.score(matcher, "微信", "weixin", null) == 1004, "original score preserved");
        matcher.result = 137;
        check(LocalPinyin.score(matcher, "元宝", "元", null) == 137, "Chinese query unchanged");
        check(LocalPinyin.score(matcher, "Calendar", "calendar", null) == 137, "Latin query unchanged");
        matcher.result = -1;
        check(LocalPinyin.score(matcher, "My App", "yuanbao", "元宝") == 960, "alias support");
        check(matcher.calls == 6, "original matcher always called once");

        final AtomicReference<Throwable> failure = new AtomicReference<>();
        final CountDownLatch finished = new CountDownLatch(4);
        long begin = System.nanoTime();
        for (int t = 0; t < 4; t++) {
            final int id = t;
            new Thread(() -> {
                try {
                    for (int i = 0; i < 20000; i++) {
                        String query = (i & 1) == 0 ? "txyb" : "tengxunyuanb";
                        if (LocalPinyin.pinyinScore("腾讯元宝" + ((i + id) % 500), query) <= 0)
                            throw new AssertionError("Concurrent matching: " + query);
                    }
                } catch (Throwable e) { failure.compareAndSet(null, e); }
                finally { finished.countDown(); }
            }).start();
        }
        finished.await();
        check(failure.get() == null, "concurrent stress: " + failure.get());
        double elapsedMs = (System.nanoTime() - begin) / 1e6;
        for (int i = 0; i < 3000; i++) LocalPinyin.pinyinScore("元宝" + i, "yuanb");
        Field cacheField = LocalPinyin.class.getDeclaredField("CACHE");
        cacheField.setAccessible(true);
        Map<?, ?> cache = (Map<?, ?>) cacheField.get(null);
        check(cache.size() <= 1024, "bounded cache");
        System.out.println("PASS: " + checks + " assertions; 80000 concurrent lookups in " + elapsedMs + " ms; cache=" + cache.size());
    }
}

