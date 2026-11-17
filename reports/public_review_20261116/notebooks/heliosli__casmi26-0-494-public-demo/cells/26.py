# ===== heliosli overlay cvjoint after FREEZE: a joint ranker over the pipeline's own evidence and ours re-judges rank 1 (reports/c3_design_v0.md 36) =====
# For every molecule, all PubChem-tier isomers of the rank-1 formula plus the natural-product table and the list's own
# members are scored by (1) FPNet -- the fold-safe model 0 of dmitriigluzdov/casmi26-fold-safe-fpnet, which like the
# public FPNet has never seen a hidden molecule -- (2) the pipeline's channel score z(FPNet) + 0.25 x documentation,
# (3) RT (heliosli/casmi26-rt-np) and natural-product membership; a LightGBM ranker (heliosli/casmi26-joint-ranker) fitted
# on structures neither RT nor FPNet model 0 had seen orders them (in-domain top 1 0.461 against 0.324 for the channel
# score), and PX v2 re-scores its 20 best (joint + 1.0 x z; 0.678 in-domain).
# Where its best differs from the list's rank 1: comb margin >= 2.66 -> it becomes rank 1 and the old rank 1 rank 2 (in-domain, such disagreements:
# joint right 91%%, channel score 0.8%%); margin >= 0.58 -> it is placed at rank 2.
# The list stays at 25; rank 1 with a spectral-library match (library_max >= 0.9) is never moved. Time guard 7.9 h after
# NB_T0 (at most 4,500 s). Any failure leaves the submission unchanged.
CVDEEP_SELFTEST = '[{"molecule_id":"xb_ADNMXQSCHOROTR","rank1":"C1[CH]2[CH]([CH]([CH]([CH](O2)OC3=CC(=C(C(=C3)O)C(=O)CCC4=CC=C(C=C4)O)O)O)OC(=O)C=CC5=CC(=C(C=C5)O)O)OC(=O)C6=CC(=C(C(=C6C7=C(C(=C(C=C7C(=O)O1)O)O)O)O)O)O","spectra":[{"precursor_mz":899.167175292969,"ms2_mzs":[125.0236969,161.0233765,167.0340881,167.2789459,179.0326385,249.0393677,273.0766602,275.0164795,300.9686584,300.9983521,304.2766418,305.4375305,347.7892456,382.8354797,627.1387329],"ms2_normalized_intensities":[0.01284626282623052,0.01937618962434291,0.0502115912499755,0.008700393169284145,0.009762623468259707,0.012403055103265061,0.07779800702255449,0.06390881016621788,0.02113921866491532,1.0,0.01889791884672393,0.009819732882379322,0.008864771128093469,0.011243335893999932,0.009297757280702855],"adduct":"[M-H]-","ionization_mode":"negative","instrument_type":"Orbitrap","collision_energy_ev":[]},{"precursor_mz":899.166931152344,"ms2_mzs":[73.01353455,96.05818176,100.5762787,107.1439514,123.0428772,149.4691467,161.0233002,167.0341644,208.412735,249.0375671,257.0079651,273.0756531,275.0187073,300.9986572,301.0346375,328.1141052,616.1881104],"ms2_normalized_intensities":[0.01288875361064257,0.0123511905364113,0.017635349298938365,0.013530604840844987,0.02529210764622538,0.012410351985746268,0.021236926054992254,0.11945399577371867,0.013173248693913401,0.02125481883888743,0.017362057981754286,0.021961446499477913,0.05511446800099622,1.0,0.017882764369784355,0.013291511974059199,0.01491488104247126],"adduct":"[M-H]-","ionization_mode":"negative","instrument_type":"Orbitrap","collision_energy_ev":[]},{"precursor_mz":899.167056741395,"ms2_mzs":[93.35707092,128.332428,161.0231171,167.0340424,226.5080872,249.0406494,273.0767517,275.0198059,284.9516602,300.9676514,300.9984436,301.0380249,304.2669678,304.3037415,421.2789307],"ms2_normalized_intensities":[0.01267355861666751,0.012519298715443416,0.019132225689265075,0.07220134197336306,0.01461561114626149,0.015058415915083926,0.08298537262370563,0.06640287950635415,0.012356259210746456,0.017042705879617648,1.0,0.029391562082982853,0.01633214994384004,0.026188227587739532,0.014495505211835406],"adduct":"[M-H]-","ionization_mode":"negative","instrument_type":"Orbitrap","collision_energy_ev":[]},{"precursor_mz":899.167114257813,"ms2_mzs":[63.33416367,78.36428833,85.88871765,103.1158142,103.5894318,131.12323,161.0235443,167.0337219,215.9610443,272.9996033,273.0757446,275.0194397,300.9985046,304.2871094],"ms2_normalized_intensities":[0.018630213986712434,0.018094457488745334,0.01796781379228379,0.02137614291992582,0.01717866124812193,0.01726380322977448,0.02011358040313455,0.033745594352721425,0.021448449754555333,0.020517633797018795,0.04355995034489258,0.09222131749980939,1.0,0.08283388449771735],"adduct":"[M-H]-","ionization_mode":"negative","instrument_type":"Orbitrap","collision_energy_ev":[]}],"pairs":[{"j":3,"smiles":"CCOc1cc(OC2OC3COC(=O)c4cc(O)c(O)c(O)c4-c4c(cc(O)c(O)c4O)C(=O)OC3C(OC(=O)c3cc(O)c(O)c(O)c3)C2O)cc2c1C(=O)CC(c1ccccc1)O2","z":0.013916015625,"z32":0.016120821237564087},{"j":4,"smiles":"CCOc1c(O)cc(C(=O)OC2C(O)C(Oc3cc(O)c4c(c3)OC(c3ccccc3)CC4=O)OC3COC(=O)c4cc(O)c(O)c(O)c4-c4c(cc(O)c(O)c4O)C(=O)OC32)cc1O","z":0.02685546875,"z32":0.025934666395187378},{"j":6,"smiles":"CCOc1cc(C(=O)OC2C(O)C(Oc3cc(O)c4c(c3)OC(c3ccccc3)CC4=O)OC3COC(=O)c4cc(O)c(O)c(O)c4-c4c(cc(O)c(O)c4O)C(=O)OC32)cc(O)c1O","z":0.0244140625,"z32":0.021322593092918396},{"j":7,"smiles":"COc1cc(C(=O)OC2C(O)C(Oc3cc(O)c4c(c3)OC(c3ccccc3)CC4=O)OC3COC(=O)c4cc(O)c(O)c(O)c4-c4c(cc(O)c(O)c4O)C(=O)OC32)cc(OC)c1O","z":0.0250244140625,"z32":0.02823135256767273},{"j":8,"smiles":"COc1cc(C(=O)OC2C(O)C(Oc3cc(OC)c4c(c3)OC(c3ccccc3)CC4=O)OC3COC(=O)c4cc(O)c(O)c(O)c4-c4c(cc(O)c(O)c4O)C(=O)OC32)cc(O)c1O","z":0.028076171875,"z32":0.028679177165031433},{"j":9,"smiles":"COc1c(O)c(O)cc2c1-c1c(cc(O)c(O)c1OC)C(=O)OC1C(COC2=O)OC(Oc2cc(O)c3c(c2)OC(c2ccccc2)CC3=O)C(O)C1OC(=O)c1cc(O)c(O)c(O)c1","z":0.0205078125,"z32":0.022146165370941162}]},{"molecule_id":"xb_AEQDXSFIHGWHDV","rank1":"CC1=CC2(O)OC3(CC2=C(C)C)C(C)CCC13","spectra":[{"precursor_mz":235.168866784183,"ms2_mzs":[53.03888702,53.97240448,55.01813507,55.04637909,55.05449677,55.0610733,57.03374481,57.0700531,59.04941559,59.8602829,61.31585312,65.03865814,67.05433655,67.05858612,69.03361511,69.06996155,69.07335663,71.04912567,77.03889465,79.054245,81.06989288,82.60015106,83.04915619,83.07985687,83.0855484,87.04415131,91.04760742,91.054245,91.06102753,93.06990051,95.04932404,95.08551788,97.02828979,97.05752563,97.06480408,97.09035492,97.10116577,97.11670685,103.054306,104.3113708,105.0444717,105.0698853,105.0872269,107.0488968,107.0854874,107.1032639,109.0647888,109.1011887,109.1097641,111.0438385,111.0802155,115.0541077,117.0698547,119.0492401,119.0600586,119.0854797,121.0647659,121.1011353,123.080307,123.1166382,125.0589752,125.0957718,128.0622711,129.0697479,131.0854645,133.0647736,133.101059,135.080307,135.1164246,137.0596313,137.0960541,139.0753021,142.0778961,143.0853424,145.1012573,147.0803375,147.1167908,149.096344,149.1323242,151.0753021,151.1115723,153.0908508,157.1010895,159.1165924,160.0891266,161.0960388,161.1321869,165.0911255,167.1069489,171.116684,175.1112976,175.1483002,177.1287231,179.1065826,184.1244202,189.127121,189.1635284,193.1233673,199.1480255,217.1584625,217.6047668,217.6251984,235.1688843],"ms2_normalized_intensities":[0.041188984359570066,0.004266495288835355,0.051944638536761574,0.006053771347718579,1.0,0.007968733656452376,0.01034249538401368,0.02491410805890791,0.029198980195112318,0.004030964718808146,0.004629570244689504,0.022964850693469922,0.3659205725512209,0.00984311067290101,0.04397382742253199,0.44965160835126455,0.0057266714840542195,0.0071088798209608004,0.00839711732710029,0.3967048809263937,0.46592505535285494,0.004339695094775522,0.06936709175320423,0.006314484939085872,0.3151792535940375,0.060134818634941425,0.010950606307042027,0.548694140393551,0.00864800245709504,0.41378493986549,0.055668161583559424,0.5145295397137244,0.004164104993223823,0.00661985092979153,0.28661243776052225,0.005727411004206037,0.4433887446596189,0.004459625772958441,0.016973409677394205,0.005162455675486741,0.019173705964594962,0.7737695034355152,0.004739663832918836,0.007201630976419164,0.89523036402948,0.00554225688191261,0.15879717336618124,0.25671535054209416,0.008179690281448477,0.016954591249701147,0.03958654925624474,0.015636698325641105,0.11074873507032151,0.06347249590051039,0.04116995275516887,0.7052151874720637,0.09481634643870646,0.1566244438727248,0.22354089679421213,0.08591408710668288,0.006745664269991996,0.05148229277112504,0.01585737783878286,0.0702863503238012,0.04833651514797144,0.09782640967869356,0.4774258778495026,0.6705331155601293,0.03782782111152691,0.06874165971507573,0.06509502646152326,0.17231411965572083,0.007423495142981882,0.059168531252273886,0.03550779666401597,0.25243451861207267,0.16296739703849233,0.04416240150830033,0.015084280325178532,0.11982429691479299,0.015666587730377022,0.31971315266993067,0.07985542639889398,0.055981153717217076,0.004336401514634723,0.1930513813525847,0.2553080919117265,0.07862155149114874,0.0048923582484524586,0.02823372215140695,0.06686134369705096,0.009478780512286775,0.005076059216185383,0.06763111463888109,0.008212723535065903,0.005988605258293833,0.1566366416409393,0.009086219664751406,0.0697552926294945,0.12663589775574058,0.00970787339950988,0.00859067416463966,0.026225148874491948],"adduct":"[M+H]+","ionization_mode":"positive","instrument_type":"Orbitrap","collision_energy_ev":[]}],"pairs":[{"j":2,"smiles":"C=C1C2CCC(C(=O)O)C23CCC(C3)C1(C)C","z":0.135986328125,"z32":0.12780849635601044},{"j":3,"smiles":"CC1=C(C(CCC1)(C)C)C=CC(=CC(=O)O)C","z":0.055206298828125,"z32":0.047474801540374756},{"j":4,"smiles":"CC1=CCCC(=CCOC(=O)C(=CCC1)C)C","z":0.1365966796875,"z32":0.1271529346704483},{"j":5,"smiles":"C=CC1(C)CCC2C(C)C(=O)OC2C1C(=C)C","z":0.201171875,"z32":0.19538559019565582},{"j":6,"smiles":"CC(=CCCC1(C)C2CC=C(C)C1C2)C(=O)O","z":0.099609375,"z32":0.08689242601394653},{"j":7,"smiles":"C=C1CCC2(O)CC1C(C)C(=O)C2C=C(C)C","z":0.0826416015625,"z32":0.07878729701042175},{"j":8,"smiles":"CC1=CCC(C)(C)C=CC(=O)C(C)=CC(O)C1","z":0.0194091796875,"z32":0.020659074187278748},{"j":9,"smiles":"CC1(C)CCCC2(C)C3COC(=O)C3=CCC12","z":0.05892181396484375,"z32":0.055322691798210144}]},{"molecule_id":"xb_AFWKBSMFXWNGRE","rank1":"COc1cc(C=CC(C)=O)ccc1O","spectra":[{"precursor_mz":193.085852176167,"ms2_mzs":[64.74906921,69.03387451,71.04923248,85.41819763,91.05438995,95.04909515,95.65985107,103.0544434,105.069931,107.0487289,107.9596481,115.0542145,115.0792999,117.0698547,119.0492477,119.0855637,123.0440292,129.0702972,131.0485382,132.0568848,133.0534363,133.0647736,136.0519867,137.0600128,143.0228424,143.0491028,143.0836945,147.080246,151.0753174,151.0862732,151.9506378,157.0634155,160.0518188,161.0596161,163.0394897,165.0917816,169.9599915,175.0384064,175.0752716,177.0538177,178.0624237,193.0432739,193.0525513,193.0858459,193.1413574,194.108551],"ms2_normalized_intensities":[0.0011055039447587162,0.0010501379713396385,0.0062569762711957196,0.0011067088861072645,0.007380292306913473,0.007908534464575075,0.0011578353193572224,0.001267098206226097,0.019341915171751503,0.0019267768016947829,0.010626668295620206,0.30370693485542954,0.0018265385617335656,0.0023038982486683368,0.011519717139118778,0.00639212782192446,0.013843151808317768,0.005868723619306133,0.0015655512644720513,0.001524175220547443,0.0014040811350693413,0.053415298736885594,0.0021207260243670976,0.0013113962697918328,0.0024970703554546103,0.38705820744339475,0.0017082018667433278,0.030895653837220725,0.06329252989300695,0.0014233979278776645,0.0020851714055664526,0.0011560292592677902,0.03913544098442491,0.15789685149877675,0.0074761365175914085,0.002284044984115186,0.0012192949481213116,0.006259945116892938,0.647934980464199,0.0017164148620122603,0.015521689675792729,0.0097701776971006,0.004791794630028595,1.0,0.0050015021110533095,0.001072220574032446],"adduct":"[M+H]+","ionization_mode":"positive","instrument_type":"Orbitrap","collision_energy_ev":[]},{"precursor_mz":193.085823656373,"ms2_mzs":[58.12197113,65.80155182,69.03359985,71.04917145,91.05435181,93.84557343,95.04905701,105.0698776,107.9595871,115.0541916,115.078125,117.070015,119.0491104,119.0852509,123.0438614,123.0798798,129.069809,132.0572052,133.0646973,136.0517883,137.0596466,143.049057,143.0759888,143.0817871,144.0573883,147.0803528,151.0751801,151.9498749,160.0518036,161.0595398,163.0388947,165.0917511,175.0409088,175.0752411,175.1111908,175.1203003,177.0543823,178.0626221,192.9748688,193.0264893,193.0442047,193.0858154,193.1280518,193.1388702,194.4079285],"ms2_normalized_intensities":[0.0010388838678148575,0.0011175524542249632,0.0017884157675291156,0.0027581070946703762,0.0066622395074810254,0.0012819293751192712,0.00806618150484283,0.020929317366893324,0.012808881060233219,0.307321160136463,0.0019240481947778458,0.002289693983541409,0.012098681655501207,0.008997684464442948,0.015433719311725574,0.002202212993699132,0.0025049099983594975,0.0014227030194868375,0.056511911218692354,0.0023510723633110024,0.0014689759352537253,0.4056481155984988,0.0014995245368091895,0.0013303202704150472,0.0011685140888599982,0.03208800374302368,0.06760554456307397,0.0021995798723756146,0.040607868887036346,0.16245455975948228,0.0062915979287821115,0.001537519480965151,0.003401273722416962,0.6322623866295712,0.004792240528610026,0.0021143633354844134,0.0019923101714910962,0.012665848717227618,0.0010762468183880358,0.0012097918685907549,0.007988230965151043,1.0,0.006714862176879631,0.007453368093568896,0.0009715948277305156],"adduct":"[M+H]+","ionization_mode":"positive","instrument_type":"Orbitrap","collision_energy_ev":[]},{"precursor_mz":193.085832202879,"ms2_mzs":[56.69766617,69.03347778,69.69820404,71.04925537,79.05452728,91.05428314,94.61125946,95.0491333,103.0544205,105.0698624,107.049202,107.9598389,115.0344925,115.0541763,116.0616684,117.0699081,119.0491257,119.0856476,123.0439758,123.0805588,129.0695343,131.0487671,132.0569305,133.0647278,135.0439911,135.0797577,136.0519257,137.0599213,143.0218811,143.049057,144.0570679,145.0649261,146.0356903,147.0802612,149.0597076,150.0671692,151.0752563,152.0232086,160.0517273,161.0595703,163.0386963,165.0919495,175.0385895,175.0752258,175.1217957,177.0544281,178.0622101,193.0431213,193.0857544],"ms2_normalized_intensities":[0.0019805366509317184,0.004076809948457763,0.002224242547031371,0.016423992178667367,0.0030160504734486567,0.032573136506735115,0.002031565921887641,0.028805504070688957,0.0035457374959931955,0.12584141338483004,0.012814470805132852,0.02219344193224498,0.010022178108378936,1.0,0.0029153461679600114,0.011037404582212395,0.03560384792371718,0.021835342537660844,0.036063066887217166,0.002695560688133532,0.017777505302582534,0.0038945163711893867,0.01426301199290136,0.18729781155160072,0.003435455568466569,0.0026130575443749577,0.026501681064337087,0.004176517280542208,0.009540314615737918,0.8576968269101556,0.0028121271304846684,0.003547385146246368,0.011379758084449779,0.07192359439919516,0.0032348818709291957,0.008050028730770301,0.07913736349569798,0.0022111047234627877,0.11761530613734547,0.2784262281909107,0.06134046363643056,0.0034587909848236152,0.003091149304584658,0.7004246433117213,0.0025548616893605845,0.017727014728695808,0.04909183409152247,0.002681224108227859,0.5437743956540722],"adduct":"[M+H]+","ionization_mode":"positive","instrument_type":"Orbitrap","collision_energy_ev":[]},{"precursor_mz":193.085787360154,"ms2_mzs":[63.02414703,69.03360748,71.04918671,79.05422974,82.93700409,91.054245,95.04916382,96.8425293,103.0541992,105.0617905,105.0699081,107.0490036,107.9598999,115.0302353,115.0347443,115.0542221,115.0731583,117.0697861,119.0492325,119.0855026,123.0439606,123.0804672,124.8475494,129.0698547,131.0493774,132.0570984,133.0647278,133.0737762,133.1006317,136.0515442,137.0597687,143.0161133,143.0491028,143.0751495,144.0564575,145.064743,146.0351715,147.0802765,149.0599976,150.0674744,151.0754242,151.0886536,160.0518036,161.0596161,161.0755157,163.0388794,165.0907745,171.1997528,175.0296173,175.0752716,175.1110382,177.0546722,178.0623474,193.0858612],"ms2_normalized_intensities":[0.002662713093220832,0.004700574994690338,0.014754154953914583,0.0030065195609781776,0.002225877112971917,0.03229270255442174,0.029223345937022208,0.002265787442230633,0.003401311203895486,0.004818765659294754,0.15263254415741326,0.011889528026905143,0.03077766052699389,0.004900924297667177,0.004470458662503076,1.0,0.01071473304756539,0.009763217983541884,0.0395588438884414,0.023375047874941702,0.032385014355214244,0.003961516042275192,0.002812332148407836,0.01522574608209686,0.00988328070564489,0.017781481130961053,0.190336499442409,0.0032874297980828907,0.002260379873843106,0.027637168115526002,0.005843635252199761,0.004286697869027625,0.9368439430681827,0.008725909249958991,0.004263542215293479,0.00388508564880629,0.003093080702385645,0.06616458961209783,0.0037179348827345096,0.008361779721215205,0.08993116528258419,0.005511116119628672,0.12052659069514644,0.2845844715187898,0.0025079886168575495,0.06622778051846782,0.0028437844477706767,0.0022570215867882756,0.0030856480603055183,0.7463015220826851,0.0043015813836328985,0.01998638112837508,0.053561597280963436,0.554097919040968],"adduct":"[M+H]+","ionization_mode":"positive","instrument_type":"Orbitrap","collision_energy_ev":[]}],"pairs":[{"j":2,"smiles":"Cc1ccc(O)c2c1CC(C)OC2=O","z":0.1376953125,"z32":0.1396273672580719},{"j":3,"smiles":"CC(=O)C=CC1=CC(=C(C=C1)OC)O","z":-0.001953125,"z32":0.0015411972999572754},{"j":4,"smiles":"COc1ccc(C=CC=O)cc1OC","z":-0.0126953125,"z32":-0.011789828538894653},{"j":5,"smiles":"COc1cccc(OC)c1C=CC=O","z":0.025390625,"z32":0.027116864919662476},{"j":6,"smiles":"COc1cc(C=CC(=O)O)ccc1C","z":0.025390625,"z32":0.02699972689151764},{"j":7,"smiles":"COc1cc2c(cc1OC)C(=O)CC2","z":0.0966796875,"z32":0.09907698631286621},{"j":8,"smiles":"CC(=CC1=CC(=C(C=C1)O)OC)C=O","z":0.0078125,"z32":0.006830319762229919},{"j":9,"smiles":"CC(=O)C=CC1=C(C=C(C=C1)OC)O","z":0.013671875,"z32":0.009549200534820557}]}]'

