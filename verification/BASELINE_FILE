"use strict";
const $ = id => document.getElementById(id);
const names = {
 peashooter:"豌豆射手",snow_pea:"寒冰射手",repeater:"双发射手",threepeater:"三线射手",split_pea:"裂荚射手",puff_shroom:"小喷菇",fume_shroom:"大喷菇",scaredy_shroom:"胆小菇",starfruit:"杨桃",kernelpult:"玉米投手",sunflower:"向日葵",wallnut:"坚果",tallnut:"高坚果",umbrella_leaf:"叶子保护伞",torchwood:"火炬树桩",spikeweed:"地刺",potato_mine:"土豆地雷",magnet_shroom:"磁力菇",chomper:"大嘴花",squash:"窝瓜",cactus:"仙人掌",cattail:"香蒲",gatling_pea:"机枪射手",cabbage_pult:"卷心菜投手",melon_pult:"西瓜投手",winter_melon:"冰瓜",gloom_shroom:"忧郁菇",garlic:"大蒜",pumpkin:"南瓜",lily_pad:"睡莲",flower_pot:"花盆",spikerock:"地刺王",cherry_bomb:"樱桃炸弹",jalapeno:"火爆辣椒",doom_shroom:"毁灭菇",ice_shroom:"寒冰菇",blover:"三叶草",hypno_shroom:"魅惑菇",
 normal:"普通僵尸",flag:"旗帜僵尸",conehead:"路障僵尸",buckethead:"铁桶僵尸",screen_door:"铁门僵尸",football:"橄榄球僵尸",pole_vaulting:"撑杆僵尸",ladder:"扶梯僵尸",digger:"矿工僵尸",dancing:"舞王僵尸",backup_dancer:"伴舞僵尸",bungee:"蹦极僵尸",gargantuar:"白眼巨人",red_eye_gargantuar:"红眼巨人",imp:"小鬼僵尸",zamboni:"冰车僵尸",catapult:"投石车僵尸",balloon:"气球僵尸",newspaper:"读报僵尸",jack_in_the_box:"礼盒僵尸",pogo:"跳跳僵尸",yeti:"雪人僵尸",pea_head:"豌豆头",gatling_head:"机枪头",wallnut_head:"坚果头",tallnut_head:"高坚果头",jalapeno_head:"辣椒头",squash_head:"窝瓜头",cob_cannon:"玉米加农炮",ladder_object:"场上梯子"
};
const labels = {id:"单位 ID",row:"行",col:"列",x:"像素 X",hp:"本体血量",helmet_hp:"头盔血量",shield_hp:"盾牌血量",cooldown:"攻击冷却（帧）",state_timer:"准备计时（帧）",layer:"植物层",garlic_direction:"大蒜换行方向",animation_phase:"动画初始相位",animation_rate:"身体动画速率",speed:"平均速度",age:"初始年龄（帧）",chilled:"寒冷剩余帧",buttered:"黄油剩余帧",frozen:"冻结剩余帧",headless:"无头",hypnotized:"魅惑",tool:"持有工具",underground:"地下挖掘",target_col:"蹦极目标列",velocity_parameter:"动画速度参数",walk_variant:"步态变体",phase:"当前阶段",phase_timer:"阶段剩余帧",jack_countdown_frames:"礼盒开盒倒计时（帧）"};
const optionNames={main:"主植物",shell:"外壳",base:"底座",random:"随机",up:"向上",down:"向下"};
// The catalog is the schema authority.  Keep a small label map for built-in
// spec fields, while unknown/new fields are inferred and rendered below.
const fieldLabels = {type:"单位类型",period:"攻击周期（帧）",windup:"出手前摇（帧）",reach:"攻击距离",helmet:"默认头盔血量",shield:"默认盾牌血量",metal:"金属单位",spawn_offset:"出生偏移",hit_offset:"命中偏移",hit_width:"命中宽度",can_lose_head:"可掉头"};
let catalog, side="plants", brush="repeater", tool="place", cell=[3,1], selected=null;
let scene={version:2,seed:2026,max_frames:100000,runs:1,mode:"who_will_win",movement_mode:"animation",brains:[{row:3,hp:70}],allow_stacking:true,rakes:[],ladders:[],plants:[],zombies:[]};
let history=[],future=[],serial=0,busy=false;
const clone = value => JSON.parse(JSON.stringify(value));
const title = type => names[type] || type;
function status(text,error=false){$("status").textContent=text;$("status").classList.toggle("error",error);}
async function api(path,body){const response=await fetch(path,{method:body?"POST":"GET",headers:body?{"Content-Type":"application/json"}:{},body:body?JSON.stringify(body):undefined});const data=await response.json();if(!response.ok)throw Error(data.error||"请求失败");return data;}
function remember(){history.push(clone(scene));if(history.length>80)history.shift();future=[];}
function nextId(){const used=new Set([...scene.plants,...scene.zombies].map(u=>u.id));let id;do{id=`ui_${++serial}`;}while(used.has(id));return id;}
function column(unit,group){if(unit.col!==undefined)return unit.col;const offset=catalog[group][unit.type].spawn_offset||0;return (unit.x-40-offset)/80+1;}
function inCell(unit,group,row,col){
 if(unit.row!==row)return false;
 const left=Math.max(1,Math.min(9,Math.round(column(unit,group))));
 return left===col || (group==="plants"&&unit.type==="cob_cannon"&&left+1===col);
}
function cobAt(row,col){return scene.plants.find(p=>p.type==="cob_cannon"&&p.row===row&&p.col===col);}
function cobCovers(row,col){return scene.plants.some(p=>p.type==="cob_cannon"&&p.row===row&&p.col+1===col);}
function unitsHere(){const result=[];for(const group of ["plants","zombies"])scene[group].forEach((u,i)=>{if(inCell(u,group,...cell))result.push({group,index:i,unit:u});});return result;}
function selectedUnit(){return selected && scene[selected.group]?.[selected.index];}
function button(text,fn,className=""){const b=document.createElement("button");b.type="button";b.textContent=text;b.className=className;b.addEventListener("click",fn);return b;}
function assetFor(type,group){return `/assets/${group==="special"&&type==="ladder"?"ladder_object":type}.png`;}
function renderPalette(){const filter=$("unit-search").value.trim().toLowerCase();const root=$("unit-palette");root.replaceChildren();const source=side==="special"?{rake:{hp:1800,period:0},ladder:{hp:0,period:0}}:catalog[side];const types=Object.keys(source).filter(t=>(title(t)+t).toLowerCase().includes(filter));$("roster-count").textContent=`${types.length} 种`;
 for(const type of types){const b=button("",()=>{if(side==="special"){brush=type;tool="place";render();return;}brush=type;tool="place";render();},`unit-card ${side==="zombies"?"zombie-unit":side==="special"?"special-unit":""} ${brush===type?"active":""}`);const mark=document.createElement("span");mark.className="unit-icon";const img=document.createElement("img");img.src=assetFor(type,side);img.alt="";img.onerror=()=>{img.src=assetFor(side==="zombies"?"normal":side==="special"?"rake":"peashooter",side);};mark.append(img);const text=document.createElement("span");text.className="unit-name";text.textContent=title(type);const small=document.createElement("small");small.textContent=type;const spec=source[type]||{};const stats=[];if(spec.hp!==undefined)stats.push(`HP ${spec.hp}`);if(spec.period)stats.push(`冷却 ${spec.period}`);if(spec.speed)stats.push(`速度 ${spec.speed}`);if(stats.length){const meta=document.createElement("small");meta.className="unit-stats";meta.textContent=stats.join(" · ");text.append(meta);}text.append(small);b.append(mark,text);b.title=stats.join(" · ");b.setAttribute("aria-label",`选择${title(type)}`);b.setAttribute("aria-pressed",String(brush===type));root.append(b);}
}
function renderBoard(){const board=$("board");board.replaceChildren();for(let row=1;row<=5;row++){const rowLabel=document.createElement("span");rowLabel.className="row-label";rowLabel.textContent=row;board.append(rowLabel);for(let col=1;col<=9;col++){
 const b=button("",()=>clickCell(row,col),`cell ${row===3?"main-row":""} ${cell[0]===row&&cell[1]===col?"selected":""}`);b.setAttribute("aria-label",`第${row}行第${col}列`);b.addEventListener("mouseenter",()=>{if(tool!=="place"||side==="special")return;const ghost=document.createElement("img");ghost.className="ghost-unit";ghost.src=assetFor(brush,side);ghost.alt="预览";ghost.onerror=()=>ghost.remove();b.append(ghost);});b.addEventListener("mouseleave",()=>b.querySelectorAll(".ghost-unit").forEach(n=>n.remove()));b.addEventListener("contextmenu",event=>{event.preventDefault();cell=[row,col];const first=unitsHere()[0];if(first){selected={group:first.group,index:first.index};tool="inspect";render();status(`已选中${title(first.unit.type)}，可编辑属性。`);}});
 const anchor=cobAt(row,col), covered=cobCovers(row,col);
 if(anchor)b.classList.add("cob-anchor");
 if(covered)b.classList.add("cob-footprint");
 for(const group of ["plants","zombies"]){let units=scene[group].filter(u=>inCell(u,group,row,col));if(covered&&col!==anchor?.col)units=[];for(const u of units){const chip=document.createElement("span");chip.className=`board-unit ${group==="zombies"?"zombie-unit":""} ${u.type==="cob_cannon"?"cob-board-unit":""}`;const icon=document.createElement("img");icon.src=assetFor(u.type,group);icon.alt=title(u.type);icon.onerror=()=>{icon.src=assetFor(group==="zombies"?"normal":"peashooter",group);};chip.append(icon);chip.title=title(u.type)+(u.x!==undefined?` X=${u.x}`:"");b.append(chip);}}
 if(anchor){const note=document.createElement("span");note.className="cob-footprint-label";note.textContent="占2格";b.append(note);} 
 if(covered&&!anchor){const note=document.createElement("span");note.className="cob-footprint-label";note.textContent="玉米加农炮";b.append(note);}
 const rake=(scene.rakes||[]).some(r=>r.row===row&&r.col===col);const ladder=(scene.ladders||[]).some(r=>r.row===row&&r.col===col);if(rake||ladder){const marker=document.createElement("img");marker.className="board-unit special-marker";marker.src=assetFor(rake?"rake":"ladder","special");marker.alt=rake?"钉耙":"梯子";b.append(marker);} if(scene.brains.some(br=>(typeof br==="number"?br:br.row)===row)&&col===1)b.classList.add("brain-lane");board.append(b);
 }}
 $("placement-hint").textContent=tool==="place"?`正在放置：${title(brush)} · 点击棋盘落子` : "查看模式 · 点击格子编辑已有单位";
}
function clickCell(row,col){
 cell=[row,col];selected=null;
 if(tool==="place"){
  if(side==="special"){
   remember(); const list=brush==="rake"?(scene.rakes||(scene.rakes=[])):(scene.ladders||(scene.ladders=[]));
   if(!list.some(item=>item.row===row&&item.col===col)){list.push({row,col});status(`已放置${brush==="rake"?"钉耙":"场上梯子"}。`);}else{status("该格已有特殊物件。");}
   render(); return;
  }
  if(side==="plants"&&brush==="cob_cannon"&&col>=9){status("玉米加农炮占用当前格及右侧一格，请从第1—8列放置。",true);render();return;}
  if(side==="plants"&&cobCovers(row,col)&&brush!=="cob_cannon"){status("该格是玉米加农炮占用的第二格。",true);render();return;}
  const unit={type:brush,row,col};
  if(side==="plants"){
   unit.layer=brush==="pumpkin"?"shell":["lily_pad","flower_pot"].includes(brush)?"base":"main";
   if(!scene.allow_stacking&&scene.plants.some(p=>p.row===row&&p.col===col&&(p.layer||"main")===unit.layer)){tool="inspect";status("该植物层已有单位；请开启同层叠放。");render();return;}
  }
  remember();unit.id=nextId();scene[side].push(unit);selected={group:side,index:scene[side].length-1};status(`已放置${title(brush)}。`);
 }else{const first=unitsHere()[0];if(first)selected={group:first.group,index:first.index};}
 render();
}
function defaultValue(group,type,name,u){
 const spec=catalog[group]?.[type]||{};
 if(u[name]!==undefined)return u[name];
 const map={hp:"hp",helmet_hp:"helmet",shield_hp:"shield",cooldown:"period",speed:"speed",reach:"reach",state_timer:null,age:null,chilled:null,buttered:null,frozen:null,headless:null,hypnotized:null,tool:null,underground:null};
 if(Object.prototype.hasOwnProperty.call(map,name)&&map[name]!==null&&spec[map[name]]!==undefined)return spec[map[name]];
 if(name==="phase")return "initial";
 if(name==="layer")return type==="pumpkin"?"shell":(["lily_pad","flower_pot"].includes(type)?"base":"main");
 if(["state_timer","age","chilled","buttered","frozen"].includes(name))return 0;
 if(["headless","hypnotized","tool","underground"].includes(name))return false;
 return "";
}
function renderInspector(){const items=unitsHere(),u=selectedUnit();$("selected-coordinate").textContent=`R${cell[0]} · C${cell[1]}`;$("cell-units").replaceChildren();for(const item of items){const b=button(title(item.unit.type),()=>{selected={group:item.group,index:item.index};renderInspector();},`cell-unit ${selected?.group===item.group&&selected?.index===item.index?"active":""}`);$("cell-units").append(b);}
 $("inspector-empty").hidden=!!u;$("unit-inspector").hidden=!u;if(!u)return;$("selected-unit-title").textContent=title(u.type);$("unit-json").value=JSON.stringify(u,null,2);const form=$("property-form");form.replaceChildren();
 if(selected.group==="zombies"){const wrap=document.createElement("label");wrap.textContent="位置输入方式";const input=document.createElement("select");input.id="position-mode";for(const v of ["col","x"]){const o=new Option(v==="col"?"格子列坐标":"精确像素 X",v);input.add(o);}input.value=u.x===undefined?"col":"x";input.onchange=()=>{remember();if(input.value==="x"){u.x=40+(catalog.zombies[u.type].spawn_offset||0)+80*(u.col-1);delete u.col;}else{u.col=column(u,"zombies");delete u.x;}render();};wrap.append(input);form.append(wrap);}
 for(const f of catalog[selected.group==="plants"?"plant_fields":"zombie_fields"]){if(f.applies_to&&!f.applies_to.includes(u.type))continue;if(f.name==="x"&&u.x===undefined||f.name==="col"&&selected.group==="zombies"&&u.x!==undefined)continue;
 const label=document.createElement("label");label.textContent=labels[f.name]||f.name;let input;
 if(f.type==="enum"||f.type==="boolean"){input=document.createElement("select");for(const value of f.type==="boolean"?["true","false"]:f.options)input.add(new Option(optionNames[value]||(value==="true"?"是":value==="false"?"否":value),value));}
 else{input=document.createElement("input");input.type=f.type==="string"?"text":"number";if(input.type==="number"){input.step=f.type==="integer"||f.name==="col"&&u.type==="bungee"?"1":"any";input.min=f.min;input.max=f.max;const bound={hp:"hp",helmet_hp:"helmet",shield_hp:"shield"}[f.name];if(bound)input.max=catalog[selected.group][u.type][bound];}}
 input.id=`property-${f.name}`;input.value=String(defaultValue(selected.group,u.type,f.name,u));input.placeholder="";input.addEventListener("change",()=>{const value=input.value;if(value!==""&&!input.checkValidity()){input.reportValidity();return;}remember();if(value==="")delete u[f.name];else u[f.name]=f.type==="boolean"?value==="true":f.type==="integer"||f.type==="number"?Number(value):value;if(f.name==="row"||f.name==="col"||f.name==="x")cell=[u.row,Math.max(1,Math.min(9,Math.round(column(u,selected.group))))];render();status("属性已更新；运行前会由模拟器校验。");});label.append(input);if(f.description){const note=document.createElement("small");note.textContent=f.description;label.append(note);}form.append(label);
 }
 // Forward-compatible escape hatch: when the model gains a new serializable
 // initial-state field, an imported scenario can still edit it immediately.
 // The server remains the validation authority; this only infers a suitable
 // control and never silently drops the value.
 const schema = new Set(catalog[selected.group==="plants"?"plant_fields":"zombie_fields"].map(f=>f.name));
 for(const name of Object.keys(u).filter(k=>!schema.has(k)&&!['id','type','shots','target','state','recently_eaten'].includes(k))){
   const value=u[name], label=document.createElement("label"); label.textContent=fieldLabels[name]||name+"（扩展属性）";
   let input;
   if(typeof value === "boolean"){input=document.createElement("select");input.add(new Option("是","true"));input.add(new Option("否","false"));}
   else {input=document.createElement("input"); input.type=typeof value==="number"?"number":"text"; input.step="any";}
   input.value=String(value); input.dataset.dynamic="true";
   input.addEventListener("change",()=>{remember();const v=input.value;if(v==="")delete u[name];else u[name]=input.type==="number"?Number(v):input.value==="true"?true:input.value==="false"?false:v;render();status(`已更新扩展属性 ${name}；运行时会校验。`);});
   label.append(input); const note=document.createElement("small");note.textContent="来自场景 JSON 的新字段";label.append(note);form.append(label);
 }
}
function syncControls(){const fields={"mode-input":"mode","seed-input":"seed","frames-input":"max_frames","runs-input":"runs","movement-input":"movement_mode","magnet-input":"magnet_distance_mode"};for(const [id,key]of Object.entries(fields))$(id).value=scene[key]??(key==="magnet_distance_mode"?"horizontal":"");$("stacking-input").checked=!!scene.allow_stacking;
 $("brain-controls").replaceChildren();for(let row=1;row<=5;row++){const br=scene.brains.find(b=>(typeof b==="number"?b:b.row)===row);const label=document.createElement("label");label.className="brain-control";const check=document.createElement("input");check.type="checkbox";check.checked=!!br;check.setAttribute("aria-label",`第${row}行脑子`);const hp=document.createElement("input");hp.type="number";hp.min=1;hp.max=70;hp.value=typeof br==="object"?br.hp:70;hp.disabled=!br;hp.setAttribute("aria-label",`第${row}行脑子血量`);const update=()=>{if(!hp.checkValidity()){hp.reportValidity();return;}remember();scene.brains=scene.brains.filter(b=>(typeof b==="number"?b:b.row)!==row);if(check.checked)scene.brains.push({row,hp:Number(hp.value)});render();};check.onchange=update;hp.onchange=update;label.append(check,document.createTextNode(`第${row}行`),hp);$("brain-controls").append(label);}
 const rakeRoot=$("rake-controls");if(rakeRoot){rakeRoot.replaceChildren();(scene.rakes||[]).forEach((rake,index)=>{const label=document.createElement("label");label.className="brain-control";const row=document.createElement("input");row.type="number";row.min=1;row.max=5;row.value=rake.row;const col=document.createElement("input");col.type="number";col.min=1;col.max=9;col.value=rake.col;const remove=button("移除",()=>{remember();scene.rakes.splice(index,1);render();});label.append(document.createTextNode(`钉耙${index+1}`),row,col,remove);const update=()=>{if(!row.checkValidity()||!col.checkValidity()){row.reportValidity();return;}remember();rake.row=Number(row.value);rake.col=Number(col.value);render();};row.onchange=update;col.onchange=update;rakeRoot.append(label);});}
}
function render(){renderPalette();renderBoard();renderInspector();syncControls();$("plants-tab").classList.toggle("active",side==="plants");$("zombies-tab").classList.toggle("active",side==="zombies");for(const [id,on]of [["plants-tab",side==="plants"],["zombies-tab",side==="zombies"],["special-tab",side==="special"],["place-tool",tool==="place"],["inspect-tool",tool==="inspect"]]){$(id).classList.toggle("active",on);$(id).setAttribute("aria-pressed",String(on));}$("undo-button").disabled=!history.length;$("redo-button").disabled=!future.length;}
function jsonText(){return JSON.stringify(scene,null,2);}
async function normalize(text){const value=await api("/api/normalize",{code:text});remember();scene=value.scenario;selected=null;tool="inspect";cell=[3,1];render();status(`已载入 ${scene.plants.length} 株植物、${scene.zombies.length} 只僵尸，随机初态已规范化。`);}
function showResult(data){const root=$("result-body");root.replaceChildren();const winners={plants:"植物获胜",zombies:"僵尸获胜",undecided:"结果未决"};$("result-tag").textContent=data.batch?`${data.runs} 轮完成`:winners[data.winner];if(data.batch){for(const [key,entry]of Object.entries(data.outcomes)){const p=document.createElement("p");p.textContent=`${winners[key]}　${entry.count} 轮 / ${(entry.probability*100).toFixed(1)}%`;root.append(p);}}else{const h=document.createElement("h3");h.textContent=winners[data.winner];const p=document.createElement("p");p.textContent=`${data.frames} 帧 · ${(data.frames/100).toFixed(2)} 秒`;const reason=document.createElement("p");reason.textContent=data.reason==="max_frames_reached"?"已达到帧数上限，不能据此判定胜负。":`结算依据：${data.reason}`;root.append(h,p,reason);}const details=document.createElement("details");const summary=document.createElement("summary");summary.textContent="完整结果 JSON";const pre=document.createElement("pre");pre.textContent=JSON.stringify(data,null,2);details.append(summary,pre);root.append(details);}
function handleError(error){status(error.message||String(error),true);}
$("plants-tab").onclick=()=>{side="plants";brush=Object.keys(catalog.plants)[0];render();};$("zombies-tab").onclick=()=>{side="zombies";brush=Object.keys(catalog.zombies)[0];render();};$("special-tab").onclick=()=>{side="special";brush="rake";render();};$("unit-search").oninput=renderPalette;
$("place-tool").onclick=()=>{tool="place";render();};$("inspect-tool").onclick=()=>{tool="inspect";render();};
$("undo-button").onclick=()=>{if(history.length){future.push(clone(scene));scene=history.pop();selected=null;render();}};$("redo-button").onclick=()=>{if(future.length){history.push(clone(scene));scene=future.pop();selected=null;render();}};
$("clear-button").onclick=()=>{remember();scene.plants=[];scene.zombies=[];selected=null;render();status("棋盘已清空，可撤销。");};
$("delete-unit").onclick=()=>{if(selected){remember();scene[selected.group].splice(selected.index,1);selected=null;render();}};
$("apply-unit-json").onclick=()=>{try{const value=JSON.parse($("unit-json").value);if(!value||typeof value!=="object"||Array.isArray(value)||!catalog[selected.group][value.type])throw Error("单位 JSON 必须包含已支持的 type。");remember();scene[selected.group][selected.index]=value;render();status("已应用单位 JSON，运行时将校验全部字段。");}catch(e){handleError(e);}};
$("import-button").onclick=()=>normalize($("formation-code").value).catch(handleError);
$("import-file").onchange=async event=>{const file=event.target.files[0];if(file){try{const text=await file.text();$("formation-code").value=text;await normalize(text);}catch(e){handleError(e);}event.target.value="";}};
$("show-json").onclick=()=>{$("formation-code").value=jsonText();status("已显示完整场景 JSON。");};
$("copy-json").onclick=async()=>{try{await navigator.clipboard.writeText(jsonText());status("完整 JSON 已复制。");}catch(e){$("formation-code").value=jsonText();$("formation-code").select();status("请在代码框手动复制 JSON。");}};
$("download-json").onclick=()=>{const url=URL.createObjectURL(new Blob([jsonText()],{type:"application/json"}));const a=document.createElement("a");a.href=url;a.download="ize-formation.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);status("已导出完整 JSON。");};
for(const [id,key,isNumber]of [["mode-input","mode"],["seed-input","seed",true],["frames-input","max_frames",true],["runs-input","runs",true],["movement-input","movement_mode"],["magnet-input","magnet_distance_mode"]])$(id).onchange=()=>{const input=$(id);if(input.value!==""&&!input.checkValidity()){input.reportValidity();return;}if(key==="seed"&&!Number.isSafeInteger(Number(input.value)))return status("界面种子须为 JavaScript 安全整数；更大的 64 位种子请使用 CLI。",true);remember();if(input.value==="")delete scene[key];else scene[key]=isNumber?Number(input.value):input.value;render();};
$("stacking-input").onchange=()=>{remember();scene.allow_stacking=$("stacking-input").checked;render();};
$("add-rake").onclick=()=>{remember();scene.rakes=scene.rakes||[];scene.rakes.push({row:3,col:8});render();status("已添加钉耙。它会在同排僵尸进入触发范围后造成一次性伤害。");};$("add-ladder").onclick=()=>{remember();scene.ladders=scene.ladders||[];scene.ladders.push({row:3,col:4});render();status("已添加独立梯子。");};$("quick-rake").onclick=()=>$("add-rake").click();
$("simulate-button").onclick=async()=>{if(busy)return;busy=true;$("simulate-button").disabled=true;status("正在本地推演…");try{const result=await api("/api/simulate",{scenario:scene});showResult(result);status("推演完成；结果为离线模型预测。");}catch(e){handleError(e);}finally{busy=false;$("simulate-button").disabled=false;}};
document.addEventListener("keydown",event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="z"){event.preventDefault();$("undo-button").click();}else if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==="y"){event.preventDefault();$("redo-button").click();}else if((event.key==="Delete"||event.key==="Backspace")&&selected&&document.activeElement.tagName!=="INPUT"&&document.activeElement.tagName!=="TEXTAREA"){event.preventDefault();$("delete-unit").click();}else if(event.key==="Escape"){selected=null;tool="inspect";render();}});
api("/api/catalog").then(data=>{catalog=data;const modelLabel=$("model-label");if(modelLabel)modelLabel.textContent=data.model;render();status("本地模拟器已连接。选择单位，点击棋盘开始布阵。");}).catch(handleError);
