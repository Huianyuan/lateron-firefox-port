const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "..", "sidepanel.js"), "utf8");
const start = source.indexOf("function ensureActiveProjectVisible() {");
const end = source.indexOf("function normalizeProject", start);
let buttonLeft = 600;
const container = {
  clientWidth: 320,
  scrollWidth: 1200,
  scrollLeft: 0,
  getBoundingClientRect: () => ({ left: 100 }),
  querySelector: () => ({
    getBoundingClientRect: () => ({ left: 100 + buttonLeft - container.scrollLeft, right: 200 + buttonLeft - container.scrollLeft })
  })
};
const context = vm.createContext({ document: { querySelector: () => container } });
vm.runInContext(source.slice(start, end), context);
const reveal = () => vm.runInContext("ensureActiveProjectVisible()", context);

reveal();
assert.strictEqual(container.scrollLeft, 388, "右侧屏外的当前项目应完整进入可视范围");
reveal();
assert.strictEqual(container.scrollLeft, 388, "已经完整可见时不重复滚动");
buttonLeft = 50;
reveal();
assert.strictEqual(container.scrollLeft, 42, "切回左侧项目应向左定位");
buttonLeft = 0;
reveal();
assert.strictEqual(container.scrollLeft, 0, "等待整理位于最左侧，滚动不能越界");
container.clientWidth = 0;
reveal();
assert.strictEqual(container.scrollLeft, 0, "尚未布局时不滚动");
console.log("PASS 侧栏当前项目左右定位、可见时保持位置及边界处理");
