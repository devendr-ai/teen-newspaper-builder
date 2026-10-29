/* global __dirname */
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const ts=require('typescript');const path=require('node:path');
function load(file,imports){const module={exports:{}};const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/widgets',file),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;vm.runInNewContext(code,{module,exports:module.exports,require:n=>{if(n in imports)return imports[n];throw Error('Unexpected import '+n)},console,setTimeout,clearTimeout,AbortController,Date,Set,Promise,URL},{filename:file});return module.exports;}
const core=load('core.ts',{});
const row={edition:'breakfast-table',name:'The Breakfast Table',date:'2026-10-28',question:'If petrol costs more, what else might cost more too, and why?',reader:'play/breakfast-table/2026-10-28.html',brief:'play/briefs/2026-10-28.json'};
const feed={v:1,editions:[row]};
assert.equal(core.parseFeed(feed).editions[0].question,row.question);
for(const date of ['2026-02-30','yesterday','../../parents.html'])assert.equal(core.validDate(date),false);
for(const edition of ['../parents','https://bad','breakfast-table/..'])assert.equal(core.intent(edition,'2026-10-28'),null);
for(const bad of [{...row,reader:'parents.html'},{...row,brief:'https://bad/x.json'},{...row,question:'<script>What?</script>'}])assert.throws(()=>core.parseFeed({v:1,editions:[bad]}));
assert.throws(()=>core.parseFeed({v:1,editions:[row,row]}));
assert.match(core.propsFor(row).url,/newspebbles:\/\/\/widget\?edition=breakfast-table&issue=2026-10-28/);
assert.equal(core.audioPath({paper:row.edition,date:row.date,audio:'audio/abc123.mp3'},row.edition,row.date),'play/audio/abc123.mp3');
for(const audio of ['../audio/abc.mp3','https://bad/a.mp3','audio/../a.mp3'])assert.equal(core.audioPath({paper:row.edition,date:row.date,audio},row.edition,row.date),null);
assert.equal(core.audioPath({paper:'other',date:row.date,audio:'audio/a.mp3'},row.edition,row.date),null);

(async()=>{
 const files=new Map();const applications=[];let calls=0,registered=0,unregistered=0;
 class File{constructor(base,name){this.uri=name?base+'/'+name:base}get exists(){return files.has(this.uri)}create(){files.set(this.uri,'')}textSync(){if(!this.exists)throw Error('missing');return files.get(this.uri)}writeSync(s){files.set(this.uri,s)}}
 files.set('cache/widgets.json',JSON.stringify(feed));
 const imports={'expo':{isRunningInExpoGo:()=>false},'expo-file-system':{File,Paths:{document:'documents'}},'react-native':{Platform:{OS:'ios'}},'../content':{BASE:'https://newspebbles.com/app/',fileUri:r=>'cache/'+r},'./core':core,'./native':{apply:async p=>applications.push(p)},'expo-background-task':{registerTaskAsync:async()=>registered++,unregisterTaskAsync:async()=>unregistered++},'expo-task-manager':{isTaskRegisteredAsync:async()=>true}};
 const service=(()=>{const module={exports:{}};const code=ts.transpileModule(fs.readFileSync(path.join(__dirname,'../src/widgets/service.ts'),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;vm.runInNewContext(code,{module,exports:module.exports,require:n=>{if(n in imports)return imports[n];throw Error('Unexpected import '+n)},fetch:async(url,opts)=>{calls++;assert.equal(url,'https://newspebbles.com/app/widgets.json');assert.equal(opts.credentials,'omit');return {ok:true,text:async()=>JSON.stringify(feed)}},setTimeout,clearTimeout,AbortController,console,Date,Set,Promise});return module.exports;})();
 await service.refresh();assert.equal(calls,0,'No background request before parent opts in');
 await service.syncFromPack();assert.equal(service.currentProps().question,core.EMPTY.question);
 await assert.rejects(service.save(true,'unknown'));
 await service.save(true,row.edition);assert.equal(calls,1);assert.equal(registered,1);assert.equal(service.currentProps().question,row.question);
 await service.save(false,row.edition);assert.equal(unregistered,1);assert.equal(applications.at(-1).question,core.EMPTY.question);
 await service.refresh();assert.equal(calls,1,'Turning off stops question requests');
 // Expo Go must not load either native widget library at startup.
 load('background.ts',{'expo':{isRunningInExpoGo:()=>true},'react-native':{Platform:{OS:'ios'}}});
 load('background.ts',{'expo':{isRunningInExpoGo:()=>true},'react-native':{Platform:{OS:'android'}}});
 console.log('Widget tests passed: feed validation, exact routes, matching audio, parent opt-in/off, background requests and Expo Go safety.');
})().catch(e=>{console.error(e);process.exit(1)});
