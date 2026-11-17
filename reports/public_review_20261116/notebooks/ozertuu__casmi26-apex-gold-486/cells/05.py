# CODE CELL 01 · Deep EDA
from pathlib import Path
from collections import Counter, defaultdict
from html import escape
import gc, math, re, warnings
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from IPython.display import HTML, display
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from math import ceil

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError as exc:
    raise RuntimeError('Reading train.parquet requires pyarrow') from exc

SHOW_INTERACTIVE_PLOTLY = False  # Static PNG charts survive Kaggle Save Version.

SEED = 26
RNG = np.random.default_rng(SEED)
META_SAMPLE_PER_ROW_GROUP = 1100     # sampled per row group; not a probability-weighted estimate of the full population
SPECTRAL_ROW_GROUPS = 5             # diagnostic sample containing complete peak arrays
SPECTRAL_RANDOM_PER_GROUP = 450
SPECTRAL_HEAD_PER_GROUP = 140
MAX_MOLS_FOR_RDKIT = 3000
MZ_TOL_DA = 0.02                     # illustrative absolute mass tolerance; not a universally valid threshold

INK, MUTED, TEAL, BLUE, CORAL, GOLD = '#EAF4FF','#AFC2D8','#57D8C9','#80B5F9','#FF9C8F','#F6CE8F'
px.defaults.template = 'plotly_dark'
px.defaults.color_discrete_sequence = [TEAL,BLUE,CORAL,GOLD,'#8C6BC0','#47A3B4','#99A3AC']

def style(fig,title,subtitle='',height=435):
    fig.update_layout(title={'text':title + (f'<br><sup>{subtitle}</sup>' if subtitle else ''), 'x':0.02},
        font=dict(family='Arial, sans-serif',color=INK,size=13),paper_bgcolor='#0F192C',plot_bgcolor='#13233B',
        height=height,margin=dict(l=62,r=25,t=90,b=66),hoverlabel=dict(bgcolor='#182A44',font=dict(color='#EDF8FF')),legend_title_text='')
    fig.update_xaxes(gridcolor='#2D435D',zeroline=False)
    fig.update_yaxes(gridcolor='#2D435D',zeroline=False)
    return fig

def note(title,body,color=TEAL):
    display(HTML(f'<div style="padding:16px 20px;border-left:5px solid {color};background:#132741;margin:14px 0;border-radius:0 12px 12px 0">'
                 f'<b style="color:{INK}">{escape(str(title))}</b><div style="margin-top:7px;color:#D0DFEA;line-height:1.65">{escape(str(body))}</div></div>'))


