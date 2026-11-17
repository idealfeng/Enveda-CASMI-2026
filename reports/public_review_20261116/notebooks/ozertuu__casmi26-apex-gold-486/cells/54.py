# CODE CELL 27 · Deep EDA
def v8_ion_power_parts(row):
    mz=np.asarray(row['ms2_mzs'],float)
    it=np.asarray(row['ms2_normalized_intensities'],float)
    power=it**2
    if len(power)==0 or power.sum()<=0:return None
    adduct=str(row['adduct'])
    if adduct not in _V5_ADDUCT_MASSES:return None
    monomer=(float(row['precursor_mz'])+_V5_ADDUCT_MASSES[adduct])/2
    around_mono=abs(mz-monomer)<=.06
    around_isotopes=np.zeros(len(mz),dtype=bool)
    for isotope in range(1,5):
        around_isotopes|=abs(mz-(monomer+isotope*1.003355))<=.06
    around_isotopes &= ~around_mono
    return np.array([power[around_mono].sum(),power[around_isotopes].sum(),
        power[~(around_mono|around_isotopes)].sum()])/power.sum()

_ion_parts=[]
for r in v8_metrics[(~v8_metrics.same_structure)&v8_metrics.dimer&
                    (v8_metrics.cosine_sym>=.8)].itertuples(index=False):
    for key in [r.a,r.b]:
        parts=v8_ion_power_parts(v5_records[key])
        if parts is not None:_ion_parts.append(parts)
if _ion_parts:
    _ion_parts=np.asarray(_ion_parts)
    med=np.median(_ion_parts,axis=0)
    med=med/med.sum() if med.sum()>0 else med
    labels=['Monomer ion','Isotope envelope','Other peaks']
    fig=go.Figure(go.Bar(x=[1],y=[100*med[0]],name=labels[0],marker_color=CORAL,
        text=[f'{med[0]:.1%}'],textposition='inside'))
    for idx,color in [(1,GOLD),(2,TEAL)]:
        fig.add_trace(go.Bar(x=[1],y=[100*med[idx]],name=labels[idx],
                  marker_color=color,text=[f'{med[idx]:.1%}'],textposition='inside'))
    fig=style(fig,'Where Does the Power in Near-Identical Dimer Spectra Come From?',
       f'{len(_ion_parts)} spectra from high-cosine pairs of different structures · median fractions',420)
    fig.update_layout(barmode='stack',yaxis_title='Share of normalized median composition, %',
                      yaxis_range=[0,105],xaxis_visible=False)
    show_chart(fig)
    display(pd.DataFrame({'Component':labels,'Median per-spectrum fraction':np.median(_ion_parts,axis=0)}).round(5))
