import streamlit as st
import pandas as pd
import numpy as np
import re
import datetime
import plotly.express as px
from modules.utils import safe_del, safe_hu

try:
    fast_render = st.fragment
except AttributeError:
    fast_render = lambda f: f

@fast_render
def render_admins(df_vekp, df_likp):
    st.markdown("<div class='section-header'><h3>🛠️ Admin Tools & Tracking</h3><p>Nástroje pro nákupčí obalů, expedici a sledování zásilek.</p></div>", unsafe_allow_html=True)

    # ==========================================
    # SEKCE 1: TRACKING ZÁSILEK (UPS / FEDEX)
    # ==========================================
    st.markdown("#### 🌍 Sledování zásilek (Tracking)")
    if df_likp is not None and not df_likp.empty:
        c_del_likp = next((c for c in df_likp.columns if "DELIVERY" in str(c).upper() or "LIEFERUNG" in str(c).upper() or "DODÁVKA" in str(c).upper()), None)
        c_bol = next((c for c in df_likp.columns if "BILL OF LADING" in str(c).upper() or "PROHLÁŠENÍ" in str(c).upper() or "NÁKLADNÍ" in str(c).upper()), None)
        
        if c_del_likp and c_bol:
            df_likp['Clean_Del'] = df_likp[c_del_likp].apply(safe_del)
            avail_dels = sorted(df_likp[df_likp[c_bol].notna() & (df_likp[c_bol] != '')]['Clean_Del'].unique().tolist())
            
            c_tr1, c_tr2 = st.columns([2, 1])
            with c_tr1: sel_del_track = st.selectbox("Vyberte zakázku (Delivery) pro zobrazení Trackingu:", options=[""] + avail_dels)
            
            if sel_del_track:
                row = df_likp[df_likp['Clean_Del'] == sel_del_track].iloc[0]
                track_id = str(row[c_bol]).strip()
                
                st.info(f"**Tracking ID:** `{track_id}`")
                
                # Chytrá detekce dopravce
                if track_id.upper().startswith('1Z'):
                    url = f"https://www.ups.com/track?tracknum={track_id}"
                    st.markdown(f"📦 Detekováno **UPS**. [➡️ Klikněte zde pro sledování zásilky na webu UPS]({url})")
                elif track_id.isdigit() and len(track_id) >= 10:
                    url = f"https://www.fedex.com/fedextrack/?trknbr={track_id}"
                    st.markdown(f"📦 Detekováno **FedEx**. [➡️ Klikněte zde pro sledování zásilky na webu FedEx]({url})")
                else:
                    st.warning("Dopravce nebyl automaticky rozpoznán. Zkuste tyto odkazy:")
                    st.markdown(f"[🔗 Zkusit UPS](https://www.ups.com/track?tracknum={track_id}) | [🔗 Zkusit FedEx](https://www.fedex.com/fedextrack/?trknbr={track_id})")
        else: st.warning("V LIKP reportu chybí sloupec 'Bill of lading' (Číslo balíku).")
    else: st.info("Pro funkci Trackingu nahrajte report LIKP.")

    st.divider()

    # ==========================================
    # SEKCE 2: PŘESUNUTO Z AUDITU - HROMADNÁ ANALÝZA OBALŮ
    # ==========================================
    st.markdown("#### 📦 Hromadná analýza obalového materiálu (Podle zakázek)")
    order_input = st.text_area("Seznam zakázek (můžete zkopírovat sloupec z Excelu):", height=100, placeholder="4941120299\n4941123347")

    if st.button("Analyzovat použité obaly", type="primary"):
        if not order_input.strip() or df_vekp is None or df_vekp.empty:
            st.error("Zadejte zakázky a ujistěte se, že máte nahraný VEKP.")
        else:
            raw_orders = re.split(r'[,\s\n]+', order_input.strip())
            clean_orders = [safe_del(o) for o in raw_orders if o]

            cols_lower = [str(c).lower().strip() for c in df_vekp.columns]
            c_del = next((c for c, l in zip(df_vekp.columns, cols_lower) if "delivery" in l or "lieferung" in l or "dodávka" in l), None)
            c_pack = next((c for c, l in zip(df_vekp.columns, cols_lower) if "packaging materials" in l or "packmittel" in l or "obalový" in l), None)
            c_hu = next((c for c, l in zip(df_vekp.columns, cols_lower) if "internal hu" in l or "hu-nummer intern" in l or "manipul" in l), None)

            if c_del and c_pack:
                df_vekp['Clean_Del'] = df_vekp[c_del].apply(safe_del)
                filt_vekp = df_vekp[df_vekp['Clean_Del'].isin(clean_orders)]
                
                if not filt_vekp.empty:
                    pack_summary = filt_vekp.groupby(c_pack)[c_hu].nunique().reset_index() if c_hu else filt_vekp.groupby(c_pack).size().reset_index()
                    pack_summary.columns = ['Obalový materiál', 'Počet použitých kusů']
                    st.dataframe(pack_summary.sort_values(by='Počet použitých kusů', ascending=False), hide_index=True)
                else: st.warning("Pro tyto zakázky nebyly nalezeny obaly.")

    st.divider()

    # ==========================================
    # SEKCE 3: PŘESUNUTO Z AUDITU - DASHBOARD A PREDIKCE
    # ==========================================
    st.markdown("#### 📈 Sledování a predikce obalu pro Nákup")
    if df_vekp is not None and not df_vekp.empty:
        cols_lower_ana = [str(c).lower().strip() for c in df_vekp.columns]
        c_pack_ana = next((c for c, l in zip(df_vekp.columns, cols_lower_ana) if "packaging materials" in l or "packmittel" in l), None)
        c_date_ana = next((c for c, l in zip(df_vekp.columns, cols_lower_ana) if "created on" in l or "erfasst am" in l or "datum" in l), None)
        c_hu_ana = next((c for c, l in zip(df_vekp.columns, cols_lower_ana) if "internal hu" in l or "hu-nummer intern" in l), None)

        if c_pack_ana and c_date_ana:
            vekp_ana = df_vekp.dropna(subset=[c_pack_ana]).copy()
            vekp_ana['TempDate'] = pd.to_datetime(vekp_ana[c_date_ana], errors='coerce')
            if c_hu_ana: vekp_ana = vekp_ana.drop_duplicates(subset=[c_hu_ana])
            vekp_ana['MonthStr'] = vekp_ana['TempDate'].dt.strftime('%Y-%m')
            
            avail_packs = sorted([p for p in vekp_ana[c_pack_ana].astype(str).unique() if p and p.lower() != 'nan'])
            
            c_sel1, c_sel2 = st.columns([2, 1])
            with c_sel1: sel_pack = st.selectbox("Vyberte obalový materiál:", options=["— Vyberte obal —"] + avail_packs)
            with c_sel2: predict_days = st.number_input("Počet dní pro predikci:", min_value=1, value=23)
            
            if sel_pack != "— Vyberte obal —":
                df_sel = vekp_ana[vekp_ana[c_pack_ana].astype(str) == sel_pack]
                total_used = len(df_sel)
                curr_month = datetime.date.today().strftime('%Y-%m')
                
                df_comp = df_sel[df_sel['MonthStr'] < curr_month]
                vk_comp = vekp_ana[vekp_ana['MonthStr'] < curr_month]
                
                if not df_comp.empty and not vk_comp.empty:
                    work_days = vk_comp['TempDate'].dt.date.nunique() or 1
                    avg_daily = len(df_comp) / work_days
                    pred = int(avg_daily * predict_days)
                    c1, c2 = st.columns(2)
                    c1.metric("📦 Historická spotřeba", f"{total_used} ks")
                    c2.metric(f"🔮 Predikce ({predict_days} dní)", f"{pred} ks")
                else: st.info("Nedostatek historických dat pro predikci.")
