import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import datetime
from database import load_from_db
from modules.utils import safe_hu

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
            
            fig_pick = go.Figure()
            fig_pick.add_trace(go.Bar(
                x=pick_daily['Date'], y=pick_daily['Total_TO'],
                name=_t('Picknuté TO', 'Picked TOs'),
                marker_color='#3b82f6',
                yaxis='y'
            ))
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
                fig_pick_hour.add_trace(go.Scatter(x=pick_day_hourly['Hour'], y=pick_day_hourly['Total_Pieces'], name=_t('Kusy', 'Pieces'), yaxis='y2', mode='lines+markers', line=dict(color='#fbbf24')))
                fig_pick_hour.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                    yaxis2=dict(side='right', overlaying='y', showgrid=False), 
                    xaxis=dict(tickmode='linear', tick0=0, dtick=1),
                    legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='left', x=0)
                )
                st.plotly_chart(fig_pick_hour, use_container_width=True)
            else:
                st.warning(_t("V tento den nejsou k dispozici žádná data o pickování.", "No picking data available for this day."))

    # -----------------------------------------
    # ZÁLOŽKA 3: BALENÍ
    # -----------------------------------------
    with tab_pack:
        if raw_vekp is not None and not raw_vekp.empty and raw_vepo is not None and not raw_vepo.empty:
            
            from modules.tab_billing import cached_billing_logic_v28
            
            df_vk = raw_vekp.copy()
            df_vp = raw_vepo.copy()
            
            # 1. Zlatá logika pro kategorie
            df_cats = load_from_db('raw_cats')
            voll_set = st.session_state.get('voll_set', set())
            qc_col = 'Delivery' if (df_pick is None or 'Transfer Order Number' not in df_pick.columns) else 'Transfer Order Number'
            
            _, df_hu_details = cached_billing_logic_v28(df_pick, raw_vekp, raw_vepo, df_cats, qc_col, voll_set)
            
            # 2. Najdeme klíče
            vk_hu_col = next((c for c in df_vk.columns if "Internal HU" in str(c) or "HU-Nummer intern" in str(c)), None)
            vp_hu_col = next((c for c in df_vp.columns if "Internal HU" in str(c) or "HU-Nummer intern" in str(c)), None)
            vp_qty_col = next((c for c in df_vp.columns if "Packed quantity" in str(c) or "VEMNG" in str(c)), None)
            
            date_col_v = next((c for c in df_vk.columns if 'CREATED ON' in str(c).upper() or 'ERFASST AM' in str(c).upper()), None)
            time_col_v = next((c for c in df_vk.columns if 'TIME' in str(c).upper() or 'UHRZEIT' in str(c).upper()), None)
            
            if vk_hu_col and vp_hu_col and date_col_v and vp_qty_col:
                # Očištění klíčů
                df_vk['Clean_HU'] = df_vk[vk_hu_col].apply(safe_hu)
                df_vp['Clean_HU'] = df_vp[vp_hu_col].apply(safe_hu)
                df_vp['VP_Qty'] = pd.to_numeric(df_vp[vp_qty_col], errors='coerce').fillna(0)
                
                if not df_hu_details.empty:
                    df_hu_details['Clean_HU'] = df_hu_details['HU_Int'].apply(safe_hu)
                
                # Agregace kusů z VEPO podle HU
                hu_pieces = df_vp.groupby('Clean_HU')['VP_Qty'].sum().reset_index()
                
                # Propojení tabulek: VEKP + Kusy + Kategorie
                pack_data = pd.merge(df_vk, hu_pieces, on='Clean_HU', how='left')
                if not df_hu_details.empty:
                    pack_data = pd.merge(pack_data, df_hu_details[['Clean_HU', 'Category_Full']], on='Clean_HU', how='left')
                    pack_data['Category'] = pack_data['Category_Full'].fillna(_t('Neznámá / Čeká na výpočet', 'Unknown / Awaiting Calc'))
                else:
                    pack_data['Category'] = _t('Bez kategorie', 'No category')
                
                # Filtrace podle data
                pack_data['TempDate'] = pd.to_datetime(pack_data[date_col_v], errors='coerce')
                pack_data = pack_data.dropna(subset=['TempDate'])
                pack_data = pack_data.drop_duplicates('Clean_HU') # 1 HU = 1 řádek
                
                # Měsíční grafika
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

                st.divider()

                # Drill-down: Detail dne pro Balení
                st.markdown(f"#### 🔍 {_t('Detail konkrétního dne', 'Specific Day Detail')}")
                col_sel_pack, _ = st.columns([1, 3])
                with col_sel_pack:
                    drill_date_pack = st.date_input(_t("Vyberte den pro detailní rozpad:", "Select day for detailed breakdown:"), value=datetime.date.today(), key="drill_pack")
                
                drill_date_pack_str = pd.to_datetime(drill_date_pack).strftime('%Y-%m-%d')
                pack_day = pack_data[pack_data['TempDate'].dt.strftime('%Y-%m-%d') == drill_date_pack_str].copy()
                
                if not pack_day.empty:
                    c1, c2 = st.columns(2)
                    
                    # GRAF 1: HODINOVÝ VÝVOJ
                    with c1:
                        st.markdown(f"**{_t('Hodinový vývoj balení', 'Hourly Packing Trend')}**")
                        if time_col_v and time_col_v in pack_day.columns:
                            def get_hour_pack(t_val):
                                try: return int(str(t_val).split(':')[0]) if ':' in str(t_val) else int(str(t_val)[0:2])
                                except: return -1
                            
                            pack_day['Hour'] = pack_day[time_col_v].apply(get_hour_pack)
                            pack_day_hourly = pack_day[pack_day['Hour'] >= 0].groupby('Hour').agg(
                                Total_HU=('Clean_HU', 'nunique'), 
                                Total_Pieces=('VP_Qty', 'sum')
                            ).reset_index()
                            
                            fig_pack_hour = go.Figure()
                            fig_pack_hour.add_trace(go.Bar(x=pack_day_hourly['Hour'], y=pack_day_hourly['Total_HU'], name='HU', marker_color='#a78bfa'))
                            fig_pack_hour.add_trace(go.Scatter(x=pack_day_hourly['Hour'], y=pack_day_hourly['Total_Pieces'], name=_t('Kusy', 'Pieces'), yaxis='y2', mode='lines+markers', line=dict(color='#34d399')))
                            fig_pack_hour.update_layout(
                                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                yaxis2=dict(side='right', overlaying='y', showgrid=False),
                                xaxis=dict(tickmode='linear', tick0=0, dtick=1),
                                legend=dict(orientation='h', yanchor='bottom', y=1.05, xanchor='left', x=0),
                                margin=dict(t=10)
                            )
                            st.plotly_chart(fig_pack_hour, use_container_width=True)
                        else:
                            st.warning(_t("Časová data (Hodiny) nejsou k dispozici.", "Hourly time data not available."))

                    # GRAF 2: ROZPAD PODLE KATEGORIÍ (Vollpalette, Misch atd.)
                    with c2:
                        st.markdown(f"**{_t('Zabalené HU podle Kategorií', 'Packed HUs by Category')}**")
                        cat_counts = pack_day.groupby('Category').size().reset_index(name='HU_Count')
                        cat_counts = cat_counts.sort_values('HU_Count', ascending=True) # Vzestupně, aby největší byl nahoře v horizontálním bar chartu
                        
                        fig_cat = px.bar(
                            cat_counts, 
                            x='HU_Count', 
                            y='Category', 
                            orientation='h', 
                            text='HU_Count',
                            color='Category',
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        fig_cat.update_traces(textposition='auto', showlegend=False)
                        fig_cat.update_layout(
                            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                            xaxis_title=_t("Počet HU", "Number of HUs"),
                            yaxis_title="",
                            margin=dict(t=10)
                        )
                        st.plotly_chart(fig_cat, use_container_width=True)
                else:
                    st.warning(_t("V tento den nejsou k dispozici žádná data o balení.", "No packing data available for this day."))
        else:
            st.warning(_t("Data pro balení (VEKP/VEPO) nejsou k dispozici. Nahrajte reporty přes Admin Zónu.", "Packing data (VEKP/VEPO) not available. Please upload reports via Admin Zone."))