# Plotly-first visualization; static fallback is used only if requested.
# Matplotlib provides an optional fallback when the notebook frontend does not render Plotly.
# The original Plotly figures remain available in interactive mode.
def show_chart(fig, *, interactive=None):
    if interactive is None:
        interactive=SHOW_INTERACTIVE_PLOTLY
    if interactive:
        return fig.show()
    from matplotlib import pyplot as _plt
    from matplotlib.colors import to_rgba
    traces=[t for t in fig.data if getattr(t,'visible',None) is not False]
    if not traces: return
    title_html=str(getattr(getattr(fig.layout,'title',None),'text','') or '')
    parts=re.split(r'<br\s*/?>',title_html,maxsplit=1,flags=re.I)
    main=re.sub(r'<[^>]+>','',parts[0]); subtitle=re.sub(r'<[^>]+>','',parts[1]) if len(parts)>1 else ''
    _fig,_ax=_plt.subplots(figsize=(10.2,5.0),dpi=115)
    _fig.patch.set_facecolor('#0F192C');_ax.set_facecolor('#13233B')
    _ax.spines['top'].set_visible(False); _ax.spines['right'].set_visible(False)
    _ax.spines['bottom'].set_color('#3B5570');_ax.spines['left'].set_color('#3B5570')
    _ax.tick_params(colors='#C2D7E9',labelsize=9)
    _ax.grid(axis='y',color='#2E435B',linewidth=.7,zorder=0)
    def val(x):
        if x is None:return []
        try:return list(x)
        except TypeError:return [x]
    def nums(x):
        return pd.to_numeric(pd.Series(val(x)),errors='coerce').to_numpy(dtype=float)
    def color(t,i):
        for attr in ('marker','line'):
            try:c=getattr(getattr(t,attr,None),'color',None)
            except Exception:c=None
            if isinstance(c,str) and c.startswith('#'): return c
        return [TEAL,BLUE,CORAL,GOLD,'#8765A1'][i%5]
    ttypes=[str(getattr(t,'type','')) for t in traces]
    if 'heatmap' in ttypes or 'image' in ttypes:
        t=next(t for t in traces if t.type in ('heatmap','image'))
        z=np.asarray(t.z,dtype=float) if t.type=='heatmap' else np.asarray(t.z,dtype=float).mean(axis=-1)
        im=_ax.imshow(z,origin='upper',aspect='auto',interpolation='nearest',cmap='YlGnBu')
        xx=val(t.x);yy=val(t.y)
        if xx:
            _ax.set_xticks(np.arange(len(xx)));_ax.set_xticklabels(list(map(str,xx)),rotation=38,ha='right',fontsize=8)
        if yy:
            _ax.set_yticks(np.arange(len(yy)));_ax.set_yticklabels(list(map(str,yy)),fontsize=8)
        _fig.colorbar(im,ax=_ax,shrink=.72,pad=.02)
        if z.size<=120:
            # Render values directly in small matrices without relying on tooltips.
            for r in range(z.shape[0]):
                for col in range(z.shape[1]):
                    if np.isfinite(z[r,col]):
                        _ax.text(col,r,f'{z[r,col]:.1f}' if np.nanmax(z)>1 else f'{z[r,col]:.2f}',
                                 ha='center',va='center',fontsize=7,
                                 color='#FFFFFF' if z[r,col]>np.nanmedian(z) else '#173047')
        _ax.grid(False)
    elif 'box' in ttypes:
        datasets=[];labels=[]
        for i,t in enumerate(traces):
            if t.type!='box':continue
            y=nums(t.y);y=y[np.isfinite(y)]
            if not len(y):continue
            datasets.append(y);labels.append(str(t.name or f'Group {i+1}'))
        if datasets:
            _ax.boxplot(datasets,tick_labels=labels,showfliers=False,patch_artist=True,
                        boxprops=dict(facecolor='#B8DBE0',edgecolor=BLUE),
                        medianprops=dict(color=CORAL,linewidth=2),
                        whiskerprops=dict(color=BLUE),capprops=dict(color=BLUE))
            _ax.tick_params(axis='x',rotation=30)
    elif 'bar' in ttypes:
        bars=[(i,t) for i,t in enumerate(traces) if t.type=='bar']
        hor=all(getattr(t,'orientation',None)=='h' for _,t in bars)
        stack=str(fig.layout.barmode or '') in ('stack','relative')
        labs=val(bars[0][1].y if hor else bars[0][1].x)
        n=len(labs);pos=np.arange(n);tot=np.zeros(n)
        width=(.76 if stack else min(.78/max(1,len(bars)),.76))
        for j,(i,t) in enumerate(bars):
            values=nums(t.x if hor else t.y)
            if len(values)!=n:continue
            off=(j-(len(bars)-1)/2)*width if not stack else 0
            kw=dict(color=color(t,i),alpha=.92,label=str(t.name or '') or None,zorder=3)
            if hor:_ax.barh(pos+off,values,height=width,left=tot if stack else None,**kw)
            else:_ax.bar(pos+off,values,width=width,bottom=tot if stack else None,**kw)
            if stack:tot+=np.nan_to_num(values)
        shown=[str(z) for z in labs]
        if hor:
            _ax.set_yticks(pos);_ax.set_yticklabels(shown,fontsize=9)
            _ax.grid(axis='x',color='#2E435B',linewidth=.7)
        else:
            _ax.set_xticks(pos);_ax.set_xticklabels(shown,rotation=35 if any(len(x)>13 for x in shown) else 0,ha='right' if any(len(x)>13 for x in shown) else 'center',fontsize=9)
        if len(bars)>1 and any(t.name for _,t in bars):_ax.legend(frameon=False,fontsize=9)
    elif 'histogram' in ttypes:
        for i,t in enumerate(traces):
            if t.type!='histogram':continue
            x=nums(t.x);x=x[np.isfinite(x)]
            if len(x):
                bins=getattr(t,'nbinsx',None) or 42
                _ax.hist(x,bins=int(bins),color=color(t,i),alpha=.72,edgecolor='#FFFFFF',linewidth=.45,label=str(t.name or ''))
        if len(traces)>1:_ax.legend(frameon=False,fontsize=9)
    else:
        for i,t in enumerate(traces):
            if t.type not in ('scatter','scattergl'):continue
            x=val(t.x);y=val(t.y)
            if not len(x) or len(x)!=len(y):continue
            # Plotly stick plots encode empty segments as None.
            try:xx=pd.to_numeric(pd.Series(x),errors='raise').to_numpy(dtype=float)
            except Exception:xx=np.asarray(x,dtype=object)
            yy=nums(y)
            mode=str(t.mode or 'lines')
            label=str(t.name or '')
            if 'markers' in mode:
                _ax.scatter(xx,yy,s=20 if len(yy)>400 else 29,color=color(t,i),alpha=.6,
                            edgecolors='none',label=label if len(traces)<7 else None,zorder=3)
            if 'lines' in mode:
                _ax.plot(xx,yy,color=color(t,i),linewidth=1.8,
                         linestyle='--' if getattr(t.line,'dash',None)=='dash' else '-',
                         alpha=.9,label=label if 'markers' not in mode and len(traces)<7 else None)
        if len(traces)>1 and len(traces)<7 and any(t.name for t in traces):_ax.legend(frameon=False,fontsize=9,loc='best')
    xlab=str(getattr(getattr(fig.layout,'xaxis',None),'title',None).text or '') if getattr(getattr(fig.layout,'xaxis',None),'title',None) else ''
    ylab=str(getattr(getattr(fig.layout,'yaxis',None),'title',None).text or '') if getattr(getattr(fig.layout,'yaxis',None),'title',None) else ''
    _ax.set_xlabel(re.sub('<[^>]+>','',xlab),fontsize=10,color=INK,labelpad=8)
    _ax.set_ylabel(re.sub('<[^>]+>','',ylab),fontsize=10,color=INK,labelpad=9)
    if main:_fig.suptitle(main,color=INK,fontweight='bold',fontsize=14,x=.11,ha='left',y=.99)
    if subtitle:_ax.set_title(subtitle,color=MUTED,fontsize=9,loc='left',pad=14)
    _fig.tight_layout(rect=[0,0,1,.91] if main else None)
    _plt.show();_plt.close(_fig)

