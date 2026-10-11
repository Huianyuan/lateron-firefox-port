const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.resolve(__dirname, "..", "url-utils.js"), "utf8");
const context = vm.createContext({ URL, globalThis: {} });
vm.runInContext(source, context, { filename: "url-utils.js" });
const normalize = context.globalThis.LaterOnUrl.normalize;

assert.strictEqual(
  normalize("https://www.Example.com/article/?utm_source=news&b=2&a=1#comments"),
  "https://example.com/article?a=1&b=2"
);
assert.strictEqual(
  normalize("https://example.com/article?a=1&b=2"),
  normalize("https://www.example.com/article/?b=2&a=1")
);

const video = "ss-ufzKALnI";
const expectedVideo = `https://youtube.com/watch?v=${video}`;
for (const url of [
  `https://www.youtube.com/watch?v=${video}&list=WL&index=23&t=15s`,
  `https://youtube.com/watch?list=PLabc&v=${video}&start=100&feature=share`,
  `https://youtu.be/${video}?si=share-code&t=30`,
  `https://m.youtube.com/watch?v=${video}`,
  `https://music.youtube.com/watch?v=${video}`,
  `https://www.youtube.com/shorts/${video}?feature=share`,
  `https://www.youtube.com/embed/${video}?start=30`,
  `https://www.youtube.com/live/${video}?si=share-code`
]) assert.strictEqual(normalize(url), expectedVideo, url);
assert.notStrictEqual(normalize(`https://youtube.com/watch?v=${video}`), normalize("https://youtube.com/watch?v=SS-ufzKALnI"), "视频 ID 大小写必须保留");
assert.notStrictEqual(normalize("https://youtube.com/playlist?list=PLone"), normalize("https://youtube.com/playlist?list=PLtwo"), "独立播放列表不能合并");
assert.notStrictEqual(normalize(`https://example.com/watch?v=${video}&t=15`), normalize(`https://example.com/watch?v=${video}`), "其他网站保留业务参数");
assert.notStrictEqual(normalize(`https://youtube.com.evil.test/watch?v=${video}`), expectedVideo, "仅匹配确切 YouTube 域名");

console.log("PASS shared URL normalization including YouTube video identity");
