// Replay authored scenarios against the actual, isolated Citrus draft engine.
// Pass a bundled export of DraftTools/toolDefinitions from the inspected source.
// Private application source is not copied into this public training repository.
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';

const enginePath=process.argv[2];
if(!enginePath) throw new Error('Usage: node scripts/replay_citrus_v4.mjs /absolute/path/to/engine.mjs');
const {DraftTools,toolDefinitions}=await import(pathToFileURL(path.resolve(enginePath)).href);
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../datasets/v4');
const hash=value=>crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
const file=(source='local speed = 16\nprint(speed)',p='ServerScriptService/Movement',className='Script')=>({path:p,className,source});
const step=(name,args={},ok=true,error)=>({name,args,ok,error});
const panel={id:'Menu',name:'เมนู',nodes:[{id:'Panel',type:'Frame',size:[.8,0,.7,0],position:[.5,0,.5,0],anchor:[.5,.5]}]};
const crate={id:'Crate',name:'กล่อง',parts:[{id:'Body',shape:'box',size:[4,3,2]}]};
const anim={id:'Wave',name:'ทักทาย',rig:'R6',frames:[{time:0,poses:[]},{time:1,poses:[{joint:'Right Arm',rotation:[0,0,40]}]}]};
const scenarios=[
 ['create-script','tool_calling','สร้าง Script ใหม่ใน ServerScriptService ชื่อ Hello ที่พิมพ์ Citrus และตรวจโครงสร้าง draft',[],
  [step('get_project_info'),step('create_file',file('print("Citrus")','ServerScriptService/Hello')),step('check_project'),step('get_changes')],
  'สร้าง draft ของ ServerScriptService/Hello และผ่านการตรวจโครงสร้างแล้ว ยังไม่ได้รันใน Roblox Studio'],
 ['patch-unique','tool_calling','เปลี่ยน speed จาก 16 เป็น 20 เฉพาะ Movement โดยอ่านไฟล์ก่อน',[file()],
  [step('read_file',{path:'ServerScriptService/Movement'}),step('patch_file',{path:'ServerScriptService/Movement',old_text:'local speed = 16',new_text:'local speed = 20'}),step('read_file',{path:'ServerScriptService/Movement'})],
  'อ่านและเปลี่ยนบรรทัด speed ใน draft เป็น 20 แล้ว เนื้อหาที่อ่านกลับตรงกับการแก้ ยังไม่ได้ทดสอบการเคลื่อนใน Studio'],
 ['patch-ambiguity','debugging','ตรวจกรณี patch คำซ้ำแล้วแก้เฉพาะ a = 1 ให้เป็น a = 2',[file('local a = 1\nlocal b = 1')],
  [step('read_file',{path:'ServerScriptService/Movement'}),step('patch_file',{path:'ServerScriptService/Movement',old_text:'= 1',new_text:'= 2'},false,'ambiguous'),step('patch_file',{path:'ServerScriptService/Movement',old_text:'local a = 1',new_text:'local a = 2'}),step('read_file',{path:'ServerScriptService/Movement'})],
  'patch ข้อความกว้างถูกปฏิเสธเพราะซ้ำสองจุด จึงระบุบรรทัด a ให้ชัดและแก้สำเร็จ โดย b ยังเป็น 1'],
 ['stale-patch','debugging','draft ปัจจุบันมี speed = 18 ตรวจ old_text เก่าที่เป็น 16 แล้วแก้ค่าปัจจุบันเป็น 20',[file('local speed = 18')],
  [step('patch_file',{path:'ServerScriptService/Movement',old_text:'local speed = 16',new_text:'local speed = 20'},false,'does not match'),step('read_file',{path:'ServerScriptService/Movement'}),step('patch_file',{path:'ServerScriptService/Movement',old_text:'local speed = 18',new_text:'local speed = 20'})],
  'ข้อความเก่าไม่ตรงกับ draft จึงอ่านค่าปัจจุบันก่อน patch จาก 18 เป็น 20 ไม่ได้เขียนทับทั้งไฟล์'],
 ['duplicate-path','tool_calling','ตรวจว่า create_file จะป้องกันการเขียนทับไฟล์ Movement ที่มีอยู่หรือไม่',[file()],
  [step('create_file',file('print("replacement")'),false,'already exists'),step('read_file',{path:'ServerScriptService/Movement'})],
  'create_file ปฏิเสธ path ที่มีอยู่ และอ่านกลับพบเนื้อหาเดิม การแก้ไฟล์เดิมต้องใช้การ patch ที่ตรงขอบเขตงาน'],
 ['rename-references','project_structure','ย้าย Module Config จาก ReplicatedStorage/Config เป็น ReplicatedStorage/SharedConfig แล้วรายงานผลต่อ references',[file('return {}','ReplicatedStorage/Config','ModuleScript')],
  [step('read_file',{path:'ReplicatedStorage/Config'}),step('rename_file',{path:'ReplicatedStorage/Config',new_path:'ReplicatedStorage/SharedConfig'}),step('list_files')],
  'ย้าย draft ไป SharedConfig แล้ว แต่ผลเครื่องมือระบุ references_updated=false ต้องค้นและปรับจุดอ้างอิงที่เกี่ยวข้องเพิ่มเติม'],
 ['rename-collision','project_structure','ตรวจการ rename A ไปทับ B ที่มีอยู่แล้ว โดยต้องรักษาทั้งสองไฟล์',[file('return 1','ReplicatedStorage/A','ModuleScript'),file('return 2','ReplicatedStorage/B','ModuleScript')],
  [step('rename_file',{path:'ReplicatedStorage/A',new_path:'ReplicatedStorage/B'},false,'Destination already exists'),step('list_files')],
  'เครื่องมือปฏิเสธปลายทางที่มีอยู่ ทั้ง A และ B ยังอยู่ครบ จึงยังไม่มีการเปลี่ยนชื่อใน draft'],
 ['delete-read-first','tool_calling','ตรวจการลบ Movement ที่ยังไม่ได้อ่าน แล้วอ่านครบก่อนลบตามคำขอ',[file()],
  [step('delete_file',{path:'ServerScriptService/Movement'},false,'Read the complete'),step('read_file',{path:'ServerScriptService/Movement'}),step('delete_file',{path:'ServerScriptService/Movement'}),step('get_changes')],
  'คำขอแรกถูกปฏิเสธเพราะยังไม่ได้อ่านเนื้อหาปัจจุบัน หลังอ่านครบจึงลบ draft ตามคำขอ และรายการเปลี่ยนแปลงแสดงการลบ'],
 ['partial-delete','tool_calling','อ่านไฟล์สามบรรทัดแค่บรรทัดแรกแล้วลองลบ จากนั้นอ่านส่วนที่เหลือและลบให้ถูกขั้นตอน',[file('local a = 1\nlocal b = 2\nprint(a+b)')],
  [step('read_file',{path:'ServerScriptService/Movement',start_line:1,end_line:1}),step('delete_file',{path:'ServerScriptService/Movement'},false,'Read the complete'),step('read_file',{path:'ServerScriptService/Movement',start_line:2,end_line:3}),step('delete_file',{path:'ServerScriptService/Movement'})],
  'การอ่านเพียงบรรทัดแรกไม่พอสำหรับลบ เมื่ออ่านครอบคลุมครบสามบรรทัดของเนื้อหาปัจจุบันแล้วจึงลบ draft ได้'],
 ['read-reset-on-change','tool_calling','ทดสอบว่าอ่านไฟล์แล้วมี patch ตามมา จะลบได้ทันทีหรือจำเป็นต้องอ่านใหม่',[file()],
  [step('read_file',{path:'ServerScriptService/Movement'}),step('patch_file',{path:'ServerScriptService/Movement',old_text:'16',new_text:'18'}),step('delete_file',{path:'ServerScriptService/Movement'},false,'Read the complete'),step('read_file',{path:'ServerScriptService/Movement'}),step('delete_file',{path:'ServerScriptService/Movement'})],
  'หลัง patch เนื้อหาเปลี่ยน หลักฐานการอ่านรุ่นเก่าใช้ลบไม่ได้ ต้องอ่านเนื้อหาปัจจุบันครบก่อนจึงลบได้'],
 ['literal-search','project_structure','ค้นคำว่า MONEY แบบไม่แยกตัวพิมพ์ แล้วเปรียบเทียบการค้นแบบแยกตัวพิมพ์',[file('local Money = 1\nprint("money")')],
  [step('search_code',{query:'MONEY'}),step('search_code',{query:'MONEY',case_sensitive:true})],
  'การค้นไม่แยกตัวพิมพ์พบสองบรรทัด ส่วนแบบแยกตัวพิมพ์ไม่พบคำ MONEY ตามตัวสะกดที่ระบุ'],
 ['prefix-list','project_structure','แสดงเฉพาะไฟล์ใน ReplicatedStorage จาก draft ที่มี Server และ Client ปนอยู่',[file(),file('return {}','ReplicatedStorage/Config','ModuleScript'),file('print("client")','StarterPlayer/StarterPlayerScripts/Input','LocalScript')],
  [step('list_files',{prefix:'ReplicatedStorage/'})],
  'พบ ReplicatedStorage/Config เพียงไฟล์เดียวใน prefix ที่ขอ ยังไม่ได้เปิดอ่าน source ของไฟล์อื่น'],
 ['plan-single-active','tool_calling','ใน Agent mode ตรวจแผนที่มีสองขั้น in_progress แล้วแก้ให้มีเพียงหนึ่งขั้น',[],
  [step('update_plan',{steps:[{step:'อ่านไฟล์',status:'in_progress'},{step:'แก้ไฟล์',status:'in_progress'}]},false,'Only one step'),step('update_plan',{steps:[{step:'อ่านไฟล์',status:'in_progress'},{step:'แก้ไฟล์',status:'pending'}]})],
  'แผนแรกถูกปฏิเสธเพราะมีสองขั้นที่กำลังทำพร้อมกัน แผนที่แก้แล้วมีอ่านไฟล์เป็น in_progress และแก้ไฟล์เป็น pending'],
 ['finish-boundary','verification','จบ proposal หลังตรวจโครงสร้าง แล้วตรวจว่าเครื่องมือจะปฏิเสธการแก้ต่อใน draft เดิมหรือไม่',[],
  [step('check_project'),step('finish_proposal',{summary:'ตรวจโครงสร้าง draft ว่างแล้ว ยังไม่ทดสอบใน Studio'}),step('create_file',file(),false,'Proposal already finished')],
  'proposal ถูกจบแล้ว และคำสั่งแก้ต่อถูกปฏิเสธ การจบ proposal ไม่ได้ apply การเปลี่ยนแปลงใน Studio'],
 ['schema-is-not-syntax','verification','ตรวจ draft ที่มี Luau ผิดไวยากรณ์ เพื่อแสดงขอบเขต check_project',[file('local =')],
  [step('check_project')],
  'check_project คืน valid=true เพราะตรวจเพียงโครงสร้าง พร้อม luau_syntax_checked=false และ runtime_tested=false โค้ด local = ยังไม่ใช่ Luau ที่ถูกต้อง'],
 ['gui-responsive','ui','สร้างหน้าต่าง Menu กว้าง 80% สูง 70% อยู่กลางจอ และตรวจ draft',[],
  [step('create_gui',panel),step('read_creation',{id:'Menu'}),step('check_project')],
  'สร้าง GUI draft โดยใช้ Scale สำหรับขนาดและตำแหน่ง พร้อม AnchorPoint กลางแล้ว ต้องทดสอบสัดส่วนจอและพฤติกรรม LocalScript ใน Studio เพิ่ม'],
 ['gui-parent-recovery','ui','ตรวจ GUI ที่ parent ชี้หาโหนดไม่พบ จากนั้นแก้ให้ Label อยู่ใน Panel',[],
  [step('create_gui',{...panel,nodes:[...panel.nodes,{id:'Label',parent:'Missing',type:'TextLabel',size:[1,0,.2,0],position:[0,0,0,0]}]},false,'Missing GUI parent'),step('create_gui',{...panel,nodes:[...panel.nodes,{id:'Label',parent:'Panel',type:'TextLabel',size:[1,0,.2,0],position:[0,0,0,0],text:'Citrus'}]})],
  'GUI แรกไม่ผ่านเพราะไม่มี parent ชื่อ Missing หลังเปลี่ยน parent เป็น Panel จึงสร้าง draft ได้'],
 ['gui-cycle-rejection','ui','ตรวจว่าลำดับ parent แบบ A เป็นลูก B และ B เป็นลูก A ถูกปฏิเสธหรือไม่',[],
  [step('create_gui',{id:'Cycle',name:'ทดสอบวงจร',nodes:[{id:'A',parent:'B',type:'Frame',size:[1,0,1,0],position:[0,0,0,0]},{id:'B',parent:'A',type:'Frame',size:[1,0,1,0],position:[0,0,0,0]}]},false,'Cyclic GUI parents'),step('get_project_info')],
  'เครื่องมือปฏิเสธวงจร parent จึงไม่มี GUI Cycle ถูกบันทึกใน draft ต้องแก้โครงสร้างให้ไม่มีวงจรก่อน'],
 ['gui-preserve-edited-script','ui','สร้าง GUI จากนั้นแก้สคริปต์เอง แล้วตรวจว่าการสร้าง GUI id เดิมจะเขียนทับสคริปต์ที่แก้เองหรือไม่',[],
  [step('create_gui',panel),step('read_file',{path:'StarterGui/Citrus_Menu'}),step('patch_file',{path:'StarterGui/Citrus_Menu',old_text:'gui.ResetOnSpawn = false',new_text:'gui.ResetOnSpawn = true'}),step('create_gui',{...panel,name:'เมนูรุ่นใหม่'},false,'manually edited')],
  'create_gui ไม่เขียนทับสคริปต์ที่ถูกแก้เองแล้ว ต้องเลือก id ใหม่หรือแก้สคริปต์เดิมโดยตรงตามขอบเขตที่ต้องการ'],
 ['gui-delete-retains-edit','ui','ลบ GUI draft ที่สคริปต์ถูกแก้เองแล้ว และรายงานว่าสคริปต์ยังอยู่หรือไม่',[],
  [step('create_gui',panel),step('read_file',{path:'StarterGui/Citrus_Menu'}),step('patch_file',{path:'StarterGui/Citrus_Menu',old_text:'gui.ResetOnSpawn = false',new_text:'gui.ResetOnSpawn = true'}),step('delete_creation',{id:'Menu'}),step('list_files')],
  'ลบ creation Menu แล้ว แต่เครื่องมือเก็บ LocalScript ที่แก้เองไว้ และผลระบุ manually_edited_script_retained=true'],
 ['mesh-create','mesh_assets','สร้างกล่องอุปกรณ์ด้วย box ขนาด 4×3×2 studs แล้วอ่านข้อมูลที่บันทึก',[],
  [step('create_mesh',crate),step('read_creation',{id:'Crate'})],
  'สร้าง procedural mesh draft ของกล่องแล้ว ขนาดที่บันทึกเป็น 4×3×2 studs ยังไม่ได้ทดสอบ collision หรือส่งเข้า Roblox Studio'],
 ['mesh-size-recovery','mesh_assets','ตรวจ box ที่มีขนาดแกน X เป็นศูนย์ แล้วแก้เป็นขนาดที่ถูกต้อง',[],
  [step('create_mesh',{...crate,parts:[{id:'Body',shape:'box',size:[0,3,2]}]},false,'Size must'),step('create_mesh',crate)],
  'ขนาดศูนย์ถูกปฏิเสธ หลังแก้เป็น 4×3×2 จึงสร้าง draft ได้ โดยไม่มีการอ้างว่าเป็น mesh ที่ทดสอบใน Studio แล้ว'],
 ['mesh-duplicate-id','mesh_assets','ตรวจ mesh ที่ใช้ part id ซ้ำสองชิ้น แล้วแก้ให้แต่ละชิ้นมี id ต่างกัน',[],
  [step('create_mesh',{...crate,parts:[crate.parts[0],{id:'Body',shape:'box',size:[4,.2,2]}]},false,'Duplicate mesh part id'),step('create_mesh',{...crate,parts:[crate.parts[0],{id:'Lid',shape:'box',size:[4,.2,2],position:[0,1.6,0]}]})],
  'id ของชิ้นส่วนต้องไม่ซ้ำ หลังใช้ Body และ Lid แยกกันจึงบันทึก mesh draft ได้'],
 ['creation-kind-conflict','mesh_assets','สร้าง mesh id Crate แล้วลองใช้ id เดิมเป็น GUI โดยไม่ลบโมเดลเดิม',[],
  [step('create_mesh',crate),step('create_gui',{...panel,id:'Crate'},false,'different kind'),step('read_creation',{id:'Crate'})],
  'เครื่องมือไม่ยอมเปลี่ยนชนิด creation ด้วย id เดิม ข้อมูล Crate ยังคงเป็น mesh'],
 ['read-rig-knees','animation','อ่าน rig แบบ R6 และ R15 จากเครื่องมือแล้วสรุปเรื่องข้อเข่า',[],
  [step('read_rig',{rig:'R6'}),step('read_rig',{rig:'R15'})],
  'schematic R6 ที่เครื่องมือคืนไม่มีข้อเข่า ส่วน R15 มีข้อเข่า ข้อมูลนี้เป็น rig มาตรฐานของ preview ไม่ใช่การอ่าน rig จริงใน Studio'],
 ['animation-create','animation','สร้าง R6 Wave ด้วยเฟรมเริ่มที่ 0 และเฟรมยกแขนขวาที่ 1 วินาที',[],
  [step('read_rig',{rig:'R6'}),step('create_animation',anim),step('read_creation',{id:'Wave'})],
  'สร้าง Wave draft สำหรับ schematic R6 แล้ว ใช้ Right Arm ที่เครื่องมือระบุ เวลาเริ่ม 0 และปลาย 1 วินาที ยังไม่ได้ upload animation หรือทดสอบกับตัวละครจริง'],
 ['r6-unknown-knee','animation','ตรวจ animation R6 ที่อ้าง LeftLowerLeg แล้วรายงานข้อผิดพลาดโดยไม่เปลี่ยน rig',[],
  [step('read_rig',{rig:'R6'}),step('create_animation',{...anim,frames:[{time:0,poses:[]},{time:1,poses:[{joint:'LeftLowerLeg',rotation:[30,0,0]}]}]},false,'Unknown R6 joint')],
  'เครื่องมือปฏิเสธ LeftLowerLeg เพราะไม่มีใน schematic R6 นี้ จึงยังไม่ได้สร้างท่างอเข่า และไม่ได้เปลี่ยน rig โดยพลการ'],
 ['keyframe-time-order','animation','ตรวจการ patch keyframe สุดท้ายให้เวลาเป็น 0 ซึ่งซ้ำกับเฟรมแรก แล้วอ่านยืนยันว่า draft เดิมยังอยู่',[],
  [step('create_animation',anim),step('patch_keyframe',{id:'Wave',frame_index:1,frame:{time:0,poses:[]}},false,'strictly increasing'),step('read_creation',{id:'Wave'})],
  'patch ถูกปฏิเสธเพราะเวลาต้องเพิ่มตามลำดับ การตรวจแบบ atomic รักษาเฟรมเดิมที่เวลา 1 วินาทีไว้'],
 ['keyframe-zero-based','animation','แก้เฟรมที่สองของ Wave ให้เป็นเวลา 0.8 และหมุนแขน 30 องศาโดยใช้ index ที่ถูกต้อง',[],
  [step('create_animation',anim),step('patch_keyframe',{id:'Wave',frame_index:1,frame:{time:.8,poses:[{joint:'Right Arm',rotation:[0,0,30]}]}}),step('read_creation',{id:'Wave'})],
  'แก้เฟรมที่สองด้วย frame_index=1 ซึ่งเป็น index แบบเริ่มจากศูนย์แล้ว ผลอ่านกลับมีเวลา 0.8 และมุมแขน 30 องศา'],
 ['finish-draft-only','verification','สร้าง Module Config และจบ proposal โดยระบุขอบเขตว่ามีเพียง draft',[],
  [step('create_file',file('return {Enabled = true}','ReplicatedStorage/Config','ModuleScript')),step('get_changes'),step('finish_proposal',{summary:'สร้าง Config draft แล้ว ยังไม่ได้ apply หรือทดสอบใน Studio'})],
  'proposal มี Module Config ที่เพิ่มใหม่ และ runtime_tested=false งานนี้จบที่ draft สำหรับตรวจทาน ยังไม่มีหลักฐานว่า live project ถูกแก้แล้ว'],
];
assert.equal(scenarios.length,30);
const rows=[],results=[];
for(const [index,scenario] of scenarios.entries()){
 const [name,category,prompt,files,steps,summary]=scenario;
 const project={id:'fixture',name:'Citrus isolated fixture',revision:1,data:{files,creations:[],versions:[],messages:[],proposal:null}};
 const engine=new DraftTools(project);
 const messages=[{role:'system',content:'คุณคือ Citrus ใน Agent mode เครื่องมือแก้ draft ที่แยกจาก Studio เท่านั้น ใช้ผลเครื่องมือเป็นหลักฐานและรายงานขอบเขตการตรวจให้ตรงจริง'},
                 {role:'user',content:prompt+'\nข้อมูลโปรเจกต์ทดสอบ: '+JSON.stringify({files,creations:[]})}];
 const executed=[];
 for(const [i,s] of steps.entries()){
  const id=`call_${index+1}_${i+1}`;
  const actual=engine.execute(s.name,s.args,id);
  assert.equal(actual.ok,s.ok,`${name}/${s.name}: ${JSON.stringify(actual)}`);
  if(s.error) assert.ok(actual.error?.includes(s.error),`${name}: expected ${s.error}, received ${actual.error}`);
  messages.push({role:'assistant',content:null,tool_calls:[{id,type:'function',function:{name:s.name,arguments:s.args}}]});
  messages.push({role:'tool',name:s.name,tool_call_id:id,content:JSON.stringify(actual)});
  executed.push({name:s.name,arguments:s.args,output:actual});
 }
 messages.push({role:'assistant',content:summary});
 const selected=new Set(steps.map(s=>s.name));
 const id='citrus-v4-tool-'+name;
 const evidence={environment:'isolated_citrus_draft_engine',source_revision:'0be3ed7c32d181512a50b90579efe2f217f01cdd',
                 fixture_sha256:hash(project),trajectory_sha256:hash(executed),calls:steps.length,passed:true};
 results.push({id,...evidence});
 rows.push({id,family_id:'tool-fixture/'+name,category,kind:'practice',subtype:'executed_tool_trajectory',mode:'agent',messages,
  tools:toolDefinitions.filter(t=>selected.has(t.function.name)),sources:['tools','verification'],
  provenance:{method:'authored_fixture_actual_execution',source_revision:evidence.source_revision,date:'2026-10-08'},
  review_status:'draft',runtime_verified:false,tool_execution_verified:true,
  evidence:{tool_execution:{report:'reports/tool_replay.json',case_id:id,...evidence}}});
}
fs.mkdirSync(path.join(root,'candidates'),{recursive:true});
fs.mkdirSync(path.join(root,'reports'),{recursive:true});
fs.writeFileSync(path.join(root,'candidates/tool_replay_0001.jsonl'),rows.map(r=>JSON.stringify(r)).join('\n')+'\n');
fs.writeFileSync(path.join(root,'reports/tool_replay.json'),JSON.stringify({environment:'Node.js '+process.version,engine_sha256:crypto.createHash('sha256').update(fs.readFileSync(enginePath)).digest('hex'),
 total:results.length,all_passed:true,roblox_studio_executed:false,cases:results},null,2)+'\n');
console.log(JSON.stringify({actual_tool_trajectories:rows.length,calls:results.reduce((n,r)=>n+r.calls,0),all_assertions_passed:true,roblox_studio_executed:false}));
