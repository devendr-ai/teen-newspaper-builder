const assert = require('node:assert/strict');
const vm = require('node:vm');
let source = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => source += chunk);
process.stdin.on('end', () => {
  const events = {}, utterances = [], audios = [];
  const words = Array.from({length: 3}, (_, index) => ({
    textContent: ['Original headline.', 'Easier headline.', 'Body.'][index],
    hidden: index === 1, marked: false,
    closest() { return this.hidden ? {} : null; },
    classList: { add() { words[index].marked = true; }, remove() { words[index].marked = false; } },
    scrollIntoView() {}
  }));
  const easy = { on: false, getAttribute() { return String(this.on); } };
  const button = { attrs: {}, lastChild: {}, setAttribute(k,v) { this.attrs[k] = v; }, addEventListener() {}, closest() { return card; }, insertAdjacentHTML() {} };
  const card = {};
  const recordings = { '0': {
    original: {src: 'original.mp3', segments: [{index:0,start:0,end:1},{index:2,start:1,end:2}]},
    easy: {src: 'easy.mp3', segments: [{index:1,start:0,end:1},{index:2,start:1,end:2}]}
  }};
  class Audio {
    constructor() { audios.push(this); this.currentTime = 0; }
    play() { return Promise.resolve(); }
    pause() { this.paused = true; }
    load() {}
    removeAttribute() {}
  }
  const speech = { getVoices: () => [], cancel() {}, speak(u) { utterances.push(u); } };
  const ctx = { assert, Audio, speech, utterances, audios, card, button, easy, words, events,
    SpeechSynthesisUtterance: function(text) { this.text = text; },
    window: {speechSynthesis:speech, addEventListener() {}}, navigator: {},
    document: { addEventListener(k,fn) { events[k] = fn; } },
    store: { get: (k,d) => k === 'rate' ? 1.2 : d, set() {} }, award() {}, calm: () => true,
    $: (selector) => selector === '#narration' ? {textContent:JSON.stringify(recordings)} : selector === '.easy' ? easy : null,
    $$: (selector) => selector === '.card' ? [card] : selector === '.s' ? words :
      selector === '.s.now' ? words.filter(w => w.marked) : selector === '.read' || selector.startsWith('.read[') ? [button] : []
  };
  const block = source.slice(source.indexOf('  // ---------------------------------------------------------------- read aloud'), source.indexOf('  const main = $(".issue");'));
  assert(block.includes('narrationAudio'));
  vm.runInNewContext(block + `
    readCard(card, button);
    assert.equal(audios[0].src, 'original.mp3');
    assert.equal(audios[0].playbackRate, 1.2);
    audios[0].currentTime = 1.5; audios[0].ontimeupdate();
    assert.equal(words[2].marked, true);
    const stale = audios[0].onended;
    readCard(card, button); // second tap stops
    assert.equal(audios[0].paused, true);
    assert.equal(reading, null);
    easy.on = true; words[0].hidden = true; words[1].hidden = false;
    readCard(card, button);
    assert.equal(audios[1].src, 'easy.mp3');
    stale(); // cancelled playback must not stop the new track
    assert.equal(reading, card);
    audios[1].onerror(); // unavailable/offline recording falls back to the visible version
    assert.equal(utterances[0].text, 'Easier headline.');
    const cancelledSpeech = utterances[0].onend;
    stop(); readCard(card, button);
    cancelledSpeech();
    assert.equal(utterances.length, 1);
    stop(); window.speechSynthesis = null;
  `, ctx);
  // Audio remains available when browser speech synthesis is absent.
  delete ctx.window.speechSynthesis;
  vm.runInNewContext(block + '\nreadCard(card, button); assert.equal(audios.at(-1).src, "easy.mp3");', {...ctx});
  console.log('Narration player: versions, highlighting, speed, stop, fallback, and cancellation passed');
});
