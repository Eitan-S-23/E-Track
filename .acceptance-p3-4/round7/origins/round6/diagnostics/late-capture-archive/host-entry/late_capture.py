import sys,csv,io,json,hashlib,re
from pathlib import Path
R=Path.cwd();sys.path.insert(0,str(R/'Tools/ota/p34-acceptance'));import live_host as h
from live_phone import Phone
N=R/'.acceptance-p3-4/round6';O=h.checked(N/'diagnostics/late-capture-archive');h.require(not O.exists(),'existing archive')
h.fresh(O);plan=h.read_json(R/'.cache/p34-live-inputs1/inputs.json');P=N/'ops/cmd-q-transfer/phone'
current=P/'runtime.json';prior=P/'previous-runtime.json'
h.require(hashlib.sha256(prior.read_bytes()).hexdigest() in plan['owned_configs'],'prior runtime unowned')
L=h.checked(R/'.cache/p34-live-device.lock');old=h.read_json(L);lock=L.read_bytes()
h.require(old['out']==str(N/'diagnostics/runtime-reconciliation'),'owner changed')
h.require(h.read_json(N/'diagnostics/runtime-reconciliation/failed.json')['error']=='new capture; preserve' and not (N/'diagnostics/runtime-reconciliation/intent.json').exists(),'prior operation uncertain')
env=h.environment(O);data=h.command(O,'previous-owner',['tasklist','/FO','CSV','/NH'],env,seconds=15)
rows=list(csv.reader(io.StringIO(data.decode('utf-8','replace'))));h.require(not any(len(x)>1 and (x[1]==str(old['pid']) or x[0].lower()=='adb.exe') for x in rows) and not h.listening(5062),'owner active')
h.raw(O/'previous-lock.json',lock);h.require(L.read_bytes()==lock,'changed lock');L.unlink()
cap='1791733411743571-151409df12fd3ec70569f908';D='files/p34-observations/'+cap
with h.device_owner(O):
 p=Phone(plan,O/'phone',900)
 try:
  p.start();names=p.captures();saved=set(h.read_json(R/'.cache/p34-authorized-capture-cleanup-20261011/result.json')['after'])
  h.require(names==saved|{cap},'different capture set')
  pid=p.cmd(['shell','pidof',p.pkg],success_codes=(0,1)).strip();h.require(pid==b'26049','different process')
  state=p.health(cap);h.require(state['upgradeStarts']==state['upgradeEnds']==0,'transfer occurred; preserve')
  data=p.file(D+'/events.jsonl');rows=[json.loads(x) for x in data.splitlines()]
  header=rows[0];h.require(header['pid']==26049 and header['captureId']==cap and header['sentinel']==plan['sentinel'] and header['target']==plan['ble_address'],'foreign capture')
  stamps=[json.loads(x['message'][15:]) for x in rows if str(x.get('message','')).startswith('OTA_EXPERIMENT ')]
  h.require(stamps and all(x['configSha256']==hashlib.sha256(current.read_bytes()).hexdigest() for x in stamps),'runtime stamp mismatch')
  h.require(p.file('files/p34-experiment.json',8192)==current.read_bytes(),'runtime changed')
  h.raw(O/'events-before-stop.jsonl',data)
  h.save(O/'stop-intent.json',dict(reason='Stop only this entry owned inactive App; no OTA, preserve late capture and restore only own failed runtime write.',pid=26049,capture=cap))
  p.cmd(['shell','am','force-stop',p.pkg]);h.require(not p.cmd(['shell','pidof',p.pkg],success_codes=(0,1)).strip(),'stop unknown')
  state=p.health(cap);h.require(state['upgradeStarts']==state['upgradeEnds']==0,'upgrade during stop')
  p.safe_remote(D);files=sorted(n for n in p.cmd(['exec-out','run-as',p.pkg,'ls','-1a',D]).decode().splitlines() if n not in ('.','..'))
  h.require(set(files)>={'events.jsonl','health.json'} and all(re.fullmatch(r'events\.jsonl|health\.json(?:\.tmp)?|snapshot-[1-4]\.jsonl',x) for x in files),'unknown files')
  originals=[]
  for name in files:
   data=p.file(D+'/'+name,allow_empty=True);item=h.raw(O/'capture'/name,data)
   digest=p.cmd(['exec-out','run-as',p.pkg,'sha256sum',D+'/'+name]).decode().split()[0];h.require(digest==item['sha256'],'archive mismatch');originals.append(item)
  p.safe_remote('files/p34-experiment.json');p.cmd(['exec-in','run-as',p.pkg,'sh','-c','cat > files/p34-experiment.json'],stdin=prior.read_bytes())
  h.require(p.file('files/p34-experiment.json',8192)==prior.read_bytes(),'restore mismatch')
  power=p.cmd(['shell','dumpsys','power']).decode('utf-8','replace');policy=p.cmd(['shell','dumpsys','window','policy']).decode('utf-8','replace')
  h.raw(O/'power.txt',power.encode());h.raw(O/'policy.txt',policy.encode())
  awake='mWakefulness=Awake' in power and bool(re.search(r'KeyguardServiceDelegate\s+showing=false\b',policy))
  h.save(O/'archive.json',dict(capture=cap,remote_directory='/data/user/0/'+p.pkg+'/'+D,header=header,health=state,originals=originals,runtime_restored=h.record(prior),captures_retained=sorted(p.captures()),phone_unlocked=awake,phone_file_deletions=0))
 except BaseException as e:
  h.save(O/'failed.json',dict(error=str(e),no_retry=True));raise
 finally:p.close()
h.save(O/'result.json',dict(archived=True,app_stopped=True,runtime_restored=True,phone_closed=True,phone_unlocked=awake,phone_file_deletions=0,ota_starts=0))
print('LATE_CAPTURE_ARCHIVED; NOT_DELETED; UNLOCKED=',awake)
