# CODE CELL 17 · Deep EDA
v8_pos=v8_metrics[(v8_metrics.same_structure)&v8_metrics.same_adduct&
    v8_metrics.same_instrument&v8_metrics.same_lib&v8_metrics.delta_e.notna()].copy()
_v8_near=v8_pos[v8_pos.delta_e<=5].groupby('key_a').cosine_sym.median()
_v8_far=v8_pos[v8_pos.delta_e>=20].groupby('key_a').cosine_sym.median()
v8_matched=pd.DataFrame({'Close energies':_v8_near,'Distant energies':_v8_far}).dropna()
if len(v8_matched):
    change=(v8_matched['Close energies']-v8_matched['Distant energies']).to_numpy(float)
    _boot_rng=np.random.default_rng(SEED+804)
    boots=np.median(change[_boot_rng.integers(0,len(change),(1600,len(change)))],axis=1)
    ci=np.quantile(boots,[.025,.975])
    fig=go.Figure(go.Histogram(x=change,nbinsx=36,marker_color=TEAL,
          hovertemplate='Cosine difference: %{x:.3f}<br>Structures: %{y}<extra></extra>'))
    fig.add_vline(x=0,line_color=CORAL,line_dash='dash',line_width=2)
    fig.add_vline(x=float(np.median(change)),line_color=BLUE,line_width=3,
                  annotation_text='Median',annotation_position='top')
    fig=style(fig,'Close Versus Distant Energies: Paired Difference',
        f'{len(change)} structures · symmetric cosine · structure-level bootstrap',465)
    fig.update_layout(xaxis_title='Cosine (ΔCE ≤ 5 eV) − Cosine (ΔCE ≥ 20 eV)',
                      yaxis_title='Number of structures')
    show_chart(fig)
    display(pd.DataFrame({'Structures':[len(change)],'Median advantage':[np.median(change)],
      '95% CI · structure bootstrap':[f'{ci[0]:.3f} … {ci[1]:.3f}'],
      'Structures with positive difference':[f'{np.mean(change>0):.1%}']}).round(3))
