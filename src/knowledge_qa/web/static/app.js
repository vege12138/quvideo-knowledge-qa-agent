const $ = (id) => document.getElementById(id);
const labels = {answered:'已有依据',clarification_required:'需要确认',insufficient_evidence:'资料不足',tool_error:'服务异常',incomplete:'尚未完成'};
let sessionId = null;
let busy = false;
function element(tag, cls, text) { const node=document.createElement(tag); if(cls)node.className=cls; if(text!==undefined)node.textContent=text; return node; }
function scrollDown(){ $('scroll-area').scrollTop=$('scroll-area').scrollHeight; }
function setBusy(value){busy=value;$('send').disabled=value;$('new-chat').disabled=value;$('question').disabled=value;document.querySelectorAll('[data-question]').forEach(b=>b.disabled=value);$('composer-hint').textContent=value?'正在检索资料并核对原文…':'基于企业知识库回答';}
function showResult(result){
  const box=element('article','message assistant-message');
  const heading=element('div','assistant-heading');heading.append(element('span','mark','✳'),element('strong','','星映知识助手'),element('span','status'+(result.status==='answered'?'':' warning'),labels[result.status]||result.status));
  if(result.mode==='mock')heading.append(element('span','status warning','离线演示'));
  box.append(heading,element('div','answer',result.answer));
  if(result.citations.length){const refs=element('div','citations');for(const ref of result.citations){const card=element('div','citation');card.append(element('div','citation-label',`${ref.doc_id} / ${ref.chunk_id} · 引用原文`),element('div','',ref.quote));refs.append(card);}box.append(refs);}
  if(result.gaps.length)box.append(element('div','gap',result.gaps.join('；')));
  const details=element('details','trace');details.append(element('summary','',`查看查证过程 · ${result.metrics.tool_calls} 次工具调用 · ${result.metrics.elapsed_seconds} 秒`));
  const list=element('ol');for(const step of result.trace){if(step.event==='tool_result'){const d=step.data;list.append(element('li','',`${d.tool==='search_documents'?'检索资料':'读取原文'} · ${JSON.stringify(d.arguments)} · ${d.observation.ok?'完成':'失败：'+d.observation.error.message}`));}else if(step.event==='validation_error')list.append(element('li','','引用或输出校验未通过，已要求修正'));}details.append(list);box.append(details);$('messages').append(box);scrollDown();
}
async function submitQuestion(question){
  question=question.trim();if(!question||busy)return;
  $('welcome').hidden=true;$('error').hidden=true;const user=element('article','message user-message');user.append(element('div','user-bubble',question));$('messages').append(user);
  $('question').value='';setBusy(true);const pending=element('div','message pending','正在查阅企业知识库…');$('messages').append(pending);scrollDown();
  try{const response=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,session_id:sessionId})});const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'请求未完成，请检查输入后重试');sessionId=data.session_id;pending.remove();showResult(data.result);}
  catch(error){pending.remove();$('error').textContent=error.message||'连接失败，请稍后重试';$('error').hidden=false;$('question').value=question;}
  finally{setBusy(false);$('question').focus();scrollDown();}
}
$('question-form').addEventListener('submit',e=>{e.preventDefault();submitQuestion($('question').value);});
$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();submitQuestion($('question').value);}});
document.querySelectorAll('[data-question]').forEach(b=>b.addEventListener('click',()=>submitQuestion(b.dataset.question)));
$('new-chat').addEventListener('click',async()=>{if(busy)return;const old=sessionId;sessionId=null;$('messages').replaceChildren();$('welcome').hidden=false;$('error').hidden=true;$('question').value='';$('question').focus();if(old)try{await fetch(`/api/sessions/${old}`,{method:'DELETE'});}catch{}});
fetch('/api/health').then(r=>r.json()).then(d=>{$('connection').textContent=d.mode==='mock'?'离线演示':'知识库已连接';}).catch(()=>{$('connection').textContent='服务未连接';});

