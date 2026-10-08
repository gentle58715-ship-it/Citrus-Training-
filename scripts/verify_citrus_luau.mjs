// Compile and execute only the explicitly authored pure-Luau test examples.
// This is NOT a Roblox Studio test or a Luau static typecheck.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {pathToFileURL,fileURLToPath} from 'node:url';
const runtime=process.argv[2];
if(!runtime) throw new Error('Pass the absolute path to luau-web/src/index.js');
const {LuauState}=await import(pathToFileURL(path.resolve(runtime)).href);
if(process.argv.includes('--child')){
 const state=await LuauState.createAsync();
 try{await state.loadstring(fs.readFileSync(0,'utf8'),'isolated_test',true)();}
 finally{state.destroy();}
 process.stdout.write('PURE_LUAU_PASS\n');
 process.exit(0);
}
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../datasets/v4');
const dataPath=path.join(root,'candidates/authored_0001.jsonl');
const rows=fs.readFileSync(dataPath,'utf8').trim().split('\n').map(JSON.parse);
const results=[];
for(const row of rows){
 if(row.subtype!=='pure_luau') continue;
 const code=[...row.messages.at(-1).content.matchAll(/```luau\n([\s\S]*?)```/g)].map(m=>m[1]).join('\n');
 if(!code||!code.includes('assert(')) throw new Error('Missing executable assertions: '+row.id);
 if(/\b(game|workspace|Instance)\b/.test(code)) throw new Error('Not pure Luau: '+row.id);
 // Each VM gets a fresh process: no cross-record globals or FFI lifetime state.
 const executed=spawnSync(process.execPath,[fileURLToPath(import.meta.url),runtime,'--child'],
  {input:code,encoding:'utf8',timeout:10000,maxBuffer:1000000});
 if(executed.status!==0||!executed.stdout.includes('PURE_LUAU_PASS'))
  throw new Error(row.id+': '+(executed.error||executed.stderr));
 const evidence={environment:'luau-web 1.5.0 / Luau WASM',scope:'pure_luau_assertions',
  code_sha256:crypto.createHash('sha256').update(code).digest('hex'),passed:true,roblox_studio:false,typechecked:false};
 row.runtime_verified=true;
 row.evidence.runtime={report:'reports/pure_luau.json',case_id:row.id,...evidence};
 results.push({id:row.id,...evidence});
}
if(results.length!==5) throw new Error('Expected five independently authored pure-Luau test records');
fs.writeFileSync(dataPath,rows.map(r=>JSON.stringify(r)).join('\n')+'\n');
fs.mkdirSync(path.join(root,'reports'),{recursive:true});
fs.writeFileSync(path.join(root,'reports/pure_luau.json'),JSON.stringify({records_tested:results.length,all_passed:true,
 runtime:'luau-web 1.5.0',roblox_studio_executed:false,static_typechecking_performed:false,cases:results},null,2)+'\n');
console.log(JSON.stringify({pure_luau_records_passed:results.length,roblox_studio_executed:false}));
