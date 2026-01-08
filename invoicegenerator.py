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

# --- 郵便番号検索関数 ---
def get_address_from_zip(zipcode):
    if not zipcode: return ""
    # ハイフンを除去
    zipcode = zipcode.replace("-", "")
    try:
        res = requests.get(f"https://zipcloud.ibsnet.co.jp/api/search?zipcode={zipcode}")
        if res.status_code == 200:
            data = res.json()
            if data['results']:
                r = data['results'][0]
                return f"{r['address1']}{r['address2']}{r['address3']}"
    except:
        pass
    return ""

# --- PDF作成関数 ---
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

    # 金額計算
    subtotal = df['金額'].sum()
    tax = int(subtotal * 0.1)
    total_amount = subtotal + tax

    c.setFont(FONT_NAME, 14)
    c.drawString(50, height - 260, f"御請求金額 {total_amount:,} 円")
    c.setFont(FONT_NAME, 10)
    c.drawString(50, height - 275, f"(内消費税等 {tax:,} 円)")

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
        if current_y < 150: break

    c.line(50, current_y + 5, 550, current_y + 5)
    
    # 合計
    c.drawString(380, current_y - 15, "小計")
    c.drawString(480, current_y - 15, f"{subtotal:,}")
    c.drawString(380, current_y - 30, "消費税(10%)")
    c.drawString(480, current_y - 30, f"{tax:,}")
    c.drawString(380, current_y - 45, "合計金額")
    c.drawString(480, current_y - 45, f"{total_amount:,}")

    # 振込先
    y_bank = current_y - 80
    c.drawString(50, y_bank, f"支払期日 ：{data['due_date']}")
    c.drawString(50, y_bank - 15, f"振込先 ：{data['bank_info']}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# --- Streamlit 状態管理 ---
if 'items_df' not in st.session_state:
    st.session_state.items_df = pd.DataFrame([{"品目": "成果物一式", "数量": 1, "単価": 20000, "金額": 20000}])

if 'editing' not in st.session_state:
    st.session_state.editing = False

# --- アプリ本体 ---
st.title("請求書作成アプリ (解決版)")

with st.expander("基本情報入力", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("発行者情報")
        issuer_name = st.text_input("氏名/社名", value="横内 拓馬")
        i_zip = st.text_input("郵便番号", value="2040023", key="i_zip")
        if st.button("住所を自動入力 (発行者)"):
            addr = get_address_from_zip(i_zip)
            if addr: st.session_state.i_addr = addr
            else: st.warning("住所が見つかりませんでした")
        issuer_address = st.text_input("住所", value=st.session_state.get('i_addr', "東京都清瀬市竹丘2-33-23"))
        issuer_reg_num = st.text_input("適格請求書発行事業者登録番号", value="T1234567890123")

    with col2:
        st.subheader("取引先情報")
        client_name = st.text_input("取引先名", value="株式会社 アットファンズ・マーケティング")
        c_zip = st.text_input("郵便番号 ", value="1500043", key="c_zip")
        if st.button("住所を自動入力 (取引先)"):
            addr = get_address_from_zip(c_zip)
            if addr: st.session_state.c_addr = addr
            else: st.warning("住所が見つかりませんでした")
        client_address = st.text_input("住所 ", value=st.session_state.get('c_addr', "東京都渋谷区道玄坂1-21-1 SHIBUYA SOLASTA 3F"))

st.subheader("明細情報")

# ボタンで編集モードを切り替え
if st.button("明細表を編集" if not st.session_state.editing else "編集を完了する"):
    st.session_state.editing = not st.session_state.editing
    # 編集完了時に計算を走らせる
    if not st.session_state.editing:
        st.session_state.items_df['金額'] = st.session_state.items_df['数量'] * st.session_state.items_df['単価']
    st.rerun()

if st.session_state.editing:
    st.info("行を追加するには一番下の行に入力してください。")
    # keyを固定し、変更を直接保持
    edited_df = st.data_editor(
        st.session_state.items_df,
        num_rows="dynamic",
        use_container_width=True,
        key="data_editor_main"
    )
    # 常に最新の状態を保持
    st.session_state.items_df = edited_df
else:
    # 閲覧モード：計算済みのデータを表示
    st.dataframe(st.session_state.items_df, use_container_width=True)

col_f1, col_f2 = st.columns(2)
with col_f1:
    date = st.date_input("発行年月日", value=datetime.now())
with col_f2:
    due_date = st.date_input("支払期日", value=datetime(2026, 1, 31))

bank_info = st.text_input("振込先", value="みずほ銀行清瀬支店 普通 1228611")

if st.button("PDFを生成する", type="primary"):
    # 最終的な金額更新
    st.session_state.items_df['金額'] = st.session_state.items_df['数量'] * st.session_state.items_df['単価']
    
    data = {
        'issuer_name': issuer_name, 'issuer_zip': i_zip, 'issuer_address': issuer_address,
        'issuer_reg_num': issuer_reg_num, 'client_name': client_name, 'client_zip': c_zip, 
        'client_address': client_address, 'date': date.strftime('%Y年%m月%d日'),
        'due_date': due_date.strftime('%Y年%m月%d日'), 'bank_info': bank_info
    }
    
    pdf_file = create_invoice_pdf(data, st.session_state.items_df)
    st.success("PDFが作成されました！")
    st.download_button("PDFをダウンロード", data=pdf_file, file_name=f"請求書_{client_name}.pdf", mime="application/pdf")
