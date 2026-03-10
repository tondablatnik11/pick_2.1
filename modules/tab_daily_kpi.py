import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import datetime
import io
from database import load_from_db

try:
    fast_render = st.fragment
except AttributeError:
    fast_render = lambda f: f

@fast_render
def render_daily_kpi(df_pick, raw_vekp):
    # Překladová funkce přímo pro tuto záložku
    def _t(cs, en): 
        return en if st.session_state.get('lang', 'cs') == 'en' else cs

    def get_shift(time_val):
        """Určí směnu podle přesných časů 5:45 - 13:45 a 13:45 - 21:45"""
        if pd.isna(time_val): return _t("Neznámá", "Unknown")
        try:
            t_str = str(time_val).strip()
            if len(t_str) == 8: 
                h, m, s = map(int, t_str.split(':'))
            elif len(t_str) == 6: 
                h, m, s = int(t_str[0:2]), int(t_str[2:4]), int(t_str[4:6])
            else:
                return _t("Neznámá", "Unknown")
                
            total_minutes = h * 60 + m
            
            # Ranní: 5:45 (345 min) až 13:44:59 (824 min)
            if 345 <= total_minutes < 825:
                return _t("Ranní (5:45 - 13:45)", "Morning (5:45 - 13:45)")
            # Odpolední: 13:45 (825 min) až 21:44:59 (1304 min)
            elif 825 <= total_minutes < 1305:
                return _t("Odpolední (13:45 - 21:45)", "Afternoon (13:45 - 21:45)")
            else:
                return _t("Noční / Mimo směnu", "Night / Off-shift")
        except:
            return _t("Neznámá", "Unknown")

    def get_hour(time_val):
        """Vrátí hodinu pro graf"""
        if pd.isna(time_val): return -1
        try:
            t_str = str(time_val).strip()
            if ':' in t_str: return int(t_str.split(':')[0])
            elif len(t_str) >= 6: return int(t_str[0:2])
            return -1
        except:
            return -1

    st.markdown(f"<div class='section-header'><h3>📊 {_t('Denní KPI & Shopfloor Board', 'Daily KPI & Shopfloor Board')}</h3><p>{_t('Ranní přehled výkonu skladu. Zadejte účast, zkontrolujte produktivitu a vyexportujte data pro Power BI.', 'Morning warehouse performance overview. Enter headcount, check productivity, and export data for Power BI.')}</p></div>", unsafe_allow_html=True)

    # 1. Výběr data
    col_date, col_space = st.columns([1, 3])
    with col_date:
        default_date = datetime.date.today() - datetime.timedelta(days=1)
        selected_date = st.date_input(f"📅 {_t('Vyberte analyzovaný den:', 'Select analyzed date:')}", value=default_date)
    
    sel_date_str = selected_date.strftime('%Y-%m-%d')
    sel_date_str_nodash = selected_date.strftime('%Y%m%d')
    
    # 2. Vstupy - Headcount (Rozbalovací okno)
    with st.expander(_t("👥 Účast (Headcount) - Zadejte počty lidí", "👥 Headcount - Enter worker count"), expanded=False):
        hc_c1, hc_c2 = st.columns(2)
        with hc_c1:
            st.info(f"**☀️ {_t('Ranní směna', 'Morning Shift')} (5:45 - 13:45)**")
            hc_r_in = st.number_input(_t("Příjem (Inbound) - Ranní", "Inbound - Morning"), min_value=0.0, step=0.5, key="hc_r_in")
            hc_r_pick = st.number_input(_t("Pickování (Outbound) - Ranní", "Picking (Outbound) - Morning"), min_value=0.0, step=0.5, key="hc_r_pick")
            hc_r_pack = st.number_input(_t("Balení (Pack) - Ranní", "Packing - Morning"), min_value=0.0, step=0.5, key="hc_r_pack")
        with hc_c2:
            st.warning(f"**🌆 {_t('Odpolední směna', 'Afternoon Shift')} (13:45 - 21:45)**")
            hc_o_in = st.number_input(_t("Příjem (Inbound) - Odpolední", "Inbound - Afternoon"), min_value=0.0, step=0.5, key="hc_o_in")
            hc_o_pick = st.number_input(_t("Pickování (Outbound) - Odpolední", "Picking (Outbound) - Afternoon"), min_value=0.0, step=0.5, key="hc_o_pick")
            hc_o_pack = st.number_input(_t("Balení (Pack) - Odpolední", "Packing - Afternoon"), min_value=0.0, step=0.5, key="hc_o_pack")

    st.divider()

    # --- ZPRACOVÁNÍ DAT: PICK ---
    pick_daily = pd.DataFrame()
    if df_pick is not None and not df_pick.empty:
        df_p = df_pick.copy()
        date_col = 'Confirmation date' if 'Confirmation date' in df_p.columns else 'Date'
        time_col = 'Confirmation time' if 'Confirmation time' in df_p.columns else 'Time'
        
        if date_col in df_p.columns and time_col in df_p.columns:
            df_p['TempDate'] = pd.to_datetime(df_p[date_col], errors='coerce').dt.strftime('%Y-%m-%d')
            pick_daily = df_p[df_p['TempDate'] == sel_date_str].copy()
            if not pick_daily.empty:
                pick_daily['Shift'] = pick_daily[time_col].apply(get_shift)
                pick_daily['Hour'] = pick_daily[time_col].apply(get_hour)
                pick_daily['Category'] = pick_daily.get('Queue', _t('Neznámá fronta', 'Unknown Queue'))

    # --- ZPRACOVÁNÍ DAT: PACK (VEKP) + OPRAVENÁ LOGIKA KATEGORIZACE ---
    pack_daily = pd.DataFrame()
    if raw_vekp is not None and not raw_vekp.empty:
        df_v = raw_vekp.copy()
        date_col_v = next((c for c in df_v.columns if 'CREATED ON' in str(c).upper()), None)
        time_col_v = next((c for c in df_v.columns if 'TIME' in str(c).upper()), None)
        
        if date_col_v and time_col_v:
            df_v['TempDate'] = pd.to_datetime(df_v[date_col_v], errors='coerce').dt.strftime('%Y-%m-%d')
            pack_daily = df_v[df_v['TempDate'] == sel_date_str].copy()
            
            if not pack_daily.empty:
                pack_daily['Shift'] = pack_daily[time_col_v].apply(get_shift)
                pack_daily['Hour'] = pack_daily[time_col_v].apply(get_hour)
                
                # Iniciační prázdná hodnota
                pack_daily['Category'] = np.nan
                mapped = False
                
                del_vekp = next((c for c in pack_daily.columns if 'GENERATED DELIVERY' in str(c).upper() or 'DELIVERY' in str(c).upper()), None)
                
                if del_vekp:
                    pack_daily['Clean_Del'] = pack_daily[del_vekp].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.lstrip('0')
                    
                    # 1. Metoda: Přesné mapování HUs z detailu Fakturace
                    df_hu = st.session_state.get('debug_hu_details')
                    hu_vekp = next((c for c in pack_daily.columns if 'HANDLING UNIT EXTERNAL' in str(c).upper() or 'HANDLING UNIT' in str(c).upper() or 'EXIDV' in str(c).upper()), None)
                    
                    if df_hu is not None and not df_hu.empty and hu_vekp and 'HU_Ext' in df_hu.columns:
                        pack_daily['Clean_HU'] = pack_daily[hu_vekp].astype(str).str.strip().str.lstrip('0')
                        b_df = df_hu.copy()
                        b_df['Clean_HU'] = b_df['HU_Ext'].astype(str).str.strip().str.lstrip('0')
                        cat_map = b_df.drop_duplicates('Clean_HU').set_index('Clean_HU')['Category_Full'].to_dict()
                        
                        test_map = pack_daily['Clean_HU'].map(cat_map)
                        if test_map.notna().any():
                            pack_daily['Category'] = test_map
                            mapped = True
                            
                    # 2. Metoda: Mapování přes číslo zakázky (Delivery) z Fakturace
                    if not mapped:
                        billing_df = st.session_state.get('billing_df')
                        if billing_df is not None and not billing_df.empty and 'Category_Full' in billing_df.columns:
                            del_bill = next((c for c in billing_df.columns if 'CLEAN_DEL' in str(c).upper() or 'DELIVERY' in str(c).upper()), None)
                            if del_bill:
                                b_df = billing_df.copy()
                                b_df['Clean_Del'] = b_df[del_bill].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.lstrip('0')
                                cat_map = b_df.drop_duplicates('Clean_Del').set_index('Clean_Del')['Category_Full'].to_dict()
                                
                                test_map = pack_daily['Clean_Del'].map(cat_map)
                                if test_map.notna().any():
                                    pack_daily['Category'] = test_map
                                    mapped = True
                                    
                    # 3. Metoda: Záložní data z původního číselníku Kategorií
                    if not mapped:
                        df_cats = load_from_db('raw_cats')
                        if df_cats is not None and not df_cats.empty:
                            c_del_cats = next((c for c in df_cats.columns if str(c).strip().lower() in ['lieferung', 'delivery', 'zakázka']), df_cats.columns[0])
                            df_cats['Clean_Del'] = df_cats[c_del_cats].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.lstrip('0')
                            if 'Kategorie' in df_cats.columns and 'Art' in df_cats.columns: 
                                df_cats['Category_Full'] = df_cats['Kategorie'].astype(str).str.strip() + " " + df_cats['Art'].astype(str).str.strip()
                                cat_map = df_cats.drop_duplicates('Clean_Del').set_index('Clean_Del')['Category_Full'].to_dict()
                                pack_daily['Category'] = pack_daily['Clean_Del'].map(cat_map)

                    # Vyplnění zbytku pro vizualizaci
                    pack_daily['Category'] = pack_daily['Category'].fillna(_t('Ostatní / Čeká na výpočet', 'Other / Awaiting Calc'))
                else:
                    pack_daily['Category'] = _t('Neznámá (Chybí Delivery)', 'Unknown (Missing Delivery)')

    # --- 3. VÝSLEDKY A PRODUKTIVITA ---
    st.markdown(f"### 📈 {_t('Výsledky za den:', 'Results for:')} {selected_date.strftime('%d.%m.%Y')}")
    
    kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
    
    with kpi_c1:
        st.markdown(f"<div style='background-color:var(--secondary-background-color); padding:15px; border-radius:8px; border-left:5px solid #94a3b8;'><h4>📥 {_t('Příjem', 'Inbound')} (Zítra)</h4><p>{_t('Čekáme na napojení reportu...', 'Waiting for report connection...')}</p></div>", unsafe_allow_html=True)
    
    with kpi_c2:
        total_pick = pick_daily.shape[0] if not pick_daily.empty else 0
        st.markdown(f"<div style='background-color:var(--secondary-background-color); padding:15px; border-radius:8px; border-left:5px solid #3b82f6;'><h4>🛒 Pick ({_t('Úkoly', 'Tasks')})</h4><h2>{total_pick:,} TO</h2></div>", unsafe_allow_html=True)
        if not pick_daily.empty:
            r_pick = pick_daily[pick_daily['Shift'].str.startswith(_t('Ranní', 'Morning'))].shape[0]
            o_pick = pick_daily[pick_daily['Shift'].str.startswith(_t('Odpolední', 'Afternoon'))].shape[0]
            st.write(f"**{_t('Ranní', 'Morning')}:** {r_pick} TO *({_t('Produktivita:', 'Productivity:')} {r_pick/hc_r_pick if hc_r_pick>0 else 0:.1f} / {_t('hlava', 'head')})*")
            st.write(f"**{_t('Odpolední', 'Afternoon')}:** {o_pick} TO *({_t('Produktivita:', 'Productivity:')} {o_pick/hc_o_pick if hc_o_pick>0 else 0:.1f} / {_t('hlava', 'head')})*")
            
            st.markdown("---")
            st.markdown(f"**{_t('Rozpad podle front (Queue):', 'Breakdown by Queue:')}**")
            q_df = pick_daily.groupby('Category').size().reset_index(name='TO').sort_values('TO', ascending=False)
            q_df.columns = [_t('Fronta (Queue)', 'Queue'), _t('Počet TO', 'Number of TOs')]
            st.dataframe(q_df, hide_index=True, use_container_width=True)

    with kpi_c3:
        total_pack = pack_daily.shape[0] if not pack_daily.empty else 0
        st.markdown(f"<div style='background-color:var(--secondary-background-color); padding:15px; border-radius:8px; border-left:5px solid #8b5cf6;'><h4>📦 {_t('Balení', 'Packing')} (HU)</h4><h2>{total_pack:,} HU</h2></div>", unsafe_allow_html=True)
        if not pack_daily.empty:
            r_pack = pack_daily[pack_daily['Shift'].str.startswith(_t('Ranní', 'Morning'))].shape[0]
            o_pack = pack_daily[pack_daily['Shift'].str.startswith(_t('Odpolední', 'Afternoon'))].shape[0]
            st.write(f"**{_t('Ranní', 'Morning')}:** {r_pack} HU *({_t('Produktivita:', 'Productivity:')} {r_pack/hc_r_pack if hc_r_pack>0 else 0:.1f} / {_t('hlava', 'head')})*")
            st.write(f"**{_t('Odpolední', 'Afternoon')}:** {o_pack} HU *({_t('Produktivita:', 'Productivity:')} {o_pack/hc_o_pack if hc_o_pack>0 else 0:.1f} / {_t('hlava', 'head')})*")
            
            st.markdown("---")
            st.markdown(f"**{_t('Rozpad podle kategorií:', 'Breakdown by Category:')}**")
            c_df = pack_daily.groupby('Category').size().reset_index(name='HU').sort_values('HU', ascending=False)
            c_df.columns = [_t('Kategorie', 'Category'), _t('Počet HU', 'Number of HUs')]
            st.dataframe(c_df, hide_index=True, use_container_width=True)

    st.divider()

    # --- 4. HODINOVÝ GRAF VÝKONU ---
    st.markdown(f"#### 🕒 {_t('Hodinový vývoj skladu (24h)', 'Hourly Warehouse Progress (24h)')}")
    hourly_data = []
    
    if not pick_daily.empty:
        ph = pick_daily[pick_daily['Hour'] >= 0].groupby('Hour').size().reset_index(name='Volume')
        ph['Process'] = _t('Pick (TO)', 'Pick (TO)')
        hourly_data.append(ph)
        
    if not pack_daily.empty:
        bh = pack_daily[pack_daily['Hour'] >= 0].groupby('Hour').size().reset_index(name='Volume')
        bh['Process'] = _t('Pack (HU)', 'Pack (HU)')
        hourly_data.append(bh)
        
    if hourly_data:
        df_hourly = pd.concat(hourly_data)
        fig = px.bar(df_hourly, x='Hour', y='Volume', color='Process', barmode='group',
                     color_discrete_map={_t('Pick (TO)', 'Pick (TO)'): '#3b82f6', _t('Pack (HU)', 'Pack (HU)'): '#8b5cf6'},
                     labels={'Hour': _t('Hodina dne', 'Hour of Day'), 'Volume': _t('Počet úkolů / HU', 'Volume (Tasks / HU)')},
                     template='plotly_white')
        
        fig.update_layout(
            xaxis=dict(tickmode='linear', tick0=0, dtick=1, range=[-0.5, 23.5]),
            paper_bgcolor='rgba(0,0,0,0)', 
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(size=12, family="Inter, sans-serif")
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(_t("Zatím žádná data pro hodinový graf v tento den.", "No data for hourly chart on this day yet."))

    st.divider()

    # --- 5. EXPORT DO POWER BI ---
    st.markdown(f"#### 🔌 {_t('Datový export pro Power BI', 'Data Export for Power BI')}")
    st.caption(_t("Tento export generuje ideální plochou tabulku (Flat Table) pro načtení do datového modelu Power BI.", "This export generates an ideal Flat Table for loading into the Power BI data model."))
    
    pbi_rows = []
    if not pick_daily.empty:
        for _, row in pick_daily.iterrows():
            pbi_rows.append({
                'Date': sel_date_str, 'Time': row.get(time_col, ''), 'Hour': row.get('Hour', -1),
                'Shift': row.get('Shift', ''), 'Process': 'Pick', 'Category': row.get('Category', ''),
                'Value': 1, 'Unit': 'TO'
            })
    if not pack_daily.empty:
        for _, row in pack_daily.iterrows():
            pbi_rows.append({
                'Date': sel_date_str, 'Time': row.get(time_col_v, ''), 'Hour': row.get('Hour', -1),
                'Shift': row.get('Shift', ''), 'Process': 'Pack', 'Category': row.get('Category', ''),
                'Value': 1, 'Unit': 'HU'
            })
            
    if pbi_rows:
        df_pbi = pd.DataFrame(pbi_rows)
        df_pbi = df_pbi[df_pbi['Hour'] >= 0]
        
        st.dataframe(df_pbi.head(3), use_container_width=True)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_pbi.to_excel(writer, index=False, sheet_name='PBI_Export')
            
        st.download_button(
            label=_t("⬇️ Stáhnout Flat Table pro Power BI (.xlsx)", "⬇️ Download Flat Table for Power BI (.xlsx)"),
            data=buffer.getvalue(),
            file_name=f"PowerBI_Export_{sel_date_str_nodash}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )
    else:
        st.warning(_t("Data pro Power BI nejsou pro vybraný den k dispozici.", "Data for Power BI is not available for the selected day."))
