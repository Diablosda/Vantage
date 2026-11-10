import test from 'node:test';import assert from 'node:assert/strict';import {options} from '../web/ui_options.js';
test('object and camera selectors render their selected option safely',()=>{const result=options({ACTOR:'人物',PROP:'物品','x"':'<标签>'},'PROP');assert.match(result,/value="PROP" selected>物品/);assert.match(result,/value="x&amp;quot;"|value="x&quot;"/);assert.match(result,/&lt;标签&gt;/);});
