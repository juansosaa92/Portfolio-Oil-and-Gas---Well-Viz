"""
Visualizador 3D de Pozo con Gas Lift - Vaca Muerta  v2.1
==========================================================
Correccion v2.1:
  - Boca de pozo arriba, profundidad crece hacia abajo (autorange reversed)
  - Camaras corregidas (up z=+1)

Ejecutar: streamlit run app.py
Dependencias: pip install -r requirements.txt
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd

st.set_page_config(
    page_title="Visualizador Pozo 3D - Vaca Muerta",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
.main-header{font-size:1.8rem;font-weight:700;margin-bottom:.15rem}
.sub-header{font-size:.95rem;color:#666;margin-bottom:1.2rem}
.valve-info{background:#fff3cd;border-left:4px solid #ffc107;
    padding:7px 12px;border-radius:4px;margin-bottom:5px;font-size:.85rem}
.casing-info{background:#d1ecf1;border-left:4px solid #17a2b8;
    padding:7px 12px;border-radius:4px;margin-bottom:5px;font-size:.85rem}
.ibox{background:#f8d7da;border-left:4px solid #dc3545;
    padding:9px 12px;border-radius:4px;margin-top:8px;font-size:.88rem}
</style>""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# DATOS DEL POZO  -  medidas tipicas Vaca Muerta
# ═══════════════════════════════════════════════════════════════════════════

WELL = {
    "nombre"   : "VM-XA-001",
    "formacion": "Vaca Muerta",
    "md_total" : 4200,
    "tvd_total": 3100,
    "kop"      : 800,
    "build_rate": 6.5,
    "azimut"   : 225,
    "inc_max"  : 88,
}

VIS_DEPTH = 3200   # profundidad maxima mostrada en la vista

CASINGS = [
    {
        "nombre": "Conductor Casing",
        "od_pulg": 20.0,  "od_mm": 508.0, "id_mm": 490.0,
        "peso": 133.0,    "grado": "K-55", "zapato": 60,
        "color_ext": "#7B3F00", "color_int": "#A0522D",
        "desc": '20" - Cemento hasta superficie',
    },
    {
        "nombre": "Surface Casing",
        "od_pulg": 13.375, "od_mm": 339.7, "id_mm": 320.0,
        "peso": 68.0,      "grado": "K-55", "zapato": 600,
        "color_ext": "#1A5276", "color_int": "#2E86C1",
        "desc": '13-3/8" - BOP / proteccion acuiferos',
    },
    {
        "nombre": "Intermediate / Production Casing",
        "od_pulg": 9.625, "od_mm": 244.5, "id_mm": 226.0,
        "peso": 53.5,     "grado": "P-110", "zapato": 2800,
        "color_ext": "#1E8449", "color_int": "#27AE60",
        "desc": '9-5/8" - Casing de produccion',
    },
]

TBG = {
    "od_pulg": 3.5,  "od_mm": 88.9, "id_mm": 76.0,
    "peso": 9.3,     "grado": "L-80",
    "fondo": 3150,
    "color_ext": "#B7950B", "color_int": "#D4AC0D",
    "desc": '3-1/2" EUE - Tubing de produccion',
}

FLUID_COLOR       = "#1A6B3C"
ANNULUS_GAS_COLOR = "#D4E6F1"

GLV = [
    {"id":1,"md":850, "tipo":"Unloading Valve","psi":1250,
     "estado":"Cerrada","color":"#E67E22","nota":"Descarga superficial"},
    {"id":2,"md":1550,"tipo":"Unloading Valve","psi":1050,
     "estado":"Cerrada","color":"#E67E22","nota":"Descarga intermedia"},
    {"id":3,"md":2300,"tipo":"Unloading Valve","psi":850,
     "estado":"Cerrada","color":"#E67E22","nota":"Descarga profunda"},
    {"id":4,"md":2900,"tipo":"Operating Valve","psi":720,
     "estado":"ABIERTA - Inyeccion activa",
     "color":"#27AE60","nota":"Valvula operativa de inyeccion"},
]

PACKER = {
    "md": 3000,
    "tipo": "Packer de Produccion Permanente",
    "od": 8.0,
    "color": "#8E44AD",
    "nota": "Sello casing-tubing | aislamiento zona productora",
}

CEMENTO = {"color": "#BDC3C7", "alpha": 0.55}

WELLHEAD_DEPTH = 0

# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## Configuracion del Pozo")
    st.markdown("---")

    st.markdown("### Elementos visibles")
    show_conductor    = st.checkbox('Conductor 20"',            value=True)
    show_surface      = st.checkbox('Surface 13-3/8"',          value=True)
    show_intermediate = st.checkbox('Intermediate 9-5/8"',      value=True)
    show_cemento      = st.checkbox("Cemento",                  value=True)
    show_tubing       = st.checkbox('Tubing 3-1/2"',            value=True)
    show_fluido       = st.checkbox("Columna de fluido",        value=True)
    show_gas_annulus  = st.checkbox("Gas en annulus",           value=True)
    show_valvulas     = st.checkbox("Valvulas GLV (mandriles)", value=True)
    show_packer       = st.checkbox("Packer",                   value=True)

    st.markdown("### Corte transversal")
    corte        = st.checkbox("Aplicar corte (ver interior)", value=True)
    angulo_corte = st.slider("Angulo del corte (deg)", 0, 360, 180, 10) if corte else 360

    st.markdown("### Intervencion")
    mi = st.checkbox("Marcar zona de intervencion", value=False)
    pi, ti = 2900, "Cambio de valvula GLV"
    if mi:
        pi = st.slider("Profundidad (m MD)", 500, 3100, 2900, 50)
        ti = st.selectbox("Tipo", [
            "Cambio de valvula GLV", "Wire-line",
            "Coiled Tubing", "Pesca de herramienta", "Caioneo"])

    st.markdown("### Transparencia")
    op_casing = st.slider("Casings",  0.3, 1.0, 0.90, 0.05)
    op_tubing  = st.slider("Tubing",  0.3, 1.0, 0.92, 0.05)
    op_fluido  = st.slider("Fluidos", 0.1, 1.0, 0.60, 0.05)

    st.markdown("### Vista")
    sl = st.checkbox("Etiquetas 3D", value=True)
    vp = st.selectbox("Vista inicial", [
        "Isometrica / Corte", "Frontal", "Lateral", "Superior"])

    st.markdown("---")
    st.caption("Medidas tipicas Vaca Muerta\nCuenca Neuquina, Argentina")

# ═══════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════

h1, h2 = st.columns([3, 1])
with h1:
    st.markdown(
        f'<div class="main-header">🛢️ Visualizador 3D — {WELL["nombre"]}</div>',
        unsafe_allow_html=True)
    st.markdown(
        f'<div class="sub-header">Gas Lift Continuo | {WELL["formacion"]} '
        f'| Cuenca Neuquina — Seccion vertical con corte 3D</div>',
        unsafe_allow_html=True)
with h2:
    st.metric("Prof. Total (MD)",  f"{WELL['md_total']} m")
    st.metric("Prof. Total (TVD)", f"{WELL['tvd_total']} m")

# ═══════════════════════════════════════════════════════════════════════════
# ESCALA VISUAL
# ═══════════════════════════════════════════════════════════════════════════

ESCALA_R = 28

def r(mm):
    return mm / 1000 * ESCALA_R

R_C0_EXT  = r(CASINGS[0]["od_mm"]); R_C0_INT  = r(CASINGS[0]["id_mm"])
R_C1_EXT  = r(CASINGS[1]["od_mm"]); R_C1_INT  = r(CASINGS[1]["id_mm"])
R_C2_EXT  = r(CASINGS[2]["od_mm"]); R_C2_INT  = r(CASINGS[2]["id_mm"])
R_TBG_EXT = r(TBG["od_mm"]);        R_TBG_INT = r(TBG["id_mm"])

# ═══════════════════════════════════════════════════════════════════════════
# GENERADOR DE CILINDROS VERTICALES
# ═══════════════════════════════════════════════════════════════════════════

NT_FULL = 36

def add_tube_vert(fig, z_top, z_bot, r_ext, r_int,
                  color, name, opacity=1.0):
    """
    Agrega un tubo (anular) vertical a la figura.
    Z crece hacia abajo (profundidad positiva = abajo).
    El corte se aplica limitando el arco angular.
    """
    ang_rad = np.radians(angulo_corte if corte else 360)
    nt      = max(4, int(NT_FULL * (angulo_corte if corte else 360) / 360))
    th      = np.linspace(0, ang_rad, nt, endpoint=(not corte))

    cos_t, sin_t = np.cos(th), np.sin(th)
    is_full = not corte

    for idx_r, (rad, show) in enumerate([(r_ext, True), (r_int, False)]):
        xt = rad * cos_t;  yt = rad * sin_t
        x_v = np.concatenate([xt, xt])
        y_v = np.concatenate([yt, yt])
        z_v = np.concatenate([np.full(nt, z_top), np.full(nt, z_bot)])

        il, jl, kl = [], [], []
        n_loop = nt if is_full else nt - 1
        for i in range(n_loop):
            i0 = i;        i1 = (i+1) % nt
            j0 = i + nt;   j1 = (i+1) % nt + nt
            il += [i0, i0]; jl += [i1, j0]; kl += [j0, j1]

        # Tapas del corte (cara plana del corte transversal)
        if corte and nt > 2:
            for i in range(nt - 2):
                il.append(0);    jl.append(i+1);    kl.append(i+2)
            b = nt
            for i in range(nt - 2):
                il.append(b);    jl.append(b+i+1);  kl.append(b+i+2)

        fig.add_trace(go.Mesh3d(
            x=x_v, y=y_v, z=z_v,
            i=il, j=jl, k=kl,
            color=color, opacity=opacity,
            name=name, showlegend=show,
            lighting=dict(ambient=0.55, diffuse=0.85,
                          specular=0.4,  roughness=0.3, fresnel=0.2),
            flatshading=False,
            hovertemplate=f"<b>{name}</b><extra></extra>",
        ))

# ═══════════════════════════════════════════════════════════════════════════
# CONSTRUCCION DE LA FIGURA
# ═══════════════════════════════════════════════════════════════════════════

fig = go.Figure()

Z0  = WELLHEAD_DEPTH
Z1  = VIS_DEPTH

# ─── TERRENO / SUPERFICIE ────────────────────────────────────────────────────
xs = np.linspace(-R_C0_EXT*2.5, R_C0_EXT*2.5, 4)
ys = np.linspace(-R_C0_EXT*2.5, R_C0_EXT*2.5, 4)
XS, YS = np.meshgrid(xs, ys)
fig.add_trace(go.Surface(
    x=XS, y=YS, z=np.zeros_like(XS),
    colorscale=[[0,"#3a6b49"],[1,"#5a9a69"]],
    opacity=0.25, showscale=False,
    name="Superficie", hoverinfo="skip"))

# ─── CONDUCTOR (20") ─────────────────────────────────────────────────────────
if show_conductor:
    add_tube_vert(fig, Z0, CASINGS[0]["zapato"],
                  R_C0_EXT, R_C0_INT,
                  CASINGS[0]["color_ext"],
                  'Conductor 20"', op_casing)

# ─── CEMENTO conductor → surface ─────────────────────────────────────────────
if show_cemento and show_surface:
    add_tube_vert(fig, CASINGS[0]["zapato"], CASINGS[1]["zapato"],
                  R_C0_INT, R_C1_EXT,
                  CEMENTO["color"], "Cemento", CEMENTO["alpha"])

# ─── SURFACE CASING (13-3/8") ────────────────────────────────────────────────
if show_surface:
    add_tube_vert(fig, Z0, CASINGS[1]["zapato"],
                  R_C1_EXT, R_C1_INT,
                  CASINGS[1]["color_ext"],
                  'Surface Casing 13-3/8"', op_casing)

# ─── CEMENTO surface → intermediate ──────────────────────────────────────────
if show_cemento and show_intermediate:
    add_tube_vert(fig, CASINGS[1]["zapato"], CASINGS[2]["zapato"],
                  R_C1_INT, R_C2_EXT,
                  CEMENTO["color"], "Cemento 2", CEMENTO["alpha"])

# ─── INTERMEDIATE CASING (9-5/8") ────────────────────────────────────────────
if show_intermediate:
    add_tube_vert(fig, Z0, min(CASINGS[2]["zapato"], Z1),
                  R_C2_EXT, R_C2_INT,
                  CASINGS[2]["color_ext"],
                  'Int. Casing 9-5/8"', op_casing)

# ─── GAS EN ANNULUS ──────────────────────────────────────────────────────────
if show_gas_annulus:
    add_tube_vert(fig, Z0, min(GLV[-1]["md"], Z1),
                  R_C2_INT, R_TBG_EXT,
                  ANNULUS_GAS_COLOR, "Gas en annulus", op_fluido)

# ─── TUBING (3-1/2") ─────────────────────────────────────────────────────────
if show_tubing:
    add_tube_vert(fig, Z0, min(TBG["fondo"], Z1),
                  R_TBG_EXT, R_TBG_INT,
                  TBG["color_ext"], 'Tubing 3-1/2"', op_tubing)

# ─── FLUIDO DENTRO DEL TUBING ────────────────────────────────────────────────
if show_fluido:
    add_tube_vert(fig, Z0, min(TBG["fondo"], Z1),
                  R_TBG_INT, 0.0,
                  FLUID_COLOR, "Columna de fluido", op_fluido)

# ─── VALVULAS GLV (mandriles) ────────────────────────────────────────────────
if show_valvulas:
    for v in GLV:
        if v["md"] > Z1:
            continue
        is_open = "ABIERTA" in v["estado"]
        nm = f"GLV-{v['id']} — {v['tipo']} ({v['md']}m)"
        r_mnd = R_TBG_EXT * 1.55
        z_top_v = v["md"] - 25
        z_bot_v = v["md"] + 25

        # Cuerpo del mandrel
        add_tube_vert(fig, z_top_v, z_bot_v,
                      r_mnd, R_TBG_INT, v["color"], nm, 1.0)

        # Capuchon lateral de la valvula
        ang_rad = np.radians(angulo_corte if corte else 360)
        nt_v    = max(4, int(20 * (angulo_corte if corte else 360) / 360))
        th_cap  = np.linspace(0, ang_rad, nt_v, endpoint=(not corte))
        cap_r   = R_TBG_EXT * 0.85
        x_c = np.concatenate([(r_mnd + cap_r*np.cos(th_cap)),
                               (r_mnd + cap_r*np.cos(th_cap))])
        y_c = np.concatenate([cap_r*np.sin(th_cap),
                               cap_r*np.sin(th_cap)])
        z_c = np.concatenate([np.full(nt_v, v["md"] - 12),
                               np.full(nt_v, v["md"] + 12)])
        ilc, jlc, klc = [], [], []
        nl = nt_v if not corte else nt_v - 1
        for i in range(nl):
            i0=i; i1=(i+1)%nt_v; j0=i+nt_v; j1=(i+1)%nt_v+nt_v
            ilc+=[i0,i0]; jlc+=[i1,j0]; klc+=[j0,j1]
        fig.add_trace(go.Mesh3d(
            x=x_c, y=y_c, z=z_c, i=ilc, j=jlc, k=klc,
            color=v["color"], opacity=1.0,
            name=nm+"_cap", showlegend=False, flatshading=False,
            hovertemplate=(
                f"<b>{nm}</b><br>"
                f"Prof: {v['md']} m MD<br>"
                f"P apertura: {v['psi']} psi<br>"
                f"Estado: {v['estado']}<br>"
                f"<i>{v['nota']}</i><extra></extra>"),
        ))

        if sl:
            lbl = "✅ " if is_open else "⭕ "
            lbl += f"GLV-{v['id']}  {v['md']} m"
            fig.add_trace(go.Scatter3d(
                x=[r_mnd * 1.7], y=[0], z=[v["md"]],
                mode="text",
                text=[lbl],
                textfont=dict(size=10,
                              color="#27AE60" if is_open else "#E67E22"),
                showlegend=False, hoverinfo="skip"))

# ─── PACKER ──────────────────────────────────────────────────────────────────
if show_packer and PACKER["md"] <= Z1:
    h_pk     = 90
    z_pk_top = PACKER["md"] - h_pk / 2
    z_pk_bot = PACKER["md"] + h_pk / 2
    add_tube_vert(fig, z_pk_top, z_pk_bot,
                  R_C2_INT * 0.97, R_TBG_EXT * 1.02,
                  PACKER["color"],
                  "Packer — sello casing/tubing", 0.95)
    if sl:
        fig.add_trace(go.Scatter3d(
            x=[R_C2_INT * 1.5], y=[0], z=[PACKER["md"]],
            mode="text",
            text=[f"PACKER  {PACKER['md']} m"],
            textfont=dict(size=10, color="#8E44AD"),
            showlegend=False, hoverinfo="skip"))

# ─── ZAPATOS DE CASING ───────────────────────────────────────────────────────
for c in CASINGS:
    if c["zapato"] > Z1:
        continue
    ang_rad = np.radians(angulo_corte if corte else 360)
    nt_z    = max(4, int(NT_FULL * (angulo_corte if corte else 360) / 360))
    th_z    = np.linspace(0, ang_rad, nt_z, endpoint=(not corte))
    x_v = np.concatenate([r(c["od_mm"])*np.cos(th_z),
                           r(c["id_mm"])*np.cos(th_z)])
    y_v = np.concatenate([r(c["od_mm"])*np.sin(th_z),
                           r(c["id_mm"])*np.sin(th_z)])
    z_v = np.concatenate([np.full(nt_z, c["zapato"]),
                           np.full(nt_z, c["zapato"])])
    il, jl, kl = [], [], []
    nl = nt_z if not corte else nt_z - 1
    for i in range(nl):
        i0=i; i1=(i+1)%nt_z; j0=i+nt_z; j1=(i+1)%nt_z+nt_z
        il+=[i0,i0]; jl+=[i1,j0]; kl+=[j0,j1]
    fig.add_trace(go.Mesh3d(
        x=x_v, y=y_v, z=z_v, i=il, j=jl, k=kl,
        color=c["color_int"], opacity=1.0,
        name=f'Zapato {c["od_pulg"]}"', showlegend=False,
        flatshading=True,
        hovertemplate=f'<b>Zapato {c["od_pulg"]}"</b> — Prof: {c["zapato"]} m<extra></extra>'))

# ─── WELLHEAD / BOP ──────────────────────────────────────────────────────────
wh_h = 60
add_tube_vert(fig, -wh_h, Z0,
              R_C0_EXT * 0.90, R_C1_EXT * 0.95,
              "#E67E22", "Wellhead / BOP", 1.0)
if sl:
    fig.add_trace(go.Scatter3d(
        x=[R_C0_EXT * 1.5], y=[0], z=[-wh_h / 2],
        mode="text", text=["WELLHEAD / BOP"],
        textfont=dict(size=10, color="white"),
        showlegend=False, hoverinfo="skip"))

# ─── LINEAS DE FLUJO Y GAS (salida en superficie) ────────────────────────────
lf_len = R_C0_EXT * 2.8
for y_off, col, nm in [
    ( R_C0_EXT, "#E74C3C", "Linea de flujo"),
    (-R_C0_EXT, "#2ECC71", "Linea de gas"),
]:
    fig.add_trace(go.Scatter3d(
        x=[0, lf_len], y=[y_off, y_off], z=[-wh_h*0.5, -wh_h*0.5],
        mode="lines", line=dict(color=col, width=8),
        name=nm,
        hovertemplate=f"<b>{nm}</b><extra></extra>"))

# ─── INTERVENCION ────────────────────────────────────────────────────────────
if mi and pi <= Z1:
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[pi],
        mode="markers+text",
        marker=dict(size=18, color="red", symbol="x",
                    line=dict(color="yellow", width=3)),
        text=[f"  INTERVENCION: {ti}"],
        textfont=dict(size=10, color="red"),
        name=f"Intervencion: {ti}",
        hovertemplate=(
            f"<b>INTERVENCION</b><br>"
            f"{ti}<br>Prof: {pi} m<extra></extra>")))

# ─── EJE DE PROFUNDIDAD (escala lateral) ─────────────────────────────────────
depth_marks = list(range(0, Z1+1, 200))
fig.add_trace(go.Scatter3d(
    x=[-R_C0_EXT * 3.2] * len(depth_marks),
    y=[0] * len(depth_marks),
    z=depth_marks,
    mode="text",
    text=[f"{d} m" for d in depth_marks],
    textfont=dict(size=8, color="#888888"),
    showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter3d(
    x=[-R_C0_EXT * 3.0, -R_C0_EXT * 3.0],
    y=[0, 0],
    z=[0, Z1],
    mode="lines",
    line=dict(color="#444", width=1, dash="dot"),
    showlegend=False, hoverinfo="skip"))

# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT  —  CORRECCION PRINCIPAL: autorange="reversed" + up z=+1
# ═══════════════════════════════════════════════════════════════════════════

CP = {
    "Isometrica / Corte": dict(
        eye=dict(x=1.8,  y=0.9, z=-0.6),
        up =dict(x=0,    y=0,   z=-1)),
    "Frontal": dict(
        eye=dict(x=0,    y=2.5, z=0),
        up =dict(x=0,    y=0,   z=-1)),
    "Lateral": dict(
        eye=dict(x=2.5,  y=0,   z=0),
        up =dict(x=0,    y=0,   z=-1)),
    "Superior": dict(
        eye=dict(x=0,    y=0,   z=-2.5),
        up =dict(x=0,    y=1,   z=0)),
}

fig.update_layout(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    scene=dict(
        bgcolor="#0d1117",
        xaxis=dict(
            title="", showgrid=False, zeroline=False,
            showticklabels=False, backgroundcolor="#0d1117"),
        yaxis=dict(
            title="", showgrid=False, zeroline=False,
            showticklabels=False, backgroundcolor="#0d1117"),
        zaxis=dict(
            title="Profundidad (m)",
            showgrid=True,  gridcolor="#1a1a2e",
            backgroundcolor="#0d1117", color="#aaa",
            # ✅ CORRECCION: autorange reversed hace que z=0 quede ARRIBA
            #    y z creciente vaya hacia ABAJO (boca de pozo en la cima)
            autorange="reversed",
        ),
        camera=CP[vp],
        aspectmode="manual",
        aspectratio=dict(x=1, y=1, z=5.0),
    ),
    legend=dict(
        bgcolor="rgba(10,10,20,0.88)",
        bordercolor="#333", borderwidth=1,
        font=dict(color="white", size=10),
        x=0.01, y=0.98,
    ),
    margin=dict(l=0, r=0, t=45, b=0),
    title=dict(
        text=(
            f"🛢️ {WELL['nombre']} — Gas Lift Continuo — Vaca Muerta"
            + (f"  |  CORTE {angulo_corte}°" if corte else "")
        ),
        font=dict(color="white", size=15),
        x=0.5,
    ),
    height=780,
)

# ═══════════════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs([
    "🌐 Vista 3D — Corte transversal",
    "📋 Datos tecnicos",
    "💡 Guia de uso",
])

with tab1:
    st.plotly_chart(fig, use_container_width=True, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "toImageButtonOptions": {
            "format": "png",
            "filename": f"pozo_{WELL['nombre']}_v2",
            "scale": 2,
        },
    })
    if mi:
        st.markdown(
            f'<div class="ibox">⚠️ <b>INTERVENCION MARCADA</b>: '
            f'{ti} @ {pi} m MD<br>'
            f'Verificar presiones y estado de valvulas '
            f'antes de iniciar trabajos.</div>',
            unsafe_allow_html=True)

with tab2:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Casings")
        for c in CASINGS:
            st.markdown(
                f'<div class="casing-info"><b>{c["nombre"]}</b><br>'
                f'OD: {c["od_pulg"]}" ({c["od_mm"]} mm) | '
                f'ID: {c["id_mm"]} mm<br>'
                f'Grado: {c["grado"]} | Peso: {c["peso"]} lb/ft<br>'
                f'Zapato: {c["zapato"]} m<br>'
                f'<i>{c["desc"]}</i></div>',
                unsafe_allow_html=True)
        st.markdown("### Tubing")
        st.markdown(
            f'<div class="casing-info" style="border-color:#D4AC0D">'
            f'OD: {TBG["od_pulg"]}" ({TBG["od_mm"]} mm) | '
            f'ID: {TBG["id_mm"]} mm<br>'
            f'Grado: {TBG["grado"]} | Fondo: {TBG["fondo"]} m</div>',
            unsafe_allow_html=True)
    with c2:
        st.markdown("### Valvulas Gas Lift")
        for v in GLV:
            bc = "#27AE60" if "ABIERTA" in v["estado"] else "#ffc107"
            st.markdown(
                f'<div class="valve-info" style="border-color:{bc}">'
                f'<b>GLV-{v["id"]} — {v["tipo"]}</b><br>'
                f'Prof: {v["md"]} m | P apertura: {v["psi"]} psi<br>'
                f'Estado: {v["estado"]}<br>'
                f'<i>{v["nota"]}</i></div>',
                unsafe_allow_html=True)
    with c3:
        st.markdown("### Trayectoria")
        df_t = pd.DataFrame({
            "Parametro": ["Prof. MD","Prof. TVD","KOP",
                          "Build Rate","Inc. max","Azimut"],
            "Valor": [
                f'{WELL["md_total"]} m',  f'{WELL["tvd_total"]} m',
                f'{WELL["kop"]} m',       f'{WELL["build_rate"]} deg/30m',
                f'{WELL["inc_max"]} deg', f'{WELL["azimut"]} deg (SO)',
            ],
        })
        st.dataframe(df_t, hide_index=True, use_container_width=True)
        st.markdown("### Packer")
        st.markdown(
            f'<div class="casing-info" style="border-color:#8E44AD">'
            f'<b>{PACKER["tipo"]}</b><br>'
            f'Prof: {PACKER["md"]} m MD | OD: {PACKER["od"]}"<br>'
            f'{PACKER["nota"]}</div>',
            unsafe_allow_html=True)

with tab3:
    st.markdown("""
