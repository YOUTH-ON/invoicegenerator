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
    st.error(f"フォントファイルが見つかりません: {e}")

# --- 郵便番号検索関数 ---
def get_address_from_zip(zipcode):
    if not zipcode: return ""
    res = requests.get(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={zipcode}")
    if res.status_code == 200:
        data = res.json()
        if data['results']:
            r = data['results'][0]
            return f"{r['address1']}{r['address2']}{r['address3']}"
    return ""

# --- PDF作成関数 (複数行対応版) ---
def create_invoice_pdf(data, df):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # 発行者情報
    c.setFont(FONT_NAME, 10)
    c.drawString(400, height - 50, f"〒{data['issuer_zip']}")
    c.drawString(400, height - 65, data['issuer_address'])
    c.drawString(400, height - 80, f"登録番号: {data['issuer_reg_num']}") # ①登録番号
    c.drawString(400, height - 95, data['issuer_name'])
    c.drawString(400, height - 115, f"発行年月日 {data['date']}")

    # 宛先情報
    c.drawString(50, height - 130, f"〒{data['client_zip']}")
    c.drawString(50, height - 145, data['client_address'])
    c.setFont(FONT_NAME, 12)
    c.drawString(50, height - 165, f"{data['client_name']} 御中")

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(width / 2, height - 210, "御 請 求 書")

    # 請求金額
    total_amount = int(df['金額'].sum() * 1.1)
    c.setFont(FONT_NAME, 14)
    c.drawString(50, height - 260, f"御請求金額 {total_amount:,} 円")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, height - 275, "(上記金額は消費税(10%)を含みます。)")

    # ③明細テーブル
    y = height - 310
    c.line(50, y, 550, y)
    c.drawString(60, y - 15, "品目")
    c.drawString(300, y - 15, "数量")
    c.drawString(380, y - 15, "単価")
    c.drawString(480, y - 15, "金額")
    c.line(50, y - 20, 550, y - 20)

    current_y = y - 35
    for _, row in df.iterrows():
        c.drawString(60, current_y, str(row['品目']))
        c.drawString(300, current_y, str(row['数量']))
        c.drawString(380, current_y, f"{int(row['単価']):,}")
        c.drawString(480, current_y, f"{int(row['金額']):,}")
        current_y -= 20
        if current_y < 100: break # 簡易的な改ページなし対策

    c.line(50, current_y + 5, 550, current_y + 5)

    # 振込先
    y_bank = current_y - 50
    c.drawString(50, y_bank, f"支払期日 ：{data['due_date']}")
    c.drawString(50, y_bank - 15, f"振込先 ：{data['bank_info']}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- Streamlit UI ---
st.title("請求書作成アプリ (Pro版)")

# セッション状態の初期化
if 'items_df' not in st.session_state:
    st.session_state.items_df = pd.DataFrame([{"品目": "成果物一式", "数量": 1, "単価": 20000, "金額": 20000}])

with st.expander("基本情報入力"):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("発行者")
        issuer_name = st.text_input("氏名/社名", value="横内 拓馬")
        i_zip = st.text_input("発行者郵便番号", value="2040023")
        if st.button("発行者住所を検索"): # ②郵便番号検索
            st.session_state.i_addr = get_address_from_zip(i_zip)
        issuer_address = st.text_input("住所", value=st.session_state.get('i_addr', "東京都清瀬市竹丘2-33-23"))
        issuer_reg_num = st.text_input("登録番号", value="T1234567890123") # ①登録番号

    with col2:
        st.subheader("取引先")
        client_name = st.text_input("取引先名", value="株式会社 アットファンズ・マーケティング")
        c_zip = st.text_input("取引先郵便番号", value="1500043")
        if st.button("取引先住所を検索"): # ②郵便番号検索
            st.session_state.c_addr = get_address_from_zip(c_zip)
        client_address = st.text_input("住所 ", value=st.session_state.get('c_addr', "東京都渋谷区道玄坂1-21-1 SHIBUYA SOLASTA 3F"))

st.subheader("③ 明細情報")
# 編集モードの切り替え
if 'editing' not in st.session_state: st.session_state.editing = False

def toggle_edit():
    st.session_state.editing = not st.session_state.editing
    # 編集完了時に金額を再計算
    if not st.session_state.editing:
        st.session_state.items_df['金額'] = st.session_state.items_df['数量'] * st.session_state.items_df['単価']

if st.button("明細表を編集" if not st.session_state.editing else "編集を完了する"):
    toggle_edit()

if st.session_state.editing:
    # 編集モード：行追加可能。再描画で値が飛ばないようdata_editorを使用
    edited_df = st.data_editor(st.session_state.items_df, num_rows="dynamic", use_container_width=True)
    st.session_state.items_df = edited_df
else:
    # 閲覧モード：計算後の表を表示
    st.table(st.session_state.items_df)

# 発行日等の入力
date = st.date_input("発行年月日", value=datetime.now())
due_date = st.date_input("支払期日", value=datetime(2026, 1, 31))
bank_info = st.text_input("振込先", value="みずほ銀行清瀬支店 普通 1228611")

if st.button("最終確認してPDFを作成"):
    # 金額の再計算（念押し）
    st.session_state.items_df['金額'] = st.session_state.items_df['数量'] * st.session_state.items_df['単価']
    
    data = {
        'issuer_name': issuer_name, 'issuer_zip': i_zip, 'issuer_address': issuer_address,
        'issuer_reg_num': issuer_reg_num, 'client_name': client_name, 'client_zip': c_zip, 
        'client_address': client_address, 'date': date.strftime('%Y年%m月%d日'),
        'due_date': due_date.strftime('%Y年%m月%d日'), 'bank_info': bank_info
    }
    
    pdf_file = create_invoice_pdf(data, st.session_state.items_df)
    st.download_button("PDFをダウンロード", data=pdf_file, file_name="invoice.pdf", mime="application/pdf")
