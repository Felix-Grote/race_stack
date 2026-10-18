"""Original-source regression: positive certified u must not query as zero speed."""
import sys,json,gzip,math,platform,argparse
from pathlib import Path
from decimal import Decimal,localcontext
from dataclasses import asdict
parser=argparse.ArgumentParser()
parser.add_argument('--repo',default='/workspace/forza-w3-audit')
parser.add_argument('--output',default='/workspace/forza-audit-records/numerical/publication')
parser.add_argument('--publish',action='store_true')
args=parser.parse_args()
ROOT=Path(args.repo)
sys.path.insert(0,str(ROOT/'planner/global_planner'))
from global_planner.route_input import validate_route
from global_planner.route_reference import Curve
from global_planner.route_corridor import OrderedCurve,_layout
from global_planner.cyclic_retime import RegionLimits,DynamicsModel,ModelRegion,SpeedKnot,SpeedProfile,curve_digest,model_digest,RetimePolicy
from global_planner.route_validate import Footprint,GeometryValidationPolicy,validate_geometry
from global_planner.route_validate_dynamics import DynamicsValidationPolicy,validate_dynamics
from global_planner.route_artifact import _reference,PolicySet,build_payload,publish_reference,artifact_identity,ValidationContext,load_reference
from global_planner.iqp_route_adapter import SolverPolicy
raw=json.loads((ROOT/'planner/global_planner/test/fixtures/project_a/s0_route.json').read_text())
for o in raw['occurrences']:
    for cap in o['caps']: cap['max_speed_mps']=1e7
route=validate_route(raw)
fixture=json.loads(gzip.decompress((ROOT/'planner/global_planner/test/fixtures/project_a/w2_a04_candidates.json.gz').read_bytes()))['candidates']['s0_route']
# Original W2 archive was created by pinned Python3.10. Python3.12 changed sum.
# On the unsupported host only, independently declared occurrence anchors are
# rebuilt while preserving actual coefficient authority; pinned run is exact.
ends=_layout(route)
q=tuple(min(ends,key=lambda a:abs(a-x)) if min(abs(a-x) for a in ends)<1e-9 else x for x in fixture['q'])
ordered=OrderedCurve(route,Curve(fixture['coefficients'],fixture['owners']),q)
limits=RegionLimits(0.,1e7,1e30,1e30,1e30,1e30,0.,'Explicit synthetic high dynamic range')
model=DynamicsModel(tuple(ModelRegion(o.id,o.surface_id,limits) for o in route.occurrences),'synthetic numerical query probe')
knots=tuple(SpeedKnot(i,0.,1e12 if i%2==0 else 1e-12) for i in range(len(ordered.curve.segments)))
profile=SpeedProfile(knots,curve_digest(ordered),model_digest(model),math.fsum(2*s.length/(math.sqrt(knots[i].u)+math.sqrt(knots[(i+1)%len(knots)].u)) for i,s in enumerate(ordered.curve.segments)))
fp=Footprint(.1,.1,.12,.01)
gp,dp=GeometryValidationPolicy(),DynamicsValidationPolicy()
g=validate_geometry(ordered,route,fp,gp,expected_curve_digest=curve_digest(ordered))
d=validate_dynamics(ordered,profile,model,dp,expected_curve_digest=curve_digest(ordered))
if args.publish: assert list(q)==fixture['q'], 'Pinned public reproduction must preserve original q exactly'
print(json.dumps({'python':platform.python_version(),'geometry':g.status,'geometry_reason':g.reason,'dynamics':d.status,'dynamics_reason':d.reason,'q_rebased_for_runtime':list(q)!=fixture['q']}),flush=True)
assert g.status=='PASS' and d.status=='PASS'
if args.publish:
    payload=build_payload(ordered,profile,model,fp,solver_policy=SolverPolicy(),retime_policy=RetimePolicy(),geometry_policy=gp,dynamics_policy=dp,approved_curve_digest=curve_digest(ordered),geometry_report=g,dynamics_report=d,provenance={'purpose':'Independent original-source query numerical repro'})
    ref=publish_reference(payload,args.output,expected_H=artifact_identity(payload),expected_curve_digest=curve_digest(ordered),validation_context=ValidationContext())
    retained_H=ref.H
    ref=load_reference(ref.path,expected_H=retained_H,validation_context=ValidationContext())
    print(json.dumps({'public_publish':'PASS','public_load':'PASS','H':ref.H,'path':str(ref.path)}),flush=True)
else:
    ref=_reference('f'*64,None,ordered,profile,model,fp,PolicySet(ordered.curve.policy,SolverPolicy(),RetimePolicy(),gp,dp),g,d,{'validation':{'dynamics':{'lap_time_s':d.lap_time_s}}})
station=math.nextafter(ref.ordered.curve.cumulative[1],0.)
sample=ref.sample(station)
with localcontext() as ctx:
    ctx.prec=80
    start=Decimal.from_float(knots[0].u)
    end=Decimal.from_float(knots[1].u)
    # At t=1, exact authority is end; the returned query is still on edge0.
    oracle_at_t1=end.sqrt()
print(json.dumps({'station':station,'next_boundary':ref.ordered.curve.cumulative[1],'segment':sample.segment,'t':sample.t,'actual_speed':sample.speed_mps,'minimum_endpoint_speed':math.sqrt(knots[1].u),'exact_endpoint_speed':str(oracle_at_t1),'actual_time':sample.time_s,'actual_acceleration':sample.acceleration_mps2}),flush=True)
assert sample.speed_mps>0.,'BUG: accepted positive moving profile queried as zero speed'
