import streamlit as st
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io
import os
import requests
import pandas as pd
from datetime import datetime

# --- 日本語フォントの設定 ---
FONT_NAME = 'JapaneseFont'
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(CURRENT_DIR, 'ipaexg.ttf')

try:
    pdfmetrics.registerFont(TTFont(FONT_NAME, FONT_PATH))
except Exception as e:
    st.error(f"フォントファイル(ipaexg.ttf)が必要です: {e}")

# --- 郵便番号検索 ---
def get_address_from_zip(zipcode):
    zipcode = zipcode.replace("-", "")
    try:
        res = requests.get(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={zipcode}")
        if res.status_code == 200:
            data = res.json()
            if data['results']:
                r = data['results'][0]
                return f"{r['address1']}{r['address2']}{r['address3']}"
    except: pass
    return ""

# --- PDF作成 ---
def create_invoice_pdf(data, df):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    c.setFont(FONT_NAME, 10)
    c.drawString(400, height - 50, f"〒{data['issuer_zip']}")
    c.drawString(400, height - 65, data['issuer_address'])
    c.drawString(400, height - 80, f"登録番号: {data['issuer_reg_num']}")
    c.drawString(400, height - 95, data['issuer_name'])
    c.drawString(400, height - 115, f"発行年月日 {data['date']}")

    c.drawString(50, height - 130, f"〒{data['client_zip']}")
    c.drawString(50, height - 145, data['client_address'])
    c.setFont(FONT_NAME, 12)
    c.drawString(50, height - 165, f"{data['client_name']} 御中")

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(width / 2, height - 210, "御 請 求 書")

    # 金額計算
    subtotal = int(df['金額'].sum())
    tax = int(subtotal * 0.1)
    total_amount = subtotal + tax

    c.setFont(FONT_NAME, 14)
    c.drawString(50, height - 260, f"御請求金額 {total_amount:,} 円")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, height - 275, f"(内消費税等 {tax:,} 円)")

    y = height - 310
    c.line(50, y, 550, y)
    c.drawString(60, y - 15, "品目")
    c.drawString(300, y - 15, "数量")
    c.drawString(380, y - 15, "単価")
    c.drawString(480, y - 15, "金額")
    c.line(50, y - 20, 550, y - 20)

    current_y = y - 35
    for _, row in df.iterrows():
        if pd.isna(row['品目']): continue
        c.drawString(60, current_y, str(row['品目']))
        c.drawString(300, current_y, str(row.get('数量', 0)))
        c.drawString(380, current_y, f"{int(row.get('単価', 0)):,}")
        c.drawString(480, current_y, f"{int(row.get('金額', 0)):,}")
        current_y -= 20

    c.line(50, current_y + 5, 550, current_y + 5)
    c.drawString(380, current_y - 15, "小計")
    c.drawString(480, current_y - 15, f"{subtotal:,}")
    c.drawString(380, current_y - 30, "消費税(10%)")
    c.drawString(480, current_y - 30, f"{tax:,}")
    c.drawString(380, current_y - 45, "合計金額")
    c.drawString(480, current_y - 45, f"{total_amount:,}")

    y_bank = current_y - 80
    c.drawString(50, y_bank, f"支払期日 ：{data['due_date']}")
    c.drawString(50, y_bank - 15, f"振込先 ：{data['bank_info']}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- 状態管理と計算ロジック ---
if 'items_df' not in st.session_state:
    st.session_state.items_df = pd.DataFrame([{"品目": "成果物一式", "数量": 1, "単価": 20000, "金額": 20000}])

def update_table():
    # 編集結果を取得して金額を再計算
    edited = st.session_state["my_editor"]
    
    # 既存行の修正、削除、追加を反映させた新しいDFを作成
    df = st.session_state.items_df.copy()
    
    # data_editorの仕様に基づきデータを更新
    # 削除された行
    for i in edited.get('deleted_rows', []):
        df = df.drop(df.index[i])
    
    # 編集された行
    for i, updates in edited.get('edited_rows', {}).items():
        for col, val in updates.items():
            df.iat[i, df.columns.get_loc(col)] = val
            
    # 追加された行
    for row in edited.get('added_rows', []):
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    
    # 全行の「金額」を再計算（数量×単価）
    df['数量'] = pd.to_numeric(df['数量']).fillna(0)
    df['単価'] = pd.to_numeric(df['単価']).fillna(0)
    df['金額'] = df['数量'] * df['単価']
    
    st.session_state.items_df = df

# --- アプリ UI ---
st.title("請求書作成アプリ (安定版)")

with st.expander("基本情報入力"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("発行者")
        issuer_name = st.text_input("氏名/社名", value="横内 拓馬")
        i_zip = st.text_input("郵便番号", value="2040023")
        if st.button("発行者の住所を検索"):
            st.session_state.i_addr = get_address_from_zip(i_zip)
        issuer_address = st.text_input("住所", value=st.session_state.get('i_addr', "東京都清瀬市竹丘2-33-23"))
        issuer_reg_num = st.text_input("登録番号", value="T1234567890123")
    with col2:
        st.subheader("取引先")
        client_name = st.text_input("取引先名", value="株式会社 アットファンズ・マーケティング")
        c_zip = st.text_input("取引先郵便番号", value="1500043")
        if st.button("取引先の住所を検索"):
            st.session_state.c_addr = get_address_from_zip(c_zip)
        client_address = st.text_input("住所 ", value=st.session_state.get('c_addr', "東京都渋谷区道玄坂1-21-1 SHIBUYA SOLASTA 3F"))

st.subheader("明細表")
st.caption("※数量や単価を変更すると自動で金額が計算されます。行追加は最終行に入力してください。")

# 常時表示・常時編集モード
st.data_editor(
    st.session_state.items_df,
    num_rows="dynamic",
    use_container_width=True,
    key="my_editor",
    on_change=update_table, # 変更された瞬間に計算を走らせる
    column_config={
        "金額": st.column_config.NumberColumn("金額", disabled=True) # 金額は自動計算なので編集不可に
    }
)

col_f1, col_f2 = st.columns(2)
with col_f1: date = st.date_input("発行日", value=datetime.now())
with col_f2: due_date = st.date_input("支払期日", value=datetime(2026, 1, 31))
bank_info = st.text_input("振込先", value="みずほ銀行清瀬支店 普通 1228611")

if st.button("PDFを生成してダウンロード", type="primary"):
    data = {
        'issuer_name': issuer_name, 'issuer_zip': i_zip, 'issuer_address': issuer_address,
        'issuer_reg_num': issuer_reg_num, 'client_name': client_name, 'client_zip': c_zip, 
        'client_address': client_address, 'date': date.strftime('%Y年%m月%d日'),
        'due_date': due_date.strftime('%Y年%m月%d日'), 'bank_info': bank_info
    }
    pdf_file = create_invoice_pdf(data, st.session_state.items_df)
    st.download_button("クリックしてダウンロード", data=pdf_file, file_name=f"請求書_{client_name}.pdf", mime="application/pdf")
