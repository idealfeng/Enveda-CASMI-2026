"""Freeze pairwise dominance revision without changing either previous stage."""
from pathlib import Path
import ast
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'scripts/evidence_early_overlay_20261114.py'
MODULE=ROOT/'scripts/evidence_pairwise_overlay_20261114.py'
BUILDER=ROOT/'scripts/build_evidence_early_20261114.py'


def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Source anchor must occur once')
    return text.replace(old,new)


def main():
    if MODULE.exists():raise FileExistsError('Preserve frozen pairwise source')
    source=BASE.read_text(encoding='utf-8')
    source=once(source,"scope='swap_agreed_same_formula_winner_to_top1'","scope='swap_pairwise_dominant_same_formula_candidate_to_top1'")
    source=once(source,"minimum_standardized_margin=.1","minimum_standardized_advantage=.1")
    start=source.index('            go=sorted(range(len(common))')
    end=source.index('\n    return final, dict(',start)
    new='''            if 0 in common:
                lead=common.index(0)
                advantages=[dict(index=i, gl=glz[j]-glz[lead], ice=icez[j]-icez[lead])
                            for j,i in enumerate(common)]
                eligible=[d for d in advantages if 0<d['index']<config['maximum_winner_rank']
                          and d['gl']>=config['minimum_standardized_advantage']
                          and d['ice']>=config['minimum_standardized_advantage']
                          and gl[d['index']]>0 and ice[d['index']]>0]
                winner=min(eligible,key=lambda d:(-(d['gl']+d['ice'])/2,d['index'])) if eligible else None
                if winner:
                    index=winner['index'];final[0],final[index]=final[index],final[0]
                decisions.append(dict(formula=forms[0],slots=common,gl=glz,ice=icez,
                    original_leader_slot=lead,pairwise_advantages=advantages,
                    eligible_candidates=eligible,promoted_from=winner['index'] if winner else None))'''
    source=source[:start]+new+source[end:];ast.parse(source);MODULE.write_text(source,encoding='utf-8')
    builder=BUILDER.read_text(encoding='utf-8')
    builder=once(builder,"MODULE=ROOT/'scripts/evidence_early_overlay_20261114.py'","MODULE=ROOT/'scripts/evidence_pairwise_overlay_20261114.py'")
    builder=once(builder,"    for branch,arm in ARMS.items():","    for branch,arm in {'dual_evidence_agreement': ARMS['dual_evidence_agreement']}.items():")
    builder=once(builder,"out=ROOT/'submission/optimization_20261114'/branch","out=ROOT/'submission/optimization_20261114'/branch/'revision2'")
    builder=once(builder,"GL and ICE agree on a same-formula candidate at original rank<=10, with both standardized winner margins>=.1 and common coverage>=.8: swap it to top1; strong library/AB rows remain",
        "Same-formula candidate at original rank2-10 beats current leader in BOTH GL and ICE standardized scores by at least.1, common coverage>=.8: promote maximum mean pairwise advantage to top1; strong library/AB rows remain")
    ast.parse(builder)
    exec(compile(builder,str(BUILDER),'exec'),dict(__name__='__main__',__file__=str(BUILDER)))


if __name__=='__main__':main()