CVJ_K1, CVJ_TOPK, CVJ_B_PX = 120, 20, 1.0                # stage 1 = 120 best by the channel score U 120 best by RT + 0.1 NP; PX on the joint top 20
CVJ_SWAP, CVJ_INS, CVJ_LIB_TAU = 2.66, 0.58, 0.90         # comb-margin thresholds (in-domain: disagreements above 2.66 -> joint right 91%, channel 0.8%)
CVJ_MODE = "swap"                                          # "swap": rank-1 swap above CVJ_SWAP, rank-2 insert above CVJ_INS; "insert": rank 2 only
CVDEEP_RT_FILE = "rt_best.pt"
CVJ_RAW_CHECK = ("CC(=O)Oc1ccccc1C(=O)O", 16551, 431)    # casmi.chem.raw_fingerprint on aspirin, as the offline build saw it
_CVJ_BITS = None


def _cvj_fps(job):
    """(smiles, formula) -> (Morgan count r2 2048 uint8, packed FPNet bits) when the SMILES parses to that formula."""
    import numpy as np
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFingerprintGenerator
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    from casmi import chem
    RDLogger.DisableLog("rdApp.*")
    smi, f0 = job
    m = Chem.MolFromSmiles(smi) if smi else None
    if m is None:
        return None
    try:
        if CalcMolFormula(m) != f0:
            return None
        mc = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048).GetCountFingerprintAsNumPy(m).clip(0, 255).astype(np.uint8)
        raw = chem.raw_fingerprint(smi)
        if raw is None:
            return None
        return mc, np.packbits(raw[_CVJ_BITS].astype(np.uint8))
    except Exception:
        return None


