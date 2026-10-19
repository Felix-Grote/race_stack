"""Read-only authenticated final hosted record verification, without product imports."""
import argparse,hashlib,json,pathlib,subprocess,zipfile,xml.etree.ElementTree as ET
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True,type=pathlib.Path);parser.add_argument('--sha',required=True);parser.add_argument('--repository',default='/workspace/forza-w3-audit');args=parser.parse_args();P=args.directory;R=args.repository;S=args.sha
def sha(x):return hashlib.sha256(x).hexdigest()
def git(*args):return subprocess.check_output(['git','-C',R,*args])
def canon(x,ascii=False):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=ascii,allow_nan=False).encode()
run=json.loads((P/'push-run.json').read_bytes()); api=json.loads((P/'push-artifacts.json').read_bytes())['artifacts'][0]; blob=(P/'original-push.zip').read_bytes()
assert run['head_sha']==S==api['workflow_run']['head_sha'] and run['event']=='push' and run['status']=='completed' and run['conclusion']=='success'
assert api['digest']=='sha256:'+sha(blob) and len(blob)==api['size_in_bytes']
with zipfile.ZipFile(P/'original-push.zip') as z:
 assert z.testzip() is None
 assert len(z.namelist())==len(set(z.namelist()))
 assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in z.namelist())
 assert all(((i.external_attr>>16)&0o170000)!=0o120000 for i in z.infolist())
 f={n:z.read(n) for n in z.namelist() if not n.endswith('/')}
summary=json.loads(f['summary.json']); groups=[]
for label,expect in summary.items():
 if not isinstance(expect,dict) or 'tests' not in expect:continue
 n='source-free/results/w3-source-free.xml' if label=='w3-source-free' else label+'.xml'
 root=ET.fromstring(f[n]); cases=list(root.iter('testcase')); assert len(cases)==int(expect['tests'])
 assert not any(i.tag in ('failure','error','skipped') for i in root.iter())
 assert all(int(expect[k])==0 for k in ('failures','errors','skipped'))
 groups.append(dict(group=label,tests=len(cases),failures=0,errors=0,skipped=0))
before=json.loads(f['source-hashes-before.json']); assert before==json.loads(f['source-hashes-after.json'])
prefix='planner/global_planner/global_planner/global_racetrajectory_optimization/'
for path,digest in before.items():
 if path.startswith(prefix):
  data=subprocess.check_output(['git','-C','/workspace/forza-audit-records/fresh-17e4ec4/checkout/'+prefix,'show','b1b38ecfefec7200d5bcb243f115af1d795b3766:'+path.removeprefix(prefix)])
 else:data=git('show',S+':'+path)
 assert sha(data)==digest,path
launch=json.loads(f['source-free/launch.json']); runtime=json.loads(f['source-free/results/runtime-identity.json'])
assert launch['expected_commit']==S and launch['source_or_build_mounts']==[] and runtime['source_commit']==S and not runtime['source_dirty']
assert set(('/src','/workspace','/work/src','/work/build','/work/optimizer'))<=set(runtime['verified_absent_paths'])
for mod,rec in runtime['modules'].items():
 assert '/work/install/' in rec['path'] and sha(git('show',S+':planner/global_planner/global_planner/'+mod.split('.')[-1]+'.py'))==rec['sha256']
build=json.loads(f['build-identity.json']);assert build['source_commit']==S and not build['source_dirty'] and build['source_hashes']==before
assert json.loads(f['source-free/results/build-identity.json'])==build
assert runtime['installed_resource_hashes']==build['installed_resource_hashes']
for relative,digest in build['installed_resource_hashes'].items():
 assert sha(git('show',S+':planner/global_planner/config/project_a/'+relative))==digest,relative
for relative,digest in build['dependency_lock_hashes'].items():
 assert sha(git('show',S+':scripts/project_a/'+relative))==digest,relative
# Resolve nested gitlinks using the literal top-level parent objects, not current checkout HEADs.
links=build['gitlinks'];top={}
for entry in git('ls-tree','-r','-z',S).split(b'\0'):
 if not entry:continue
 info,name=entry.split(b'\t',1)
 if info.startswith(b'160000 '):top[name.decode()]=info.decode().split()[2]
for path,commit in links.items():
 if path in top:assert commit==top[path],path
 else:
  parent=max((p for p in top if path.startswith(p+'/')),key=len)
  expected=subprocess.check_output(['git','-C','/workspace/forza-audit-records/fresh-17e4ec4/checkout/'+parent,'rev-parse',top[parent]+':'+path.removeprefix(parent+'/')]).decode().strip()
  assert expected==commit,path
assert len(links)==7
legacy=json.loads(f['legacy-identity-comparison.json']);assert legacy['identities_equal'] and legacy['baseline']==legacy['actual'] and len(legacy['actual'])==10
campaign=json.loads(f['source-free/results/w3-scenario-campaign.json']);assert campaign['source_commit']==S
catalog=[]
for out in campaign['outcomes']:
 case=out['case']; base='source-free/results/w3-scenarios/'+case+'/'
 compile=json.loads(f[base+'compile.json']); validate=json.loads(f[base+'validate.json'])
 H=compile['H']; rel='w3-scenarios/'+case+'/references/'+H+'/reference.json'; raw=f['source-free/results/'+rel]; envelope=json.loads(raw); payload=envelope['payload']
 curve=dict(payload['curve']);curve.update(route_digest=sha(canon(payload['approved_route'],True)),numeric_policy=payload['policies']['numeric']); C=sha(canon(curve,True))
 assert H==sha(canon(payload))==envelope['H']==validate['H']==out['H']
 assert C==payload['approved_curve_digest']==compile['geometry']['curve_digest']==compile['dynamics']['curve_digest']==out['curve_digest']
 assert compile['status']==validate['status']==out['status']==out['geometry']==out['dynamics']=='PASS'
 assert all(c['returncode']==0 and c['status']=='PASS' for c in out['commands'])
 row=dict(case=case,H=H,curve_digest=C,relative_artifact=rel,artifact_sha256=sha(raw),bytes=len(raw),authority_source='Authenticated original push CI compile/validate receipts and campaign; never embedded artifact hash alone')
 catalog.append(row)
 target=P/'hosted-inputs'/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
assert len(catalog)==9
(P/'controlled-hosted-catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
report=dict(PASS=True,implementation=S,run_id=run['id'],artifact_id=api['id'],zip_sha256=sha(blob),zip_bytes=len(blob),zip_files=len(f),functional_groups=groups,tests=sum(x['tests'] for x in groups),groups=len(groups),source_hashes_equal_literal_git=len(before),source_before_after_equal=True,installed_resources_exact_Git=len(build['installed_resource_hashes']),dependency_locks_exact_Git=len(build['dependency_lock_hashes']),recursive_gitlinks_exact_Git=len(links),source_free_launch=launch,source_free_runtime=runtime,legacy_failures_exact=legacy,controlled_catalog=catalog,scope='Independent read-only byte/provenance audit of this exact original hosted push run. Numerical unchanged-artifact replay and independent acceptance decision are separate.')
(P/'hosted-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('functional_groups','source_free_launch','source_free_runtime','legacy_failures_exact','controlled_catalog')}))
