"""
Visualizador 3D de Pozo con Gas Lift - Vaca Muerta  v2
=======================================================
Mejoras v2:
  - Boca de pozo arriba, profundidad crece hacia abajo
  - Solo seccion vertical con la completacion (0 - 3200 m)
  - Corte transversal 3D tipo diagrama tecnico con volumen real
  - Casings concentricos visibles en el corte
  - Valvulas como cuerpos 3D en el tubing
  - Packer como sello visible entre casing y tubing

Ejecutar: streamlit run app.py
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
    "nombre"  : "VM-XA-001",
    "formacion": "Vaca Muerta",
    "md_total" : 4200,   # m MD total del pozo
    "tvd_total": 3100,   # m TVD total
    "kop"      : 800,    # m - kick off point (inicio de curvatura)
    "build_rate": 6.5,   # deg/30m
    "azimut"   : 225,    # deg
    "inc_max"  : 88,     # deg - cuasi-horizontal
}

# Profundidad maxima mostrada en la vista vertical
VIS_DEPTH = 3200   # m  (un poco debajo del packer)

# Casings - diametros reales en pulgadas y mm
CASINGS = [
    {
        "nombre": "Conductor Casing",
        "od_pulg": 20.0, "od_mm": 508.0, "id_mm": 490.0,
        "peso": 133.0, "grado": "K-55", "zapato": 60,
        "color_ext": "#7B3F00",   # cafe oscuro exterior
        "color_int": "#A0522D",   # cafe interior / cara interna
        "desc": '20" - Cemento hasta superficie',
    },
    {
        "nombre": "Surface Casing",
        "od_pulg": 13.375, "od_mm": 339.7, "id_mm": 320.0,
        "peso": 68.0, "grado": "K-55", "zapato": 600,
        "color_ext": "#1A5276",
        "color_int": "#2E86C1",
        "desc": '13-3/8" - BOP / proteccion acuiferos',
    },
    {
        "nombre": "Intermediate / Production Casing",
        "od_pulg": 9.625, "od_mm": 244.5, "id_mm": 226.0,
        "peso": 53.5, "grado": "P-110", "zapato": 2800,
        "color_ext": "#1E8449",
        "color_int": "#27AE60",
        "desc": '9-5/8" - Casing de produccion',
    },
]

TBG = {
    "od_pulg": 3.5, "od_mm": 88.9, "id_mm": 76.0,
    "peso": 9.3, "grado": "L-80",
    "fondo": 3150,   # m MD - fondo del tubing (cerca del packer)
    "color_ext": "#B7950B",
    "color_int": "#D4AC0D",
    "desc": '3-1/2" EUE - Tubing de produccion',
}

# Fluido dentro del tubing (columna de produccion)
FLUID_COLOR = "#1A6B3C"   # verde oscuro - columna liquida

# Espacio anular entre tubing y casing  (gas inyectado)
ANNULUS_GAS_COLOR = "#D4E6F1"  # azul muy claro - gas

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

CEMENTO = {"color": "#BDC3C7", "alpha": 0.55}  # gris claro - cemento

WELLHEAD_DEPTH = 0    # m (tope = boca de pozo)

# ═══════════════════════════════════════════════════════════════════════════
# UTILIDADES GEOMETRICAS
# ═══════════════════════════════════════════════════════════════════════════

def tubo_vertical(z_top, z_bot, r_ext, r_int, color, name,
                  opacity=1.0, n_theta=32, show_legend=True):
    """
    Genera un tubo (anillo) vertical entre z_top y z_bot.
    Z positivo = profundidad hacia abajo (boca en z=0).
    r_ext > r_int definen el espesor de pared.
    Retorna lista de trazas Mesh3d.
    """
    traces = []
    th = np.linspace(0, 2 * np.pi, n_theta, endpoint=False)
    cos_t, sin_t = np.cos(th), np.sin(th)

    for r, suffix, col, show in [
        (r_ext, "ext", color, show_legend),
        (r_int, "int", color, False),
    ]:
        # Vertices del cilindro
        x_top = r * cos_t;  y_top = r * sin_t
        x_bot = r * cos_t;  y_bot = r * sin_t
        z_top_arr = np.full(n_theta, z_top)
        z_bot_arr = np.full(n_theta, z_bot)

        x_v = np.concatenate([x_top, x_bot])
        y_v = np.concatenate([y_top, y_bot])
        z_v = np.concatenate([z_top_arr, z_bot_arr])

        il, jl, kl = [], [], []
        for i in range(n_theta):
            i0 = i; i1 = (i+1) % n_theta
            j0 = i + n_theta; j1 = (i+1) % n_theta + n_theta
            il += [i0, i0]; jl += [i1, j0]; kl += [j0, j1]

        traces.append(go.Mesh3d(
            x=x_v, y=y_v, z=z_v,
            i=il, j=jl, k=kl,
            color=col, opacity=opacity,
            name=name, showlegend=show,
            lighting=dict(ambient=0.55, diffuse=0.85,
                          specular=0.4, roughness=0.35,
                          fresnel=0.2),
            flatshading=False,
            hovertemplate=f"<b>{name}</b><extra></extra>",
        ))
    return traces


def anillo_horizontal(z_pos, r_in, r_out, color, name,
                      opacity=1.0, n_theta=32):
    """Disco / zapato de casing en profundidad z_pos."""
    th = np.linspace(0, 2*np.pi, n_theta, endpoint=False)
    th_c = np.append(th, th[0])
    r_vals = [r_in, r_out]
    x_v, y_v, z_v = [], [], []
    for r in r_vals:
        x_v += list(r * np.cos(th)); y_v += list(r * np.sin(th))
        z_v += [z_pos] * n_theta

    il, jl, kl = [], [], []
    for i in range(n_theta):
        i0=i; i1=(i+1)%n_theta; j0=i+n_theta; j1=(i+1)%n_theta+n_theta
        il+=[i0,i0]; jl+=[i1,j0]; kl+=[j0,j1]

    return go.Mesh3d(
        x=x_v, y=y_v, z=z_v, i=il, j=jl, k=kl,
        color=color, opacity=opacity, name=name, showlegend=False,
        flatshading=True,
        hovertemplate=f"<b>Zapato {name}</b><extra></extra>",
    )


def valvula_3d(z_pos, r_tbg_ext, color, name, size_factor=1.8):
    """Mandra / valvula GLV como toro aplanado en el tubing."""
    n_th = 24
    R_big = r_tbg_ext * size_factor   # radio del mandrel (mas grande que OD tubing)
    R_small = r_tbg_ext * 0.35         # radio del cuerpo tubular
    th_big = np.linspace(0, 2*np.pi, n_th, endpoint=False)
    th_sml = np.linspace(0, 2*np.pi, 12, endpoint=False)

    # Generar superficie toroidal achatada
    x_v, y_v, z_v = [], [], []
    for tb in th_big:
        for ts in th_sml:
            r = R_big + R_small * np.cos(ts)
            x_v.append(r * np.cos(tb))
            y_v.append(r * np.sin(tb))
            z_v.append(z_pos + R_small * 0.6 * np.sin(ts))

    n_big = n_th; n_sml = 12
    il, jl, kl = [], [], []
    for i in range(n_big):
        for j in range(n_sml):
            a = i*n_sml + j
            b = i*n_sml + (j+1)%n_sml
            c = ((i+1)%n_big)*n_sml + j
            d = ((i+1)%n_big)*n_sml + (j+1)%n_sml
            il+=[a,a]; jl+=[b,c]; kl+=[c,d]

    return go.Mesh3d(
        x=x_v, y=y_v, z=z_v, i=il, j=jl, k=kl,
        color=color, opacity=1.0, name=name, showlegend=True,
        lighting=dict(ambient=0.5, diffuse=0.9, specular=0.6,
                      roughness=0.3, fresnel=0.3),
        flatshading=False,
        hovertemplate=f"<b>{name}</b><extra></extra>",
    )


def packer_3d(z_pos, r_tbg_ext, r_csg_int, color, name):
    """Packer como cono truncado entre tubing y casing."""
    n_th = 32
    th = np.linspace(0, 2*np.pi, n_th, endpoint=False)
    h = 80   # altura del packer en metros

    # Parte superior (ancha, contra el casing)
    x_v, y_v, z_v = [], [], []
    for frac in np.linspace(0, 1, 8):
        r = r_tbg_ext + (r_csg_int - r_tbg_ext) * frac
        z = z_pos - h/2 + h * frac
        x_v += list(r * np.cos(th))
        y_v += list(r * np.sin(th))
        z_v += [z] * n_th

    il, jl, kl = [], [], []
    n_rings = 8
    for ring in range(n_rings - 1):
        base = ring * n_th
        for i in range(n_th):
            a = base + i; b = base + (i+1)%n_th
            c = base + n_th + i; d = base + n_th + (i+1)%n_th
            il+=[a,a]; jl+=[b,c]; kl+=[c,d]

    return go.Mesh3d(
        x=x_v, y=y_v, z=z_v, i=il, j=jl, k=kl,
        color=color, opacity=0.95, name=name, showlegend=True,
        lighting=dict(ambient=0.5, diffuse=0.9, specular=0.5,
                      roughness=0.3, fresnel=0.3),
        flatshading=False,
        hovertemplate=f"<b>{name}</b><br>Prof: {z_pos} m<extra></extra>",
    )


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## Configuracion del Pozo")
    st.markdown("---")

    st.markdown("### Elementos visibles")
    show_conductor    = st.checkbox('Conductor 20"',        value=True)
    show_surface      = st.checkbox('Surface 13-3/8"',      value=True)
    show_intermediate = st.checkbox('Intermediate 9-5/8"',  value=True)
    show_cemento      = st.checkbox("Cemento",              value=True)
    show_tubing       = st.checkbox('Tubing 3-1/2"',        value=True)
    show_fluido       = st.checkbox("Columna de fluido",    value=True)
    show_gas_annulus  = st.checkbox("Gas en annulus",       value=True)
    show_valvulas     = st.checkbox("Valvulas GLV (mandriles)", value=True)
    show_packer       = st.checkbox("Packer",               value=True)

    st.markdown("### Corte transversal")
    corte = st.checkbox("Aplicar corte (ver interior)", value=True)
    angulo_corte = st.slider("Angulo del corte (deg)", 0, 180, 90, 10) if corte else 180

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
# Para que el pozo se vea con proporcion razonable en 3D escalamos
# los radios con un factor (los diametros reales son << que las profundidades)

ESCALA_R = 28   # factor de escala radial

def r(mm):
    return mm / 1000 * ESCALA_R

# Radios escalados (en metros visuales)
R_C0_EXT = r(CASINGS[0]["od_mm"]); R_C0_INT = r(CASINGS[0]["id_mm"])
R_C1_EXT = r(CASINGS[1]["od_mm"]); R_C1_INT = r(CASINGS[1]["id_mm"])
R_C2_EXT = r(CASINGS[2]["od_mm"]); R_C2_INT = r(CASINGS[2]["id_mm"])
R_TBG_EXT = r(TBG["od_mm"]);       R_TBG_INT = r(TBG["id_mm"])


# ═══════════════════════════════════════════════════════════════════════════
# MASCARA DE CORTE
# Para el half-cut: solo generamos geometria en el semi-espacio Y >= 0
# (Plotly no tiene corte nativo, lo simulamos con n_theta y offset angular)
# ═══════════════════════════════════════════════════════════════════════════

def n_theta_corte(corte, angulo, full=32):
    """Devuelve n_theta efectivo y angulo inicial para simular corte."""
    if not corte:
        return full, 0.0
    frac = angulo / 360.0
    return max(4, int(full * frac)), 0.0


# ═══════════════════════════════════════════════════════════════════════════
# CONSTRUCCION DE LA FIGURA
# ═══════════════════════════════════════════════════════════════════════════

fig = go.Figure()

NT_FULL = 36   # resolucion angular para cilindros completos
nt, ang0 = n_theta_corte(corte, angulo_corte, NT_FULL)


def add_tube_vert(z_top, z_bot, r_ext, r_int, color, name,
                  opacity=1.0, n_theta=None):
    """Wrapper para tubo vertical con resolucion del corte."""
    if n_theta is None:
        n_theta = nt
    th = np.linspace(ang0, ang0 + np.radians(angulo_corte if corte else 360),
                     n_theta, endpoint=not corte)
    cos_t, sin_t = np.cos(th), np.sin(th)

    traces_out = []
    for rad, show, nm_suffix in [
        (r_ext, True,  ""),
        (r_int, False, "_int"),
    ]:
        xt = rad * cos_t; yt = rad * sin_t
        xb = rad * cos_t; yb = rad * sin_t
        x_v = np.concatenate([xt, xb])
        y_v = np.concatenate([yt, yb])
        z_v = np.concatenate([np.full(n_theta, z_top),
                               np.full(n_theta, z_bot)])
        il, jl, kl = [], [], []
        for i in range(n_theta - 1 if corte else n_theta):
            i0 = i; i1 = (i+1) % n_theta
            j0 = i + n_theta; j1 = (i+1) % n_theta + n_theta
            il += [i0, i0]; jl += [i1, j0]; kl += [j0, j1]

        # Tapas en el corte
        if corte and len(th) > 2:
            # tapa superior
            for i in range(n_theta - 2):
                il.append(0); jl.append(i+1); kl.append(i+2)
            # tapa inferior
            base = n_theta
            for i in range(n_theta - 2):
                il.append(base); jl.append(base+i+1); kl.append(base+i+2)

        traces_out.append(go.Mesh3d(
            x=x_v, y=y_v, z=z_v,
            i=il, j=jl, k=kl,
            color=color, opacity=opacity,
            name=name, showlegend=show,
            lighting=dict(ambient=0.55, diffuse=0.85,
                          specular=0.4, roughness=0.3, fresnel=0.2),
            flatshading=False,
            hovertemplate=f"<b>{name}</b><extra></extra>",
        ))
    return traces_out


# ─── PROFUNDIDADES DE VISUALIZACION ──────────────────────────────────────────
Z0 = WELLHEAD_DEPTH    # boca de pozo  (z=0 = arriba)
Z1 = VIS_DEPTH         # limite inferior de la vista

# ─── SUPERFICIE / TERRENO ────────────────────────────────────────────────────
xs = np.linspace(-R_C0_EXT*2.5, R_C0_EXT*2.5, 4)
ys = np.linspace(-R_C0_EXT*2.5, R_C0_EXT*2.5, 4)
XS, YS = np.meshgrid(xs, ys)
fig.add_trace(go.Surface(
    x=XS, y=YS, z=np.zeros_like(XS) + Z0,
    colorscale=[[0,"#4a7c59"],[1,"#6aaa82"]],
    opacity=0.22, showscale=False,
    name="Superficie", hoverinfo="skip"))

# ─── CONDUCTOR CASING (20") ─── hasta zapato 60 m ────────────────────────────
if show_conductor:
    for tr in add_tube_vert(Z0, CASINGS[0]["zapato"],
                            R_C0_EXT, R_C0_INT,
                            CASINGS[0]["color_ext"],
                            'Conductor 20"', op_casing):
        fig.add_trace(tr)

# ─── CEMENTO entre conductor y surface (60 a 600 m) ──────────────────────────
if show_cemento and show_surface:
    for tr in add_tube_vert(CASINGS[0]["zapato"], CASINGS[1]["zapato"],
                            R_C0_INT, R_C1_EXT,
                            CEMENTO["color"],
                            "Cemento", CEMENTO["alpha"]):
        fig.add_trace(tr)

# ─── SURFACE CASING (13-3/8") ─── hasta zapato 600 m ─────────────────────────
if show_surface:
    for tr in add_tube_vert(Z0, CASINGS[1]["zapato"],
                            R_C1_EXT, R_C1_INT,
                            CASINGS[1]["color_ext"],
                            'Surface Casing 13-3/8"', op_casing):
        fig.add_trace(tr)

# ─── CEMENTO entre surface e intermediate ─────────────────────────────────────
if show_cemento and show_intermediate:
    for tr in add_tube_vert(CASINGS[1]["zapato"], CASINGS[2]["zapato"],
                            R_C1_INT, R_C2_EXT,
                            CEMENTO["color"],
                            "Cemento 2", CEMENTO["alpha"]):
        fig.add_trace(tr)

# ─── INTERMEDIATE CASING (9-5/8") ─── hasta zapato 2800 m ────────────────────
if show_intermediate:
    for tr in add_tube_vert(Z0, min(CASINGS[2]["zapato"], Z1),
                            R_C2_EXT, R_C2_INT,
                            CASINGS[2]["color_ext"],
                            'Int. Casing 9-5/8"', op_casing):
        fig.add_trace(tr)

# ─── GAS EN ANNULUS (entre int casing y tubing) ───────────────────────────────
if show_gas_annulus and show_intermediate and show_tubing:
    # Solo desde superficie hasta la valvula operativa (GLV-4)
    z_gas_bot = min(GLV[-1]["md"], Z1)
    for tr in add_tube_vert(Z0, z_gas_bot,
                            R_C2_INT, R_TBG_EXT,
                            ANNULUS_GAS_COLOR,
                            "Gas en annulus", op_fluido):
        fig.add_trace(tr)

# ─── TUBING (3-1/2") ──────────────────────────────────────────────────────────
if show_tubing:
    z_tbg_bot = min(TBG["fondo"], Z1)
    for tr in add_tube_vert(Z0, z_tbg_bot,
                            R_TBG_EXT, R_TBG_INT,
                            TBG["color_ext"],
                            'Tubing 3-1/2"', op_tubing, n_theta=nt):
        fig.add_trace(tr)

# ─── FLUIDO DENTRO DEL TUBING ─────────────────────────────────────────────────
if show_fluido and show_tubing:
    z_fl_bot = min(TBG["fondo"], Z1)
    for tr in add_tube_vert(Z0, z_fl_bot,
                            R_TBG_INT, 0.0,
                            FLUID_COLOR,
                            "Columna de fluido", op_fluido):
        fig.add_trace(tr)

# ─── VÁLVULAS GLV (mandriles) ─────────────────────────────────────────────────
if show_valvulas:
    for v in GLV:
        if v["md"] > Z1:
            continue
        is_open = "ABIERTA" in v["estado"]
        nm = f"GLV-{v['id']} — {v['tipo']} ({v['md']}m)"

        # Mandrel como cilindro corto mas ancho que el tubing
        r_mnd_ext = R_TBG_EXT * 1.55
        r_mnd_int = R_TBG_INT
        z_top_v = v["md"] - 25
        z_bot_v = v["md"] + 25

        for tr in add_tube_vert(z_top_v, z_bot_v,
                                r_mnd_ext, r_mnd_int,
                                v["color"], nm, 1.0):
            fig.add_trace(tr)

        # Capuchon lateral de la valvula (lado derecho)
        # Pequeno cilindro horizontal simulado con una esfera aplanada
        cap_r = R_TBG_EXT * 0.9
        th_cap = np.linspace(0, 2*np.pi, 20)
        x_cap = r_mnd_ext + cap_r * np.cos(th_cap)
        y_cap = cap_r * np.sin(th_cap)
        z_cap_t = np.full(20, v["md"] - 12)
        z_cap_b = np.full(20, v["md"] + 12)
        xc = np.concatenate([x_cap, x_cap])
        yc = np.concatenate([y_cap, y_cap])
        zc = np.concatenate([z_cap_t, z_cap_b])
        ilc, jlc, klc = [], [], []
        for i in range(19):
            ilc+=[i,i]; jlc+=[(i+1)%20,i+20]; klc+=[i+20,(i+1)%20+20]
        fig.add_trace(go.Mesh3d(
            x=xc, y=yc, z=zc, i=ilc, j=jlc, k=klc,
            color=v["color"], opacity=1.0,
            name=nm+"_cap", showlegend=False,
            flatshading=False,
            hovertemplate=(
                f"<b>{nm}</b><br>"
                f"Prof: {v['md']} m MD<br>"
                f"P apertura: {v['psi']} psi<br>"
                f"Estado: {v['estado']}<br>"
                f"<i>{v['nota']}</i><extra></extra>"),
        ))

        # Etiqueta
        if sl:
            lbl = "✅ " if is_open else "⭕ "
            lbl += f"GLV-{v['id']}  {v['md']}m"
            fig.add_trace(go.Scatter3d(
                x=[r_mnd_ext * 1.6], y=[0], z=[v["md"]],
                mode="text",
                text=[lbl],
                textfont=dict(size=10,
                              color="#27AE60" if is_open else "#E67E22"),
                showlegend=False, hoverinfo="skip"))

# ─── PACKER ───────────────────────────────────────────────────────────────────
if show_packer and PACKER["md"] <= Z1:
    h_pk = 90    # altura visual del packer
    z_pk_top = PACKER["md"] - h_pk/2
    z_pk_bot = PACKER["md"] + h_pk/2

    # Goma del packer (cuerpo principal - rellena annulus)
    for tr in add_tube_vert(z_pk_top, z_pk_bot,
                            R_C2_INT * 0.97, R_TBG_EXT * 1.02,
                            PACKER["color"],
                            "Packer — sello casing/tubing", 0.95):
        fig.add_trace(tr)

    # Etiqueta
    if sl:
        fig.add_trace(go.Scatter3d(
            x=[R_C2_INT * 1.4], y=[0], z=[PACKER["md"]],
            mode="text",
            text=[f"PACKER  {PACKER['md']}m"],
            textfont=dict(size=10, color="#8E44AD"),
            showlegend=False, hoverinfo="skip"))

# ─── ZAPATOS DE CASING ────────────────────────────────────────────────────────
for c in CASINGS:
    if c["zapato"] <= Z1:
        # Anillo inferior del casing (zapato)
        th = np.linspace(0, 2*np.pi if not corte else np.radians(angulo_corte), nt, endpoint=not corte)
        x_v = np.concatenate([r(c["od_mm"])*np.cos(th), r(c["id_mm"])*np.cos(th)])
        y_v = np.concatenate([r(c["od_mm"])*np.sin(th), r(c["id_mm"])*np.sin(th)])
        z_v = np.concatenate([np.full(nt, c["zapato"]),  np.full(nt, c["zapato"])])
        il,jl,kl=[],[],[]
        for i in range(nt-1 if corte else nt):
            i0=i; i1=(i+1)%nt; j0=i+nt; j1=(i+1)%nt+nt
            il+=[i0,i0]; jl+=[i1,j0]; kl+=[j0,j1]
        fig.add_trace(go.Mesh3d(
            x=x_v, y=y_v, z=z_v, i=il, j=jl, k=kl,
            color=c["color_int"], opacity=1.0,
            name=f'Zapato {c["od_pulg"]}"', showlegend=False,
            flatshading=True,
            hovertemplate=f'<b>Zapato {c["od_pulg"]}"</b><br>Prof: {c["zapato"]} m<extra></extra>'))

# ─── WELLHEAD ────────────────────────────────────────────────────────────────
# Cabezal de pozo como cilindro ancho en superficie
wh_r = R_C0_EXT * 0.9
wh_h = 60   # altura visual
for tr in add_tube_vert(-wh_h, 0, wh_r, R_C1_EXT*0.95,
                        "#E67E22", "Wellhead / BOP", 1.0, n_theta=nt):
    fig.add_trace(tr)
if sl:
    fig.add_trace(go.Scatter3d(
        x=[wh_r * 1.5], y=[0], z=[-wh_h/2],
        mode="text", text=["WELLHEAD / BOP"],
        textfont=dict(size=10, color="white"),
        showlegend=False, hoverinfo="skip"))

# ─── BOCA DE POZO - lineas de flujo ──────────────────────────────────────────
# Tuberias que salen a superficie (linea de flujo y linea de gas)
lf_len = R_C0_EXT * 2.8
for y_off, col, nm in [(R_C0_EXT, "#E74C3C","Linea de flujo"),
                        (-R_C0_EXT, "#2ECC71","Linea de gas")]:
    fig.add_trace(go.Scatter3d(
        x=[0, lf_len], y=[y_off, y_off], z=[-wh_h*0.5, -wh_h*0.5],
        mode="lines",
        line=dict(color=col, width=8),
        name=nm,
        hovertemplate=f"<b>{nm}</b><extra></extra>"))

# ─── INTERVENCION ────────────────────────────────────────────────────────────
if mi and pi <= Z1:
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[pi],
        mode="markers+text",
        marker=dict(size=18, color="red", symbol="x",
                    line=dict(color="yellow", width=3)),
        text=[f"  INTERVENCION\n{ti}"],
        textfont=dict(size=10, color="red"),
        name=f"Intervencion: {ti}",
        hovertemplate=f"<b>INTERVENCION</b><br>{ti}<br>Prof: {pi} m<extra></extra>"))

# ─── EJE DE PROFUNDIDAD ──────────────────────────────────────────────────────
depth_marks = list(range(0, Z1+1, 200))
fig.add_trace(go.Scatter3d(
    x=[-R_C0_EXT*3]*len(depth_marks),
    y=[0]*len(depth_marks),
    z=depth_marks,
    mode="text",
    text=[f"{d} m" for d in depth_marks],
    textfont=dict(size=8, color="#aaaaaa"),
    showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter3d(
    x=[-R_C0_EXT*2.9, -R_C0_EXT*2.9],
    y=[0, 0],
    z=[0, Z1],
    mode="lines",
    line=dict(color="#555", width=1, dash="dot"),
    showlegend=False, hoverinfo="skip"))

# ═══════════════════════════════════════════════════════════════════════════
# LAYOUT
# ═══════════════════════════════════════════════════════════════════════════

CP = {
    "Isometrica / Corte": dict(eye=dict(x=1.8, y=0.9, z=0.4),
                               up=dict(x=0, y=0, z=-1)),
    "Frontal":            dict(eye=dict(x=0, y=2.5, z=0),
                               up=dict(x=0, y=0, z=-1)),
    "Lateral":            dict(eye=dict(x=2.5, y=0, z=0),
                               up=dict(x=0, y=0, z=-1)),
    "Superior":           dict(eye=dict(x=0, y=0, z=-2.5),
                               up=dict(x=0, y=1, z=0)),
}

fig.update_layout(
    paper_bgcolor="#0d1117",
    plot_bgcolor="#0d1117",
    scene=dict(
        bgcolor="#0d1117",
        xaxis=dict(title="", showgrid=False, zeroline=False,
                   showticklabels=False, backgroundcolor="#0d1117"),
        yaxis=dict(title="", showgrid=False, zeroline=False,
                   showticklabels=False, backgroundcolor="#0d1117"),
        zaxis=dict(
            title="Profundidad (m)",
            showgrid=True, gridcolor="#1a1a2e",
            backgroundcolor="#0d1117", color="#aaa",
            # Z positivo = profundidad hacia abajo
            # boca de pozo en z=0 (arriba), fondo en z=Z1 (abajo)
            range=[-100, Z1 + 50],
        ),
        camera=CP[vp],
        aspectmode="manual",
        # Relacion de aspecto: Z muy elongado para ver el pozo vertical
        aspectratio=dict(x=1, y=1, z=5.0),
    ),
    legend=dict(
        bgcolor="rgba(10,10,20,0.88)",
        bordercolor="#333",
        borderwidth=1,
        font=dict(color="white", size=10),
        x=0.01, y=0.98,
    ),
    margin=dict(l=0, r=0, t=45, b=0),
    title=dict(
        text=(f"🛢️ {WELL['nombre']} — Gas Lift Continuo — Vaca Muerta"
              f"{'  |  CORTE ' + str(angulo_corte) + '°' if corte else ''}"),
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
            f'Verificar presiones de operacion y estado de valvulas '
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
                f'{WELL["md_total"]} m',
                f'{WELL["tvd_total"]} m',
                f'{WELL["kop"]} m',
                f'{WELL["build_rate"]} deg/30m',
                f'{WELL["inc_max"]} deg',
                f'{WELL["azimut"]} deg (SO)',
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
## Guia de Uso — Visualizador 3D v2

### Corte transversal
- Activar **"Aplicar corte"** para ver el interior del pozo
- Ajustar el **angulo del corte** para mostrar mas o menos seccion
- El corte revela los cilindros concentricos: cemento, casings, annulus, tubing y fluido

### Controles 3D
| Accion | Control |
|--------|---------|
| Rotar | Click + arrastrar |
| Zoom | Scroll / pellizco |
| Pan | Click derecho |
| Info | Hover sobre elemento |

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
2. Ajustar la profundidad
3. Seleccionar tipo de trabajo
4. Usar la vista isometrica + corte para comunicar la ubicacion exacta al equipo

---
*Portfolio — Ingenieria de Yacimientos | Vaca Muerta | Streamlit + Plotly v2*
""")

st.markdown("---")
st.markdown(
    "<center><small>Visualizador de Pozo v2 | Gas Lift | Vaca Muerta | "
    "Streamlit + Plotly</small></center>",
    unsafe_allow_html=True)