def _cvdeep_entry(smi):
    import px_deploy as X
    try:
        return X.graph_entry(smi)
    except Exception:
        return None



import sys as _cvj_sys                                     # pool workers look the functions up on __main__
if _cvj_sys.modules.get('__main__') is not None:
    setattr(_cvj_sys.modules['__main__'], '_cvj_fps', _cvj_fps)
    setattr(_cvj_sys.modules['__main__'], '_cvdeep_entry', _cvdeep_entry)


def _cvjoint_overlay(work='/kaggle/working', inp='/kaggle/input'):
    import glob
    import json
    import math
    import os
    import pickle
    import shutil
    import sys
    import time
    from multiprocessing import Pool

    import numpy as np
    import pandas as pd
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    t0 = time.monotonic()
    budget = 4500.0
    if "NB_T0" in globals():
        budget = max(0.0, min(budget, 7.9 * 3600 - (time.time() - float(globals()["NB_T0"]))))

    def find(pattern):
        hits = sorted(glob.glob(inp + "/**/" + pattern, recursive=True), key=len)
        return hits[0] if hits else None

    ck_path = os.environ.get("RTNP_CKPT") or find(CVDEEP_RT_FILE)
    rk_path = os.environ.get("CVDEEP_RANKER") or find("deep_ranker.txt")
    db_path = os.environ.get("RTNP_DB") or find("npdb_np.parquet")
    ad_path = os.environ.get("RTNP_ADDUCTS") or find("rt_adducts.json")
    emu = os.environ.get("CVDEEP_EMU")
    pop_hit = find("pc_lsid.npy")                 # every tier array from one dataset root, so rows stay aligned
    pop_tier = os.path.join(os.path.dirname(pop_hit), "casmi26-pubchem-tier", "pc_mass.npy") if pop_hit else None
    tier = None if emu else (pop_tier if pop_tier and os.path.exists(pop_tier) else find("pc_mass.npy"))
    hit = find("px_deploy.py")
    ds = os.environ.get("PXR_DS") or (os.path.dirname(hit) if hit else None)
    rrcfg = find("rr3_config.json")
    v4 = os.environ.get("PXR_V4") or globals().get("V4CODE")
    if not v4:
        if os.path.isdir(os.path.join(work, "v43_v4code", "casmi")):
            v4 = os.path.join(work, "v43_v4code")
        else:
            h = find("casmi26-v4b-models/**/casmi/engine.py")
            v4 = os.path.dirname(os.path.dirname(h)) if h else None
    paths = {k: os.path.join(work, f) for k, f in (("ev", "frozen_candidate_evidence.parquet"), ("pc", "pc_lists.json"), ("eng", "eng_lists.json"))}
    lost = [os.path.basename(p) for p in paths.values() if not os.path.exists(p)]
    if not (ck_path and db_path and ad_path and (emu or tier) and ds and rrcfg and v4) or lost:
        print("[cvjoint] skipped: missing", dict(rt=bool(ck_path), db=bool(db_path), adducts=bool(ad_path), tier=bool(emu or tier), px=bool(ds),
                                                rr=bool(rrcfg), v4=bool(v4), lost=lost))
        return
    code = "/tmp/cvdeepcode"
    os.makedirs(code, exist_ok=True)
    for d in (os.path.dirname(rrcfg), ds):
        for f in os.listdir(d):
            if f.endswith(".py"):
                shutil.copy(os.path.join(d, f), code)
    for d in (v4, code):
        if d in sys.path:
            sys.path.remove(d)
        sys.path.insert(0, d)
    for name in ("px_data", "px_model", "px_deploy"):
        sys.modules.pop(name, None)
    import px_deploy as X
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors
    from rdkit.Chem.rdMolDescriptors import CalcMolFormula
    RDLogger.DisableLog("rdApp.*")
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    # --- PX, with the pxr overlay's self-test ---
    sc = X.Scorer(os.path.join(ds, "pxv2_30000.pt"))
    use_bf16 = sc.dev == "cuda" and torch.cuda.get_device_capability()[0] >= 8

    def zs(queries):
        if not queries:
            return np.zeros(0)
        if use_bf16:
            return sc.z(queries)
        out = []
        with torch.no_grad():
            for i in range(0, len(queries), 32):
                b = X.collate_queries(queries[i:i + 32])
                b = {k: (torch.from_numpy(v).to(sc.dev) if isinstance(v, np.ndarray) else v) for k, v in b.items()}
                x, lp, cu = sc.model.views(b)
                z, _ = sc.model.pair_logit(b, x, lp, cu)
                out += z.float().cpu().tolist()
        return np.asarray(out, np.float64)

    for case in json.loads(CVDEEP_SELFTEST):
        specs = X.query_specs(case["spectra"])
        e1 = X.graph_entry(case["rank1"])
        qs = [X.pair_query(case["molecule_id"], specs, X.graph_entry(p["smiles"]), e1) for p in case["pairs"]]
        if any(q is None for q in qs):
            print("[cvjoint] PX self-test %s: a query could not be built; overlay skipped" % case["molecule_id"])
            return
        got = zs(qs)
        ref = np.asarray([p["z"] if use_bf16 else p["z32"] for p in case["pairs"]])
        tol = 0.3 if use_bf16 else 0.02
        d = float(np.max(np.abs(got - ref)))
        if d > tol or not bool(np.all((np.sign(got) == np.sign(ref)) | (np.abs(ref) < tol))):
            print("[cvjoint] PX self-test failed (max |dz| %.4f): overlay skipped" % d)
            return
    # --- RT (the retrieval model of heliosli/casmi26-rt-np) ---
    D_, K_ = 256, 32

    def fourier(x, lo, hi, n):
        w = torch.exp(torch.linspace(math.log(lo), math.log(hi), n, device=x.device))
        a = x.unsqueeze(-1) * (2 * math.pi / w)
        return torch.cat([torch.sin(a), torch.cos(a)], -1)

    class SpecEnc(nn.Module):
        def __init__(self, n_add):
            super().__init__()
            self.tok = nn.Linear(64 * 2 + 64 * 2 + 1, D_)
            self.cond = nn.Linear(64 * 2 + 3, D_)
            self.add = nn.Embedding(n_add + 1, D_)
            self.cls = nn.Parameter(torch.zeros(1, 1, D_))
            layer = nn.TransformerEncoderLayer(D_, 8, 4 * D_, dropout=0.1, batch_first=True, norm_first=True, activation="gelu")
            self.tf = nn.TransformerEncoder(layer, 4)
            self.out = nn.Sequential(nn.LayerNorm(D_), nn.Linear(D_, D_))

        def forward(self, mz, it, mask, prec, add, mode, ce, tims):
            nl = (prec.unsqueeze(1) - mz).clamp(min=0)
            t = torch.cat([fourier(mz, 0.01, 2000.0, 64), fourier(nl, 0.01, 2000.0, 64), it.unsqueeze(-1)], -1)
            x = self.tok(t)
            c = self.cond(torch.cat([fourier(prec, 0.1, 3000.0, 64), mode.unsqueeze(-1), torch.nan_to_num(ce, nan=-1.0).unsqueeze(-1) / 50.0,
                                     tims.unsqueeze(-1)], -1)) + self.add(add)
            x = torch.cat([self.cls.expand(len(x), -1, -1), c.unsqueeze(1), x], 1)
            pad = torch.cat([torch.zeros(len(x), 2, dtype=torch.bool, device=x.device), ~mask], 1)
            h = self.tf(x, src_key_padding_mask=pad)
            return F.normalize(self.out(h[:, 0]), dim=-1)

    class StructEnc(nn.Module):
        def __init__(self, nb=2048):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(nb, 1024), nn.GELU(), nn.LayerNorm(1024), nn.Dropout(0.1), nn.Linear(1024, 512), nn.GELU(),
                                     nn.LayerNorm(512), nn.Linear(512, D_))

        def forward(self, fp):
            return F.normalize(self.net(torch.log1p(fp.float())), dim=-1)

    class RT(nn.Module):
        def __init__(self, n_add):
            super().__init__()
            self.s = SpecEnc(n_add)
            self.m = StructEnc()
            self.logit_scale = nn.Parameter(torch.tensor(math.log(1 / 0.05)))

    ck = torch.load(ck_path, map_location=dev)
    model = RT(ck["n_add"]).to(dev)
    model.load_state_dict(ck["model"])
    model.eval()
    acode = {a: i + 1 for i, a in enumerate(json.load(open(ad_path))["adducts"])}

    if emu or not tier:
        print("[cvjoint] skipped: needs the PubChem tier (no emulation)")
        return
    NP = pd.read_parquet(db_path)
    np_keys = set(NP.key14)
    np_by_f = NP.groupby("formula").indices
    tdir = os.path.dirname(tier)
    root = os.path.dirname(tdir)
    PM = np.load(tier, mmap_mode="r")
    PO = np.load(os.path.join(tdir, "pc_off.npy"), mmap_mode="r")
    PS = np.load(os.path.join(tdir, "pc_smiles.npy"), mmap_mode="r")
    at_root = lambda f: os.path.join(root, f) if os.path.exists(os.path.join(root, f)) else find(f)
    PK = np.load(at_root("pc_ik14.npy"), mmap_mode="r")
    PN = np.load(at_root("pc_np.npy"), mmap_mode="r")
    assert len(PK) == len(PM) == len(PN), "tier arrays differ in length"
    te_df = globals().get("te")
    if not isinstance(te_df, pd.DataFrame) or "ms2_mzs" not in te_df.columns:
        tp = globals().get("TEST_PATH")
        if tp is None or not os.path.exists(str(tp)):
            hits = sorted(glob.glob(inp + "/**/test.parquet", recursive=True), key=lambda p: ("mass-spectra" not in p.lower(), len(p)))
            tp = hits[0]
        te_df = pd.read_parquet(str(tp))
    cols = ["precursor_mz", "ms2_mzs", "ms2_normalized_intensities", "adduct", "ionization_mode", "instrument_type", "collision_energy_ev"]
    raw, specs = {}, {}
    for r in te_df.itertuples(index=False):
        mid = str(r.molecule_id)
        raw.setdefault(mid, []).append({c: getattr(r, c, None) for c in cols})
        mz = np.asarray(r.ms2_mzs, np.float64)
        it = np.asarray(r.ms2_normalized_intensities, np.float64)
        prec = float(r.precursor_mz)
        ix = np.flatnonzero((mz <= prec + 1.0) & (it > 0))
        if not len(ix):
            continue
        o = ix[np.argsort(-it[ix])[:K_]]
        cev = getattr(r, "collision_energy_ev", None)
        try:
            ce = float(np.nanmean(np.asarray(cev, np.float64))) if cev is not None and np.size(cev) else float("nan")
        except Exception:
            ce = float("nan")
        specs.setdefault(mid, []).append((mz[o].astype(np.float32), np.sqrt(it[o] / it[o].max()).astype(np.float32), prec, acode.get(str(r.adduct), 0),
                                          int(str(r.ionization_mode) == "positive"), ce, int(str(getattr(r, "instrument_type", "")) == "timsTOF")))
    ev = pd.read_parquet(paths["ev"], columns=["molecule_id", "smiles", "metric_key"])
    ev["molecule_id"] = ev["molecule_id"].astype(str)
    ev_key = {m: {s: str(k) for s, k in zip(g["smiles"].astype(str), g["metric_key"]) if isinstance(k, str) and k}
              for m, g in ev.groupby("molecule_id", sort=False)}
    pcl = json.load(open(paths["pc"]))
    engl = json.load(open(paths["eng"]))
    kcache = {}

    def key14(s):
        if s not in kcache:
            try:
                mm = Chem.MolFromSmiles(s)
                kcache[s] = Chem.MolToInchiKey(mm)[:14] if mm is not None else None
            except Exception:
                kcache[s] = None
        return kcache[s]

    # --- FPNet (fold-safe model 0: it never saw the hidden molecules either) and the joint ranker ---
    fp0 = os.environ.get("CVJ_FPNET") or find("casmi26-fold-safe-fpnet/fpnet_fold0.pt") or find("fpnet_fold0.pt")
    jm = os.environ.get("CVJ_MODEL") or find("joint_scn.txt")
    if not (fp0 and jm and not emu):
        print("[cvjoint] skipped: missing", dict(fpnet=bool(fp0), joint=bool(jm), emu=bool(emu)))
        return
    from casmi import chem, fpnet
    from casmi.spectra import merge_spectra
    import lightgbm as lgb
    bits = np.load(os.path.join(os.path.dirname(fp0), "fp_bits.npy"))
    globals()["_CVJ_BITS"] = bits
    raw0 = chem.raw_fingerprint(CVJ_RAW_CHECK[0])
    if raw0 is None or len(raw0) != CVJ_RAW_CHECK[1] or int(raw0.sum()) != CVJ_RAW_CHECK[2]:
        print("[cvjoint] fingerprint code differs from the offline build (%s): overlay skipped" % (None if raw0 is None else (len(raw0), int(raw0.sum()))))
        return
    bank = fpnet.ModelBank([fp0], dev)
    if bank.nbits != len(bits):
        print("[cvjoint] FPNet bits %d != %d: overlay skipped" % (bank.nbits, len(bits)))
        return
    jmeta = json.load(open(jm[:-4] + ".json"))
    feats = jmeta["features"]
    booster = lgb.Booster(model_file=jm)
    LS = np.load(at_root("pc_lsid.npy"), mmap_mode="r")
    LP = np.load(at_root("pc_lpmid.npy"), mmap_mode="r")
    ev_lib = pd.read_parquet(paths["ev"], columns=["molecule_id", "smiles", "library_max"])
    ev_lib["molecule_id"] = ev_lib["molecule_id"].astype(str)
    libmax = {(m, s): float(x) for m, s, x in zip(ev_lib.molecule_id, ev_lib.smiles.astype(str), ev_lib.library_max) if x == x}

    skc = {}

    def skey(s_):
        """the metric's own key (tautomer-canonical InChIKey-14), as the pipeline computes it"""
        if s_ not in skc:
            try:
                skc[s_] = chem.score_key(s_) or key14(s_)
            except Exception:
                skc[s_] = key14(s_)
        return skc[s_]

    def candidates(f0, m0):
        """every tier structure of formula f0 (by mass; formula checked with the fingerprints) + the natural-product table,
        nothing excluded -- the population the joint ranker was fitted on. (smiles, key, documentation, np bits, kind)"""
        out, seen = [], set()
        lo, hi = np.searchsorted(PM, m0 - 5e-5), np.searchsorted(PM, m0 + 5e-5)
        for i in range(lo, hi):
            k = bytes(PK[i]).decode("ascii", "ignore")
            if not k or k in seen:
                continue
            seen.add(k)
            out.append((bytes(PS[PO[i]:PO[i + 1]]).decode("ascii", "ignore"), k, float(np.float32(LS[i]) + np.float32(LP[i])), int(PN[i]), 1))
        for j in np_by_f.get(f0, []):
            k = NP.key14.iat[j]
            if k not in seen:
                seen.add(k)
                out.append((NP.smiles.iat[j], k, 0.0, 0, -1))
        return out, seen

    def fp_logits(rs):
        """engine.py's FPNet queries: every spectrum alone + the spectra of each polarity merged; z = 0.5 (mean + mean)."""
        sp = []
        for s_ in rs[:8]:
            try:
                arr = np.asarray(s_.get("collision_energy_ev"), np.float64).ravel()
                ce = float(np.nanmean(arr)) if arr.size else np.nan
                ce_n = int(np.sum(~np.isnan(arr))) if arr.size else 1
            except Exception:
                ce, ce_n = np.nan, 1
            sp.append(dict(mz=np.asarray(s_["ms2_mzs"], np.float64), it=np.asarray(s_["ms2_normalized_intensities"], np.float64), prec=float(s_["precursor_mz"]),
                           adduct=str(s_["adduct"]), ce=ce, ce_n=max(1, ce_n), mode=1 if str(s_["ionization_mode"]) == "positive" else -1))
        items_s = []
        for s_ in sp:
            pm, pi = fpnet.prep_peaks(s_["mz"], s_["it"], s_["prec"])
            ok = not np.isnan(s_["ce"])
            items_s.append(dict(mz=pm, it=pi, prec=s_["prec"], adduct_ix=chem.adduct_index(s_["adduct"]), ce=s_["ce"] if ok else 0.0,
                                ce_known=1.0 if ok else 0.0, n_merged=min(s_["ce_n"], 8), mode=float(s_["mode"])))
        items_m = []
        for md in (1, -1):
            grp = [s_ for s_ in sp if s_["mode"] == md]
            if not grp:
                continue
            mm, ii = merge_spectra([(s_["mz"], s_["it"]) for s_ in grp])
            prec = float(np.median([s_["prec"] for s_ in grp]))
            pm, pi = fpnet.prep_peaks(mm, ii, prec)
            ces = [s_["ce"] for s_ in grp if not np.isnan(s_["ce"])]
            ads = [s_["adduct"] for s_ in grp]
            items_m.append(dict(mz=pm, it=pi, prec=prec, adduct_ix=chem.adduct_index(max(set(ads), key=ads.count)), ce=float(np.mean(ces)) if ces else 0.0,
                                ce_known=1.0 if ces else 0.0, n_merged=min(sum(s_["ce_n"] for s_ in grp), 8), mode=float(md)))
        zs_ = bank.logits(items_s)
        zm_ = bank.logits(items_m) if items_m else zs_
        return 0.5 * (zs_.mean(0) + zm_.mean(0))

    def joint_features(fz, v, pop, isnp, npb, kind):
        """joint_build.py + joint_train.prep, row for row: stage 1 = 120 best by the channel score U 120 best by RT + 0.1 NP."""
        n = len(fz)
        fzz = (fz - fz.mean()) / (fz.std() + 1e-9)
        chan = fzz + 0.25 * pop
        rtnp = v + 0.1 * isnp
        o_f = np.argsort(np.argsort(-fz)) + 1
        o_c = np.argsort(np.argsort(-chan)) + 1
        o_r = np.argsort(np.argsort(-v)) + 1
        sel = np.array(sorted(set(np.argsort(-chan)[:CVJ_K1].tolist()) | set(np.argsort(-rtnp)[:CVJ_K1].tolist())), dtype=np.int64)
        nb = npb[sel].astype(np.int64)
        Fd = dict(fzz=fzz[sel], fz_gap=fzz[sel] - fzz.max(), lfz_rank=np.log(o_f[sel]), fzz_g1=fzz[sel] - fzz[sel].max(),
                  rt=v[sel], rt_gap=v[sel] - v.max(), lrt_rank=np.log(o_r[sel]), rt_g1=v[sel] - v[sel].max(), ln=np.full(len(sel), np.log(n)),
                  chan=chan[sel], chan_gap=chan[sel] - chan.max(), lchan_rank=np.log(o_c[sel]), chan_g1=chan[sel] - chan[sel].max(),
                  isnp=isnp[sel], in_table=(kind[sel] == -1).astype(np.float64), in_tier=(kind[sel] >= 0).astype(np.float64),
                  np_coconut=(nb >> 0) & 1, np_lotus=(nb >> 1) & 1, np_npatlas=(nb >> 2) & 1)
        return sel, np.stack([np.asarray(Fd[f], np.float64) for f in feats], 1).astype(np.float32)

    sub_path = os.path.join(work, "submission.csv")
    sub = pd.read_csv(sub_path, dtype=str, keep_default_na=False)
    shutil.copy(sub_path, os.path.join(work, "submission_pre_cvjoint.csv"))
    audit = dict(mode=CVJ_MODE, swap=CVJ_SWAP, ins=CVJ_INS, molecules=len(sub), with_candidates=0, candidates=0, scored=0, agree=0, swapped=0, inserted=0,
                 below=0, library_kept=0, failed=0, timed_out=0, budget_s=round(budget, 1))
    # stage A: candidates for every molecule, then both fingerprints in one pool
    work_items = {}
    for mid, smiles in zip(sub["molecule_id"].astype(str), sub["smiles"].astype(str)):
        L = [s for s in smiles.split(";") if s]
        if not L or mid not in specs or mid not in raw:
            continue
        try:
            r0 = Chem.MolFromSmiles(L[0])
            if r0 is None:
                continue
            f0, m0 = CalcMolFormula(r0), Descriptors.ExactMolWt(r0)
            cand, seen = candidates(f0, m0)
            s2k = ev_key.get(mid, {})
            for x in L:                                   # list members outside the tier and the table still compete
                k = s2k.get(x) or key14(x)
                if k and k not in seen:
                    seen.add(k)
                    cand.append((x, k, 0.0, 0, -2))
            work_items[mid] = (L, f0, cand)
        except Exception:
            audit["failed"] += 1
        if time.monotonic() - t0 > budget * 0.35:
            break
    jobs = sorted({(c[0], w[1]) for w in work_items.values() for c in w[2]})
    with Pool(4) as pool:
        fps = dict(zip(jobs, pool.map(_cvj_fps, jobs, chunksize=128)))
    audit["candidates"] = len(jobs)
    # stage B: FPNet, RT, documentation -> joint ranker; its 20 best go to PX
    shortlist = {}
    for mid, (L, f0, cand) in work_items.items():
        if time.monotonic() - t0 > budget * 0.75:
            audit["timed_out"] += 1
            continue
        try:
            keep = [(c, fps.get((c[0], f0))) for c in cand]
            keep = [(c, f) for c, f in keep if f is not None]
            if len(keep) < 2:
                continue
            audit["with_candidates"] += 1
            z = fp_logits(raw[mid]).astype(np.float32)
            cfp = np.unpackbits(np.stack([f[1] for _, f in keep]), axis=1)[:, :len(bits)].astype(np.float32)
            fz = cfp @ z
            S = specs[mid][:8]
            n = len(S)
            mz = np.zeros((n, K_), np.float32)
            itn = np.zeros((n, K_), np.float32)
            mask = np.zeros((n, K_), bool)
            for a, x in enumerate(S):
                mz[a, :len(x[0])], itn[a, :len(x[0])], mask[a, :len(x[0])] = x[0], x[1], True
            with torch.no_grad():
                tt = lambda v_, dt=torch.float32: torch.as_tensor(v_, dtype=dt, device=dev)
                e = model.s(tt(mz), tt(itn), torch.as_tensor(mask, device=dev), tt([x[2] for x in S]), tt([x[3] for x in S], torch.long), tt([x[4] for x in S]),
                            tt([x[5] for x in S]), tt([x[6] for x in S]))
                q = F.normalize(e.mean(0, keepdim=True), dim=-1)
                cf = torch.as_tensor(np.stack([f[0] for _, f in keep]), device=dev)
                v = torch.cat([model.m(cf[i:i + 8192]) @ q.T for i in range(0, len(keep), 8192)]).squeeze(1).float().cpu().numpy()
            pop = np.array([c[2] for c, _ in keep], np.float32)
            npb = np.array([c[3] for c, _ in keep], np.int64)
            kind = np.array([c[4] for c, _ in keep], np.int64)
            isnp = ((npb > 0) | (kind == -1) | np.array([c[1] in np_keys for c, _ in keep])).astype(np.float32)
            sel, Xf = joint_features(fz, v, pop, isnp, npb, kind)
            js = booster.predict(Xf, num_iteration=jmeta.get("best_iteration"))
            o = np.argsort(-js)[:CVJ_TOPK]
            shortlist[mid] = (L, [keep[sel[i]][0] for i in o], js[o])
            audit["scored"] += 1
        except Exception:
            audit["failed"] += 1
    # stage C: PX z against the joint ranker's first, then the decision against the list's own rank 1
    ents = sorted({c[0] for v_ in shortlist.values() for c in v_[1]})
    with Pool(4) as pool:
        ent = dict(zip(ents, pool.map(_cvdeep_entry, ents, chunksize=16)))
    dump = {} if globals().get("CVJ_DUMP") else None
    new_lists = {}
    for mid, (L, cs, js) in shortlist.items():
        if time.monotonic() - t0 > budget:
            audit["timed_out"] += 1
            continue
        try:
            px_specs = X.query_specs(raw.get(mid, []))
            ref = ent.get(cs[0][0])
            qs, idx = [], []
            for j in range(1, len(cs)):
                qq = X.pair_query(mid, px_specs, ent.get(cs[j][0]), ref) if px_specs else None
                if qq is not None:
                    qs.append(qq)
                    idx.append(j)
            zz = np.zeros(len(cs))
            if qs:
                zz[idx] = zs(qs)
            comb = js + CVJ_B_PX * zz
            o = np.argsort(-comb)
            best = cs[o[0]]
            margin = float(comb[o[0]] - comb[o[1]]) if len(o) > 1 else 9.0
            s2k = ev_key.get(mid, {})
            mk = lambda s_: s2k.get(s_) or skey(s_)
            keys = [mk(x) for x in L]
            kb = mk(best[0])
            if kb == keys[0]:
                audit["agree"] += 1
                act = "agree"
            else:
                at = next((x for x, k in zip(L, keys) if k == kb), None)
                best_smi = at if at is not None else best[0]
                rest = [x for x, k in zip(L[1:], keys[1:]) if k != kb and x != best_smi]
                lib = libmax.get((mid, L[0]), 0.0)
                if CVJ_MODE == "swap" and margin >= CVJ_SWAP and lib < CVJ_LIB_TAU:
                    new_lists[mid] = ([best_smi, L[0]] + rest)[:25]
                    audit["swapped"] += 1
                    act = "swap"
                elif margin >= CVJ_INS:
                    new_lists[mid] = ([L[0], best_smi] + rest)[:25]
                    audit["inserted"] += 1
                    act = "insert"
                    if CVJ_MODE == "swap" and margin >= CVJ_SWAP:
                        audit["library_kept"] += 1
                else:
                    audit["below"] += 1
                    act = "below"
            if dump is not None:
                dump[mid] = dict(act=act, best=best[0], best_key=best[1], margin=round(margin, 3), n=len(cs), rank1_key=keys[0])
        except Exception:
            audit["failed"] += 1
    out = [";".join(new_lists.get(mid) or [x for x in smiles.split(";") if x]) for mid, smiles in zip(sub["molecule_id"].astype(str), sub["smiles"].astype(str))]
    res = sub.copy()
    res["smiles"] = out
    assert len(res) == len(sub) and list(res["molecule_id"]) == list(sub["molecule_id"])
    assert res["smiles"].str.split(";").map(len).max() <= 25
    assert all(len(set(x.split(";"))) == len(x.split(";")) for x in res["smiles"])
    res.to_csv(os.path.join(work, "submission.tmp.csv"), index=False)
    os.replace(os.path.join(work, "submission.tmp.csv"), sub_path)
    audit["seconds"] = round(time.monotonic() - t0, 1)
    with open(os.path.join(work, "cvjoint_overlay_audit.json"), "w") as f:
        json.dump(audit, f, indent=1)
    if dump is not None:
        with open(globals()["CVJ_DUMP"], "wb") as f:
            pickle.dump(dump, f)
    print("[cvjoint] done:", json.dumps(audit))


try:
    _cvjoint_overlay(**globals().get("CVJ_DRYRUN_ARGS", {}))
except Exception:
    import traceback

    traceback.print_exc()
    print("[cvjoint] overlay failed; the submission is unchanged")
