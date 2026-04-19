import pandas as pd
import qrcode
from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin
import os
import tkinter as tk
from tkinter import ttk, messagebox

# --- [설정 및 디자인 로직] ---
FONT_PATH = "NotoSansCJK-Regular.ttc"
INPUT_CSV = "input.csv"
TAG_DIR = "temp_tags"
FINAL_PDF = "mellow_selected_tags.pdf"
BASE_URL = "https://ooni0921.github.io/mellow-pharmacy/?id="
WIDTH, HEIGHT = 708, 448
A4_W, A4_H = 2480, 3508

def draw_text_with_scaling(draw, text, position, font_path, initial_size, max_width, fill=(0,0,0)):
    current_size = initial_size
    font = ImageFont.truetype(font_path, current_size)
    display_text = str(text) if pd.notnull(text) else ""
    while draw.textlength(display_text, font=font) > max_width and current_size > 16:
        current_size -= 2
        font = ImageFont.truetype(font_path, current_size)
    draw.text(position, display_text, font=font, fill=fill)

def create_tag_image(row):
    img = Image.new("RGB", (WIDTH, HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    margin_left, max_text_w = 45, 410

    # 1. 한글 상품명 (기존 블랙 유지)
    draw_text_with_scaling(draw, row['한글상품명'], (margin_left, 45), FONT_PATH, 48, max_text_w, fill=(0, 0, 0))
    
    # 2. 외국어 설명 (빨간색 변경: 255, 0, 0)
    draw_text_with_scaling(draw, row['영어명'], (margin_left, 105), FONT_PATH, 32, max_text_w, fill=(255, 0, 0))
    draw_text_with_scaling(draw, row['중국어 설명'], (margin_left, 165), FONT_PATH, 28, max_text_w, fill=(255, 0, 0))
    draw_text_with_scaling(draw, row['일본어 설명'], (margin_left, 205), FONT_PATH, 28, max_text_w, fill=(255, 0, 0))
    
    # 3. 가격 (그레이색 변경: 128, 128, 128)
    price_val = str(row['가격']).replace(',', '')
    if price_val.isdigit(): price_val = format(int(price_val), ',')
    draw.text((margin_left, 310), f"₩{price_val}", font=ImageFont.truetype(FONT_PATH, 65), fill=(128, 128, 128))
    
    # 4. QR 코드 조건부 생성
    qr_id = str(row['QR코드id값']).strip() if pd.notnull(row['QR코드id값']) else ""
    if qr_id and qr_id.lower() != "nan" and qr_id != "":
        qr = qrcode.QRCode(box_size=6, border=1)
        qr.add_data(f"{BASE_URL}{qr_id}")
        qr.make(fit=True)
        qr_img = qr.make_image().convert('RGB').resize((180, 180))
        img.paste(qr_img, (470, 110))
        detail_font = ImageFont.truetype(FONT_PATH, 18)
        draw.text((490, 300), "상품 상세 정보", font=detail_font, fill=(34, 139, 34))

    if not os.path.exists(TAG_DIR): os.makedirs(TAG_DIR)
    # 파일명 결정
    clean_name = "".join([c for c in str(row['한글상품명']) if c.isalnum() or c in (' ', '_')]).strip().replace(" ", "_")
    file_id = qr_id if qr_id else clean_name
    path = f"{TAG_DIR}/{file_id}.png"
    img.save(path)
    return path

def generate_pdf(image_paths):
    pages, cols, rows = [], 3, 7
    mx, my = (A4_W - (WIDTH * cols)) // 2, (A4_H - (HEIGHT * rows)) // 2
    curr_page = Image.new("RGB", (A4_W, A4_H), (255, 255, 255))
    draw = ImageDraw.Draw(curr_page)
    for idx, path in enumerate(image_paths):
        i = idx % 21
        if i == 0 and idx > 0:
            pages.append(curr_page)
            curr_page = Image.new("RGB", (A4_W, A4_H), (255, 255, 255))
            draw = ImageDraw.Draw(curr_page)
        c, r = i % cols, i // cols
        px, py = mx + (c * WIDTH), my + (r * HEIGHT)
        curr_page.paste(Image.open(path), (px, py))
        draw.rectangle([px, py, px + WIDTH, py + HEIGHT], outline=(220, 220, 220), width=1)
    pages.append(curr_page)
    pages[0].save(FINAL_PDF, save_all=True, append_images=pages[1:])

# --- [GUI 클래스] ---
class MellowApp:
    def __init__(self, root):
        self.root = root
        self.root.title("mellow PHARMACY - 가격표 통합 매니저")
        self.root.geometry("1150x850")
        self.load_data()

        main_frame = tk.Frame(root); main_frame.pack(pady=10, fill="both", expand=True, padx=20)
        search_f = tk.Frame(main_frame); search_f.pack(fill="x", pady=5)
        tk.Label(search_f, text="상품 검색:").pack(side="left")
        self.search_var = tk.StringVar(); self.search_var.trace_add("write", self.update_search_list)
        tk.Entry(search_f, textvariable=self.search_var, width=30).pack(side="left", padx=5)

        list_c = tk.Frame(main_frame); list_c.pack(fill="both", expand=True, pady=10)
        l_f = tk.Frame(list_c); l_f.pack(side="left", fill="both", expand=True)
        self.tree_source = ttk.Treeview(l_f, columns=("ID", "Name", "Price"), show='headings')
        self.tree_source.heading("ID", text="ID"); self.tree_source.heading("Name", text="상품명"); self.tree_source.heading("Price", text="가격")
        self.tree_source.column("ID", width=70); self.tree_source.column("Name", width=180); self.tree_source.column("Price", width=80)
        self.tree_source.pack(fill="both", expand=True)
        self.tree_source.bind("<<TreeviewSelect>>", lambda e: self.on_item_select(self.tree_source))

        m_f = tk.Frame(list_c); m_f.pack(side="left", padx=10)
        tk.Button(m_f, text="추가 ▶", command=self.add_to_print_list, width=8).pack(pady=5)
        tk.Button(m_f, text="◀ 제거", command=self.remove_from_print_list, width=8).pack(pady=5)

        r_f = tk.Frame(list_c); r_f.pack(side="left", fill="both", expand=True)
        self.tree_print = ttk.Treeview(r_f, columns=("ID", "Name", "Price"), show='headings')
        self.tree_print.heading("ID", text="ID"); self.tree_print.heading("Name", text="상품명"); self.tree_print.heading("Price", text="가격")
        self.tree_print.column("ID", width=70); self.tree_print.column("Name", width=180); self.tree_print.column("Price", width=80)
        self.tree_print.pack(fill="both", expand=True)
        self.tree_print.bind("<<TreeviewSelect>>", lambda e: self.on_item_select(self.tree_print))

        bottom_frame = tk.Frame(root); bottom_frame.pack(fill="x", padx=20, pady=10)
        edit_f = tk.LabelFrame(bottom_frame, text=" 가격 수정 ", padx=10, pady=10)
        edit_f.pack(side="left", fill="both", expand=True, padx=5)
        self.sel_id = None; self.sel_name_var = tk.StringVar(value="상품을 선택하세요")
        tk.Label(edit_f, textvariable=self.sel_name_var, fg="blue", wraplength=150).pack()
        self.new_p_var = tk.StringVar(); tk.Entry(edit_f, textvariable=self.new_p_var, width=15).pack(pady=5)
        tk.Button(edit_f, text="수정 저장", command=self.update_price, bg="#f0ad4e").pack()

        reg_f = tk.LabelFrame(bottom_frame, text=" 신규 상품 등록 ", padx=10, pady=10)
        reg_f.pack(side="left", fill="both", expand=True, padx=5)
        self.reg_vars = {k: tk.StringVar() for k in ['한글상품명','영어명','중국어 설명','일본어 설명','가격','QR코드id값']}
        for i, (label, var) in enumerate(self.reg_vars.items()):
            tk.Label(reg_f, text=label).grid(row=i//2, column=(i%2)*2, sticky="w")
            tk.Entry(reg_f, textvariable=var, width=15).grid(row=i//2, column=(i%2)*2+1, padx=5, pady=2)
        tk.Button(reg_f, text="신규 등록 완료", command=self.register_product, bg="#5bc0de").grid(row=3, column=0, columnspan=4, pady=10)

        act_f = tk.Frame(bottom_frame); act_f.pack(side="right", padx=10)
        self.stat_var = tk.StringVar(value="인쇄 대기: 0개")
        tk.Label(act_f, textvariable=self.stat_var).pack()
        tk.Button(act_f, text="PDF 생성 및 열기", command=self.run_pdf, bg="#228B22", fg="white", font=("", 11, "bold"), width=20, height=2).pack(pady=5)

        self.update_search_list()

    def load_data(self):
        try:
            if not os.path.exists(INPUT_CSV):
                pd.DataFrame(columns=['한글상품명','영어명','중국어 설명','일본어 설명','가격','QR코드id값']).to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
            self.df = pd.read_csv(INPUT_CSV, encoding='utf-8-sig')
            self.df['QR코드id값'] = self.df['QR코드id값'].fillna('')
        except Exception as e: messagebox.showerror("오류", f"데이터 로드 실패: {e}")

    def update_search_list(self, *args):
        query = self.search_var.get().strip()
        for i in self.tree_source.get_children(): self.tree_source.delete(i)
        if 0 < len(query) < 2: return
        f_df = self.df if len(query) < 2 else self.df[self.df['한글상품명'].str.contains(query, case=False, na=False)]
        for _, r in f_df.iterrows():
            id_disp = r['QR코드id값'] if r['QR코드id값'] != "" else "(없음)"
            self.tree_source.insert("", "end", values=(id_disp, r['한글상품명'], format(int(str(r['가격']).replace(',','')), ',')))

    def on_item_select(self, tree):
        sel = tree.selection()
        if not sel: return
        item = tree.item(sel[0]); self.sel_id = item['values'][0]
        if self.sel_id == "(없음)": self.sel_id = ""
        self.sel_name_var.set(item['values'][1]); self.new_p_var.set(str(item['values'][2]).replace(',',''))

    def register_product(self):
        data = {k: v.get().strip() for k, v in self.reg_vars.items()}
        if not data['한글상품명'] or not data['가격']: return messagebox.showwarning("경고", "상품명과 가격은 필수입니다.")
        if data['QR코드id값'] != "" and data['QR코드id값'] in self.df['QR코드id값'].astype(str).values: return messagebox.showerror("에러", "ID 중복!")
        self.df = pd.concat([self.df, pd.DataFrame([data])], ignore_index=True)
        self.df.to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
        messagebox.showinfo("성공", "등록 완료"); self.update_search_list()

    def update_price(self):
        new_p = self.new_p_var.get().strip()
        if not new_p.isdigit(): return
        if self.sel_id == "": idx = self.df[(self.df['한글상품명'] == self.sel_name_var.get()) & (self.df['QR코드id값'] == "")].index
        else: idx = self.df[self.df['QR코드id값'] == self.sel_id].index
        if len(idx) > 0:
            self.df.loc[idx, '가격'] = int(new_p)
            self.df.to_csv(INPUT_CSV, index=False, encoding='utf-8-sig')
            messagebox.showinfo("알림", "가격 수정 완료"); self.update_search_list()

    def add_to_print_list(self):
        for s in self.tree_source.selection(): self.tree_print.insert("", "end", values=self.tree_source.item(s)['values'])
        self.stat_var.set(f"인쇄 대기: {len(self.tree_print.get_children())}개")

    def remove_from_print_list(self):
        for s in self.tree_print.selection(): self.tree_print.delete(s)
        self.stat_var.set(f"인쇄 대기: {len(self.tree_print.get_children())}개")

    def run_pdf(self):
        items = self.tree_print.get_children()
        if not items: return messagebox.showwarning("알림", "출력할 상품이 없습니다.")
        paths = []
        for i in items:
            vals = self.tree_print.item(i)['values']
            cur_id = vals[0] if vals[0] != "(없음)" else ""
            cur_name = vals[1]
            row = self.df[(self.df['한글상품명'] == cur_name) & (self.df['QR코드id값'] == cur_id)].iloc[0]
            paths.append(create_tag_image(row))
        generate_pdf(paths)
        try: os.startfile(FINAL_PDF)
        except Exception as e: messagebox.showerror("오류", f"파일 열기 실패: {e}")

if __name__ == "__main__":
    root = tk.Tk(); app = MellowApp(root); root.mainloop()