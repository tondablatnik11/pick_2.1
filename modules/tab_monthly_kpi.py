import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import datetime
from database import load_from_db

try:
    fast_render = st.fragment
except AttributeError:
    fast_render = lambda f: f

@fast_render
def render_monthly_kpi(df_pick, raw_vekp, raw_vepo):
    def _t(cs, en): 
        return en if st.session_state.get('lang', 'cs') == 'en' else cs

    st.markdown(f"<div class='section-header'><h3>📅 {_t('Měsíční KPI & Cíle', 'Monthly KPI & Targets')}</h3><p>{_t('Dlouhodobý přehled, plnění cílů a predikce na konec měsíce.', 'Long-term overview, target fulfillment, and end-of-month predictions.')}</p></div>", unsafe_allow_html=True)

    # Rozdělení na záložky
    tab_in, tab_pick, tab_pack = st.tabs([
        f"📥 {_t('Příjem (Inbound)', 'Inbound')}", 
        f"🛒 {_t('Pickování', 'Picking')}", 
        f"📦 {_t('Balení', 'Packing')}"
    ])

    # -----------------------------------------
    # ZÁLOŽKA 1: PŘÍJEM (Zatím prázdná)
    # -----------------------------------------
    with tab_in:
        st.info(_t("Zde bude měsíční přehled příjmu, jakmile nadefinujeme datový zdroj pro Inbound.", "Monthly inbound overview will be here once we define the data source."))

    # -----------------------------------------
    # ZÁLOŽKA 2: PICKOVÁNÍ
    # -----------------------------------------
    with tab_pick:
        if df_pick is not None and not df_pick.empty:
            df_p = df_pick.copy()
            
            # Očištění data
            date_col = 'Confirmation date' if 'Confirmation date' in df_p.columns else 'Date'
            df_p['TempDate'] = pd.to_datetime(df_p[date_col], errors='coerce')
            df_p = df_p.dropna(subset=['TempDate'])
            
            # Seskupení po dnech
            pick_daily = df_p.groupby(df_p['TempDate'].dt.date).agg(
                Total_TO=('Delivery', 'count'),      # Každý řádek je 1 TO
                Total_Pieces=('Qty', 'sum')          # Součet kusů
            ).reset_index()
            pick_daily.rename(columns={'TempDate': 'Date'}, inplace=True)
            
            # Zjištění metrik
            total_month_to = pick_daily['Total_TO'].sum()
            total_month_pcs = pick_daily['Total_Pieces'].sum()
            avg_daily_to = pick_daily['Total_TO'].mean()
            
            # Predikce (Zjednodušená - průměr * 21 pracovních dní)
            prediction_to = avg_daily_to * 21 if pd.notna(avg_daily_to) else 0

            # Metriky nahoře
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(_t("Celkem TO (Měsíc)", "Total TOs (Month)"), f"{int(total_month_to):,}")
            m2.metric(_t("Celkem Kusů (Měsíc)", "Total Pieces (Month)"), f"{int(total_month_pcs):,}")
            m3.metric(_t("Průměr TO / Den", "Avg TOs / Day"), f"{int(avg_daily_to):,}")
            m4.metric(_t("Predikce na konec měsíce", "End of Month Prediction"), f"{int(prediction_to):,} TO", help=_t("Odhad na základě průměru za odpracované dny (počítáno na 21 dní).", "Estimate based on average working days."))

            # Měsíční Graf s cílovou čarou
            st.markdown(f"#### 📊 {_t('Měsíční vývoj Pickování (Cíl: 300 TO/den)', 'Monthly Picking Trend (Target: 300 TO/day)')}")
            
            # Vytvoření grafu se dvěma osami (TO a Kusy)
            fig_pick = go.Figure()
            
            # Sloupečky pro TO
            fig_pick.add_trace(go.Bar(
                x=pick_daily['Date'], y=pick_daily['Total_TO'],
                name=_t('Picknuté TO', 'Picked TOs'),
                marker_color='#3b82f6',
                yaxis='y'
            ))
            
            # Čára pro Kusy
            fig_pick.add_trace(go.Scatter(
                x=pick_daily['Date'], y=pick_daily['Total_Pieces'],
                name=_t('Vypikované Kusy', 'Picked Pieces'),
                mode='lines+markers',
                line=dict(color='#f59e0b', width=3),
                yaxis='y2'
            ))
            
            # Přidání horizontální čáry pro CÍL 300
            fig_pick.add_hline(y=300, line_dash="dash", line_color="red", annotation_text=_t("Denní Cíl (300 TO)", "Daily Target (300 TO)"), annotation_position="top left")

            fig_pick.update_layout(
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                hovermode="x unified",
                legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='left', x=0),
                yaxis=dict(title=_t("Počet TO", "Number of TOs")),
                yaxis2=dict(title=_t("Počet Kusů", "Number of Pieces"), side='right', overlaying='y', showgrid=False)
            )
            st.plotly_chart(fig_pick, use_container_width=True)

            st.divider()
            
            # Drill-down: Detail dne
            st.markdown(f"#### 🔍 {_t('Detail konkrétního dne (Hodinový graf)', 'Specific Day Detail (Hourly Chart)')}")
            col_sel, _ = st.columns([1, 3])
            with col_sel:
                drill_date = st.date_input(_t("Vyberte den pro detailní rozpad:", "Select day for detailed breakdown:"), value=datetime.date.today(), key="drill_pick")
            
            drill_date_str = pd.to_datetime(drill_date).strftime('%Y-%m-%d')
            pick_day = df_p[df_p['TempDate'].dt.strftime('%Y-%m-%d') == drill_date_str].copy()
            
            if not pick_day.empty:
                time_col = 'Confirmation time' if 'Confirmation time' in pick_day.columns else 'Time'
                def get_hour(t_val):
                    try: return int(str(t_val).split(':')[0]) if ':' in str(t_val) else int(str(t_val)[0:2])
                    except: return -1
                
                pick_day['Hour'] = pick_day[time_col].apply(get_hour)
                pick_day_hourly = pick_day[pick_day['Hour'] >= 0].groupby('Hour').agg(
                    Total_TO=('Delivery', 'count'), Total_Pieces=('Qty', 'sum')
                ).reset_index()
                
                fig_pick_hour = go.Figure()
                fig_pick_hour.add_trace(go.Bar(x=pick_day_hourly['Hour'], y=pick_day_hourly['Total_TO'], name='TO', marker_color='#60a5fa'))
                fig_pick_hour.add_trace(go.Scatter(x=pick_day_hourly['Hour'], y=pick_day_hourly['Total_Pieces'], name='Kusy', yaxis='y2', mode='lines+markers', line=dict(color='#fbbf24')))
                fig_pick_hour.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', yaxis2=dict(side='right', overlaying='y', showgrid=False), xaxis=dict(tickmode='linear', tick0=0, dtick=1))
                st.plotly_chart(fig_pick_hour, use_container_width=True)
            else:
                st.warning(_t("V tento den nejsou k dispozici žádná data o pickování.", "No picking data available for this day."))

    # -----------------------------------------
    # ZÁLOŽKA 3: BALENÍ
    # -----------------------------------------
    with tab_pack:
        if raw_vekp is not None and not raw_vekp.empty and raw_vepo is not None and not raw_vepo.empty:
            df_vk = raw_vekp.copy()
            df_vp = raw_vepo.copy()
            
            # Najdeme spojovací klíč (Interní HU)
            vk_hu_col = next((c for c in df_vk.columns if "Internal HU" in str(c) or "HU-Nummer intern" in str(c)), None)
            vp_hu_col = next((c for c in df_vp.columns if "Internal HU" in str(c) or "HU-Nummer intern" in str(c)), None)
            vp_qty_col = next((c for c in df_vp.columns if "Packed quantity" in str(c) or "VEMNG" in str(c)), None)
            
            date_col_v = next((c for c in df_vk.columns if 'CREATED ON' in str(c).upper() or 'ERFASST AM' in str(c).upper()), None)
            
            if vk_hu_col and vp_hu_col and date_col_v and vp_qty_col:
                # Očištění klíčů a sloučení pro získání kusů na paletách
                df_vk['Clean_HU'] = df_vk[vk_hu_col].astype(str).str.strip().str.lstrip('0')
                df_vp['Clean_HU'] = df_vp[vp_hu_col].astype(str).str.strip().str.lstrip('0')
                df_vp['VP_Qty'] = pd.to_numeric(df_vp[vp_qty_col], errors='coerce').fillna(0)
                
                # Agregace kusů z VEPO podle HU
                hu_pieces = df_vp.groupby('Clean_HU')['VP_Qty'].sum().reset_index()
                
                # Připojení k VEKP
                pack_data = pd.merge(df_vk, hu_pieces, on='Clean_HU', how='left')
                pack_data['TempDate'] = pd.to_datetime(pack_data[date_col_v], errors='coerce')
                pack_data = pack_data.dropna(subset=['TempDate'])
                
                # Seskupení po dnech
                pack_daily = pack_data.groupby(pack_data['TempDate'].dt.date).agg(
                    Total_HU=('Clean_HU', 'nunique'),
                    Total_Pieces=('VP_Qty', 'sum')
                ).reset_index()
                pack_daily.rename(columns={'TempDate': 'Date'}, inplace=True)
                
                total_month_hu = pack_daily['Total_HU'].sum()
                total_month_pcs = pack_daily['Total_Pieces'].sum()
                avg_daily_hu = pack_daily['Total_HU'].mean()
                
                p1, p2, p3 = st.columns(3)
                p1.metric(_t("Celkem HU (Měsíc)", "Total HUs (Month)"), f"{int(total_month_hu):,}")
                p2.metric(_t("Celkem Kusů (Měsíc)", "Total Pieces (Month)"), f"{int(total_month_pcs):,}")
                p3.metric(_t("Průměr HU / Den", "Avg HUs / Day"), f"{int(avg_daily_hu):,}")
                
                st.markdown(f"#### 📊 {_t('Měsíční vývoj Balení', 'Monthly Packing Trend')}")
                
                fig_pack = go.Figure()
                fig_pack.add_trace(go.Bar(x=pack_daily['Date'], y=pack_daily['Total_HU'], name=_t('Zabalené HU', 'Packed HUs'), marker_color='#8b5cf6'))
                fig_pack.add_trace(go.Scatter(x=pack_daily['Date'], y=pack_daily['Total_Pieces'], name=_t('Zabalené Kusy', 'Packed Pieces'), mode='lines+markers', line=dict(color='#10b981', width=3), yaxis='y2'))
                
                fig_pack.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    hovermode="x unified", legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='left', x=0),
                    yaxis=dict(title=_t("Počet HU", "Number of HUs")),
                    yaxis2=dict(title=_t("Počet Kusů", "Number of Pieces"), side='right', overlaying='y', showgrid=False)
                )
                st.plotly_chart(fig_pack, use_container_width=True)
        else:
            st.warning(_t("Data pro balení (VEKP/VEPO) nejsou k dispozici.", "Packing data not available."))
