# CODE CELL 55 · Deep EDA
from IPython.display import HTML
cards=[
 ('2 539 608','spectra in full train','#EAF3FC'),
 ('10 299','spectra in the targeted subset','#59DFCD'),
 ('221','structures with both energy controls','#88B8F8'),
 ('274','two-candidate isomer queries','#F5CC89'),
]
_html='<div style="display:flex;gap:12px;flex-wrap:wrap;max-width:1030px;margin:12px 0 17px;">'
for value,label,color in cards:
    _html+=f'<div style="flex:1 1 205px;min-width:180px;padding:17px 19px;background:#14243B;border:1px solid #35516A;border-radius:12px;"><div style="color:{color};font-size:27px;font-weight:850;">{value}</div><div style="color:#BBD0E0;font-size:12px;margin-top:6px;line-height:1.55;">{label}</div></div>'
_html+='</div>'
display(HTML(_html))
