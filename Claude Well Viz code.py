import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

st.set_page_config(
    page_title="Visualizador de Pozo - Vaca Muerta",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
.main-header{font-size:2rem;font-weight:700;margin-bottom:.2rem}
.sub-header{font-size:1rem;color:#555;margin-bottom:1.5rem}
.valve-info{background:#fff3cd;border-left:4px solid #ffc107;padding:8px 14px;
    border-radius:4px;margin-bottom:6px;font-size:.88rem}
.casing-info{background:#d1ecf1;border-left:4px solid #17a2b8;padding:8px 14px;
    border-radius:4px;margin-bottom:6px;font-size:.88rem}
.intervention-box{background:#f8d7da;border-left:4px solid #dc3545;padding:10px 14px;
    border-radius:4px;margin-top:10px;font-size:.9rem}
</style>""", unsafe_allow_html=True)

# ─── DATOS DEL POZO (medidas tipicas Vaca Muerta) ────────────────────────────

WELL = {
    "nombre": "VM-XA-001",
    "formacion": "Vaca Muerta",
    "md_total": 4200,       # m MD
    "tvd_total": 3100,      # m TVD
    "kop": 800,             # m - kick off point
    "build_rate": 6.5,      # deg/30m
    "azimut": 225,          # deg
    "inc_max": 88,          # deg (casi horizontal)
}

CASINGS = [
    {"nombre":"Conductor Casing","od_pulg":20.0,"od_mm":508.0,
     "peso":133.0,"grado":"K-55","zapato":60,"color":"#8B4513",
     "desc":'20" - Cemento hasta superficie'},
    {"nombre":"Surface Casing","od_pulg":13.375,"od_mm":339.7,
     "peso":68.0,"grado":"K-55","zapato":600,"color":"#4A90D9",
     "desc":'13-3/8" - BOP / proteccion acuiferos'},
    {"nombre":"Intermediate Casing","od_pulg":9.625,"od_mm":244.5,
     "peso":53.5,"grado":"P-110","zapato":2800,"color":"#5BA85A",
     "desc":'9-5/8" - Casing de produccion'},
]

TBG = {"od_pulg":3.5,"od_mm":88.9,"id_mm":76.0,"peso":9.3,
       "grado":"L-80","fondo":3800,"color":"#E8A838"}

GLV = [
    {"id":1,"md":850, "tipo":"Unloading Valve","psi":1250,
     "estado":"Cerrada","color":"#FF6B35","nota":"Descarga superficial"},
    {"id":2,"md":1550,"tipo":"Unloading Valve","psi":1050,
     "estado":"Cerrada","color":"#FF6B35","nota":"Descarga intermedia"},
    {"id":3,"md":2300,"tipo":"Unloading Valve","psi":850,
     "estado":"Cerrada","color":"#FF6B35","nota":"Descarga profunda"},
    {"id":4,"md":2900,"tipo":"Operating Valve","psi":720,
     "estado":"ABIERTA - Punto de inyeccion operativo",
     "color":"#00CC44","nota":"Valvula operativa de inyeccion de gas"},
]

PACKER = {"md":3000,"tipo":"Packer Permanente","od":8.0,
          "color":"#9B59B6","nota":"Sello casing-tubing"}

# ─── FUNCIONES DE TRAYECTORIA ─────────────────────────────────────────────────

def calcular_trayectoria(md_total, kop, br, inc_max, az):
    n = 500
    md = np.linspace(0, md_total, n)
    x, y, z = np.zeros(n), np.zeros(n), np.zeros(n)
    az_r = np.radians(az)
    mbe = kop + (inc_max / (br / 30))
    for i in range(1, n):
        dmd = md[i] - md[i-1]; d = md[i]
        inc = (0.0 if d <= kop
               else min((d-kop)*(br/30), inc_max) if d <= mbe
               else inc_max)
        ir = np.radians(inc)
        x[i] = x[i-1] + dmd*np.sin(ir)*np.sin(az_r)
        y[i] = y[i-1] + dmd*np.sin(ir)*np.cos(az_r)
        z[i] = z[i-1] + dmd*np.cos(ir)
    return md, x, y, z


def md_a_xyz(mv, md, x, y, z):
    i = np.clip(np.searchsorted(md, mv), 1, len(md)-1)
    t = (mv - md[i-1]) / (md[i] - md[i-1] + 1e-9)
    return (x[i-1]+t*(x[i]-x[i-1]),
            y[i-1]+t*(y[i]-y[i-1]),
            z[i-1]+t*(z[i]-z[i-1]))


def generar_cilindro(md, x, y, z, r, a, b, nt=14):
    msk = (md >= a) & (md <= b); idx = np.where(msk)[0]
    if len(idx) < 2: return None
    step = max(1, len(idx)//80); idx = idx[::step]
    if idx[-1] != np.where(msk)[0][-1]:
        idx = np.append(idx, np.where(msk)[0][-1])
    cx, cy, cz = x[idx], y[idx], z[idx]
    th = np.linspace(0, 2*np.pi, nt, endpoint=False)
    vx, vy, vz, il, jl, kl = [], [], [], [], [], []
    for s in range(len(cx)):
        tg = (np.array([cx[s+1]-cx[s], cy[s+1]-cy[s], cz[s+1]-cz[s]])
              if s < len(cx)-1
              else np.array([cx[s]-cx[s-1], cy[s]-cy[s-1], cz[s]-cz[s-1]]))
        nm = np.linalg.norm(tg)
        tg = tg/nm if nm > 1e-9 else np.array([0, 0, 1])
        rf = np.array([1,0,0]) if abs(tg[0]) < 0.9 else np.array([0,1,0])
        n1 = np.cross(tg, rf); n1 /= np.linalg.norm(n1)
        n2 = np.cross(tg, n1); n2 /= np.linalg.norm(n2)
        bs = s * nt
        for t in th:
            vx.append(cx[s] + r*(np.cos(t)*n1[0]+np.sin(t)*n2[0]))
            vy.append(cy[s] + r*(np.cos(t)*n1[1]+np.sin(t)*n2[1]))
            vz.append(cz[s] + r*(np.cos(t)*n1[2]+np.sin(t)*n2[2]))
        if s < len(cx)-1:
            nb = (s+1)*nt
            for ti in range(nt):
                t0,t1 = bs+ti, bs+(ti+1)%nt
                t2,t3 = nb+ti, nb+(ti+1)%nt
                il += [t0,t0]; jl += [t1,t2]; kl += [t2,t3]
    return np.array(vx), np.array(vy), np.array(vz), il, jl, kl

# ─── SIDEBAR ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Configuracion del Pozo"); st.markdown("---")
    st.markdown("### Casings")
    sc = st.checkbox('Conductor 20"', value=True)
    ss = st.checkbox('Surface 13-3/8"', value=True)
    si = st.checkbox('Intermediate 9-5/8"', value=True)
    st.markdown("### Completacion")
    st_ = st.checkbox('Tubing 3-1/2"', value=True)
    sv  = st.checkbox("Valvulas GLV", value=True)
    sp  = st.checkbox("Packer", value=True)
    sf  = st.checkbox("Zona productora", value=True)
    st.markdown("### Intervencion")
    mi = st.checkbox("Marcar intervencion", value=False)
    pi, ti = 2900, "Cambio GLV"
    if mi:
        pi = st.slider("Profundidad (m MD)", 500, 3800, 2900, 50)
        ti = st.selectbox("Tipo", ["Cambio GLV","Wire-line",
                                    "Coiled Tubing","Pesca","Caioneo"])
    st.markdown("### Vista")
    oc = st.slider("Transparencia casings", 0.1, 1.0, 0.50, 0.05)
    sl = st.checkbox("Etiquetas 3D", value=True)
    vp = st.selectbox("Vista inicial",
         ["Isometrica","Frontal (X-Z)","Lateral (Y-Z)","Superior (X-Y)"])
    st.markdown("---")
    st.caption("Medidas tipicas Vaca Muerta\nCuenca Neuquina, Argentina")

# ─── HEADER ──────────────────────────────────────────────────────────────────

c1, c2 = st.columns([3,1])
with c1:
    st.markdown(f'<div class="main-header">Visualizador 3D - {WELL["nombre"]}</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header">Gas Lift Continuo | {WELL["formacion"]} | Cuenca Neuquina</div>',
        unsafe_allow_html=True)
with c2:
    st.metric("Prof. Total (MD)", f"{WELL['md_total']} m")
    st.metric("Prof. Total (TVD)", f"{WELL['tvd_total']} m")

# ─── TRAYECTORIA ─────────────────────────────────────────────────────────────

md, x, y, z = calcular_trayectoria(
    WELL["md_total"], WELL["kop"],
    WELL["build_rate"], WELL["inc_max"], WELL["azimut"])

# ─── FIGURA 3D ───────────────────────────────────────────────────────────────

fig = go.Figure()
fig.add_trace(go.Scatter3d(
    x=x, y=y, z=-z, mode="lines",
    line=dict(color="white", width=1, dash="dot"),
    name="Eje pozo", showlegend=False, hoverinfo="skip"))

E = 15  # factor escala visual para radios

def add_tube(f, a, b, r, col, nm, op, nt=14):
    res = generar_cilindro(md, x, y, z, r, a, b, nt)
    if res is None: return
    vx, vy, vz, il, jl, kl = res
    f.add_trace(go.Mesh3d(
        x=vx, y=vy, z=-vz, i=il, j=jl, k=kl,
        color=col, opacity=op, name=nm, showlegend=True,
        lighting=dict(ambient=0.5, diffuse=0.8, specular=0.3, roughness=0.5),
        flatshading=False,
        hovertemplate=f"<b>{nm}</b><extra></extra>"))

# Casings
if sc:
    c = CASINGS[0]
    add_tube(fig, 0, c["zapato"], c["od_mm"]/1000*E, c["color"],
             f'Conductor {c["od_pulg"]}"', oc*0.9)
if ss:
    c = CASINGS[1]
    add_tube(fig, 0, c["zapato"], c["od_mm"]/1000*E, c["color"],
             f'Surface {c["od_pulg"]}"', oc)
if si:
    c = CASINGS[2]
    add_tube(fig, 0, c["zapato"], c["od_mm"]/1000*E, c["color"],
             f'Int. Casing {c["od_pulg"]}"', oc)

# Tubing
if st_:
    add_tube(fig, 0, TBG["fondo"], TBG["od_mm"]/1000*E*0.85,
             TBG["color"], f'Tubing {TBG["od_pulg"]}"', 0.92, 12)

# Zona productora
if sf:
    add_tube(fig, WELL["md_total"]-300, WELL["md_total"],
             CASINGS[2]["od_mm"]/1000*E*0.55,
             "#00BFFF", "Zona Productora", 0.35, 12)

# Valvulas GLV
if sv:
    for v in GLV:
        xi, yi, zi = md_a_xyz(v["md"], md, x, y, z)
        is_open = "ABIERTA" in v["estado"]
        fig.add_trace(go.Scatter3d(
            x=[xi], y=[yi], z=[-zi],
            mode="markers+text" if sl else "markers",
            marker=dict(size=11 if is_open else 9, color=v["color"],
                        symbol="diamond", line=dict(color="white", width=1.5)),
            text=[f"  GLV-{v['id']} ({v['md']}m)"] if sl else None,
            textfont=dict(size=9, color="white"),
            name=f"GLV-{v['id']} @ {v['md']}m",
            hovertemplate=(
                f"<b>{v['tipo']}</b><br>"
                f"Prof: {v['md']} m MD<br>"
                f"P apertura: {v['psi']} psi<br>"
                f"Estado: {v['estado']}<br>"
                f"<i>{v['nota']}</i><extra></extra>")))
    # Linea de gas inyectado
    iop = np.searchsorted(md, GLV[-1]["md"])
    fig.add_trace(go.Scatter3d(
        x=x[:iop], y=y[:iop], z=-z[:iop], mode="lines",
        line=dict(color="#00CC44", width=4, dash="dash"),
        name="Gas inyectado (annulus)", hoverinfo="name"))

# Packer
if sp:
    xp, yp, zp = md_a_xyz(PACKER["md"], md, x, y, z)
    fig.add_trace(go.Scatter3d(
        x=[xp], y=[yp], z=[-zp],
        mode="markers+text" if sl else "markers",
        marker=dict(size=14, color=PACKER["color"], symbol="square",
                    line=dict(color="white", width=2)),
        text=["  Packer"] if sl else None,
        textfont=dict(size=9, color="white"),
        name=f"Packer @ {PACKER['md']}m",
        hovertemplate=(
            f"<b>{PACKER['tipo']}</b><br>"
            f"Prof: {PACKER['md']} m MD | OD: {PACKER['od']}"<extra></extra>")))

# Intervencion
if mi:
    xi, yi, zi = md_a_xyz(pi, md, x, y, z)
    fig.add_trace(go.Scatter3d(
        x=[xi], y=[yi], z=[-zi], mode="markers+text",
        marker=dict(size=18, color="red", symbol="x",
                    line=dict(color="yellow", width=3)),
        text=[f"  INTERVENCION: {ti}"],
        textfont=dict(size=10, color="red"),
        name=f"Intervencion: {ti}",
        hovertemplate=(
            f"<b>ZONA DE INTERVENCION</b><br>"
            f"{ti}<br>Prof: {pi} m MD<extra></extra>")))

# Zapatos de casing
for c in CASINGS:
    xz, yz, zz = md_a_xyz(c["zapato"], md, x, y, z)
    if sl:
        fig.add_trace(go.Scatter3d(
            x=[xz], y=[yz], z=[-zz], mode="markers+text",
            marker=dict(size=5, color=c["color"], symbol="circle"),
            text=[f'  Zapato {c["od_pulg"]}"'],
            textfont=dict(size=8, color=c["color"]),
            name=f'Zapato {c["od_pulg"]}"', showlegend=False,
            hovertemplate=f'<b>Zapato {c["od_pulg"]}"</b><br>Prof: {c["zapato"]} m<extra></extra>'))

# Wellhead
fig.add_trace(go.Scatter3d(
    x=[0], y=[0], z=[0], mode="markers+text",
    marker=dict(size=12, color="white", symbol="square",
                line=dict(color="#555", width=2)),
    text=["  Wellhead/BOP"], textfont=dict(size=10, color="white"),
    name="Wellhead",
    hovertemplate="<b>Wellhead / BOP</b><br>Superficie<extra></extra>"))

# Plano de superficie
xpl = np.linspace(-60,60,4); ypl = np.linspace(-60,60,4)
XPL, YPL = np.meshgrid(xpl, ypl)
fig.add_trace(go.Surface(
    x=XPL, y=YPL, z=np.zeros_like(XPL),
    colorscale=[[0,"#4a7c59"],[1,"#6aaa82"]],
    opacity=0.18, showscale=False, name="Superficie", hoverinfo="skip"))

# Layout
CP = {
    "Isometrica":    dict(eye=dict(x=1.5, y=1.5, z=0.8)),
    "Frontal (X-Z)": dict(eye=dict(x=0, y=2.5, z=0)),
    "Lateral (Y-Z)": dict(eye=dict(x=2.5, y=0, z=0)),
    "Superior (X-Y)":dict(eye=dict(x=0, y=0, z=2.5)),
}
fig.update_layout(
    paper_bgcolor="#0d1117", plot_bgcolor="#0d1117",
    scene=dict(
        bgcolor="#0d1117",
        xaxis=dict(title="Este (m)", showgrid=True, gridcolor="#222",
                   backgroundcolor="#0d1117", color="#aaa"),
        yaxis=dict(title="Norte (m)", showgrid=True, gridcolor="#222",
                   backgroundcolor="#0d1117", color="#aaa"),
        zaxis=dict(title="Prof. TVD (m)", showgrid=True, gridcolor="#222",
                   backgroundcolor="#0d1117", color="#aaa",
                   autorange="reversed"),
        camera=CP[vp],
        aspectmode="manual",
        aspectratio=dict(x=1, y=1, z=2.5)),
    legend=dict(bgcolor="rgba(20,20,30,0.85)", bordercolor="#444",
                borderwidth=1, font=dict(color="white", size=11),
                x=0.01, y=0.99),
    margin=dict(l=0, r=0, t=40, b=0),
    title=dict(
        text=f"Pozo {WELL['nombre']} - Gas Lift Continuo - Vaca Muerta",
        font=dict(color="white", size=16), x=0.5),
    height=720)

# ─── TABS ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(
    ["Vista 3D Interactiva", "Datos del Pozo", "Guia de Uso"])

with tab1:
    st.plotly_chart(fig, use_container_width=True, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "toImageButtonOptions": {"format":"png","filename":"pozo_VM"},
    })
    if mi:
        st.markdown(
            f'<div class="intervention-box">INTERVENCION MARCADA: {ti} '
            f'@ {pi} m MD<br>Verificar presiones y estado de valvulas '
            f'antes de iniciar trabajos.</div>',
            unsafe_allow_html=True)

with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Casings")
        for c in CASINGS:
            st.markdown(
                f'<div class="casing-info"><b>{c["nombre"]}</b><br>'
                f'OD: {c["od_pulg"]}" ({c["od_mm"]} mm) | Grado: {c["grado"]}<br>'
                f'Peso: {c["peso"]} lb/ft | Zapato: {c["zapato"]} m<br>'
                f'<i>{c["desc"]}</i></div>', unsafe_allow_html=True)
        st.markdown("### Tubing")
        st.markdown(
            f'<div class="casing-info" style="border-color:#E8A838">'
            f'OD: {TBG["od_pulg"]}" ({TBG["od_mm"]} mm) | ID: {TBG["id_mm"]} mm<br>'
            f'Grado: {TBG["grado"]} | Fondo: {TBG["fondo"]} m</div>',
            unsafe_allow_html=True)
    with c2:
        st.markdown("### Valvulas Gas Lift")
        for v in GLV:
            bc = "#00CC44" if "ABIERTA" in v["estado"] else "#ffc107"
            st.markdown(
                f'<div class="valve-info" style="border-color:{bc}">'
                f'<b>GLV-{v["id"]} — {v["tipo"]}</b><br>'
                f'Prof: {v["md"]} m | P apertura: {v["psi"]} psi<br>'
                f'Estado: {v["estado"]}<br><i>{v["nota"]}</i></div>',
                unsafe_allow_html=True)
    with c3:
        st.markdown("### Trayectoria")
        df_t = pd.DataFrame({
            "Parametro": ["Prof. MD","Prof. TVD","KOP",
                          "Build Rate","Inc. max","Azimut"],
            "Valor": [f'{WELL["md_total"]} m', f'{WELL["tvd_total"]} m',
                      f'{WELL["kop"]} m', f'{WELL["build_rate"]} /30m',
                      f'{WELL["inc_max"]}', f'{WELL["azimut"]} (SO)'],
        })
        st.dataframe(df_t, hide_index=True, use_container_width=True)
        st.markdown("### Packer")
        st.markdown(
            f'<div class="casing-info" style="border-color:#9B59B6">'
            f'<b>{PACKER["tipo"]}</b><br>'
            f'Prof: {PACKER["md"]} m | OD: {PACKER["od"]}"<br>'
            f'{PACKER["nota"]}</div>', unsafe_allow_html=True)

with tab3:
    st.markdown("""
## Guia de Uso

### Controles 3D
| Accion | Control |
|--------|---------|
| Rotar | Click + arrastrar |
| Zoom | Scroll |
| Info | Hover sobre elemento |

### Uso para Intervenciones
1. Activar "Marcar intervencion" en el panel lateral
2. Ajustar profundidad al punto de trabajo
3. Seleccionar tipo de operacion
4. Compartir pantalla con el equipo
""")

st.markdown("---")
st.markdown("<center><small>Visualizador de Pozo | Gas Lift | Vaca Muerta | Streamlit + Plotly</small></center>",
            unsafe_allow_html=True)
