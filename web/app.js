'use strict';
const $ = id => document.getElementById(id);
let token, wallet, challengeId, protocol, code = '', connectedAgent;
function message(text, error=false) { $('message').textContent=text; $('message').classList.toggle('error',error); }
async function api(path, body) {
  const r=await fetch('/api'+path,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(token?{'Authorization':'Bearer '+token}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await r.json();
  if(!r.ok) throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
  return data;
}
function button(id, fn) { $(id).addEventListener('click',async()=> { $(id).disabled=true; try { await fn(); } catch(e) { message(e.message,true); } finally { $(id).disabled= id==='submit'?!challengeId:id==='mint'?!$('checks').dataset.passed:false; } }); }
function step(n) { document.querySelectorAll('.step').forEach((e,i)=>e.classList.toggle('active',i===n)); }
async function poll(states) {
  const until=Date.now()+210000;
  while(Date.now()<until) {
    const s=await api(`/challenges/${challengeId}/status`);
    if(!states.includes(s.state)) return s;
    await new Promise(r=>setTimeout(r,1500));
  }
  throw new Error('Verification is still running. Reconnect and draw to resume the active challenge.');
}
async function record() {
  const r=await api('/skills/'+connectedAgent); const s=r.record;
  $('skillRecord').replaceChildren();
  const title=document.createElement('strong');title.textContent='AGENT #'+connectedAgent;
  const details=document.createElement('p'); details.textContent=s.exists?`${s.totalSolves} verified solves · ${s.solvesPerClass.join(' / ')} across three classes · permanently locked`:(s.revoked?'Record revoked.':'No skill record yet. Your first verified mint creates it.');
  const quota=document.createElement('small');quota.textContent=`${r.collectiblesMinted} / 2 lifetime collectibles minted`;
  $('skillRecord').append(title,details,quota);
}
async function loadChallenge() {
  code=''; let i=0, p;
  do { p=await api(`/challenges/${challengeId}/fragments/${i}`); code+=p.code; i++; } while(i<p.total);
  $('source').textContent=code; $('patch').value=code; $('poc').value='';
  $('challengeInfo').textContent=p.title+' · '+challengeId+' · 1-hour timer started';
  $('copy').disabled=false; $('submit').disabled=false; step(2);
}
button('connect',async()=>{
  if(!window.ethereum) throw new Error('Install or open an EVM wallet to continue.');
  connectedAgent=$('agentId').value.trim();
  if(!/^\d+$/.test(connectedAgent)) throw new Error('Enter a numeric Agent ID.');
  if(!protocol) protocol=await api('/protocol_info');
  [wallet]=await ethereum.request({method:'eth_requestAccounts'});
  const wanted='0x'+Number(protocol.chainId).toString(16);
  if((await ethereum.request({method:'eth_chainId'}))!==wanted) await ethereum.request({method:'wallet_switchEthereumChain',params:[{chainId:wanted}]});
  const prep=await api('/prepare',{wallet,agentId:connectedAgent});
  const signature=await ethereum.request({method:'eth_signTypedData_v4',params:[wallet,JSON.stringify(prep.typedData)]});
  token=(await api('/login',{nonce:prep.nonce,signature})).token;
  $('wallet').textContent=wallet+' · Agent #'+connectedAgent; $('start').disabled=false; step(1); message('Ownership verified. Draw a challenge.'); await record();
});
button('start',async()=>{
  $('mint').disabled=true; delete $('checks').dataset.passed; $('checks').replaceChildren();
  message('Checking reference solution in the isolated verifier…');
  try { const r=await api('/start',{vulnClass:Number($('vulnClass').value)}); challengeId=r.challengeId; }
  catch(e) { const match=e.message.match(/"challengeId":"([^"]+)"/); if(!match) throw e; challengeId=match[1]; }
  const state=await poll(['calibrating','grading']);
  if(state.state==='issued') { await loadChallenge(); message('Read the contract and submit a PoC with your repair.'); }
  else if(['passed','authorized'].includes(state.state)) { $('checks').dataset.passed='true'; $('mint').disabled=false; message('Verified solve restored. Authorize & mint to continue.'); }
  else throw new Error('Challenge ended with state '+state.state+'. Draw a fresh challenge.');
});
button('copy',async()=>{await navigator.clipboard.writeText(code);message('Source copied.');});
button('submit',async()=>{
  message('Running your PoC against both versions and checking normal functionality…');
  await api(`/challenges/${challengeId}/submit`,{patch:$('patch').value,poc:$('poc').value});
  const s=await poll(['grading']); $('submit').disabled=true;
  if(!s.result) throw new Error('Verifier unavailable. Draw a new challenge to retry.');
  $('checks').replaceChildren();
  for(const [key,label] of [['pocProvesBug','Exploit proven'],['pocFailsAfterPatch','Exploit stopped'],['hiddenTestsPass','Functions preserved'],['patchWithinLimits','Patch within limits']]) {
    const el=document.createElement('span');el.className='check '+(s.result[key]?'pass':'fail');el.textContent=(s.result[key]?'✓ ':'× ')+label;$('checks').append(el);
  }
  if(s.state==='passed') {$('checks').dataset.passed='true';$('mint').disabled=false;step(3);message('Repair verified. You can now mint both outcomes.');}
  else message('Repair did not pass. '+s.result.log+' Draw a fresh challenge to try again.',true);
});
button('mint',async()=>{
  if((await ethereum.request({method:'eth_chainId'}))!=='0x'+Number(protocol.chainId).toString(16)) throw new Error('Switch back to the configured test network.');
  const r=await api(`/challenges/${challengeId}/authorize`,{});
  message('Authorization ready. Review the mint transaction in your wallet.');
  const hash=await ethereum.request({method:'eth_sendTransaction',params:[{from:wallet,to:protocol.collectible,data:r.calldata,value:'0x0'}]});
  message('Transaction submitted: '+hash);
  const until=Date.now()+180000;
  while(Date.now()<until){const receipt=await ethereum.request({method:'eth_getTransactionReceipt',params:[hash]});if(receipt){if(receipt.status!=='0x1')throw new Error('Mint reverted. Check the gate, quota and hourly cap.');message('Mint confirmed. Your skill record is on chain. Collectible rarity awaits the operator’s batch reveal.');await record();delete $('checks').dataset.passed;$('mint').disabled=true;return;}await new Promise(r=>setTimeout(r,2000));}
  message('Transaction still pending: '+hash+'. Check your wallet before retrying.');
});
if(window.ethereum?.on){for(const event of ['accountsChanged','chainChanged']) ethereum.on(event,()=>{token=null;challengeId=null;['start','submit','mint'].forEach(id=>$(id).disabled=true);message('Wallet changed. Connect and sign in again.');});}
api('/protocol_info').then(p=>{protocol=p;$('supply').textContent=p.minted.toLocaleString()+' / '+p.maxSupply.toLocaleString();$('network').textContent=p.chainId===97?'BSC testnet · 97':'Local Anvil · 31337';$('gate').textContent=p.open?'Open for repairs':'Gate closed';}).catch(()=>{$('network').textContent='Unavailable';$('gate').textContent='Backend not configured';message('The chain connection is unavailable. Check backend configuration.',true);});
