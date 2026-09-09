const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../research_avatar/paper_studio/static/app.js'), 'utf8');
function definition(name) {
  const start = source.indexOf(`function ${name}(`);
  assert.ok(start >= 0);
  return source.slice(start, source.indexOf('\n}\n', start) + 3);
}
const controls = new Map();
const control = id => {
  if (!controls.has(id)) controls.set(id, { disabled: false, value: '', textContent: '', title: '', classList: { remove() {} } });
  return controls.get(id);
};
const context = vm.createContext({
  state: { pdf: { exists: false }, title_editor: { current_title: 'QA title' } },
  titleBusy: false,
  renderTitleDraftInput: (input, _key, value) => { input.value = value; },
  $: control,
  document: { querySelectorAll: () => [control('dynamic-panel-generate')] },
});
const controlStart = source.indexOf('const DEMO_READ_ONLY_CONTROL_IDS = [');
vm.runInContext(source.slice(controlStart, source.indexOf('];', controlStart) + 2), context);
vm.runInContext(definition('applyDraftJobRestrictions') + definition('updateTitleSaveButton') + definition('renderTitleEditor'), context);
control('paper-title').value = 'QA title';
vm.runInContext('updateTitleSaveButton()', context);
assert.equal(control('title-save').textContent, 'Current title');
context.state.pdf.exists = true;
vm.runInContext('updateTitleSaveButton()', context);
assert.equal(control('title-save').textContent, 'Written to PDF');
control('paper-title').value = 'Revised QA title';
vm.runInContext('updateTitleSaveButton()', context);
assert.equal(control('title-save').disabled, false);
assert.equal(control('title-save').textContent, 'Confirm writing to LaTeX');
for (const jobType of ['full_draft', 'section_draft']) {
  context.state = { [jobType]: { job: { status: 'running' } } };
  for (const item of controls.values()) item.disabled = false;
  vm.runInContext('applyDraftJobRestrictions()', context);
  for (const id of ['reset-generated', 'generate', 'accept', 'full-draft-start', 'section-draft-start', 'figure-draw', 'table-agent-edit', 'dynamic-panel-generate']) {
    assert.equal(control(id).disabled, true, `${jobType} must lock ${id}`);
  }
  assert.equal(control('full-draft-cancel').disabled, false);
  assert.equal(control('figures-view').disabled, false);
  assert.equal(control('project-export').disabled, false);
  // A preview callback may calculate that an action is ready; the job lock
  // must win again when that callback reapplies the restrictions.
  control('figure-draw').disabled = false;
  vm.runInContext('applyDraftJobRestrictions()', context);
  assert.equal(control('figure-draw').disabled, true);
}
context.state = { full_draft: { job: { status: 'completed' } } };
control('generate').disabled = false;
vm.runInContext('applyDraftJobRestrictions()', context);
assert.equal(control('generate').disabled, false);

context.state = { pdf: { exists: true }, title_editor: { current_title: 'QA title' } };
control('paper-title').disabled = true;
control('title-gpt-prompt').disabled = true;
vm.runInContext('renderTitleEditor()', context);
assert.equal(control('paper-title').disabled, false);
assert.equal(control('title-gpt-prompt').disabled, false);
context.titleBusy = true;
vm.runInContext('renderTitleEditor()', context);
assert.equal(control('paper-title').disabled, true);
assert.equal(control('title-gpt-prompt').disabled, true);
console.log('Paper Studio UI state regressions passed');

// Untrusted section titles must stay text; parsing them as HTML is a regression.
const titlePayload = '<img src=x onerror="document.title=\'QA-XSS-MARKER\'">';
const sectionChildren = [];
const sectionsRoot = { set innerHTML(value) { assert.equal(value, ''); }, appendChild(child) { sectionChildren.push(child); } };
const sectionContext = vm.createContext({
  state: { sections: { qa: { title: titlePayload } } }, activeSection: 'qa', activeView: 'writing',
  $: () => sectionsRoot,
  document: { createElement(tag) { return { tag, children: [], appendChild(child) { this.children.push(child); }, set innerHTML(_value) { throw new Error('Section content must not be parsed as HTML'); } }; } },
});
vm.runInContext(definition('renderSections') + '\nrenderSections()', sectionContext);
assert.equal(sectionChildren[0].textContent, titlePayload);
assert.equal(sectionChildren[0].children[0].tag, 'span');