## Guia de Uso — Visualizador 3D v2.1

### Corte transversal
- Activar **"Aplicar corte"** para ver el interior del pozo
- Ajustar el **angulo del corte** (0-360°) para ver mas o menos seccion
- El corte revela los cilindros concentricos:
  cemento → casings → gas annulus → tubing → fluido

### Controles 3D
| Accion | Control |
|--------|---------|
| Rotar | Click + arrastrar |
| Zoom | Scroll / pellizco |
| Pan | Click derecho |
| Info elemento | Hover |

### Leyenda de colores
| Color | Elemento |
|-------|---------|
| Cafe | Conductor 20" |
| Azul | Surface Casing 13-3/8" |
| Verde | Intermediate Casing 9-5/8" |
| Gris claro | Cemento |
| Amarillo | Tubing 3-1/2" |
| Azul claro | Gas en annulus |
| Verde oscuro | Columna de fluido |
| Naranja (mandrel) | GLV descargas |
| Verde (mandrel) | GLV operativa |
| Violeta | Packer |
| Naranja (cabezal) | Wellhead / BOP |

### Para intervenciones
1. Activar **"Marcar zona de intervencion"**
2. Ajustar la profundidad al punto de trabajo
3. Seleccionar el tipo de operacion
4. Usar la vista isometrica + corte para mostrar al equipo la ubicacion exacta

---
*Portfolio — Ingenieria de Yacimientos | Vaca Muerta | Streamlit + Plotly v2.1*
""")

st.markdown("---")
st.markdown(
    "<center><small>Visualizador de Pozo v2.1 | Gas Lift | Vaca Muerta | "
    "Streamlit + Plotly</small></center>",
    unsafe_allow_html=True)
