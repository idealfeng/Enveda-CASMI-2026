# CODE CELL 44 · Deep EDA
libs=[k for k,_ in lib_count.most_common(8) if k in lib_structures]
if libs:
    jac=np.zeros((len(libs),len(libs)))
    inter=np.zeros_like(jac,dtype=int)
    for i,a in enumerate(libs):
        for j,b in enumerate(libs):
            A=lib_structures[a];B=lib_structures[b]
            inter[i,j]=len(A&B)
            jac[i,j]=inter[i,j]/max(1,len(A|B))
    fig=px.imshow(jac,x=libs,y=libs,text_auto='.3f',color_continuous_scale='Teal',zmin=0,zmax=1)
    fig=style(fig,'Structural Overlap Between Spectral Libraries','Full training set · Jaccard by InChIKey14',575)
    show_chart(fig)
    display(pd.DataFrame([{'Library':lib,'Structures':len(lib_structures[lib]),'Also present in another library':len(lib_structures[lib] & set().union(*(lib_structures[x] for x in libs if x!=lib)))} for lib in libs]))
note('An Important Distinction','Row splits evaluate spectral recognition, while structure splits evaluate transfer to unseen molecules.')